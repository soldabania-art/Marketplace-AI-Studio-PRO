'use client'

import Link from 'next/link'
import { useEffect,useMemo,useState } from 'react'
import { ArrowLeft,Boxes,Building2,CheckCircle2,Database,LockKeyhole,Truck } from 'lucide-react'
import { useActiveStore } from '../lib/useActiveStore'

const kinds={marketplace:['Маркетплейсы',Boxes],accounting:['Учёт и ERP',Database],logistics:['Склады и логистика',Truck]}
const stages={available:'доступно',read_beta:'чтение · beta',discovery:'исследование',planned:'в плане'}
const capabilityNames={catalog:'товары',stocks:'остатки',sales:'продажи',finance:'финансы',advertising:'реклама',feedbacks:'отзывы',content_write:'карточки',warehouses:'склады',orders:'заказы',costs:'себестоимость',documents:'документы',webhooks:'webhooks',cross_border:'кроссбордер',localization:'локализация',costs_import:'импорт затрат',saved_mapping:'схемы колонок',validation:'проверка',reservations:'резервы',shipments:'отгрузки',returns:'возвраты',compliance:'комплаенс'}

export default function IntegrationHubWorkspace(){
 const {storeId,storeName,loading,error:storeError}=useActiveStore();const [data,setData]=useState(null);const [error,setError]=useState('')
 useEffect(()=>{if(!storeId)return;let active=true;fetch(`/api/integrations/catalog?store_id=${encodeURIComponent(storeId)}`,{cache:'no-store'}).then(async r=>{const p=await r.json();if(!r.ok)throw new Error(p.error||'Не удалось загрузить Integration Hub');if(active)setData(p)}).catch(e=>active&&setError(e.message));return()=>{active=false}},[storeId])
 const groups=useMemo(()=>Object.fromEntries(Object.keys(kinds).map(kind=>[kind,(data?.connectors||[]).filter(row=>row.kind===kind)])),[data])
 return <main className="sectionPage"><header className="sectionTop"><Link href="/" className="ghostBtn"><ArrowLeft size={16}/> На главную</Link><Link href="/account" className="ghostBtn">Безопасность и подключения</Link></header>
  <section className="workHero"><span className="eyebrow">TROVENDI · ЕДИНОЕ ЯДРО</span><h1>Integration Hub</h1><p>Маркетплейсы, 1С, учётные системы и склады подключаются через единый безопасный контракт. Будущие адаптеры показаны заранее, но не выдаются за работающие.</p><div className="sectionStoreContext"><Building2 size={16}/><span>{loading?'Загружаем магазин…':storeId?`Активный магазин: ${storeName}`:'Активный магазин не выбран'}</span></div>{data&&<small>Версия каталога: {data.catalog_version}</small>}</section>
  {(storeError||error)&&<div className="sectionNotice">{storeError||error}</div>}
  {Object.entries(kinds).map(([kind,[label,Icon]])=><section key={kind}><div className="panelTitle"><div><span className="eyebrow">{label}</span><h2>{label}</h2></div><Icon size={22}/></div><div className="sectionCards">{groups[kind].map(row=><article className="sectionCard" key={row.code}><div className="brandMark">{row.connected?<CheckCircle2 size={18}/>:<LockKeyhole size={18}/>}</div><span className="eyebrow">{row.connected?'подключено':stages[row.stage]}</span><h3>{row.name}</h3><p>{row.capabilities.map(code=>capabilityNames[code]||code).join(' · ')}</p><small>Следующий контроль: {row.next_gate}</small>{row.code==='wildberries'&&<Link href="/account" className="ghostBtn">{row.connected?'Управлять':'Подключить безопасно'}</Link>}</article>)}</div></section>)}
 </main>
}
