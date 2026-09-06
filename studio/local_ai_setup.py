import os, shutil, subprocess, time
from pathlib import Path
import requests


def _which(name): return shutil.which(name)

def ollama_path():
    p=_which('ollama')
    if p:return p
    if os.name=='nt':
        candidates=[Path(os.environ.get('LOCALAPPDATA',''))/'Programs'/'Ollama'/'ollama.exe',Path(os.environ.get('PROGRAMFILES',''))/'Ollama'/'ollama.exe']
        for c in candidates:
            if c.exists():return str(c)
    return None

def winget_path(): return _which('winget') if os.name=='nt' else None

def free_space_gb(path=None):
    try:
        target=Path(path or os.environ.get('LOCALAPPDATA') or Path.home()); target=target if target.exists() else Path.home(); return round(shutil.disk_usage(str(target)).free/(1024**3),1)
    except Exception:return None

def recommended_text_model(hardware=None):
    hardware=hardware or {}; ram=float(hardware.get('ram_gb') or 0); gpu=hardware.get('gpu') or {}; vram=float(gpu.get('vram_gb') or 0)
    if ram>=32 or vram>=10:return {'model':'qwen2.5:7b','estimated_gb':5.5,'tier':'quality'}
    if ram>=16 or vram>=6:return {'model':'qwen2.5:3b','estimated_gb':2.8,'tier':'balanced'}
    return {'model':'qwen2.5:1.5b','estimated_gb':1.6,'tier':'light'}

def install_ollama(progress=None):
    existing=ollama_path()
    if existing:return {'ok':True,'already_installed':True,'path':existing}
    if os.name!='nt':raise RuntimeError('Автоустановка Ollama сейчас реализована для Windows. Установите Ollama вручную и повторите проверку.')
    winget=winget_path()
    if not winget:raise RuntimeError('winget не найден. Установите App Installer из Microsoft Store или Ollama вручную.')
    if progress:progress(15,'Устанавливаю Ollama через winget...')
    p=subprocess.run([winget,'install','--id','Ollama.Ollama','-e','--accept-source-agreements','--accept-package-agreements'],capture_output=True,text=True,timeout=900)
    if p.returncode!=0:raise RuntimeError('Не удалось установить Ollama через winget:\n'+(p.stderr or p.stdout or '')[-1500:])
    if progress:progress(70,'Проверяю установленный Ollama...')
    path=ollama_path()
    if not path:time.sleep(2);path=ollama_path()
    if not path:raise RuntimeError('Ollama установлен, но executable пока не найден. Перезапустите приложение и повторите проверку.')
    return {'ok':True,'already_installed':False,'path':path}

def ollama_running(url='http://127.0.0.1:11434',timeout=2):
    try:return requests.get(url.rstrip('/')+'/api/tags',timeout=max(0.1,float(timeout))).ok
    except Exception:return False

def ensure_ollama_running():
    path=ollama_path()
    if not path:raise RuntimeError('Ollama не установлен.')
    if ollama_running():return path
    try:subprocess.Popen([path,'serve'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except Exception:pass
    for _ in range(12):
        if ollama_running(timeout=.5):break
        time.sleep(.5)
    return path

def pull_ollama_model(model='qwen2.5:3b',progress=None):
    path=ensure_ollama_running(); model=(model or 'qwen2.5:3b').strip()
    if progress:progress(20,f'Загружаю локальную модель {model}...')
    p=subprocess.run([path,'pull',model],capture_output=True,text=True,timeout=7200)
    if p.returncode!=0:raise RuntimeError('Не удалось загрузить модель '+model+':\n'+(p.stderr or p.stdout or '')[-1500:])
    if progress:progress(100,f'Модель {model} готова')
    return {'ok':True,'model':model,'url':'http://127.0.0.1:11434/v1','path':path}

def find_image_launchers():
    names=('webui-user.bat','run.bat','webui.bat');out=[];home=Path.home();common=[home/'stable-diffusion-webui',home/'stable-diffusion-webui-forge',home/'Forge',home/'Downloads'/'stable-diffusion-webui-forge']
    for root in common:
        for n in names:
            p=root/n
            if p.exists():out.append(str(p))
    return list(dict.fromkeys(out))

def local_image_running(base_url='http://127.0.0.1:7860',timeout=2):
    try:return requests.get(base_url.rstrip('/')+'/sdapi/v1/sd-models',timeout=max(0.1,float(timeout))).ok
    except Exception:return False

def launch_image_server(launcher,extra_args='--api'):
    p=Path(str(launcher or ''))
    if not p.exists():raise RuntimeError('Файл запуска Local Image AI не найден.')
    if local_image_running():return {'ok':True,'launcher':str(p),'already_running':True,'args':[]}
    extra=[x for x in str(extra_args or '--api').split() if x];cmd=['cmd.exe','/c',str(p)]+extra if p.suffix.lower() in ('.bat','.cmd') else [str(p)]+extra
    subprocess.Popen(cmd,cwd=str(p.parent),creationflags=getattr(subprocess,'CREATE_NEW_CONSOLE',0));return {'ok':True,'launcher':str(p),'already_running':False,'args':extra}

def autostart_local_services(cfg):
    cfg=cfg or {};result={'text':None,'image':None}
    if cfg.get('local_text_autostart',True):
        try:
            if ollama_path():ensure_ollama_running();result['text']={'ok':True,'running':ollama_running(timeout=.5)}
            else:result['text']={'ok':False,'reason':'ollama_missing'}
        except Exception as e:result['text']={'ok':False,'error':str(e)}
    if cfg.get('local_image_autostart',False):
        launcher=str(cfg.get('local_image_launcher') or '')
        try:
            if local_image_running(str(cfg.get('local_image_url') or 'http://127.0.0.1:7860'),timeout=.5):result['image']={'ok':True,'already_running':True}
            elif launcher and Path(launcher).exists():result['image']=launch_image_server(launcher,'--api')
            else:result['image']={'ok':False,'reason':'launcher_missing'}
        except Exception as e:result['image']={'ok':False,'error':str(e)}
    return result

def setup_status(hardware=None):
    rec=recommended_text_model(hardware or {})
    return {'ollama':ollama_path(),'ollama_running':ollama_running(timeout=.35),'winget':winget_path(),'image_launchers':find_image_launchers(),'image_running':local_image_running(timeout=.35),'free_space_gb':free_space_gb(),'recommended_model':rec}
