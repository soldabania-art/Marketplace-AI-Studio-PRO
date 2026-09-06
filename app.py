import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json, base64, mimetypes, requests, sqlite3, os
from pathlib import Path

APP='Marketplace AI Studio PRO'
DATA=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'MarketplaceAIStudioPRO'
DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'marketplace.db'; CFG=DATA/'settings.json'

def settings():
    d={'openai_api_key':'','openai_model':'gpt-5.6','wb_token':'','ozon_client_id':'','ozon_api_key':''}
    if CFG.exists():
        try:d.update(json.loads(CFG.read_text(encoding='utf-8')))
        except:pass
    return d

def save_settings(d): CFG.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')

def init_db():
    with sqlite3.connect(DB) as c:
        c.execute('CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY,name TEXT,result TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP)')

def ai_card(key,model,photo,info):
    if not key: raise RuntimeError('Укажите OpenAI API key в разделе Подключения.')
    content=[{'type':'input_text','text':f'''Ты senior product manager Wildberries и Ozon. По фото и данным создай полную продающую карточку товара. Не выдумывай неизвестные характеристики. Данные: {info}\nВерни JSON: product_type, title_variants, description, benefits, seo, attributes, faq, infographic_plan, missing_facts.'''}]
    if photo:
        mime=mimetypes.guess_type(photo)[0] or 'image/jpeg'
        b64=base64.b64encode(Path(photo).read_bytes()).decode()
        content.append({'type':'input_image','image_url':f'data:{mime};base64,{b64}'})
    r=requests.post('https://api.openai.com/v1/responses',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},json={'model':model,'input':[{'role':'user','content':content}]},timeout=120)
    if not r.ok: raise RuntimeError(f'OpenAI {r.status_code}: {r.text[:600]}')
    chunks=[]
    for item in r.json().get('output',[]):
        for x in item.get('content',[]):
            if x.get('type')=='output_text': chunks.append(x.get('text',''))
    return '\n'.join(chunks)

class App(tk.Tk):
    def __init__(self):
        super().__init__(); init_db(); self.cfg=settings(); self.photo=''
        self.title(APP+' — 1.0'); self.geometry('1280x820'); self.configure(bg='#111827')
        side=tk.Frame(self,bg='#1f2937',width=210); side.pack(side='left',fill='y'); side.pack_propagate(False)
        tk.Label(side,text='Marketplace\nAI Studio PRO',bg='#1f2937',fg='white',font=('Segoe UI',18,'bold')).pack(padx=16,pady=24,anchor='w')
        for n,f in [('Dashboard',self.dashboard),('AI Фабрика',self.factory),('Подключения',self.connections)]:
            tk.Button(side,text=n,command=f,bg='#1f2937',fg='white',relief='flat',anchor='w',font=('Segoe UI',11),padx=16,pady=12).pack(fill='x')
        self.body=tk.Frame(self,bg='#111827'); self.body.pack(fill='both',expand=True); self.dashboard()
    def clear(self):
        for w in self.body.winfo_children():w.destroy()
    def head(self,t,s=''):
        tk.Label(self.body,text=t,bg='#111827',fg='white',font=('Segoe UI',24,'bold')).pack(anchor='w',padx=28,pady=(25,3))
        tk.Label(self.body,text=s,bg='#111827',fg='#9ca3af',font=('Segoe UI',10)).pack(anchor='w',padx=28,pady=(0,20))
    def button(self,p,t,c): return tk.Button(p,text=t,command=c,bg='#2563eb',fg='white',relief='flat',font=('Segoe UI',10,'bold'),padx=14,pady=9)
    def dashboard(self):
        self.clear(); self.head('Dashboard','Wildberries + Ozon + AI в одном приложении')
        p=tk.Frame(self.body,bg='#1f2937',padx=20,pady=20); p.pack(fill='x',padx=28)
        tk.Label(p,text='Release 1.0',bg='#1f2937',fg='white',font=('Segoe UI',18,'bold')).pack(anchor='w')
        tk.Label(p,text='Откройте «Подключения», добавьте ключи, затем создавайте карточки в AI Фабрике.',bg='#1f2937',fg='#d1d5db').pack(anchor='w',pady=8)
    def factory(self):
        self.clear(); self.head('AI Фабрика','Фото + характеристики → карточка товара, SEO и инфографика')
        p=tk.Frame(self.body,bg='#1f2937',padx=18,pady=18); p.pack(fill='x',padx=28)
        self.pl=tk.Label(p,text=self.photo or 'Фото не выбрано',bg='#1f2937',fg='#d1d5db'); self.pl.pack(anchor='w')
        self.button(p,'Выбрать фото',self.pick).pack(anchor='w',pady=8)
        self.info=tk.Text(p,height=7,bg='#0f172a',fg='white',insertbackground='white'); self.info.pack(fill='x',pady=8)
        self.button(p,'Создать полную карточку',self.generate).pack(anchor='w')
        self.out=tk.Text(self.body,bg='#0f172a',fg='white',insertbackground='white'); self.out.pack(fill='both',expand=True,padx=28,pady=15)
    def pick(self):
        x=filedialog.askopenfilename(filetypes=[('Images','*.jpg *.jpeg *.png *.webp')]);
        if x:self.photo=x;self.pl.config(text=x)
    def generate(self):
        try:
            text=ai_card(self.cfg['openai_api_key'],self.cfg['openai_model'],self.photo,self.info.get('1.0','end').strip())
            self.out.delete('1.0','end');self.out.insert('end',text)
            with sqlite3.connect(DB) as c:c.execute('INSERT INTO projects(name,result) VALUES(?,?)',('AI карточка',text))
        except Exception as e:messagebox.showerror('AI',str(e))
    def connections(self):
        self.clear(); self.head('Подключения','OpenAI, Wildberries и Ozon')
        p=tk.Frame(self.body,bg='#1f2937',padx=18,pady=18);p.pack(fill='x',padx=28)
        self.entries={}
        for label,key,secret in [('OpenAI API key','openai_api_key',1),('AI модель','openai_model',0),('WB token','wb_token',1),('Ozon Client ID','ozon_client_id',0),('Ozon API key','ozon_api_key',1)]:
            r=tk.Frame(p,bg='#1f2937');r.pack(fill='x',pady=5);tk.Label(r,text=label,bg='#1f2937',fg='white',width=20,anchor='w').pack(side='left');e=tk.Entry(r,show='*' if secret else '');e.insert(0,self.cfg.get(key,''));e.pack(side='left',fill='x',expand=True);self.entries[key]=e
        self.button(p,'Сохранить',self.save).pack(anchor='w',pady=12)
    def save(self):
        self.cfg.update({k:e.get().strip() for k,e in self.entries.items()});save_settings(self.cfg);messagebox.showinfo('Настройки','Сохранено')

if __name__=='__main__': App().mainloop()
