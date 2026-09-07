'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import { ArrowLeft, Building2, Search, WandSparkles } from 'lucide-react'
import { useActiveStore } from '../lib/useActiveStore'

const seed=[
{id:'WB-18374629',name:'Органайзер для хранения',market:'WB',status:'Нужно улучшить',score:62,stock:38,margin:18},
{id:'OZ-902114',name:'Набор контейнеров',market:'Ozon',status:'Хорошо',score:84,stock:71,margin:27},
{id:'WB-77120433',name:'Складной бокс',market:'WB',status:'Риск SEO',score:55,stock:12,margin:14},
{id:'OZ-554931',name:'Корзина для белья',market:'Ozon',status:'Хорошо',score:91,stock:44,margin:31},
]

export default function ProductsWorkspace(){
 const [q,setQ]=useState(''); const [selected,setSelected]=useState(seed[0]); const [notice,setNotice]=useState('')
 const {storeId,storeName,loading,error}=useActiveStore()
 const rows=useMemo(()=>seed.filter(x=>(x.name+x.id+x.market).toLowerCase().includes(q.toLowerCase())),[q])
 function explain(action){
   if(loading){setNotice('Загружаем активный магазин…');return}
   if(!storeId){setNotice('Сначала создайте или выберите магазин в аккаунте.');return}
   setNotice(`${action}: магазин «${storeName}» выбран. Каталог пока показывает демо-данные до подключения импорта товаров.`)
 }
 return <main className="workPage"><div className="workHead"><Link href="/" className="ghostBtn"><ArrowLeft size={16}/> На главную</Link><Link href="/card-factory" className="primaryBtn"><WandSparkles size={16}/> AI Card Factory</Link></div>
 <section className="workHero"><span className="eyebrow">КАТАЛОГ</span><h1>Товары</h1><p>Рабочий центр карточек WB и Ozon. Данные всегда будут изолированы по выбранному магазину.</p><div className="sectionStoreContext"><Building2 size={16}/><span>{loading?'Загружаем магазин…':storeId?`Активный магазин: ${storeName}`:'Активный магазин не выбран'}</span></div></section>
 {error&&<div className="sectionNotice">{error}</div>}
 <div className="workGrid"><section className="workPanel"><div className="toolbar"><div className="searchBox"><Search size={17}/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Поиск по товару или SKU"/></div><button onClick={()=>explain('Импорт')}>Импортировать</button></div>
 <div className="productTable"><div className="productRow head"><span>Товар</span><span>Маркет</span><span>AI score</span><span>Остаток</span><span>Маржа</span></div>{rows.map(x=><button className={`productRow ${selected.id===x.id?'selected':''}`} key={x.id} onClick={()=>setSelected(x)}><span><strong>{x.name}</strong><small>{x.id}</small></span><span>{x.market}</span><span>{x.score}/100</span><span>{x.stock}</span><span>{x.margin}%</span></button>)}</div></section>
 <aside className="workPanel detailPanel"><span className="eyebrow">КАРТОЧКА</span><h2>{selected.name}</h2><p>{selected.id} · {selected.market}</p><div className="detailMetric"><span>Качество карточки</span><strong>{selected.score}/100</strong></div><div className="detailMetric"><span>Статус</span><strong>{selected.status}</strong></div><div className="detailMetric"><span>Остаток</span><strong>{selected.stock} шт.</strong></div><div className="detailMetric"><span>Маржа</span><strong>{selected.margin}%</strong></div><Link href={`/card-factory?sku=${encodeURIComponent(selected.id)}&name=${encodeURIComponent(selected.name)}`} className="primaryBtn">Улучшить через AI</Link><button className="ghostBtn full" onClick={()=>explain(`Аудит ${selected.id}`)}>Проверить карточку</button></aside></div>
 {notice&&<div className="sectionNotice">{notice}</div>}
 </main>
}
