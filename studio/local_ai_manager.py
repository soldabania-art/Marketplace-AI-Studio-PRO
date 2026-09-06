import ctypes, os, shutil, subprocess
import requests

from .local_ai_setup import ollama_path, ollama_running, recommended_text_model


OLLAMA_BASE='http://127.0.0.1:11434'


def _ram_state():
    """Return total/available RAM without extra dependencies."""
    try:
        if os.name=='nt':
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_=[('dwLength',ctypes.c_ulong),('dwMemoryLoad',ctypes.c_ulong),('ullTotalPhys',ctypes.c_ulonglong),('ullAvailPhys',ctypes.c_ulonglong),('ullTotalPageFile',ctypes.c_ulonglong),('ullAvailPageFile',ctypes.c_ulonglong),('ullTotalVirtual',ctypes.c_ulonglong),('ullAvailVirtual',ctypes.c_ulonglong),('sullAvailExtendedVirtual',ctypes.c_ulonglong)]
            st=MEMORYSTATUSEX(); st.dwLength=ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                total=st.ullTotalPhys/(1024**3); avail=st.ullAvailPhys/(1024**3)
                return {'total_gb':round(total,1),'available_gb':round(avail,1),'used_percent':round((1-avail/total)*100,1) if total else None}
        if hasattr(os,'sysconf'):
            total=os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')/(1024**3)
            avail=None
            try:
                with open('/proc/meminfo','r',encoding='utf-8') as f:
                    data={k.strip():v.strip() for k,v in (line.split(':',1) for line in f if ':' in line)}
                avail=float(data.get('MemAvailable','0 kB').split()[0])/1024/1024
            except Exception:pass
            return {'total_gb':round(total,1),'available_gb':round(avail,1) if avail is not None else None,'used_percent':round((1-avail/total)*100,1) if avail is not None and total else None}
    except Exception:pass
    return {'total_gb':None,'available_gb':None,'used_percent':None}


def _gpu_state():
    exe=shutil.which('nvidia-smi')
    if not exe:return {'name':None,'total_gb':None,'used_gb':None,'free_gb':None,'used_percent':None}
    try:
        out=subprocess.check_output([exe,'--query-gpu=name,memory.total,memory.used,memory.free','--format=csv,noheader,nounits'],text=True,timeout=5,stderr=subprocess.STDOUT)
        first=(out.strip().splitlines() or [''])[0]; parts=[x.strip() for x in first.rsplit(',',3)]
        if len(parts)!=4:return {'name':None,'total_gb':None,'used_gb':None,'free_gb':None,'used_percent':None}
        total=float(parts[1])/1024; used=float(parts[2])/1024; free=float(parts[3])/1024
        return {'name':parts[0],'total_gb':round(total,1),'used_gb':round(used,1),'free_gb':round(free,1),'used_percent':round(used/total*100,1) if total else None}
    except Exception:
        return {'name':None,'total_gb':None,'used_gb':None,'free_gb':None,'used_percent':None}


def ollama_models(base_url=OLLAMA_BASE):
    try:
        r=requests.get(base_url.rstrip('/')+'/api/tags',timeout=4); r.raise_for_status()
        items=[]
        for m in r.json().get('models') or []:
            items.append({'name':m.get('name') or m.get('model') or '', 'size_gb':round(float(m.get('size') or 0)/(1024**3),2), 'modified_at':m.get('modified_at')})
        return items
    except Exception:return []


def ollama_running_models(base_url=OLLAMA_BASE):
    try:
        r=requests.get(base_url.rstrip('/')+'/api/ps',timeout=4); r.raise_for_status()
        out=[]
        for m in r.json().get('models') or []:
            out.append({'name':m.get('name') or m.get('model') or '', 'size_gb':round(float(m.get('size') or 0)/(1024**3),2), 'size_vram_gb':round(float(m.get('size_vram') or 0)/(1024**3),2), 'expires_at':m.get('expires_at')})
        return out
    except Exception:return []


def _rank_model(name):
    n=str(name or '').lower()
    for marker,rank in [('0.5b',1),('1b',2),('1.5b',3),('2b',4),('3b',5),('4b',6),('7b',7),('8b',8),('14b',9),('32b',10),('70b',11)]:
        if marker in n:return rank
    return 99


def lighter_installed_model(current, installed):
    current_rank=_rank_model(current)
    candidates=[m.get('name') for m in installed if m.get('name') and _rank_model(m.get('name'))<current_rank]
    candidates.sort(key=_rank_model,reverse=True)
    return candidates[0] if candidates else None


def stop_ollama_model(model):
    path=ollama_path()
    if not path or not model:return False
    try:
        p=subprocess.run([path,'stop',str(model)],capture_output=True,text=True,timeout=30)
        return p.returncode==0
    except Exception:return False


def manager_status(cfg=None):
    cfg=cfg or {}; ram=_ram_state(); gpu=_gpu_state(); running=ollama_running()
    installed=ollama_models() if running else []; loaded=ollama_running_models() if running else []
    current=str(cfg.get('local_ai_model') or '')
    pressure='normal'; reasons=[]
    ram_used=ram.get('used_percent'); gpu_used=gpu.get('used_percent')
    if ram_used is not None and ram_used>=92:pressure='critical'; reasons.append(f'RAM {ram_used:.0f}%')
    elif ram_used is not None and ram_used>=84:pressure='high'; reasons.append(f'RAM {ram_used:.0f}%')
    if gpu_used is not None and gpu_used>=95:pressure='critical'; reasons.append(f'VRAM {gpu_used:.0f}%')
    elif gpu_used is not None and gpu_used>=88 and pressure!='critical':pressure='high'; reasons.append(f'VRAM {gpu_used:.0f}%')
    lighter=lighter_installed_model(current,installed) if pressure in ('high','critical') else None
    return {'ollama_running':running,'current_model':current,'installed':installed,'loaded':loaded,'ram':ram,'gpu':gpu,'pressure':pressure,'reasons':reasons,'lighter_installed':lighter,'recommended':recommended_text_model({'ram_gb':ram.get('total_gb'),'gpu':{'vram_gb':gpu.get('total_gb')}})}


def auto_optimize(cfg=None, allow_switch=True):
    """Switch only to an already-installed lighter model. Never downloads, installs, or enables paid APIs."""
    cfg=cfg or {}; st=manager_status(cfg); result={'status':st,'changed':False,'from':st.get('current_model'),'to':None}
    if not allow_switch or st.get('pressure') not in ('high','critical'):return result
    target=st.get('lighter_installed')
    if not target:return result
    current=st.get('current_model')
    if current and current!=target:stop_ollama_model(current)
    cfg['local_ai_model']=target
    result.update({'changed':True,'to':target,'reason':', '.join(st.get('reasons') or [])})
    return result
