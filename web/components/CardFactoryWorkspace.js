'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Building2, LockKeyhole, Sparkles } from 'lucide-react'
import { useActiveStore } from '../lib/useActiveStore'

export default function CardFactoryWorkspace(){
 const params=useSearchParams(); const nmId=Number(params.get('nm_id')||0)
 const {storeId,storeName,loading:storeLoading,error:storeError}=useActiveStore()
 const [source,setSource]=useState(null); const [generated,setGenerated]=useState(null); const [tab,setTab]=useState('WB'); const [notice,setNotice]=useState(''); const [busy,setBusy]=useState(false)
 useEffect(()=>{if(!storeId||!nmId){setSource(null);return}let alive=true;setBusy(true);setNotice('Загружаем подтверждённые факты из каталога WB…');fetch(`/api/card-factory/card/${nmId}?store_id=${encodeURIComponent(storeId)}`,{cache:'no-store'}).then(async r=>{const p=await r.json();if(!r.ok)throw new Error(p.error||'Не удалось загрузить карточку');if(!alive)return;setSource(p);setGenerated(null);setNotice('Карточка загружена. Набор фактов зафиксирован на сервере и недоступен для подмены.')}).catch(e=>alive&&setNotice(e.message)).finally(()=>alive&&setBusy(false));return()=>{alive=false}},[storeId,nmId])
 const facts=source?.fact_set?.facts||[]
 const ready=useMemo(()=>Boolean(storeId&&nmId&&facts.length&&!busy),[storeId,nmId,facts.length,busy])
 async function generate(){setBusy(true);setNotice('AI улучшает карточку и проверяет результат по исходным фактам…');try{const r=await fetch('/api/card-factory/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:storeId,nm_id:nmId})});const p=await r.json();if(!r.ok)throw new Error(p.error||'Не удалось создать AI-черновик');setGenerated(p.draft);setNotice('AI-черновик создан из зафиксированного набора фактов. Публикация в WB не выполнялась.')}catch(e){setNotice(e.message)}finally{setBusy(false)}}
 const title=tab==='WB'?generated?.wb_title:generated?.ozon_title
 return <main className="workPage"><div className="workHead"><Link href="/products" className="ghostBtn"><ArrowLeft size={16}/> К товарам</Link><Link href="/account" className="ghostBtn">Подключения</Link></div>
 <section className="workHero"><span className="eyebrow">AI КОНТЕНТ · РЕАЛЬНАЯ КАРТОЧКА</span><h1>AI Card Factory</h1><p>Backend загружает карточку по nmId из выбранного магазина, фиксирует подтверждённые WB-факты и только после этого запускает AI.</p><div className="sectionStoreContext"><Building2 size={16}/><span>{storeLoading?'Загружаем магазин…':storeId?`Активный магазин: ${storeName}`:'Активный магазин не выбран'}</span></div></section>
 {storeError&&<div className="sectionNotice">{storeError}</div>}
 {!nmId&&<div className="sectionNotice">Откройте товар в разделе «Товары» и нажмите «Улучшить через AI» — Card Factory нужен реальный nmId.</div>}
 <div className="factoryGrid"><section className="workPanel formPanel"><h2>Подтверждённые данные</h2>{source?<><div className="lockedCard"><div><span className="eyebrow">WB КАРТОЧКА</span><h3>{source.card.title||`Товар ${nmId}`}</h3><small>{source.card.vendor_code} · nmId {nmId}</small></div><LockKeyhole size={20}/></div><div className="factList">{facts.map(x=><div key={x.id}><span>{x.label}</span><strong>{x.value}</strong></div>)}</div><small className="factHash">Fact set: {source.fact_set.sha256.slice(0,16)}… · {facts.length} фактов</small></>:<div className="emptyFacts">{busy?'Загружаем карточку…':'Карточка не выбрана или ещё не синхронизирована.'}</div>}<button className="primaryBtn" disabled={!ready} onClick={generate}><Sparkles size={17}/>{busy?' Проверяем…':' Сгенерировать через AI'}</button></section>
 <section className="workPanel previewPanel"><div className="previewTabs"><button className={tab==='WB'?'active':''} onClick={()=>setTab('WB')}>Wildberries</button><button className={tab==='Ozon'?'active':''} onClick={()=>setTab('Ozon')}>Ozon</button></div>{generated?<div className="previewContent"><span className="eyebrow">ЗАГОЛОВОК</span><h2>{title}</h2><span className="eyebrow">ОПИСАНИЕ</span><p>{generated.description}</p><span className="eyebrow">SEO ФРАЗЫ</span><div className="chips">{generated.seo_phrases.map(x=><span key={x}>{x}</span>)}</div><span className="eyebrow">ВИЗУАЛЬНЫЙ ПЛАН</span><div className="visualPlan">{generated.visual_plan.map((x,i)=><div key={`${i}-${x}`}>{i+1}. {x}</div>)}</div><button className="primaryBtn" onClick={()=>setNotice('Черновик готов к ручной проверке. Автопубликация отключена; отправка в WB потребует отдельного явного подтверждения.')}>Подготовить к проверке</button></div>:<div className="emptyPreview">Здесь появится AI-черновик после серверной проверки по фактам карточки.</div>}</section></div>
 {notice&&<div className="sectionNotice">{notice}</div>}</main>
}
