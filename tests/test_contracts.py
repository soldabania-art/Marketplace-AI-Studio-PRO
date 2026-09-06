import unittest
from unittest.mock import MagicMock, patch

from studio.ai_router import AIRouter, LocalTextAI
from studio.connectors import WB
from studio.local_ai_manager import _rank_model, lighter_installed_model
from studio.local_ai_setup import recommended_text_model
from studio.review_autopilot import ReviewAutopilot
from studio.safety_control import limit_for
from studio.wb_ad_manager import WBAdManager


class FakeResponse:
    def __init__(self, ok=True, status_code=200, data=None, text=''):
        self.ok=ok; self.status_code=status_code; self._data=data or {}; self.text=text; self.content=b'{}'
    def json(self): return self._data


class TestLocalAI(unittest.TestCase):
    def test_model_rank_is_not_substring_based(self):
        self.assertEqual(_rank_model('qwen2.5:1.5b'), 1.5); self.assertEqual(_rank_model('qwen2.5:3b'), 3.0); self.assertEqual(_rank_model('qwen2.5:14b'), 14.0); self.assertEqual(_rank_model('model:32b'), 32.0)
    def test_lighter_installed_model_chooses_closest_lower(self):
        installed=[{'name':'qwen:1.5b'},{'name':'qwen:3b'},{'name':'qwen:7b'},{'name':'qwen:14b'}]
        self.assertEqual(lighter_installed_model('qwen:14b',installed),'qwen:7b'); self.assertEqual(lighter_installed_model('qwen:7b',installed),'qwen:3b')
    def test_hardware_model_recommendation(self):
        self.assertEqual(recommended_text_model({'ram_gb':8,'gpu':{}})['model'],'qwen2.5:1.5b'); self.assertEqual(recommended_text_model({'ram_gb':16,'gpu':{}})['model'],'qwen2.5:3b'); self.assertEqual(recommended_text_model({'ram_gb':32,'gpu':{}})['model'],'qwen2.5:7b')
    @patch('studio.ai_router.requests.post')
    def test_local_raw_text_uses_chat_completions(self, post):
        post.return_value=FakeResponse(data={'choices':[{'message':{'content':'ok'}}]}); ai=LocalTextAI('http://127.0.0.1:11434/v1','qwen:3b')
        self.assertEqual(ai.raw_text('hello',33),'ok'); args,kwargs=post.call_args; self.assertTrue(args[0].endswith('/chat/completions')); self.assertEqual(kwargs['timeout'],33)
    def test_free_router_never_uses_paid_fallback(self):
        r=AIRouter({'ai_mode':'free','ai_allow_paid_fallback':False,'local_images_enabled':False}); r.local.raw_text=MagicMock(side_effect=RuntimeError('local down')); r.premium._call=MagicMock(return_value='paid')
        with self.assertRaises(RuntimeError): r.raw_text('x')
        r.premium._call.assert_not_called()
    def test_economy_router_uses_paid_only_when_allowed(self):
        r=AIRouter({'ai_mode':'economy','ai_allow_paid_fallback':True,'local_images_enabled':False}); r.local.raw_text=MagicMock(side_effect=RuntimeError('local down')); r.premium._call=MagicMock(return_value='paid'); self.assertEqual(r.raw_text('x'),'paid'); r.premium._call.assert_called_once()


class TestReviews(unittest.TestCase):
    def test_review_normalize(self):
        r=ReviewAutopilot.normalize({'feedbackId':'f1','nmId':123,'productValuation':'5','text':'Хорошо'}); self.assertEqual(r['id'],'f1'); self.assertEqual(r['nm_id'],'123'); self.assertEqual(r['rating'],5)
    def test_review_classifier_uses_public_raw_text(self):
        ai=MagicMock(); ai.raw_text.return_value='{"sentiment":"positive","risk":"low","needs_human":false,"reason":"ok"}'; ap=ReviewAutopilot(MagicMock(),ai); out=ap.classify({'id':'f1','rating':5,'text':'Отлично'}); self.assertEqual(out['risk'],'low'); ai.raw_text.assert_called_once()
    def test_review_prepare_marks_only_safe_positive_auto(self):
        ai=MagicMock(); ai.raw_text.return_value='{"sentiment":"positive","risk":"low","needs_human":false,"reason":"ok"}'; ai.review_reply.return_value='Спасибо!'; ap=ReviewAutopilot(MagicMock(),ai); out=ap.prepare([{'id':'f1','rating':5,'text':'Отлично'}]); self.assertTrue(out[0]['safe_auto'])


