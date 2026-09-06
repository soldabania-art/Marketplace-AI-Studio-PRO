import base64, json, mimetypes, requests
from pathlib import Path
from .services import AIService
from .local_image import LocalImageEngine


class LocalTextAI:
    """Small adapter for an OpenAI-compatible local text server (llama.cpp/Ollama proxy/etc.)."""
    def __init__(self, base_url='http://127.0.0.1:8080/v1', model='local-model', timeout=180):
        self.base_url=(base_url or 'http://127.0.0.1:8080/v1').rstrip('/')
        self.model=(model or 'local-model').strip()
        self.timeout=timeout

    def health(self):
        try:
            r=requests.get(self.base_url+'/models',timeout=5)
            return {'ok':r.ok,'status':r.status_code,'url':self.base_url}
        except Exception as e:
            return {'ok':False,'error':str(e),'url':self.base_url}

    def _call(self,prompt,photo=None,timeout=None):
        content=[{'type':'text','text':prompt}]
        if photo and Path(photo).exists():
            mime=mimetypes.guess_type(photo)[0] or 'image/jpeg'
            b64=base64.b64encode(Path(photo).read_bytes()).decode()
            content.append({'type':'image_url','image_url':{'url':f'data:{mime};base64,{b64}'}})
        payload={'model':self.model,'messages':[{'role':'user','content':content}],'temperature':0.2}
        r=requests.post(self.base_url+'/chat/completions',json=payload,timeout=timeout or self.timeout)
        if not r.ok:
            raise RuntimeError(f'Local AI {r.status_code}: {(r.text or "")[:500]}')
        data=r.json(); choices=data.get('choices') or []
        if not choices: raise RuntimeError('Local AI не вернул ответ.')
        msg=choices[0].get('message') or {}; return str(msg.get('content') or '').strip()

    def raw_text(self,prompt,timeout=120):
        return self._call(str(prompt or ''),timeout=timeout)

    @staticmethod
    def _json(text):
        text=(text or '').strip()
        if text.startswith('```'):
            text=text.strip('`')
            if text.lower().startswith('json'):text=text[4:].strip()
        try:return json.loads(text)
        except Exception:return {'raw_text':text}

    def product_card(self,photo,info):
        prompt=f'''Ты senior e-commerce strategist для Wildberries/Ozon. Используй только подтвержденные факты: {info}. Не выдумывай характеристики. Верни только JSON с полями product_type, category, title_variants, selected_title, description, short_description, benefits, seo, attributes, faq, visual_concept, infographic_plan, marketplace_texts, missing_facts, risks, ready_percent. Русский язык.'''
        return self._json(self._call(prompt,photo))
    def review_reply(self,text,rating):return self._call(f'Напиши короткий профессиональный ответ продавца. Оценка {rating}/5. Отзыв: {text}')
    def review_complaint(self,text,rating):return self._call(f'Подготовь нейтральный проект жалобы на отзыв без выдуманных нарушений. Оценка {rating}/5. Отзыв: {text}')
    def seo_audit(self,text):return self._call('Проведи SEO-аудит карточки WB/Ozon и дай конкретные правки. Текст: '+text)
    def seo_rebuild(self,text):return self._call('Перепиши слабую карточку WB/Ozon. Не выдумывай факты. Верни JSON с заголовками, описанием, SEO, преимуществами, характеристиками-кандидатами и планом 6 слайдов. Исходные данные: '+text)
    def director_plan(self,text):return self._call('Ты AI-директор marketplace бизнеса. Сформируй приоритетный план по прибыли, рекламе, SEO, карточкам, отзывам, запасам и финансам. Данные: '+text)


class AIRouter:
    """Free-first AI router. Local text and local image engines are preferred; paid OpenAI is explicit."""
    MODES=('free','economy','premium')
    def __init__(self,cfg):
        self.cfg=cfg or {}; self.mode=str(self.cfg.get('ai_mode','free') or 'free').lower()
        if self.mode not in self.MODES:self.mode='free'
        self.local=LocalTextAI(self.cfg.get('local_ai_url','http://127.0.0.1:8080/v1'),self.cfg.get('local_ai_model','local-model'))
        self.local_images=LocalImageEngine(self.cfg.get('local_image_url','http://127.0.0.1:7860'),self.cfg.get('local_image_model',''))
        self.premium=AIService(self.cfg.get('openai_api_key',''),self.cfg.get('openai_model','gpt-5.6-sol'))

    def status(self):
        return {
            'mode':self.mode,
            'local':self.local.health(),
            'local_images':self.local_images.health() if self.cfg.get('local_images_enabled',True) else {'ok':False,'disabled':True},
            'paid_allowed':self.mode=='premium' or bool(self.cfg.get('ai_allow_paid_fallback',False)),
            'paid_images_allowed':self.mode=='premium' or bool(self.cfg.get('ai_allow_paid_images',False)),
        }

    def _text(self,method,*args):
        if self.mode=='premium':return getattr(self.premium,method)(*args)
        try:return getattr(self.local,method)(*args)
        except Exception:
            if self.mode=='economy' and self.cfg.get('ai_allow_paid_fallback',False):return getattr(self.premium,method)(*args)
            raise

    def raw_text(self,prompt,timeout=120):
        """Public raw-text route for internal agents/classifiers. Honors the same paid-fallback policy."""
        if self.mode=='premium':return self.premium._call(str(prompt or ''),timeout)
        try:return self.local.raw_text(prompt,timeout)
        except Exception:
            if self.mode=='economy' and self.cfg.get('ai_allow_paid_fallback',False):
                return self.premium._call(str(prompt or ''),timeout)
            raise

    def product_card(self,photo,info):return self._text('product_card',photo,info)
    def review_reply(self,text,rating):return self._text('review_reply',text,rating)
    def review_complaint(self,text,rating):return self._text('review_complaint',text,rating)
    def seo_audit(self,text):return self._text('seo_audit',text)
    def seo_rebuild(self,text):return self._text('seo_rebuild',text)
    def director_plan(self,text):return self._text('director_plan',text)

    def _paid_images_allowed(self):
        return self.mode=='premium' or bool(self.cfg.get('ai_allow_paid_images',False))

    def generate_infographics(self,*args,**kwargs):
        if self.mode!='premium' and self.cfg.get('local_images_enabled',True):
            try:return self.local_images.generate_infographics(*args,**kwargs)
            except Exception:
                if not self._paid_images_allowed():raise
        if not self._paid_images_allowed():
            raise RuntimeError('Локальный Image AI недоступен, а платная генерация OpenAI отключена. Запустите локальный Stable Diffusion WebUI/Forge API или вручную разрешите Premium изображения.')
        return self.premium.generate_infographics(*args,**kwargs)

    def full_product_pack(self,photo,info,count=6,progress=None,is_cancelled=None):
        if progress:progress(5,'AI создаёт тексты карточки')
        card=self.product_card(photo,info)
        if not isinstance(card,dict) or 'raw_text' in card:raise RuntimeError('AI не вернул структурированную карточку.')
        if is_cancelled and is_cancelled():return {'cancelled':True,'card':card,'images':[]}
        if progress:progress(25,'Тексты готовы; создаю визуалы')
        name=card.get('product_type') or 'product'
        paths=self.generate_infographics(card,name,count,progress=(lambda p,t:progress(25+int(p*.75),t)) if progress else None,is_cancelled=is_cancelled,source_photo=photo)
        return {'card':card,'images':[str(p) for p in paths],'cancelled':bool(is_cancelled and is_cancelled()),'image_provider':'local-first'}
