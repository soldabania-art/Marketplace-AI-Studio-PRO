'use client'

import Link from 'next/link'
import { useState } from 'react'
import { ArrowLeft, CheckCircle2, Play, Sparkles } from 'lucide-react'

export default function StudioSection({ eyebrow, title, description, cards = [], primary = 'Запустить анализ' }) {
  const [notice, setNotice] = useState('')
  return <main className="sectionPage">
    <header className="sectionTop"><Link href="/" className="ghostBtn"><ArrowLeft size={16}/> На главную</Link><Link href="/account" className="ghostBtn">Аккаунт</Link></header>
    <section className="sectionHero"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p><button className="primaryBtn" onClick={()=>setNotice(`${primary}: задача подготовлена. Для работы с реальными данными подключите WB/Ozon в аккаунте.`)}><Play size={17}/>{primary}</button></section>
    {notice&&<div className="sectionNotice"><CheckCircle2 size={18}/>{notice}</div>}
    <section className="sectionCards">{cards.map((card)=><article className="sectionCard" key={card.title}><div className="brandMark"><Sparkles size={18}/></div><h3>{card.title}</h3><p>{card.text}</p><button onClick={()=>setNotice(`${card.action}: функция готова к подключению реальных данных магазина.`)}>{card.action}</button></article>)}</section>
  </main>
}
