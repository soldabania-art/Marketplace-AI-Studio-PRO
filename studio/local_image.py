import base64, json, requests, time
from pathlib import Path
from PIL import Image
from .core import generated_dir, save_asset
from .services import AIService, safe_name


class LocalImageEngine:
    """Free local image generation through AUTOMATIC1111/Forge-compatible WebUI API."""
    def __init__(self,base_url='http://127.0.0.1:7860',model='',timeout=600):
        self.base_url=(base_url or 'http://127.0.0.1:7860').rstrip('/')
        self.model=(model or '').strip(); self.timeout=timeout

    def health(self):
        try:
            r=requests.get(self.base_url+'/sdapi/v1/options',timeout=5)
            data=r.json() if r.ok and r.content else {}
            return {'ok':r.ok,'status':r.status_code,'url':self.base_url,'model':data.get('sd_model_checkpoint') or self.model}
        except Exception as e:
            return {'ok':False,'error':str(e),'url':self.base_url,'model':self.model}

    def _set_model(self):
        if not self.model:return
        try:
            requests.post(self.base_url+'/sdapi/v1/options',json={'sd_model_checkpoint':self.model},timeout=30)
        except Exception:
            pass

    @staticmethod
    def _img_b64(path):
        p=Path(path)
        if not p.exists():return None
        return base64.b64encode(p.read_bytes()).decode()

    def _request(self,prompt,source_photo=None,width=768,height=1152,steps=20):
        self._set_model()
        common={'prompt':prompt,'negative_prompt':'text, letters, watermark, logo, distorted product, extra objects, fake labels, low quality','steps':steps,'width':width,'height':height,'cfg_scale':5.5,'sampler_name':'DPM++ 2M','batch_size':1,'n_iter':1}
        src=self._img_b64(source_photo) if source_photo else None
        if src:
            payload={**common,'init_images':[src],'denoising_strength':0.42}
            url=self.base_url+'/sdapi/v1/img2img'
        else:
            payload=common; url=self.base_url+'/sdapi/v1/txt2img'
        r=requests.post(url,json=payload,timeout=self.timeout)
        if not r.ok:raise RuntimeError(f'Local Image {r.status_code}: {(r.text or "")[:500]}')
        data=r.json(); images=data.get('images') or []
        if not images:raise RuntimeError('Local Image API не вернул изображение.')
        return images[0]

    def generate_infographics(self,card,project_name='product',count=6,progress=None,is_cancelled=None,source_photo=None):
        if not isinstance(card,dict):raise RuntimeError('Сначала создайте структурированную AI-карточку.')
        plan=card.get('infographic_plan') or []
        if not plan:raise RuntimeError('В карточке нет плана инфографики.')
        count=max(1,min(int(count),10)); out=[]
        folder=generated_dir()/f"local_{int(time.time())}_{safe_name(project_name)}"; folder.mkdir(parents=True,exist_ok=True)
        concept=card.get('visual_concept') or {}
        overlay=AIService('', '')
        for i,slide in enumerate(plan[:count],1):
            if is_cancelled and is_cancelled():break
            if progress:progress(int((i-1)/count*100),f'Local AI создаёт визуал {i}/{count}')
            if isinstance(slide,dict):
                headline=slide.get('headline',''); visual=slide.get('visual',''); copy=slide.get('copy',''); goal=slide.get('goal','')
            else:
                headline=str(slide); visual=''; copy=''; goal=''
            prompt=(f"Premium ecommerce marketplace product infographic. Preserve the exact real product identity from the input photo: shape, materials, colors, packaging and proportions. "
                    f"Product: {card.get('product_type','product')}. Goal: {goal}. Visual direction: {visual}. Art direction: {json.dumps(concept,ensure_ascii=False)}. "
                    "Realistic studio lighting, clean composition, product-first, high conversion, empty lower safe area for text. No words, no letters, no logos, no fake features.")
            raw=self._request(prompt,source_photo)
            path=folder/f'slide_{i:02d}.jpg'; temp=folder/f'slide_{i:02d}.png'; temp.write_bytes(base64.b64decode(raw))
            Image.open(temp).convert('RGB').save(path,quality=95)
            try:temp.unlink()
            except Exception:pass
            overlay._overlay_exact_text(path,headline,copy)
            save_asset(project_name,'infographic_local',path); out.append(path)
        if progress:progress(100,f'Локальные визуалы готовы: {len(out)}')
        return out
