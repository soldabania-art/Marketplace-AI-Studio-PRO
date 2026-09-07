'use client'

import Link from 'next/link'
import { useState } from 'react'
import { ArrowLeft, Building2, CheckCircle2, Play, Sparkles } from 'lucide-react'
import { useActiveStore } from '../lib/useActiveStore'

export default function StudioSection({ eyebrow, title, description, cards = [], primary = 'Запустить анализ' }) {
  const [notice, setNotice] = useState('')
  const {storeId,storeName,loading,error}=useActiveStore()

  function explain(action){
    if(loading){setNotice('Загружаем активный магазин…');return}
    if(!storeId){setNotice('Сначала создайте или выберите магазин в аккаунте.');return}
    setNotice(`${action}: выбран магазин «${storeName}». Реальные данные появятся после подключения соответствующего API-модуля.`)
  }

  return <main className="sectionPage">
    <header className="sectionTop"><Link href="/" className="ghostBtn"><ArrowLeft size={16}/> На главную</Link><Link href="/account" className="ghostBtn">Аккаунт</Link></header>
    <section className="sectionHero"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p><div className="sectionStoreContext"><Building2 size={16}/><span>{loading?'Загружаем магазин…':storeId?`Активный магазин: ${storeName}`:'Активный магазин не выбран'}</span></div>{error&&<div className="sectionNotice">{error}</div>}<button className="primaryBtn" onClick={()=>explain(primary)} disabled={loading}><Play size={17}/>{primary}</button></section>
    {notice&&<div className="sectionNotice"><CheckCircle2 size={18}/>{notice}</div>}
    <section className="sectionCards">{cards.map((card)=><article className="sectionCard" key={card.title}><div className="brandMark"><Sparkles size={18}/></div><h3>{card.title}</h3><p>{card.text}</p><button onClick={()=>explain(card.action)} disabled={loading}>{card.action}</button></article>)}</section>
  </main>
}
