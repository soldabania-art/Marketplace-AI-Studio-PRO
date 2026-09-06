'use client'

import Link from 'next/link'
import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, BellRing, RefreshCw, Warehouse } from 'lucide-react'

const demo=[
  {warehouse_name:'Коледино',date:'2026-09-08',coefficient:0,free_acceptance:true,box_type_id:2,is_sorting_center:false},
  {warehouse_name:'Электросталь',date:'2026-09-09',coefficient:1,free_acceptance:false,box_type_id:2,is_sorting_center:false},
  {warehouse_name:'Казань',date:'2026-09-10',coefficient:0,free_acceptance:true,box_type_id:2,is_sorting_center:false},
]

const slotKey=x=>`${x.warehouse_name}|${x.date}|${x.coefficient}|${x.box_type_id}`

export default function FboSlotsWorkspace(){
  const [marketplace,setMarketplace]=useState('wildberries')
  const [freeOnly,setFreeOnly]=useState(true)
  const [rows,setRows]=useState([])
  const [loading,setLoading]=useState(false)
  const [message,setMessage]=useState('')
  const [watching,setWatching]=useState(false)
  const [permission,setPermission]=useState('default')
  const seen=useRef(new Set())
  const timer=useRef(null)
  const visible=useMemo(()=>rows.filter(x=>!freeOnly||x.free_acceptance),[rows,freeOnly])

  useEffect(()=>{if(typeof Notification!=='undefined')setPermission(Notification.permission)},[])
  useEffect(()=>()=>{if(timer.current)clearInterval(timer.current)},[])

  async function enablePush(){
    if(typeof Notification==='undefined'){setMessage('Этот браузер не поддерживает системные уведомления.');return false}
    const result=await Notification.requestPermission();setPermission(result)
    if(result!=='granted'){setMessage('Разрешите уведомления для сайта в браузере, чтобы получать сигнал о свободном складе.');return false}
    new Notification('Marketplace AI Studio',{body:'Пуш-уведомления о свободных складах включены.'})
    return true
  }

  function notify(slots){
    if(!slots.length||typeof Notification==='undefined'||Notification.permission!=='granted')return
    const first=slots[0]
    const extra=slots.length>1?` Ещё вариантов: ${slots.length-1}.`:''
    new Notification('Свободный склад для FBO найден!',{body:`${first.warehouse_name} — ${new Date(first.date).toLocaleDateString('ru-RU')}, коэффициент ${first.coefficient}.${extra}`,tag:'fbo-slot-found',requireInteraction:true})
  }

  async function search({silent=false}={}){
    if(!silent)setLoading(true)
    if(!silent)setMessage('')
    try{
      const qs=new URLSearchParams({marketplace,free_only:String(freeOnly)})
      const response=await fetch(`/api/marketplace/fbo-slots?${qs.toString()}`,{cache:'no-store'})
      const payload=await response.json()
      if(!response.ok) throw new Error(payload.error||'Не удалось получить слоты')
      const slots=payload.slots||[]
      const fresh=slots.filter(x=>!seen.current.has(slotKey(x)))
      slots.forEach(x=>seen.current.add(slotKey(x)))
      setRows(slots)
      if(fresh.length)notify(fresh)
      setMessage(slots.length?`Найдено доступных вариантов: ${slots.length}${watching?' · мониторинг включён':''}`:`Свободных вариантов сейчас нет${watching?' · продолжаю проверять':''}.`)
      return true
    }catch(error){
      if(!silent){setRows(demo);setMessage(`${error.message} Ниже показан демонстрационный формат результата, реальные слоты не подменяются.`)}
      return false
    }finally{if(!silent)setLoading(false)}
  }

  async function toggleWatch(){
    if(watching){if(timer.current)clearInterval(timer.current);timer.current=null;setWatching(false);setMessage('Автопоиск остановлен.');return}
    const allowed=permission==='granted'||await enablePush();if(!allowed)return
    seen.current=new Set()
    const ok=await search();if(!ok)return
    setWatching(true)
    timer.current=setInterval(()=>search({silent:true}),60000)
    setMessage('Автопоиск включён: проверяю склады каждую минуту. При появлении нового свободного слота покажу системное уведомление.')
  }

  return <main className="workPage"><div className="workHead"><Link href="/inventory" className="ghostBtn"><ArrowLeft size={16}/> Остатки</Link><Link href="/account" className="ghostBtn">Подключения</Link></div>
    <section className="workHero"><span className="eyebrow">FBO / FBW ПОСТАВКИ</span><h1>Свободные склады для приёмки</h1><p>Поиск доступных дат и складов для поставки. Включите автопоиск — когда появится новый подходящий слот, браузер покажет системное пуш-уведомление.</p></section>
    <section className="workPanel fboFilters"><div><label>Маркетплейс<select value={marketplace} onChange={e=>setMarketplace(e.target.value)} disabled={watching}><option value="wildberries">Wildberries</option><option value="ozon">Ozon</option></select></label><label className="fboCheck"><input type="checkbox" checked={freeOnly} onChange={e=>setFreeOnly(e.target.checked)} disabled={watching}/> Только бесплатная приёмка</label></div><div className="fboActions"><button className="ghostBtn" onClick={toggleWatch}><BellRing size={17}/>{watching?'Остановить автопоиск':'Включить автопоиск + PUSH'}</button><button className="primaryBtn" onClick={()=>search()} disabled={loading}><RefreshCw size={17}/>{loading?'Проверяем…':'Найти сейчас'}</button></div></section>
    <div className="sectionNotice">PUSH: {permission==='granted'?'разрешён':permission==='denied'?'заблокирован браузером':'нужно разрешение'} · Автопоиск: {watching?'включён, проверка раз в минуту':'выключен'}</div>
    {message&&<div className="sectionNotice">{message}</div>}
    <section className="fboGrid">{visible.length?visible.map((slot,i)=><article className="workPanel fboCard" key={`${slot.warehouse_name}-${slot.date}-${i}`}><div className="fboIcon"><Warehouse size={21}/></div><div><span className="eyebrow">{slot.free_acceptance?'БЕСПЛАТНО':'ДОСТУПНО'}</span><h3>{slot.warehouse_name}</h3><p>{slot.date?new Date(slot.date).toLocaleDateString('ru-RU'):'Дата не указана'}</p><div className="fboMeta"><span>Коэффициент <b>{slot.coefficient}</b></span><span>{slot.is_sorting_center?'Сортировочный центр':'Склад'}</span></div></div></article>):<div className="workPanel emptyPreview">Нажмите «Найти сейчас» или включите автопоиск. Для реальных данных необходимо подключение магазина.</div>}</section>
  </main>
}
