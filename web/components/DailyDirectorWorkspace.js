'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Bot, CheckCircle2, CircleAlert, Clock3, RefreshCw, ShieldCheck } from 'lucide-react'
import { useActiveStore } from '../lib/useActiveStore'

const sourceNames={catalog:'Каталог',stocks:'Остатки',sales_velocity_7d:'Заказы 7 дней',finance_realization_sync:'Финансы 30 дней',advertising_sync:'Реклама 30 дней'}
const stateNames={live:'актуально',stale:'устарело',missing:'нет данных',incomplete:'загрузка не завершена'}
const rubles=kopecks=>kopecks===null||kopecks===undefined?'Не рассчитано':`${(Math.abs(kopecks)/100).toLocaleString('ru-RU',{minimumFractionDigits:2,maximumFractionDigits:2})} ₽`

export default function DailyDirectorWorkspace(){
  const {storeId,storeName,loading:storeLoading,error:storeError}=useActiveStore()
  const [data,setData]=useState(null); const [busy,setBusy]=useState(false); const [error,setError]=useState('')
  const load=useCallback(async()=>{
    if(!storeId){setData(null);return}
    setBusy(true);setError('')
    try{
      const response=await fetch(`/api/director?store_id=${encodeURIComponent(storeId)}`,{cache:'no-store'})
      const payload=await response.json(); if(!response.ok)throw new Error(payload.error||'Не удалось загрузить план')
      setData(payload)
    }catch(e){setData(null);setError(e.message)}finally{setBusy(false)}
  },[storeId])
  useEffect(()=>{load()},[load])
  const questions=useMemo(()=>data?[
    ['Что случилось',data.summary.what_happened],
    ['Где теряем деньги',data.summary.money_losses.observed_kopecks===null?'Подтверждённый убыток не найден или данных недостаточно.':`${rubles(data.summary.money_losses.observed_kopecks)} обнаруженного убытка`],
    ['Что сделать сегодня',`${data.summary.today_actions} задач в порядке приоритета`],
    ['Что безопасно',`${data.summary.safe_actions} диагностических действий без изменения WB`],
    ['Что подтвердить',`${data.summary.approval_required} действий требуют решения владельца`],
    ['Что изменилось',data.summary.measured_changes],
  ]:[],[data])
  return <main className="workPage directorPage">
    <div className="workHead"><Link href="/" className="ghostBtn"><ArrowLeft size={16}/> На главную</Link><button className="ghostBtn" onClick={load} disabled={busy||!storeId}><RefreshCw size={16}/>{busy?' Проверяем…':' Обновить факты'}</button></div>
    <section className="workHero directorHero"><div><span className="eyebrow">DAILY AI DIRECTOR · БЕЗ ВЫДУМАННЫХ ДАННЫХ</span><h1>План управления магазином</h1><p>Единая очередь по прибыли, остаткам, карточкам и состоянию источников. Первая версия работает на прозрачных правилах за 0 ₽ и ничего не меняет в Wildberries без подтверждения.</p></div><div className={`directorMode ${data?.mode||'waiting'}`}><Bot size={20}/><span>{data?.mode==='live'?'Все источники готовы':data?.mode==='partial'?'Часть источников не готова':'Ожидаем данные'}</span></div></section>
    {(storeError||error)&&<div className="sectionNotice"><CircleAlert size={17}/>{storeError||error}</div>}
    <section className="workPanel directorContext"><div><span>Активный магазин</span><strong>{storeLoading?'Загружаем…':storeName||'Не выбран'}</strong></div><div><span>Режим</span><strong>Только предложения</strong></div><div><span>Стоимость анализа</span><strong>0 ₽ · Rules Free</strong></div><div><span>Последний расчёт</span><strong>{data?.generated_at?new Date(data.generated_at).toLocaleString('ru-RU'):'—'}</strong></div></section>
    {data&&<>
      <section className="directorQuestions">{questions.map(([title,value],index)=><article className="workPanel" key={title}><span>0{index+1}</span><h2>{title}</h2><p>{value}</p></article>)}</section>
      <section className="workPanel directorSources"><div className="directorSectionHead"><div><span className="eyebrow">ДОКАЗАТЕЛЬНАЯ БАЗА</span><h2>Источники решения</h2></div><small>Актуальность: 15 минут</small></div><div className="directorSourceGrid">{data.sources.map(source=><div className={source.state} key={source.name}>{source.state==='live'?<CheckCircle2 size={17}/>:<Clock3 size={17}/>}<span>{sourceNames[source.name]||source.name}</span><b>{stateNames[source.state]}</b></div>)}</div></section>
      <section className="workPanel directorQueue"><div className="directorSectionHead"><div><span className="eyebrow">СЕГОДНЯ · ДО 10 ДЕЙСТВИЙ</span><h2>Очередь по влиянию и риску</h2></div><small>{data.ranking.formula}</small></div>{data.actions.length?<div className="directorActions">{data.actions.map((item,index)=><article key={item.id} className={`directorAction ${item.urgency}`}><div className="directorRank"><b>{index+1}</b><span>{item.priority_score}</span></div><div className="directorActionBody"><div className="directorActionTitle"><h3>{item.title}</h3><div><span>{item.provider.label}</span>{item.requires_approval&&<span className="approvalBadge"><ShieldCheck size={13}/> Нужно подтверждение</span>}</div></div><p>{item.reason}</p><div className="directorEvidence">Факт: {item.evidence}</div><small>{item.priority_reason} · Денежный эффект: {rubles(item.observed_effect_kopecks)}</small><Link href={item.href} className="ghostBtn">Открыть источник</Link></div></article>)}</div>:<div className="directorEmpty"><CheckCircle2 size={28}/><b>Подтверждённых задач сейчас нет</b><span>Director не создаёт рекомендации без фактов.</span></div>}</section>
      <div className="directorGuard"><ShieldCheck size={19}/><div><b>Контур безопасности включён</b><span>{data.automation.note} Исполнение и сравнение результата появятся отдельным этапом с журналом и откатом.</span></div></div>
    </>}
  </main>
}
