'use client'

import Link from 'next/link'
import { ArrowLeft, Building2, Clock3, Sparkles } from 'lucide-react'
import { useActiveStore } from '../lib/useActiveStore'

export default function StudioSection({ eyebrow, title, description, stage, limitation, cards = [], availableLink }) {
  const {storeId,storeName,loading,error}=useActiveStore()

  return <main className="sectionPage">
    <header className="sectionTop"><Link href="/" className="ghostBtn"><ArrowLeft size={16}/> На главную</Link><Link href="/account" className="ghostBtn">Аккаунт</Link></header>
    <section className="sectionHero"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p><div className="sectionStoreContext"><Building2 size={16}/><span>{loading?'Загружаем магазин…':storeId?`Активный магазин: ${storeName}`:'Активный магазин не выбран'}</span></div><div className="sectionStage"><Clock3 size={18}/><div><span>СТАТУС ЭКРАНА</span><strong>{stage}</strong></div></div><p className="sectionLimitation">{limitation}</p>{availableLink&&<Link className="primaryBtn" href={availableLink.href}>{availableLink.label}</Link>}{error&&<div className="sectionNotice">{error}</div>}</section>
    <section className="sectionCards">{cards.map((card)=><article className="sectionCard" key={card.title}><div className="brandMark"><Sparkles size={18}/></div><span className="eyebrow">ПЛАНИРУЕТСЯ</span><h3>{card.title}</h3><p>{card.text}</p></article>)}</section>
  </main>
}
