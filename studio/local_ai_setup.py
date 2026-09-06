import os, shutil, subprocess, time
from pathlib import Path


def _which(name):
    return shutil.which(name)


def ollama_path():
    p=_which('ollama')
    if p:return p
    if os.name=='nt':
        candidates=[
            Path(os.environ.get('LOCALAPPDATA',''))/'Programs'/'Ollama'/'ollama.exe',
            Path(os.environ.get('PROGRAMFILES',''))/'Ollama'/'ollama.exe',
        ]
        for c in candidates:
            if c.exists():return str(c)
    return None


def winget_path():
    return _which('winget') if os.name=='nt' else None


def install_ollama(progress=None):
    """Install Ollama on Windows via winget when available. Never installs silently on non-Windows."""
    existing=ollama_path()
    if existing:return {'ok':True,'already_installed':True,'path':existing}
    if os.name!='nt':
        raise RuntimeError('Автоустановка Ollama сейчас реализована для Windows. Установите Ollama вручную и повторите проверку.')
    winget=winget_path()
    if not winget:
        raise RuntimeError('winget не найден. Установите App Installer из Microsoft Store или Ollama вручную.')
    if progress:progress(15,'Устанавливаю Ollama через winget...')
    cmd=[winget,'install','--id','Ollama.Ollama','-e','--accept-source-agreements','--accept-package-agreements']
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=900)
    if p.returncode!=0:
        raise RuntimeError('Не удалось установить Ollama через winget:\n'+(p.stderr or p.stdout or '')[-1500:])
    if progress:progress(70,'Проверяю установленный Ollama...')
    path=ollama_path()
    if not path:
        time.sleep(2); path=ollama_path()
    if not path:
        raise RuntimeError('Ollama установлен, но executable пока не найден. Перезапустите приложение и повторите проверку.')
    return {'ok':True,'already_installed':False,'path':path}


def ensure_ollama_running():
    path=ollama_path()
    if not path:raise RuntimeError('Ollama не установлен.')
    try:
        subprocess.Popen([path,'serve'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except Exception:
        pass
    return path


def pull_ollama_model(model='qwen2.5:3b',progress=None):
    path=ensure_ollama_running(); model=(model or 'qwen2.5:3b').strip()
    if progress:progress(20,f'Загружаю локальную модель {model}...')
    p=subprocess.run([path,'pull',model],capture_output=True,text=True,timeout=7200)
    if p.returncode!=0:
        raise RuntimeError('Не удалось загрузить модель '+model+':\n'+(p.stderr or p.stdout or '')[-1500:])
    if progress:progress(100,f'Модель {model} готова')
    return {'ok':True,'model':model,'url':'http://127.0.0.1:11434/v1','path':path}


def find_image_launchers():
    """Find existing Forge/A1111 launchers without downloading third-party software."""
    roots=[]
    for env in ('USERPROFILE','LOCALAPPDATA'):
        base=os.environ.get(env)
        if base:roots.append(Path(base))
    names=('webui-user.bat','run.bat','webui.bat')
    out=[]
    common=[]
    home=Path.home()
    common += [home/'stable-diffusion-webui',home/'stable-diffusion-webui-forge',home/'Forge',home/'Downloads'/'stable-diffusion-webui-forge']
    for root in common:
        for n in names:
            p=root/n
            if p.exists():out.append(str(p))
    return list(dict.fromkeys(out))


def launch_image_server(launcher,extra_args='--api'):
    p=Path(str(launcher or ''))
    if not p.exists():raise RuntimeError('Файл запуска Local Image AI не найден.')
    args=[str(p)]
    extra=[x for x in str(extra_args or '--api').split() if x]
    if p.suffix.lower()=='.bat':
        cmd=['cmd.exe','/c',str(p)]+extra
    else:
        cmd=args+extra
    subprocess.Popen(cmd,cwd=str(p.parent),creationflags=getattr(subprocess,'CREATE_NEW_CONSOLE',0))
    return {'ok':True,'launcher':str(p),'args':extra}


def setup_status():
    return {
        'ollama':ollama_path(),
        'winget':winget_path(),
        'image_launchers':find_image_launchers(),
    }
