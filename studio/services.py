import base64, json, mimetypes, requests, time
from pathlib import Path
from openpyxl import Workbook
from .core import DATA, generated_dir, save_asset

class AIService:
    def __init__(self,key,model):
        self.key=key.strip(); self.model=model.strip() or 'gpt-5.6-sol'

    def _headers(self):
        if not self.key: raise RuntimeError('Не указан OpenAI API key')
        return {'Authorization':f'Bearer {self.key}','Content-Type':'application/json'}

    def _call(self,input_data,timeout=120):
        r=requests.post('https://api.openai.com/v1/responses',headers=self._headers(),json={'model':self.model,'input':input_data},timeout=timeout)
        if not r.ok: raise RuntimeError(f'OpenAI {r.status_code}: {r.text[:700]}')
        return ''.join(c.get('text','') for i in r.json().get('output',[]) for c in i.get('content',[]) if c.get('type')=='output_text').strip()

    def product_card(self,photo,info):
        content=[{'type':'input_text','text':f'''Ты senior e-commerce strategist для Wildberries и Ozon. Создай коммерчески сильную полную карточку товара. Не выдумывай факты: неизвестное помечай как ТРЕБУЕТ УТОЧНЕНИЯ. Данные пользователя: {info}. Верни только JSON с полями: product_type, category, title_variants(5), description, benefits, seo(primary_keywords, secondary_keywords, search_phrases, negative_keywords), attributes, faq, infographic_plan(минимум 6 слайдов: slide, headline, visual, copy), missing_facts, risks, ready_percent.'''}]
        if photo:
            mime=mimetypes.guess_type(photo)[0] or 'image/jpeg'
            b64=base64.b64encode(open(photo,'rb').read()).decode()
            content.append({'type':'input_image','image_url':f'data:{mime};base64,{b64}'})
        text=self._call([{'role':'user','content':content}])
        if text.startswith('```'):
            text=text.strip('`')
            if text.lower().startswith('json'): text=text[4:].strip()
        try:return json.loads(text)
        except:return {'raw_text':text}

    def generate_infographics(self,card,project_name='product',count=6):
        if not isinstance(card,dict): raise RuntimeError('Сначала создайте структурированную AI-карточку.')
        plan=card.get('infographic_plan') or []
        if not plan: raise RuntimeError('В карточке нет плана инфографики.')
        out=[]; folder=generated_dir()/f"{int(time.time())}_{safe_name(project_name)}"; folder.mkdir(parents=True,exist_ok=True)
        for i,slide in enumerate(plan[:max(1,min(count,10))],start=1):
            headline=slide.get('headline','') if isinstance(slide,dict) else str(slide)
            visual=slide.get('visual','') if isinstance(slide,dict) else ''
            copy=slide.get('copy','') if isinstance(slide,dict) else ''
            prompt=(f"Commercial marketplace product infographic, premium ecommerce style. Product type: {card.get('product_type','product')}. "
                    f"Slide {i}. Headline concept: {headline}. Visual direction: {visual}. Supporting message: {copy}. "
                    "Clean composition, strong hierarchy, product-first, realistic studio lighting, no logos, no fake certifications, no fabricated specifications. "
                    "Leave safe readable space for Russian text overlays; do not render long paragraphs inside the image.")
            r=requests.post('https://api.openai.com/v1/images/generations',headers=self._headers(),json={
                'model':'gpt-image-2','prompt':prompt,'size':'1024x1536','quality':'medium','n':1
            },timeout=180)
            if not r.ok: raise RuntimeError(f'Image API {r.status_code}: {r.text[:700]}')
            data=r.json().get('data',[])
            if not data: raise RuntimeError('Image API не вернул изображение.')
            item=data[0]; raw=item.get('b64_json')
            path=folder/f'slide_{i:02d}.png'
            if raw:
                path.write_bytes(base64.b64decode(raw))
            elif item.get('url'):
                img=requests.get(item['url'],timeout=120); img.raise_for_status(); path.write_bytes(img.content)
            else:
                raise RuntimeError('Не удалось получить байты изображения.')
            save_asset(project_name,'infographic',path); out.append(path)
        return out

    def review_reply(self,text,rating):
        return self._call(f'Напиши профессиональный ответ продавца на отзыв. Оценка {rating}/5. Отзыв: {text}. Коротко, вежливо, без выдумок.',90)

    def review_complaint(self,text,rating):
        return self._call(f'''Подготовь аргументированный проект жалобы на отзыв для маркетплейса. Оценка {rating}/5. Отзыв: {text}. Не заявляй о нарушении, если его нельзя уверенно определить. Структура: возможное основание, аргументы, нейтральный текст обращения в поддержку, что приложить как доказательства.''',90)

    def seo_audit(self,text):
        return self._call('Проведи SEO-аудит карточки для Wildberries/Ozon: оцени заголовок, структуру, ключевые слова, переспам, пользу, недостающие запросы и дай конкретные правки. Текст: '+text,90)

    def director_plan(self,text):
        return self._call('Ты AI-директор marketplace бизнеса. По данным сформируй приоритетный план: критические проблемы, быстрые победы, реклама, SEO, карточки, отзывы, запасы, финансы и задачи на 7 дней. Данные: '+text,90)

def safe_name(value):
    s=''.join(ch if ch.isalnum() or ch in ('-','_') else '_' for ch in str(value))
    return s[:60] or 'product'

def calc_profit(revenue,commission,logistics,ads,cogs): return revenue-commission-logistics-ads-cogs

def export_xlsx(rows,name='export.xlsx'):
    out=DATA/'exports'; out.mkdir(exist_ok=True); p=out/name
    wb=Workbook(); ws=wb.active
    if rows:
        headers=list(rows[0].keys()); ws.append(headers)
        for r in rows: ws.append([r.get(h,'') for h in headers])
    wb.save(p); return p
