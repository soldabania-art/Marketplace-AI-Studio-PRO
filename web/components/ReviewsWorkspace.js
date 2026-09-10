'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { ArrowLeft, Building2, MessageSquareText, ShieldCheck, Star } from 'lucide-react'
import { useActiveStore } from '../lib/useActiveStore'

export default function ReviewsWorkspace(){
 const {storeId,storeName,loading,error:storeError}=useActiveStore(); const [data,setData]=useState(null); const [error,setError]=useState('')
 useEffect(()=>{if(!storeId)return;let active=true;setError('');fetch(`/api/reviews?store_id=${encodeURIComponent(storeId)}`,{cache:'no-store'}).then(async r=>{const p=await r.json();if(!r.ok)throw new Error(p.error||'Не удалось загрузить отзывы');if(active)setData(p)}).catch(e=>active&&setError(e.message));return()=>{active=false}},[storeId])
 const m=data?.metrics; const freshness=data?.freshness?.created_at?new Date(data.freshness.created_at).toLocaleString('ru-RU'):'ожидается первая синхронизация'
 return <main className="sectionPage"><header className="sectionTop"><Link href="/" className="ghostBtn"><ArrowLeft size={16}/> На главную</Link><Link href="/account" className="ghostBtn">Аккаунт</Link></header>
  <section className="workHero"><span className="eyebrow">РЕПУТАЦИЯ · WILDBERRIES</span><h1>Отзывы покупателей</h1><p>Безопасный read-only обзор отзывов выбранного магазина. TROVENDI не публикует ответы автоматически и не сохраняет имя покупателя.</p><div className="sectionStoreContext"><Building2 size={16}/><span>{loading?'Загружаем магазин…':storeId?`Активный магазин: ${storeName}`:'Активный магазин не выбран'}</span></div><small>Актуальность: {freshness}{data?.sync_required?' · обновление поставлено в очередь':''}</small></section>
  {(storeError||error)&&<div className="sectionNotice">{storeError||error}</div>}
  <section className="sectionCards"><article className="sectionCard"><MessageSquareText/><h3>{m?.loaded??'—'}</h3><p>Отзывов загружено в защищённый снимок</p></article><article className="sectionCard"><Star/><h3>{m?.average_rating??'—'}</h3><p>Средняя оценка в загруженной выборке</p></article><article className="sectionCard"><ShieldCheck/><h3>{m?.unanswered??'—'}</h3><p>Без ответа по данным WB</p></article></section>
  <section className="sectionCards">{(data?.reviews||[]).map(item=><article className="sectionCard" key={item.feedback_id}><span className="eyebrow">{item.rating} / 5 · nmID {item.nm_id}</span><h3>{item.product_name||item.vendor_code||'Товар WB'}</h3><p>{item.text||item.cons||item.pros||'Покупатель оставил оценку без текста.'}</p><small>{item.answered?'Ответ продавца уже есть':'Ожидает ответа · публикация из TROVENDI отключена'}</small></article>)}</section>
 </main>
}
