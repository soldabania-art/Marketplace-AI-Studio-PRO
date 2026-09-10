'use client'

import Link from 'next/link'
import { useCallback,useEffect,useState } from 'react'
import { ArrowLeft,Boxes,Check,ChevronRight,Factory,RefreshCw,ShieldCheck,ShoppingBag,Store,Tags } from 'lucide-react'
import { useActiveStore } from '../lib/useActiveStore'

const models=[
 {key:'reseller',icon:ShoppingBag,title:'Реселлер / импортёр',text:'Закупаю готовые товары и перепродаю.',answers:{buys_finished_goods:true,makes_products:false,controls_rrp:false}},
 {key:'manufacturer',icon:Factory,title:'Собственное производство',text:'Произвожу или собираю товары сам.',answers:{buys_finished_goods:false,makes_products:true,controls_rrp:false}},
 {key:'distributor',icon:Tags,title:'Официальный дистрибьютор',text:'Представляю бренды и контролирую РРЦ.',answers:{buys_finished_goods:true,makes_products:false,controls_rrp:true}},
 {key:'mixed',icon:Boxes,title:'Смешанная модель',text:'Совмещаю производство, закупки или дистрибуцию.',answers:{buys_finished_goods:true,makes_products:true,controls_rrp:false}},
]

export default function OnboardingWorkspace(){
 const {storeId,storeName,loading:storeLoading,error:storeError}=useActiveStore();const [data,setData]=useState(null);const [selected,setSelected]=useState('');const [loading,setLoading]=useState(false);const [saving,setSaving]=useState(false);const [error,setError]=useState('');const [notice,setNotice]=useState('')
 const load=useCallback(async()=>{if(!storeId){setData(null);return}setLoading(true);setError('');try{const response=await fetch(`/api/onboarding?store_id=${encodeURIComponent(storeId)}`,{cache:'no-store'});const payload=await response.json();if(!response.ok)throw new Error(payload.error||'Не удалось проверить магазин');setData(payload);setSelected(payload.profile?.operating_model||'')}catch(e){setError(e.message)}finally{setLoading(false)}},[storeId])
 useEffect(()=>{load()},[load])
 async function confirm(){const option=models.find(item=>item.key===selected);if(!option||!storeId)return;setSaving(true);setError('');setNotice('');try{const response=await fetch('/api/onboarding',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:storeId,operating_model:option.key,...option.answers})});const payload=await response.json();if(!response.ok)throw new Error(payload.error||'Не удалось подтвердить профиль');setData(payload);setNotice('Профиль подтверждён. Финансовые параметры по-прежнему потребуют отдельных проверенных данных продавца.')}catch(e){setError(e.message)}finally{setSaving(false)}}
 const evidence=data?.evidence||{}
 return <main className="onboardingPage"><header className="onboardingTop"><Link href="/" className="ghostBtn"><ArrowLeft size={16}/> В панель</Link><span>AI-Мастер настройки</span><Link href="/start" className="ghostBtn">Новый товар</Link></header><section className="onboardingBody">
  <div className="onboardingHero"><div><span className="eyebrow">TROVENDI · ПЕРВЫЙ ЗАПУСК</span><h1>{storeName?`Настраиваем «${storeName}»`:'Настройте первый магазин'}</h1><p>Мастер проверяет подключение, импортирует факты и показывает три первых действия без выдуманных показателей.</p></div><div className="setupScore"><strong>{data?.completion_percent??0}%</strong><span>{data?.status==='ready'?'готово к работе':'настройки завершено'}</span></div></div>
  {(error||storeError)&&<div className="setupNotice error">{error||storeError}</div>}{notice&&<div className="setupNotice">{notice}</div>}
  <section className="setupSteps">{data?.steps?.map((step,index)=><article className={step.complete?'complete':''} key={step.key}><span>{step.complete?<Check size={16}/>:index+1}</span><b>{step.label}</b></article>)||<p>{storeLoading||loading?'Проверяем магазин…':'Выберите магазин в аккаунте.'}</p>}<button onClick={load} disabled={loading||!storeId}><RefreshCw size={15}/>{loading?' Проверяем…':' Проверить снова'}</button></section>
  <section className="evidencePanel"><div><span>Факты после сканирования</span><h2>Что TROVENDI уже знает</h2></div><div className="evidenceGrid"><article><strong>{evidence.catalog_cards??'—'}</strong><span>карточек WB</span></article><article><strong>{evidence.brands??'—'}</strong><span>брендов</span></article><article><strong>{evidence.stock_units??'—'}</strong><span>единиц остатка</span></article><article><strong>{evidence.products_with_sales??'—'}</strong><span>товаров с продажами</span></article></div><small><ShieldCheck size={14}/> Только данные подключённого магазина. Чужие магазины и общая база не используются.</small></section>
  <section className="profilePanel" id="business-profile"><div className="profileIntro"><span>Требуется подтверждение владельца</span><h2>Как устроен ваш бизнес?</h2><p>{data?.profile_decision?.reason||'Выберите основной рабочий сценарий.'}</p></div><div className="modelGrid">{models.map(item=>{const Icon=item.icon;return <button className={selected===item.key?'selected':''} key={item.key} onClick={()=>setSelected(item.key)}><Icon size={22}/><strong>{item.title}</strong><span>{item.text}</span></button>})}</div><button className="confirmProfile" disabled={!selected||saving||!storeId} onClick={confirm}>{saving?'Сохраняем…':data?.profile?'Обновить подтверждённый профиль':'Подтвердить модель бизнеса'}</button></section>
  <section className="firstActions"><div><span>Первые действия</span><h2>{data?.status==='ready'?'Ваш стартовый план готов':'Что сделать дальше'}</h2></div>{data?.actions?.map((item,index)=><Link href={item.href} key={item.key}><b>0{index+1}</b><div><strong>{item.title}</strong><span>{item.reason}</span></div><em>{item.action}<ChevronRight size={15}/></em></Link>)}</section>
 </section></main>
}
