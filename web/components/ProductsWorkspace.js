'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Building2, RefreshCw, Search, WandSparkles } from 'lucide-react'
import { useActiveStore } from '../lib/useActiveStore'

export default function ProductsWorkspace(){
 const [q,setQ]=useState(''); const [selected,setSelected]=useState(null); const [notice,setNotice]=useState(''); const [data,setData]=useState({products:[],freshness:null,sync_required:false}); const [busy,setBusy]=useState(false)
 const {storeId,storeName,loading,error}=useActiveStore()
 useEffect(()=>{if(!storeId)return;let alive=true;setBusy(true);fetch(`/api/seller-data/products?store_id=${encodeURIComponent(storeId)}`,{cache:'no-store'}).then(async r=>{const p=await r.json();if(!r.ok)throw new Error(p.error||'Не удалось загрузить товары');if(!alive)return;setData(p);setSelected(p.products?.[0]||null)}).catch(e=>alive&&setNotice(e.message)).finally(()=>alive&&setBusy(false));return()=>{alive=false}},[storeId])
 const rows=useMemo(()=>data.products.filter(x=>`${x.title} ${x.sku} ${x.nm_id}`.toLowerCase().includes(q.toLowerCase())),[q,data.products])
 async function refresh(){if(!storeId)return;setBusy(true);setNotice('Ставим обновление данных WB в очередь…');try{const r=await fetch(`/api/sync/wildberries?store_id=${encodeURIComponent(storeId)}`,{method:'POST'});const p=await r.json();if(!r.ok)throw new Error(p.error||'Не удалось запустить синхронизацию');setNotice(`Синхронизация поставлена в очередь${p.job_id?` · job ${p.job_id}`:''}. Текущие данные остаются доступны.`)}catch(e){setNotice(e.message)}finally{setBusy(false)}}
 const freshness=data.freshness?.created_at?new Date(data.freshness.created_at).toLocaleString('ru-RU'):'данных ещё нет'
 return <main className="workPage"><div className="workHead"><Link href="/" className="ghostBtn"><ArrowLeft size={16}/> На главную</Link><Link href="/card-factory" className="primaryBtn"><WandSparkles size={16}/> AI Card Factory</Link></div>
 <section className="workHero"><span className="eyebrow">КАТАЛОГ · WILDBERRIES</span><h1>Товары</h1><p>Реальные товары, остатки и 7-дневная скорость заказов из сохранённых WB-снапшотов. Полный контент карточек подключается следующим этапом.</p><div className="sectionStoreContext"><Building2 size={16}/><span>{loading?'Загружаем магазин…':storeId?`Активный магазин: ${storeName}`:'Активный магазин не выбран'}</span></div><small>Актуальность: {freshness}{data.sync_required?' · обновление требуется':''}</small></section>
 {error&&<div className="sectionNotice">{error}</div>}
 <div className="workGrid"><section className="workPanel"><div className="toolbar"><div className="searchBox"><Search size={17}/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Поиск по SKU, nmId или названию"/></div><button onClick={refresh} disabled={busy||!storeId}><RefreshCw size={15}/>{busy?' Обновляем…':' Обновить WB'}</button></div>
 {!busy&&!rows.length&&<div className="sectionNotice">{storeId?'Товаров в последнем снапшоте пока нет. Запустите синхронизацию WB.':'Сначала выберите магазин.'}</div>}
 <div className="productTable"><div className="productRow head"><span>Товар</span><span>Маркет</span><span>Заказы 7д</span><span>Остаток</span><span>Складов</span></div>{rows.map(x=><button className={`productRow ${selected?.nm_id===x.nm_id?'selected':''}`} key={x.nm_id} onClick={()=>setSelected(x)}><span><strong>{x.title}</strong><small>{x.sku} · nmId {x.nm_id}</small></span><span>WB</span><span>{x.orders_7d}</span><span>{x.stock}</span><span>{x.warehouse_count}</span></button>)}</div></section>
 <aside className="workPanel detailPanel"><span className="eyebrow">ТОВАР WB</span>{selected?<><h2>{selected.title}</h2><p>{selected.sku} · nmId {selected.nm_id}</p><div className="detailMetric"><span>Заказы за 7 дней</span><strong>{selected.orders_7d}</strong></div><div className="detailMetric"><span>Среднее заказов/день</span><strong>{selected.avg_daily_orders}</strong></div><div className="detailMetric"><span>Остаток</span><strong>{selected.stock} шт.</strong></div><div className="detailMetric"><span>Складов с остатком</span><strong>{selected.warehouse_count}</strong></div><Link href={`/card-factory?sku=${encodeURIComponent(selected.sku)}&name=${encodeURIComponent(selected.title)}`} className="primaryBtn">Улучшить через AI</Link><Link className="ghostBtn full" href="/fbo-slots">Открыть FBO</Link></>:<p>Выберите товар после синхронизации.</p>}</aside></div>
 {notice&&<div className="sectionNotice">{notice}</div>}
 </main>
}
