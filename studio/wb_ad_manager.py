import math
from .autopilot import queue_action, set_action_status


class WBAdManager:
    """Guarded WB Promotion API bid automation.

    Uses the current PATCH /api/advert/v1/bids contract. Automatic writes are only
    performed for actions that contain an explicit current bid and stay inside the
    configured percentage guardrail.
    """

    def __init__(self, wb):
        self.wb = wb

    def min_bids(self, advert_id, nm_ids, payment_type='cpm', placement_types=None):
        ids = [int(x) for x in nm_ids if str(x).isdigit()][:100]
        if not ids:
            return []
        data = self.wb._request(
            'POST', self.wb.ADVERT + '/api/advert/v1/bids/min',
            json={
                'advert_id': int(advert_id),
                'nm_ids': ids,
                'payment_type': payment_type,
                'placement_types': placement_types or ['combined'],
            },
        )
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ('bids', 'data', 'items'):
                if isinstance(data.get(key), list):
                    return data[key]
        return []

    def change_bids(self, bid_rows):
        payload = {'bids': []}
        by_campaign = {}
        for row in bid_rows:
            advert_id = int(row['advert_id'])
            item = {
                'nm_id': int(row['nm_id']),
                'bid_kopecks': int(row['bid_kopecks']),
                'placement': row.get('placement') or 'combined',
            }
            by_campaign.setdefault(advert_id, []).append(item)
        for advert_id, nm_bids in by_campaign.items():
            payload['bids'].append({'advert_id': advert_id, 'nm_bids': nm_bids})
        if not payload['bids']:
            raise ValueError('Нет ставок для изменения')
        if len(payload['bids']) > 50:
            raise ValueError('За один запрос допускается не более 50 кампаний')
        return self.wb._request('PATCH', self.wb.ADVERT + '/api/advert/v1/bids', json=payload)

    @staticmethod
    def _walk_nm_stats(value, advert_id=None, out=None):
        out = out if out is not None else []
        if isinstance(value, dict):
            aid = value.get('advertId') or value.get('advert_id') or value.get('advertid') or advert_id
            nm = value.get('nmId') or value.get('nm_id') or value.get('nmID')
            if nm is not None:
                def num(*keys):
                    for k in keys:
                        if value.get(k) not in (None, ''):
                            try: return float(value.get(k))
                            except Exception: pass
                    return 0.0
                bid = num('bid_kopecks', 'bidKopecks', 'bid')
                out.append({
                    'advert_id': int(aid) if str(aid or '').isdigit() else None,
                    'nm_id': int(nm) if str(nm).isdigit() else None,
                    'spend': num('sum', 'spend'),
                    'sales': num('sum_price', 'sumPrice', 'sales'),
                    'orders': int(num('orders')),
                    'clicks': int(num('clicks')),
                    'views': int(num('views')),
                    'current_bid': int(bid) if bid > 0 else None,
                    'raw': value,
                })
            for v in value.values():
                WBAdManager._walk_nm_stats(v, aid, out)
        elif isinstance(value, list):
            for v in value:
                WBAdManager._walk_nm_stats(v, advert_id, out)
        return out

    def sku_stats(self, fullstats_rows):
        rows = self._walk_nm_stats(fullstats_rows)
        merged = {}
        for r in rows:
            if not r.get('advert_id') or not r.get('nm_id'):
                continue
            key = (r['advert_id'], r['nm_id'])
            b = merged.setdefault(key, {
                'advert_id': r['advert_id'], 'nm_id': r['nm_id'], 'spend': 0.0,
                'sales': 0.0, 'orders': 0, 'clicks': 0, 'views': 0,
                'current_bid': None,
            })
            b['spend'] += r['spend']; b['sales'] += r['sales']; b['orders'] += r['orders']
            b['clicks'] += r['clicks']; b['views'] += r['views']
            if r.get('current_bid'): b['current_bid'] = r['current_bid']
        for b in merged.values():
            b['drr'] = (b['spend'] / b['sales'] * 100.0) if b['sales'] else (999.0 if b['spend'] else 0.0)
        return list(merged.values())

    def propose(self, fullstats_rows, target_drr=15.0, max_change_pct=15.0):
        proposals = []
        for s in self.sku_stats(fullstats_rows):
            spend, sales, drr = s['spend'], s['sales'], s['drr']
            if spend < 100:
                continue
            current = s.get('current_bid')
            if sales <= 0 and spend >= 500:
                factor, reason = 0.85, 'Есть расход без продаж — снизить ставку'
            elif drr > target_drr * 1.35:
                factor, reason = 0.90, f'ДРР {drr:.1f}% существенно выше цели {target_drr:.1f}%'
            elif 0 < drr < target_drr * 0.65 and s['orders'] >= 2:
                factor, reason = 1.10, f'ДРР {drr:.1f}% ниже цели и есть продажи — можно масштабировать'
            else:
                continue
            proposed = None
            if current:
                limit = max(1.0, min(float(max_change_pct), 30.0)) / 100.0
                factor = max(1.0 - limit, min(1.0 + limit, factor))
                proposed = max(1, int(round(current * factor)))
            proposals.append({**s, 'proposed_bid': proposed, 'reason': reason})
        return proposals

    def queue_proposals(self, proposals):
        ids = []
        for p in proposals:
            risk = 'medium' if p.get('proposed_bid') else 'low'
            ids.append(queue_action('WB', p.get('nm_id'), 'ad_bid_change' if p.get('proposed_bid') else 'ad_bid_review', p, p.get('reason','Рекламная оптимизация'), risk))
        return ids

    def execute_action(self, action, max_change_pct=15.0):
        p = action if isinstance(action, dict) else {}
        current = int(p.get('current_bid') or 0)
        proposed = int(p.get('proposed_bid') or 0)
        if current <= 0 or proposed <= 0:
            raise RuntimeError('Нет надёжной текущей ставки — автоматическая запись заблокирована')
        change = abs(proposed - current) / current * 100.0
        if change > min(max(float(max_change_pct), 1.0), 30.0) + 0.001:
            raise RuntimeError(f'Изменение {change:.1f}% превышает лимит автопилота')
        return self.change_bids([{
            'advert_id': p['advert_id'], 'nm_id': p['nm_id'],
            'bid_kopecks': proposed, 'placement': p.get('placement') or 'combined'
        }])
