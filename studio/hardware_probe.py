import os, platform, shutil, subprocess


def _ram_gb():
    try:
        if os.name == 'nt':
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_=[('dwLength',ctypes.c_ulong),('dwMemoryLoad',ctypes.c_ulong),('ullTotalPhys',ctypes.c_ulonglong),('ullAvailPhys',ctypes.c_ulonglong),('ullTotalPageFile',ctypes.c_ulonglong),('ullAvailPageFile',ctypes.c_ulonglong),('ullTotalVirtual',ctypes.c_ulonglong),('ullAvailVirtual',ctypes.c_ulonglong),('sullAvailExtendedVirtual',ctypes.c_ulonglong)]
            st=MEMORYSTATUSEX(); st.dwLength=ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return round(st.ullTotalPhys/(1024**3),1)
        if hasattr(os,'sysconf'):
            pages=os.sysconf('SC_PHYS_PAGES'); size=os.sysconf('SC_PAGE_SIZE')
            return round((pages*size)/(1024**3),1)
    except Exception:
        pass
    return None


def _nvidia():
    exe=shutil.which('nvidia-smi')
    if not exe:return None
    try:
        out=subprocess.check_output([exe,'--query-gpu=name,memory.total','--format=csv,noheader,nounits'],text=True,timeout=6,stderr=subprocess.STDOUT)
        first=(out.strip().splitlines() or [''])[0]
        if not first:return None
        parts=[x.strip() for x in first.rsplit(',',1)]
        return {'name':parts[0],'vram_gb':round(float(parts[1])/1024,1) if len(parts)>1 else None}
    except Exception:
        return None


def probe_hardware():
    ram=_ram_gb(); gpu=_nvidia(); rec='text_only'
    if gpu and (gpu.get('vram_gb') or 0)>=12:rec='local_image_high'
    elif gpu and (gpu.get('vram_gb') or 0)>=8:rec='local_image_medium'
    elif gpu and (gpu.get('vram_gb') or 0)>=6:rec='local_image_light'
    elif (ram or 0)>=32:rec='local_image_cpu_slow'
    return {
        'os':platform.platform(),
        'machine':platform.machine(),
        'ram_gb':ram,
        'gpu':gpu,
        'recommendation':rec,
    }


def recommendation_text(info=None):
    info=info or probe_hardware(); gpu=info.get('gpu') or {}; ram=info.get('ram_gb'); rec=info.get('recommendation')
    base=f"RAM: {ram if ram is not None else '?'} GB · GPU: {gpu.get('name') or 'не обнаружена'}"
    if gpu.get('vram_gb') is not None:base+=f" · VRAM: {gpu['vram_gb']} GB"
    notes={
        'local_image_high':'Подходит для локальной генерации изображений высокого качества.',
        'local_image_medium':'Подходит для локальной генерации в среднем качестве/разрешении.',
        'local_image_light':'Локальные изображения возможны в облегчённом режиме.',
        'local_image_cpu_slow':'Можно запускать локально на CPU, но генерация будет медленной.',
        'text_only':'Рекомендуется Local AI для текста; изображения лучше генерировать на другом локальном ПК или включать Premium вручную.',
    }
    return base+'\n'+notes.get(rec,'')
