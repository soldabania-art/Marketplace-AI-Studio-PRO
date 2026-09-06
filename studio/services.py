import base64, json, mimetypes, requests
from openpyxl import Workbook
from .core import DATA

class AIService:
    def __init__(self,key,model): self.key=key.strip(); self.model=model.strip() or 'gpt-5.6'
    def _call(self,input_data,timeout=120):
        if not self.key: raise RuntimeError('Не указан OpenAI API key')
        r=requests.post('https://api.openai.com/v1/responses',headers={'Authorization':f'Bearer {self.key}','Content-Type':'application/json'},json={'model':self.model,'input':input_data},timeout=timeout)
        if not r.ok: raise RuntimeError(f'OpenAI {r.status_code}: {r.text[:700]}')
        return ''.join(c.get('text','') for i in r.json().get('output',[]) for c in i.get('content',[]) if c.get('type')=='output_text').strip()
    def product_card(self,photo,info):
        content=[{'type':'input_text','text':f'''Ты senior e-commerce strategist для Wildberries и Ozon. Создай полную продающую карточку товара. Не выдумывай факты. Данные: {info}. Верни только JSON: product_type, category, title_variants(5), description, benefits, seo(primary_keywords, secondary_keywords, search_phrases), attributes, faq, infographic_plan(минимум 6 слайдов), missing_facts, risks, ready_percent.'''}]
        if photo:
            mime=mimetypes.guess_type(photo)[0] or 'image/jpeg'
            b64=base64.b64encode(open(photo,'rb').read()).decode()
            content.append({'type':'input_image','image_url':f'data:{mime};base64,{b64}'})
        text=self._call([{'role':'user','content':content}])
        if text.startswith('```'): text=text.strip('`').removeprefix('json').strip()
        try:return json.loads(text)
        except:return {'raw_text':text}
    def review_reply(self,text,rating):
        return self._call(f'Напиши профессиональный ответ продавца на отзыв. Оценка {rating}/5. Отзыв: {text}. Коротко, вежливо, без выдумок.',90)
    def seo_audit(self,text):
        return self._call('Проведи SEO-аудит карточки для Wildberries/Ozon: оцени заголовок, структуру, ключевые слова, переспам, пользу, недостающие запросы и дай конкретные правки. Текст: '+text,90)
    def director_plan(self,text):
        return self._call('Ты AI-директор marketplace бизнеса. По данным сформируй приоритетный план: критические проблемы, быстрые победы, реклама, SEO, карточки, отзывы, запасы, финансы и задачи на 7 дней. Данные: '+text,90)

def calc_profit(revenue,commission,logistics,ads,cogs): return revenue-commission-logistics-ads-cogs

def export_xlsx(rows,name='export.xlsx'):
    out=DATA/'exports'; out.mkdir(exist_ok=True); p=out/name
    wb=Workbook(); ws=wb.active
    if rows:
        headers=list(rows[0].keys()); ws.append(headers)
        for r in rows:ws.append([r.get(h,'') for h in headers])
    wb.save(p); return p