class TestWildberriesLogic(unittest.TestCase):
    def setUp(self): WB.clear_cache(); WB._last_request.clear()
    def test_sales_summary_handles_returns(self):
        rows=[{'saleID':'S1','finishedPrice':100,'forPay':80},{'saleID':'R2','finishedPrice':-100,'forPay':-80}]; s=WB.sales_summary(rows); self.assertEqual(s['units'],1); self.assertEqual(s['returns'],1); self.assertEqual(s['gross'],0)
    def test_hydrate_products_keeps_partial_data_on_api_failure(self):
        wb=WB('token'); wb.prices=MagicMock(side_effect=RuntimeError('rate')); wb.warehouse_stocks=MagicMock(return_value={'by_nm':{'1':7}}); out=wb.hydrate_products([{'external_id':'1','price':10,'stock':0}]); self.assertEqual(out[0]['price'],10); self.assertEqual(out[0]['stock'],7); self.assertTrue(out[0]['sync_warnings'])
    def test_endpoint_policies_protect_expensive_calls(self):
        key,gap,ttl=WB._endpoint_policy('GET','https://advert-api.wildberries.ru/adv/v3/fullstats'); self.assertGreaterEqual(gap,20); self.assertGreaterEqual(ttl,60)
        key,gap,ttl=WB._endpoint_policy('POST','https://finance-api.wildberries.ru/api/finance/v1/sales-reports/detailed'); self.assertGreaterEqual(gap,60); self.assertGreaterEqual(ttl,300)
    @patch('studio.connectors.requests.request')
    def test_identical_get_is_served_from_cache(self, request):
        request.return_value=FakeResponse(data={'name':'seller'}); wb=WB('token')
        with patch.object(WB,'_pace',return_value=None):
            a=wb.seller_info(); b=wb.seller_info()
        self.assertEqual(a,b); self.assertEqual(request.call_count,1)
    @patch('studio.connectors.requests.request')
    def test_write_clears_cached_reads(self, request):
        request.side_effect=[FakeResponse(data={'name':'seller'}),FakeResponse(status_code=204,data={}),FakeResponse(data={'name':'seller2'})]; wb=WB('token')
        with patch.object(WB,'_pace',return_value=None):
            wb.seller_info(); wb.answer_review('f1','Спасибо'); result=wb.seller_info()
        self.assertEqual(result['name'],'seller2'); self.assertEqual(request.call_count,3)


class TestAdvertising(unittest.TestCase):
    def test_sku_stats_aggregates_nested_fullstats(self):
        fake=MagicMock(); fake.ADVERT='https://advert-api.wildberries.ru'; mgr=WBAdManager(fake); data=[{'advertId':1,'days':[{'apps':[{'nms':[{'nmId':10,'sum':100,'sum_price':1000,'orders':2,'clicks':5,'views':100}]}]}]}]; rows=mgr.sku_stats(data); self.assertEqual(len(rows),1); self.assertEqual(rows[0]['nm_id'],10); self.assertAlmostEqual(rows[0]['drr'],10.0)
    def test_change_bids_groups_by_campaign(self):
        fake=MagicMock(); fake.ADVERT='https://advert-api.wildberries.ru'; fake._request.return_value={}; mgr=WBAdManager(fake); mgr.change_bids([{'advert_id':1,'nm_id':10,'bid_kopecks':250},{'advert_id':1,'nm_id':11,'bid_kopecks':300}]); payload=fake._request.call_args.kwargs['json']; self.assertEqual(len(payload['bids']),1); self.assertEqual(len(payload['bids'][0]['nm_bids']),2)
    def test_execute_action_blocks_large_delta(self):
        fake=MagicMock(); fake.ADVERT='x'; mgr=WBAdManager(fake)
        with self.assertRaises(RuntimeError): mgr.execute_action({'advert_id':1,'nm_id':2,'current_bid':100,'proposed_bid':140},max_change_pct=15)


class TestSafety(unittest.TestCase):
    def test_default_limits(self): self.assertEqual(limit_for({},'publish_card'),3); self.assertEqual(limit_for({},'ad_bid_change'),10)


if __name__=='__main__': unittest.main()
