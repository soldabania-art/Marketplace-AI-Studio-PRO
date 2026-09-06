import os, re, requests
from pathlib import Path
from .core import DATA
from . import __version__

REPO='soldabania-art/Marketplace-AI-Studio-PRO'
API='https://api.github.com/repos/'+REPO+'/releases/latest'


def _version_tuple(value):
    nums=re.findall(r'\d+',str(value or ''))
    return tuple(int(x) for x in nums[:3]) if nums else (0,0,0)


def check_latest(timeout=20):
    r=requests.get(API,headers={'Accept':'application/vnd.github+json','User-Agent':'MarketplaceAIStudioPRO'},timeout=timeout)
    if not r.ok:raise RuntimeError(f'GitHub update check HTTP {r.status_code}')
    data=r.json(); tag=str(data.get('tag_name') or '')
    assets=data.get('assets') or []
    setup=next((a for a in assets if str(a.get('name') or '').lower().endswith('_setup.exe')),None)
    latest=_version_tuple(tag); current=_version_tuple(__version__)
    return {'current':__version__,'tag':tag,'newer':latest>current,'asset':setup,'html_url':data.get('html_url'),'name':data.get('name')}


def download_installer(info,progress=None):
    asset=(info or {}).get('asset') or {}
    url=asset.get('browser_download_url')
    if not url:raise RuntimeError('В последнем GitHub Release не найден Windows Setup.exe')
    folder=DATA/'updates'; folder.mkdir(parents=True,exist_ok=True)
    path=folder/(asset.get('name') or 'Marketplace_AI_Studio_PRO_Setup.exe')
    with requests.get(url,stream=True,timeout=180) as r:
        r.raise_for_status(); total=int(r.headers.get('content-length') or 0); done=0
        with path.open('wb') as f:
            for chunk in r.iter_content(1024*256):
                if not chunk:continue
                f.write(chunk); done+=len(chunk)
                if progress and total:progress(min(100,int(done/total*100)))
    return path


def launch_installer(path):
    p=Path(path)
    if not p.exists():raise FileNotFoundError(str(p))
    if os.name!='nt':raise RuntimeError('Автоустановка доступна только в Windows-сборке')
    os.startfile(str(p))
    return True
