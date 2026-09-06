import json, os
from .autopilot import actions, set_action_status, save_card_version
from .wb_publisher import WBPublisher


def _extract_urls(images):
    urls=[]
    for item in images or []:
        if isinstance(item,str) and item.startswith('http'):
            urls.append(item); continue
        if isinstance(item,dict):
            for key in ('big','c900x1200','c516x688','square','tm','url'):
                value=item.get(key)
                if isinstance(value,str) and value.startswith('http'):
                    urls.append(value); break
    return urls


def _local_paths(images):
    out=[]
    for item in images or []:
        if isinstance(item,str) and not item.startswith('http') and os.path.exists(item):out.append(item)
    return out


class WBRollbackExecutor:
    def __init__(self,wb):
        self.wb=wb

    def execute_payload(self,nm_id,payload):
        previous_card=payload.get('previous_card') or {}
        previous_images=payload.get('previous_images') or []
        prepared=WBPublisher(self.wb).prepare_update(nm_id,previous_card)
        result={'text':None,'media_mode':'unchanged','media_count':0}
        result['text']=self.wb.update_card(prepared['payload'])
        local=_local_paths(previous_images)
        urls=_extract_urls(previous_images)
        if local:
            uploaded=[]
            for i,path in enumerate(local,1):uploaded.append(self.wb.upload_media_file(nm_id,path,i))
            result['media_mode']='local_files'; result['media_count']=len(uploaded)
        elif urls:
            self.wb.save_media_urls(nm_id,urls)
            result['media_mode']='urls'; result['media_count']=len(urls)
        version=save_card_version('WB',nm_id,previous_card,previous_images,'rollback_published',payload.get('before_metrics') or {})
        result['rollback_version']=version
        return result

    def execute_action(self,action_id):
        row=next((x for x in actions(1000) if int(x.get('id') or 0)==int(action_id)),None)
        if not row:raise RuntimeError('Rollback action не найден')
        if row.get('marketplace')!='WB' or row.get('action_type')!='rollback_card':raise RuntimeError('Действие не является WB rollback')
        if row.get('status')=='done':return {'already_done':True}
        try:payload=json.loads(row.get('payload') or '{}')
        except Exception:raise RuntimeError('Повреждён payload rollback')
        set_action_status(action_id,'running')
        try:
            result=self.execute_payload(row.get('entity_id'),payload)
            set_action_status(action_id,'done',result); return result
        except Exception as e:
            set_action_status(action_id,'failed',{'error':str(e)}); raise
