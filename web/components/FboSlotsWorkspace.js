'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, BellRing, RefreshCw, Warehouse } from 'lucide-react'
import { getActiveStoreId, STORE_EVENT } from '../lib/useActiveStore'

function urlBase64ToUint8Array(base64String){
  const padding='='.repeat((4-base64String.length%4)%4)
  const base64=(base64String+padding).replace(/-/g,'+').replace(/_/g,'/')
  const raw=window.atob(base64)
  return Uint8Array.from([...raw].map(char=>char.charCodeAt(0)))
}

export default function FboSlotsWorkspace(){
  const [marketplace,setMarketplace]=useState('wildberries')
  const [freeOnly,setFreeOnly]=useState(false)
  const [storeId,setStoreId]=useState('')
  const [storeName,setStoreName]=useState('')
  const [rows,setRows]=useState([])
  const [loading,setLoading]=useState(false)
  const [message,setMessage]=useState('')
  const [watching,setWatching]=useState(false)
  const [permission,setPermission]=useState('default')
  const [pushReady,setPushReady]=useState(false)
  const visible=useMemo(()=>rows.filter(x=>!freeOnly||x.free_acceptance),[rows,freeOnly])

  async function loadStoreContext(selected){
    setStoreId(selected||'')
    setRows([])
    setMessage('')
    setWatching(false)
    if(!selected){setStoreName('');return}
    try{
      const storesResponse=await fetch('/api/stores',{cache:'no-store'})
      const storesPayload=await storesResponse.json()
      const store=storesPayload.stores?.find(x=>x.id===selected)
      setStoreName(store?.name||'')
      const watchResponse=await fetch(`/api/marketplace/fbo-watch?store_id=${encodeURIComponent(selected)}`,{cache:'no-store'})
      const watchPayload=await watchResponse.json()
      if(watchResponse.ok&&typeof watchPayload.enabled==='boolean'){
        setWatching(watchPayload.enabled)
        setFreeOnly(Array.isArray(watchPayload.coefficients)&&watchPayload.coefficients.length===1&&watchPayload.coefficients[0]===0)
      }
    }catch{}
  }

  useEffect(()=>{
    if(typeof Notification!=='undefined')setPermission(Notification.permission)
    loadStoreContext(getActiveStoreId())
    function changed(event){loadStoreContext(event?.detail?.store_id||getActiveStoreId())}
    window.addEventListener(STORE_EVENT,changed)
    return ()=>window.removeEventListener(STORE_EVENT,changed)
  },[])

  async function search(){
    if(!storeId){setMessage('Сначала выберите магазин в глобальном переключателе или разделе «Подключения».');return false}
    setLoading(true); setMessage('')
    try{
      const qs=new URLSearchParams({marketplace,free_only:String(freeOnly),store_id:storeId})
      const response=await fetch(`/api/marketplace/fbo-slots?${qs.toString()}`,{cache:'no-store'})
      const payload=await response.json()
      if(!response.ok) throw new Error(payload.error||'Не удалось получить слоты')
      const slots=payload.slots||[]
      setRows(slots)
      setStoreName(payload.store_name||storeName)
      setMessage(slots.length?`Найдено доступных вариантов: ${slots.length}`:'Свободных вариантов сейчас нет.')
      return true
    }catch(error){setRows([]);setMessage(error.message);return false}finally{setLoading(false)}
  }

  async function createPushSubscription(){
    if(typeof window==='undefined'||!('serviceWorker' in navigator)||typeof Notification==='undefined') throw new Error('Этот браузер не поддерживает Web Push.')
    const result=await Notification.requestPermission(); setPermission(result)
    if(result!=='granted') throw new Error('Разрешите уведомления для сайта в настройках браузера.')
    const configResponse=await fetch('/api/push/config',{cache:'no-store'})
    const config=await configResponse.json()
    if(!configResponse.ok) throw new Error(config.error||'Не удалось получить настройки PUSH.')
    if(!config.enabled||!config.public_key) throw new Error('Web Push ещё не настроен на сервере.')
    const registration=await navigator.serviceWorker.register('/push-sw.js')
    await navigator.serviceWorker.ready
    let subscription=await registration.pushManager.getSubscription()
    if(!subscription) subscription=await registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:urlBase64ToUint8Array(config.public_key)})
    const saveResponse=await fetch('/api/push/subscription',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(subscription.toJSON())})
    const savePayload=await saveResponse.json()
    if(!saveResponse.ok) throw new Error(savePayload.error||'Не удалось сохранить PUSH-подписку.')
    setPushReady(true)
  }

  async function toggleWatch(){
    if(!storeId){setMessage('Сначала выберите магазин в глобальном переключателе.');return}
    setMessage('')
    try{
      if(watching){
        const response=await fetch('/api/marketplace/fbo-watch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({marketplace,store_id:storeId,warehouse_filter:'',free_only:freeOnly,enabled:false})})
        const payload=await response.json(); if(!response.ok) throw new Error(payload.error||'Не удалось остановить мониторинг.')
        setWatching(false); setMessage(`Мониторинг для ${storeName||'магазина'} остановлен.`); return
      }
      await createPushSubscription()
      const response=await fetch('/api/marketplace/fbo-watch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({marketplace,store_id:storeId,warehouse_filter:'',free_only:freeOnly,enabled:true})})
      const payload=await response.json(); if(!response.ok) throw new Error(payload.error||'Не удалось включить мониторинг.')
      setWatching(true)
      setMessage(`Серверный мониторинг включён для магазина ${storeName||'WB'}: все склады, коэффициенты ${payload.coefficients?.join(' и ')||'0 и 1'}.`)
      await search()
    }catch(error){setMessage(error.message)}
  }

  return <main className="workPage">
    <div className="workHead"><Link href="/inventory" className="ghostBtn"><ArrowLeft size={16}/> Остатки</Link><Link href="/account" className="ghostBtn">Подключения</Link></div>
    <section className="workHero"><span className="eyebrow">FBO / FBW ПОСТАВКИ</span><h1>Свободные склады для приёмки</h1><p>Реальный поиск по активному магазину Wildberries. При переключении магазина этот экран автоматически меняет контекст и не смешивает мониторинг между магазинами.</p></section>
    <div className="sectionNotice">Магазин: {storeName||'не выбран'} · PUSH: {permission==='granted'?(pushReady?'подключён':'разрешён'):(permission==='denied'?'заблокирован браузером':'нужно разрешение')} · Мониторинг: {watching?'активен на сервере':'выключен'} · Коэффициенты: {freeOnly?'0':'0 и 1'}</div>
    <section className="workPanel fboFilters"><div><label>Маркетплейс<select value={marketplace} onChange={e=>setMarketplace(e.target.value)} disabled={watching}><option value="wildberries">Wildberries</option><option value="ozon" disabled>Ozon — скоро</option></select></label><label className="fboCheck"><input type="checkbox" checked={freeOnly} onChange={e=>setFreeOnly(e.target.checked)} disabled={watching}/> Только бесплатная приёмка</label></div><div className="fboActions"><button className="ghostBtn" onClick={toggleWatch}><BellRing size={17}/>{watching?'Остановить мониторинг':'Включить мониторинг + PUSH'}</button><button className="primaryBtn" onClick={search} disabled={loading}><RefreshCw size={17}/>{loading?'Проверяем…':'Найти сейчас'}</button></div></section>
    {message&&<div className="sectionNotice">{message}</div>}
    <section className="fboGrid">{visible.length?visible.map((slot,i)=><article className="workPanel fboCard" key={`${slot.warehouse_name}-${slot.date}-${slot.coefficient}-${i}`}><div className="fboIcon"><Warehouse size={21}/></div><div><span className="eyebrow">{slot.free_acceptance?'БЕСПЛАТНО':'ДОСТУПНО'}</span><h3>{slot.warehouse_name}</h3><p>{slot.date?new Date(slot.date).toLocaleDateString('ru-RU'):'Дата не указана'}</p><div className="fboMeta"><span>Коэффициент <b>{slot.coefficient}</b></span><span>{slot.is_sorting_center?'Сортировочный центр':'Склад'}</span></div></div></article>):<div className="workPanel emptyPreview">Выберите магазин, подключите Wildberries и запустите поиск. Данные другого магазина сюда не попадут.</div>}</section>
  </main>
}
