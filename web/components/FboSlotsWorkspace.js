'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import { ArrowLeft, RefreshCw, Warehouse } from 'lucide-react'

const demo=[
  {warehouse_name:'Коледино',date:'2026-09-08',coefficient:0,free_acceptance:true,box_type_id:2,is_sorting_center:false},
  {warehouse_name:'Электросталь',date:'2026-09-09',coefficient:1,free_acceptance:false,box_type_id:2,is_sorting_center:false},
  {warehouse_name:'Казань',date:'2026-09-10',coefficient:0,free_acceptance:true,box_type_id:2,is_sorting_center:false},
]

export default function FboSlotsWorkspace(){
  const [marketplace,setMarketplace]=useState('wildberries')
  const [freeOnly,setFreeOnly]=useState(true)
  const [rows,setRows]=useState([])
  const [loading,setLoading]=useState(false)
  const [message,setMessage]=useState('')
  const visible=useMemo(()=>rows.filter(x=>!freeOnly||x.free_acceptance),[rows,freeOnly])

  async function search(){
    setLoading(true);setMessage('')
    try{
      const qs=new URLSearchParams({marketplace,free_only:String(freeOnly)})
      const response=await fetch(`/api/marketplace/fbo-slots?${qs.toString()}`,{cache:'no-store'})
      const payload=await response.json()
      if(!response.ok) throw new Error(payload.error||'Не удалось получить слоты')
      setRows(payload.slots||[])
      setMessage(`Найдено доступных вариантов: ${(payload.slots||[]).length}`)
    }catch(error){
      setRows(demo)
      setMessage(`${error.message} Ниже показан демонстрационный формат результата, реальные слоты не подменяются.`)
    }finally{setLoading(false)}
  }

  return <main className="workPage"><div className="workHead"><Link href="/inventory" className="ghostBtn"><ArrowLeft size={16}/> Остатки</Link><Link href="/account" className="ghostBtn">Подключения</Link></div>
    <section className="workHero"><span className="eyebrow">FBO / FBW ПОСТАВКИ</span><h1>Свободные склады для приёмки</h1><p>Поиск доступных дат и складов для поставки. Для Wildberries используются коэффициенты приёмки: доступными считаются варианты с разрешённой разгрузкой и коэффициентом 0 или 1; коэффициент 0 отмечается как бесплатная приёмка.</p></section>
    <section className="workPanel fboFilters"><div><label>Маркетплейс<select value={marketplace} onChange={e=>setMarketplace(e.target.value)}><option value="wildberries">Wildberries</option><option value="ozon">Ozon</option></select></label><label className="fboCheck"><input type="checkbox" checked={freeOnly} onChange={e=>setFreeOnly(e.target.checked)}/> Только бесплатная приёмка</label></div><button className="primaryBtn" onClick={search} disabled={loading}><RefreshCw size={17}/>{loading?'Проверяем…':'Найти свободные склады'}</button></section>
    {message&&<div className="sectionNotice">{message}</div>}
    <section className="fboGrid">{visible.length?visible.map((slot,i)=><article className="workPanel fboCard" key={`${slot.warehouse_name}-${slot.date}-${i}`}><div className="fboIcon"><Warehouse size={21}/></div><div><span className="eyebrow">{slot.free_acceptance?'БЕСПЛАТНО':'ДОСТУПНО'}</span><h3>{slot.warehouse_name}</h3><p>{slot.date?new Date(slot.date).toLocaleDateString('ru-RU'):'Дата не указана'}</p><div className="fboMeta"><span>Коэффициент <b>{slot.coefficient}</b></span><span>{slot.is_sorting_center?'Сортировочный центр':'Склад'}</span></div></div></article>):<div className="workPanel emptyPreview">Нажмите «Найти свободные склады». После подключения магазина здесь появятся реальные данные маркетплейса.</div>}</section>
  </main>
}
