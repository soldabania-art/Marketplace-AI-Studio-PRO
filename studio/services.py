import base64, json, mimetypes, requests, time, textwrap
from pathlib import Path
from openpyxl import Workbook
from PIL import Image, ImageDraw, ImageFont
from .core import DATA, generated_dir, save_asset


class AIService:
    def __init__(self,key,model):
        self.key=(key or '').strip(); self.model=(model or '').strip() or 'gpt-5.6-sol'

    def _headers(self):
        if not self.key: raise RuntimeError('Не указан OpenAI API key')
        return {'Authorization':f'Bearer {self.key}','Content-Type':'application/json'}

    def _auth_headers(self):
        if not self.key: raise RuntimeError('Не указан OpenAI API key')
        return {'Authorization':f'Bearer {self.key}'}

    def _call(self,input_data,timeout=120):
        r=requests.post('https://api.openai.com/v1/responses',headers=self._headers(),json={'model':self.model,'input':input_data},timeout=timeout)
        if not r.ok: raise RuntimeError(f'OpenAI {r.status_code}: {r.text[:700]}')
        return ''.join(c.get('text','') for i in r.json().get('output',[]) for c in i.get('content',[]) if c.get('type')=='output_text').strip()

    @staticmethod
    def _json(text):
        text=(text or '').strip()
        if text.startswith('```'):
            text=text.strip('`')
            if text.lower().startswith('json'): text=text[4:].strip()
        try:return json.loads(text)
        except:return {'raw_text':text}

    def product_card(self,photo,info):
        content=[{'type':'input_text','text':f'''Ты senior e-commerce strategist и арт-директор для Wildberries и Ozon. На основе фото и подтверждённых фактов создай полностью готовое коммерческое наполнение карточки товара. Не выдумывай характеристики, сертификаты, состав, размеры или обещания: неизвестное помечай ТРЕБУЕТ УТОЧНЕНИЯ. Данные пользователя: {info}.
Верни только JSON с полями:
product_type, category,
title_variants(5), selected_title,
description, short_description,
benefits,
seo(primary_keywords, secondary_keywords, search_phrases, negative_keywords),
attributes,
faq,
visual_concept(style, background, lighting, composition, palette_notes, do_not_use),
infographic_plan(минимум 6 слайдов: slide, goal, headline, visual, copy),
marketplace_texts(wb_title, wb_description, ozon_title, ozon_description),
missing_facts, risks, ready_percent.
Тексты должны быть на русском, коммерчески сильные, читаемые, без переспама и без ложных фактов.'''}]
        if photo:
            mime=mimetypes.guess_type(photo)[0] or 'image/jpeg'
            b64=base64.b64encode(open(photo,'rb').read()).decode()
            content.append({'type':'input_image','image_url':f'data:{mime};base64,{b64}'})
        return self._json(self._call([{'role':'user','content':content}]))

    def _image_request(self,prompt,source_photo=None):
        source=Path(source_photo) if source_photo else None
        if source and source.exists():
            mime=mimetypes.guess_type(str(source))[0] or 'image/jpeg'
            with source.open('rb') as fh:
                r=requests.post(
                    'https://api.openai.com/v1/images/edits',
                    headers=self._auth_headers(),
                    data={'model':'gpt-image-2','prompt':prompt,'size':'1024x1536','quality':'medium','n':'1'},
                    files={'image':(source.name,fh,mime)},
                    timeout=300,
                )
        else:
            r=requests.post('https://api.openai.com/v1/images/generations',headers=self._headers(),json={
                'model':'gpt-image-2','prompt':prompt,'size':'1024x1536','quality':'medium','n':1
            },timeout=240)
        if not r.ok: raise RuntimeError(f'Image API {r.status_code}: {r.text[:700]}')
        return r.json()

    @staticmethod
    def _font(size,bold=False):
        candidates=[]
        if bold:
            candidates += [Path('C:/Windows/Fonts/seguisb.ttf'),Path('C:/Windows/Fonts/arialbd.ttf')]
        candidates += [Path('C:/Windows/Fonts/segoeui.ttf'),Path('C:/Windows/Fonts/arial.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
        for p in candidates:
            if p.exists():
                try:return ImageFont.truetype(str(p),size=size)
                except Exception:pass
        return ImageFont.load_default()

    @staticmethod
    def _wrap_text(draw,text,font,max_width,max_lines):
        words=str(text or '').strip().split()
        if not words:return []
        lines=[]; current=''
        for word in words:
            test=(current+' '+word).strip()
            if draw.textbbox((0,0),test,font=font)[2] <= max_width:
                current=test
            else:
                if current:lines.append(current)
                current=word
                if len(lines)>=max_lines:break
        if current and len(lines)<max_lines:lines.append(current)
        consumed=' '.join(lines)
        original=' '.join(words)
        if consumed!=original and lines:
            while lines[-1] and draw.textbbox((0,0),lines[-1]+'…',font=font)[2] > max_width:
                lines[-1]=lines[-1][:-1]
            lines[-1]=lines[-1].rstrip()+'…'
        return lines

    def _overlay_exact_text(self,path,headline,copy):
        """Render exact Russian text locally so marketplace slides do not depend on image-model typography."""
        image=Image.open(path).convert('RGBA')
        w,h=image.size; draw=ImageDraw.Draw(image,'RGBA')
        headline=str(headline or '').strip(); copy=str(copy or '').strip()
        if not headline and not copy:
            image.convert('RGB').save(path,quality=95); return
        margin=max(36,int(w*0.055)); panel_w=w-2*margin
        headline_font=self._font(max(34,int(w*0.052)),True)
        copy_font=self._font(max(23,int(w*0.031)),False)
        head_lines=self._wrap_text(draw,headline,headline_font,panel_w-2*margin,3)
        copy_lines=self._wrap_text(draw,copy,copy_font,panel_w-2*margin,4)
        head_h=sum(draw.textbbox((0,0),x,font=headline_font)[3]+10 for x in head_lines)
        copy_h=sum(draw.textbbox((0,0),x,font=copy_font)[3]+7 for x in copy_lines)
        panel_h=max(170,head_h+copy_h+2*margin)
        y=h-panel_h-margin
        draw.rounded_rectangle((margin,y,w-margin,h-margin),radius=28,fill=(8,12,20,205))
        ty=y+margin
        for line in head_lines:
            draw.text((margin*2,ty),line,font=headline_font,fill=(255,255,255,255))
            ty += draw.textbbox((0,0),line,font=headline_font)[3]+10
        if head_lines and copy_lines:ty+=8
        for line in copy_lines:
            draw.text((margin*2,ty),line,font=copy_font,fill=(235,240,248,255))
            ty += draw.textbbox((0,0),line,font=copy_font)[3]+7
        image.convert('RGB').save(path,quality=95)

    def generate_infographics(self,card,project_name='product',count=6,progress=None,is_cancelled=None,source_photo=None):
        if not isinstance(card,dict): raise RuntimeError('Сначала создайте структурированную AI-карточку.')
        plan=card.get('infographic_plan') or []
        if not plan: raise RuntimeError('В карточке нет плана инфографики.')
        count=max(1,min(int(count),10)); out=[]
        folder=generated_dir()/f"{int(time.time())}_{safe_name(project_name)}"; folder.mkdir(parents=True,exist_ok=True)
        concept=card.get('visual_concept') or {}
        preserve=('The uploaded image is the real product reference. Preserve the product identity, shape, proportions, materials, colors, packaging and visible details. '
                  'Do not replace it with a different product, redesign it, add fake accessories, labels, logos, certifications or features. ')
        for i,slide in enumerate(plan[:count],start=1):
            if is_cancelled and is_cancelled(): break
            if progress: progress(int((i-1)/count*100),f'AI создаёт визуал {i}/{count}')
            headline=slide.get('headline','') if isinstance(slide,dict) else str(slide)
            visual=slide.get('visual','') if isinstance(slide,dict) else ''
            copy=slide.get('copy','') if isinstance(slide,dict) else ''
            goal=slide.get('goal','') if isinstance(slide,dict) else ''
            prompt=(preserve+
                    f"Create a premium marketplace product infographic for Wildberries/Ozon. Product: {card.get('product_type','product')}. "
                    f"Art direction: {json.dumps(concept,ensure_ascii=False)}. Slide {i}. Goal: {goal}. "
                    f"Visual direction: {visual}. Product-first composition, realistic commercial studio lighting, clean premium e-commerce design, high conversion focus. "
                    "Keep the real product clearly recognizable and visually faithful to the reference. Do not render text, letters, words, numbers, logos, certificates or fake technical claims. Leave a clean lower safe zone for exact text that the application will add after generation.")
            data=self._image_request(prompt,source_photo)
            items=data.get('data',[])
            if not items: raise RuntimeError('Image API не вернул изображение.')
            item=items[0]; raw=item.get('b64_json'); path=folder/f'slide_{i:02d}.jpg'
            temp=folder/f'slide_{i:02d}_raw.png'
            if raw:temp.write_bytes(base64.b64decode(raw))
            elif item.get('url'):
                img=requests.get(item['url'],timeout=120); img.raise_for_status(); temp.write_bytes(img.content)
            else:raise RuntimeError('Не удалось получить байты изображения.')
            Image.open(temp).convert('RGB').save(path,quality=95)
            try:temp.unlink()
            except Exception:pass
            self._overlay_exact_text(path,headline,copy)
            save_asset(project_name,'infographic',path); out.append(path)
        if progress: progress(100,f'Визуалы готовы: {len(out)}')
        return out

    def full_product_pack(self,photo,info,count=6,progress=None,is_cancelled=None):
        """One-click AI pipeline: analyze real product -> create all texts -> preserve product -> render exact text."""
        if progress: progress(5,'AI анализирует товар и строит карточку')
        if is_cancelled and is_cancelled(): return {'cancelled':True}
        card=self.product_card(photo,info)
        if not isinstance(card,dict) or 'raw_text' in card:
            raise RuntimeError('AI не вернул структурированную карточку. Повторите генерацию.')
        if progress: progress(25,'Тексты, SEO и структура карточки готовы')
        if is_cancelled and is_cancelled(): return {'cancelled':True,'card':card}
        name=card.get('product_type') or 'product'
        paths=self.generate_infographics(card,name,count,
            progress=(lambda p,t: progress(25+int(p*0.75),t)) if progress else None,
            is_cancelled=is_cancelled,
            source_photo=photo)
        return {'card':card,'images':[str(p) for p in paths],'cancelled':bool(is_cancelled and is_cancelled())}

    def review_reply(self,text,rating):
        return self._call(f'Напиши профессиональный ответ продавца на отзыв. Оценка {rating}/5. Отзыв: {text}. Коротко, вежливо, без выдумок.',90)

    def review_complaint(self,text,rating):
        return self._call(f'''Подготовь аргументированный проект жалобы на отзыв для маркетплейса. Оценка {rating}/5. Отзыв: {text}. Не заявляй о нарушении, если его нельзя уверенно определить. Структура: возможное основание, аргументы, нейтральный текст обращения в поддержку, что приложить как доказательства.''',90)

    def seo_audit(self,text):
        return self._call('Проведи SEO-аудит карточки для Wildberries/Ozon: оцени заголовок, структуру, ключевые слова, переспам, пользу, недостающие запросы и дай конкретные правки. Текст: '+text,90)

    def seo_rebuild(self,text):
        return self._call('''Полностью перепиши слабую карточку маркетплейса. Верни только JSON: title_variants(5), selected_title, description, short_description, seo_keywords, benefits, attributes_to_fill, infographic_plan(6 слайдов: headline, visual, copy), risks. Не выдумывай неподтверждённые характеристики. Исходные данные: '''+text,120)

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
