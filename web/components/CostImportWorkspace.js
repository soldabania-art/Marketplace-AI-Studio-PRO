'use client'

import Link from 'next/link'
import {useEffect,useMemo,useState} from 'react'
import {CheckCircle2,CircleAlert,Clock3,FileSpreadsheet,LockKeyhole,Save,Trash2,Upload} from 'lucide-react'
import {normalizeCostModel,normalizeMoney,parseCostCsv,suggestCostMapping} from '../lib/costImportCsv.mjs'

const sourceOptions=[['csv','CSV (включая экспорт Excel)'],['1c','1С'],['moysklad','МойСклад'],['saby','Saby / СБИС'],['kontur','Контур'],['partner_api','Партнёрская система']]
const sourceLabels=Object.fromEntries(sourceOptions)
const modelLabels={reseller:'Реселлер',manufacturer:'Производство',distributor:'Дистрибьютор'}
const statusLabels={preview:'Ожидает подтверждения',committed:'Применён',expired:'Истёк'}

export default function CostImportWorkspace({storeId,profile,onCommitted,onNotice}){
  const [parsed,setParsed]=useState(null)
  const [fileName,setFileName]=useState('')
  const [sourceSystem,setSourceSystem]=useState('csv')
  const [documentReference,setDocumentReference]=useState('')
  const [mapping,setMapping]=useState({nm_id:'',operating_model:'',row_source:'',components:{}})
  const [preview,setPreview]=useState(null)
  const [errors,setErrors]=useState([])
  const [busy,setBusy]=useState(false)
  const [confirmed,setConfirmed]=useState(false)
  const [presets,setPresets]=useState([])
  const [presetName,setPresetName]=useState('')
  const [selectedPresetId,setSelectedPresetId]=useState('')
  const [history,setHistory]=useState([])

  const componentCatalog=profile?.component_catalog||{}
  const allowedModels=profile?.allowed_sku_models||[]
  const componentKeys=useMemo(()=>[...new Set(allowedModels.flatMap(model=>Object.keys(componentCatalog[model]||{})))],[allowedModels,componentCatalog])

  useEffect(()=>{if(!storeId)return;let active=true
    Promise.all([fetch(`/api/profit-center/cost-import-mappings?store_id=${encodeURIComponent(storeId)}`),fetch(`/api/profit-center/cost-imports?store_id=${encodeURIComponent(storeId)}`)]).then(async responses=>Promise.all(responses.map(async response=>({response,payload:await response.json()})))).then(([presetResult,historyResult])=>{if(!active)return;if(presetResult.response.ok)setPresets(presetResult.payload.items||[]);if(historyResult.response.ok)setHistory(historyResult.payload.items||[]) }).catch(()=>{})
    return()=>{active=false}
  },[storeId])

  async function refreshHistory(){try{const response=await fetch(`/api/profit-center/cost-imports?store_id=${encodeURIComponent(storeId)}`);if(response.ok){const payload=await response.json();setHistory(payload.items||[])}}catch{}}

  function invalidate(){setPreview(null);setConfirmed(false);setErrors([])}
  function updateMapping(key,value){invalidate();setMapping(current=>({...current,[key]:value}))}
  function updateComponent(key,value){invalidate();setMapping(current=>({...current,components:{...current.components,[key]:value}}))}

  function applyPreset(id){
    setSelectedPresetId(id)
    const preset=presets.find(item=>item.id===id);if(!preset||!parsed)return
    const columns=new Set(parsed.headers);const next=preset.mapping
    const required=[next.nm_id,next.operating_model,next.row_source,...Object.values(next.components||{})].filter(Boolean)
    if(required.some(column=>!columns.has(column))){setErrors([{error:'В выбранном файле нет одной или нескольких колонок сохранённой схемы.'}]);return}
    invalidate();setMapping(next);setSourceSystem(preset.source_system);setPresetName(preset.name)
  }

  async function savePreset(){
    if(!mapping.nm_id||presetName.trim().length<2)return
    setBusy(true);setErrors([])
    try{const response=await fetch('/api/profit-center/cost-import-mappings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:storeId,name:presetName.trim(),source_system:sourceSystem,mapping})});const payload=await response.json();if(!response.ok)throw new Error(payload.error||'Не удалось сохранить схему.');setPresets(current=>[...current.filter(item=>item.id!==payload.id&&item.name!==payload.name),payload].sort((a,b)=>a.name.localeCompare(b.name,'ru')));onNotice?.('Схема сопоставления сохранена для этого магазина.')}
    catch(error){setErrors([{error:error.message}])}finally{setBusy(false)}
  }

  async function deletePreset(){
    const preset=presets.find(item=>item.id===selectedPresetId);if(!preset)return
    if(!window.confirm(`Удалить схему «${preset.name}»? Это действие нельзя отменить.`))return
    setBusy(true);setErrors([])
    try{const response=await fetch(`/api/profit-center/cost-import-mappings/${encodeURIComponent(preset.id)}?store_id=${encodeURIComponent(storeId)}`,{method:'DELETE'});if(!response.ok){const payload=await response.json();throw new Error(payload.error||'Не удалось удалить схему.')}setPresets(current=>current.filter(item=>item.id!==preset.id));setPresetName('');setSelectedPresetId('');onNotice?.('Схема удалена.')}
    catch(error){setErrors([{error:error.message}])}finally{setBusy(false)}
  }

  async function selectFile(event){
    const file=event.target.files?.[0]; invalidate()
    if(!file){setParsed(null);setFileName('');return}
    if(file.size>2*1024*1024){setParsed(null);setFileName('');setErrors([{error:'Файл больше 2 МБ. Разделите импорт на части.'}]);return}
    try{
      const result=parseCostCsv(await file.text())
      if(result.headers.some(header=>header.includes('\uFFFD')))throw new Error('Не удалось прочитать кодировку. Сохраните CSV в UTF-8 и повторите загрузку.')
      setParsed(result);setFileName(file.name);setMapping(suggestCostMapping(result.headers,componentKeys))
    }catch(error){setParsed(null);setFileName(file.name);setErrors([{error:error.message}])}
  }

  function normalizedRows(){
    if(!mapping.nm_id)throw new Error('Выберите колонку nmId.')
    if(allowedModels.length>1&&!mapping.operating_model)throw new Error('Для смешанного магазина выберите колонку модели SKU.')
    const result=[];const rowErrors=[]
    for(const record of parsed.records){
      const rawId=String(record.values[mapping.nm_id]||'').trim()
      const nmId=/^\d+$/.test(rawId)?Number(rawId):0
      const model=allowedModels.length===1?allowedModels[0]:normalizeCostModel(record.values[mapping.operating_model])
      try{
        if(!Number.isSafeInteger(nmId)||nmId<=0)throw new Error('Некорректный nmId.')
        if(!model||!allowedModels.includes(model))throw new Error('Неизвестная или недоступная модель SKU.')
        const components={};const sourceReferences={}
        const rowSource=String(mapping.row_source?record.values[mapping.row_source]||'':'').trim()||documentReference.trim()
        for(const key of Object.keys(componentCatalog[model]||{})){
          const column=mapping.components[key]
          if(!column)continue
          const amount=normalizeMoney(record.values[column])
          if(amount===null||Number(amount)===0)continue
          if(!rowSource)throw new Error('Для ненулевых сумм нужен источник или номер документа.')
          components[key]=amount;sourceReferences[key]=rowSource
        }
        if(!Object.keys(components).length)throw new Error('Не найдено ни одного ненулевого компонента себестоимости.')
        result.push({nm_id:nmId,operating_model:model,components_rub:components,source_references:sourceReferences})
      }catch(error){rowErrors.push({row:record.rowNumber,nm_id:nmId||rawId||'—',error:error.message})}
    }
    if(rowErrors.length){const error=new Error('Исправьте строки импорта.');error.rowErrors=rowErrors;throw error}
    return result
  }

  async function createPreview(){
    if(!parsed||!storeId)return
    setBusy(true);invalidate()
    try{
      if(documentReference.trim().length<2)throw new Error('Укажите документ или выгрузку — это общий источник импорта.')
      const rows=normalizedRows()
      const response=await fetch('/api/profit-center/cost-imports/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:storeId,source_system:sourceSystem,source_document_reference:documentReference.trim(),rows})})
      const payload=await response.json()
      if(!response.ok){const error=new Error(payload.error||'Не удалось создать превью.');error.rowErrors=payload.details?.row_errors||[];throw error}
      setPreview(payload);await refreshHistory();onNotice?.(`Превью готово: ${payload.row_count} строк. Проверьте суммы перед применением.`)
    }catch(error){setErrors(error.rowErrors?.length?error.rowErrors:[{error:error.message}]);onNotice?.(error.message)}finally{setBusy(false)}
  }

  async function commitPreview(){
    if(!preview||!confirmed)return
    setBusy(true);setErrors([])
    try{
      const response=await fetch(`/api/profit-center/cost-imports/${encodeURIComponent(preview.id)}/commit`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:storeId,preview_sha256:preview.preview_sha256,confirmed:true})})
      const payload=await response.json()
      if(!response.ok)throw new Error(payload.error||'Не удалось применить импорт.')
      setPreview(payload);setConfirmed(false);onNotice?.(`Применено строк: ${payload.row_count}. Изменение записано в аудит.`);await Promise.all([onCommitted?.(),refreshHistory()])
    }catch(error){setErrors([{error:error.message}]);onNotice?.(error.message)}finally{setBusy(false)}
  }

  function downloadTemplate(){
    const headers=['nmId',...(allowedModels.length>1?['model']:[]),...componentKeys,'source']
    const blob=new Blob([`\uFEFF${headers.join(';')}\r\n`],{type:'text/csv;charset=utf-8'})
    const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='trovendi-cost-import.csv';link.click();URL.revokeObjectURL(url)
  }

  if(!profile)return <section className="workPanel costImportPanel"><div className="costImportTitle"><FileSpreadsheet size={22}/><div><h2>Массовый импорт себестоимости</h2><p>Сначала подтвердите модель бизнеса — она определяет допустимые колонки и правила расчёта.</p></div><Link href="/onboarding#business-profile" className="ghostBtn">Настроить</Link></div></section>

  return <section className="workPanel costImportPanel"><div className="costImportTitle"><FileSpreadsheet size={22}/><div><span className="eyebrow">БЕЗОПАСНЫЙ ИМПОРТ</span><h2>Себестоимость из учётной системы</h2><p>До подтверждения данные не меняются. Максимум 500 строк и 2 МБ за одно превью.</p></div><button type="button" className="ghostBtn" onClick={downloadTemplate}>Скачать шаблон</button></div>
    <div className="costImportSetup"><label>Источник<select value={sourceSystem} onChange={event=>{invalidate();setSourceSystem(event.target.value)}}>{sourceOptions.map(([value,label])=><option value={value} key={value}>{label}</option>)}</select></label><label>Документ / выгрузка<input value={documentReference} maxLength={300} onChange={event=>{invalidate();setDocumentReference(event.target.value)}} placeholder="Например: 1С, расчёт №42 от 10.09.2026"/></label><label className="costFile"><Upload size={16}/><span>{fileName||'Выбрать CSV'}</span><input type="file" accept=".csv,.txt,text/csv,text/plain" onChange={selectFile}/></label></div>
    {parsed&&<><div className="costPresetBar"><label>Сохранённая схема<select value={selectedPresetId} onChange={event=>applyPreset(event.target.value)}><option value="">Выберите схему</option>{presets.map(item=><option value={item.id} key={item.id}>{item.name}</option>)}</select></label><label>Название схемы<input value={presetName} maxLength={80} onChange={event=>setPresetName(event.target.value)} placeholder="Например: Выгрузка 1С"/></label><button type="button" onClick={savePreset} disabled={busy||!mapping.nm_id||presetName.trim().length<2}><Save size={15}/>Сохранить</button><button type="button" className="dangerGhost" aria-label="Удалить выбранную схему" onClick={deletePreset} disabled={busy||!selectedPresetId}><Trash2 size={15}/></button></div><div className="costMapping"><div><b>Сопоставление колонок</b><span>{parsed.records.length} строк · разделитель {parsed.separator==='\t'?'табуляция':parsed.separator}</span></div><label>nmId<select value={mapping.nm_id} onChange={event=>updateMapping('nm_id',event.target.value)}><option value="">Не выбрано</option>{parsed.headers.map(header=><option key={header}>{header}</option>)}</select></label>{allowedModels.length>1&&<label>Модель SKU<select value={mapping.operating_model} onChange={event=>updateMapping('operating_model',event.target.value)}><option value="">Не выбрано</option>{parsed.headers.map(header=><option key={header}>{header}</option>)}</select></label>}<label>Источник строки<select value={mapping.row_source} onChange={event=>updateMapping('row_source',event.target.value)}><option value="">Общий документ</option>{parsed.headers.map(header=><option key={header}>{header}</option>)}</select></label>{componentKeys.map(key=><label key={key}>{componentCatalog[allowedModels.find(model=>componentCatalog[model]?.[key])]?.[key]||key}<select value={mapping.components[key]||''} onChange={event=>updateComponent(key,event.target.value)}><option value="">Не импортировать</option>{parsed.headers.map(header=><option key={header}>{header}</option>)}</select></label>)}</div></>}
    {errors.length>0&&<div className="costImportErrors" role="alert"><b><CircleAlert size={16}/> Найдены ошибки</b>{errors.slice(0,20).map((item,index)=><span key={`${item.row||0}-${index}`}>{item.row?`Строка ${item.row}, nmId ${item.nm_id}: `:''}{item.error}</span>)}{errors.length>20&&<span>Ещё ошибок: {errors.length-20}</span>}</div>}
    {parsed&&!preview&&<button type="button" className="primaryBtn costPreviewBtn" onClick={createPreview} disabled={busy||!mapping.nm_id}><LockKeyhole size={16}/>{busy?'Проверяем…':'Создать защищённое превью'}</button>}
    {preview&&<div className={`costPreview ${preview.status==='committed'?'committed':''}`} aria-live="polite"><div><CheckCircle2 size={18}/><b>{preview.status==='committed'?'Импорт применён':'Превью готово'}</b><span>{preview.row_count} строк · SHA {preview.preview_sha256.slice(0,12)}</span></div><div className="costPreviewRows">{preview.rows.slice(0,20).map(item=><span key={item.nm_id}><b>nmId {item.nm_id}</b><i>{modelLabels[item.operating_model]}</i><strong>{item.cogs_rub} ₽</strong></span>)}</div>{preview.status!=='committed'&&<div className="costCommit"><label><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/><span>Я проверил источник, соответствие колонок и итоговые суммы</span></label><button type="button" className="costSave" disabled={!confirmed||busy} onClick={commitPreview}>{busy?'Применяем…':'Применить импорт'}</button></div>}</div>}
    {history.length>0&&<div className="costImportHistory"><div><Clock3 size={16}/><b>Последние импорты</b><span>Без раскрытия построчных финансовых данных</span></div>{history.map(item=><div className={`costHistoryRow ${item.status}`} key={item.id}><span><b>{sourceLabels[item.source_system]||item.source_system}</b><small>{item.source_document_reference}</small></span><span>{item.row_count} строк</span><span>{new Date(item.created_at).toLocaleString('ru-RU',{dateStyle:'short',timeStyle:'short'})}</span><strong>{statusLabels[item.status]||item.status}</strong></div>)}</div>}
  </section>
}
