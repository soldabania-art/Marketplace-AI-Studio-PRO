'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { Activity, AlertTriangle, ArrowLeft, CheckCircle2, Clock3, Database, RefreshCw, ShieldAlert, WifiOff } from 'lucide-react'
import { useActiveStore } from '../lib/useActiveStore'

const statusMeta={
  healthy:{label:'Актуально',icon:CheckCircle2,tone:'healthy'},
  syncing:{label:'Синхронизация',icon:RefreshCw,tone:'syncing'},
  delayed:{label:'Задержка',icon:Clock3,tone:'delayed'},
  stale:{label:'Устарело',icon:AlertTriangle,tone:'stale'},
  error:{label:'Ошибка',icon:ShieldAlert,tone:'error'},
  missing:{label:'Нет данных',icon:Database,tone:'missing'},
  disconnected:{label:'Не подключено',icon:WifiOff,tone:'missing'},
}

function age(seconds){
  if(seconds===null||seconds===undefined)return 'данные ещё не получены'
  if(seconds<60)return 'меньше минуты назад'
  if(seconds<3600)return `${Math.floor(seconds/60)} мин назад`
  if(seconds<86400)return `${Math.floor(seconds/3600)} ч назад`
  return `${Math.floor(seconds/86400)} дн назад`
}

export default function DataHealthWorkspace(){
  const {storeId,storeName,loading:storeLoading,error:storeError}=useActiveStore()
  const [data,setData]=useState(null);const [error,setError]=useState('');const [loading,setLoading]=useState(false);const [syncing,setSyncing]=useState(false);const [notice,setNotice]=useState('')
  const load=useCallback(async()=>{
    if(!storeId){setData(null);return}
    setLoading(true);setError('')
    try{const response=await fetch(`/api/data-health?store_id=${encodeURIComponent(storeId)}`,{cache:'no-store'});const payload=await response.json();if(!response.ok)throw new Error(payload.error||'Не удалось проверить источники');setData(payload)}catch(e){setError(e.message)}finally{setLoading(false)}
  },[storeId])
  useEffect(()=>{load()},[load])
  async function syncCore(){
    if(!storeId)return
    setSyncing(true);setError('');setNotice('')
    try{const response=await fetch(`/api/sync/wildberries?store_id=${encodeURIComponent(storeId)}`,{method:'POST'});const payload=await response.json();if(!response.ok)throw new Error(payload.error||'Не удалось запустить синхронизацию');setNotice(`Задача ${payload.job_id} поставлена в очередь. Обновите статус через несколько минут.`);await load()}catch(e){setError(e.message)}finally{setSyncing(false)}
  }
  const overall=statusMeta[data?.overall_status]||statusMeta.missing
  const OverallIcon=overall.icon
  return <main className="healthPage"><header className="healthTop"><Link href="/" className="ghostBtn"><ArrowLeft size={16}/> На главную</Link><Link href="/account" className="ghostBtn">Подключения</Link></header><section className="healthContent">
    <div className="healthHero"><div><span className="eyebrow">DATA HEALTH CENTER</span><h1>Здоровье источников данных</h1><p>AI Director принимает решения только на достаточно свежих данных выбранного магазина.</p></div><div className={`overall ${overall.tone}`}><OverallIcon size={22}/><div><span>Общий статус</span><strong>{overall.label}</strong></div></div></div>
    <section className="healthToolbar"><div><b>{storeLoading?'Загружаем магазин…':storeName||'Магазин не выбран'}</b><span>{data?.checked_at?`Проверено ${new Date(data.checked_at).toLocaleString('ru-RU')}`:'Выберите магазин в аккаунте'}</span></div><button className="ghostBtn" onClick={load} disabled={loading||!storeId}><RefreshCw size={15}/>{loading?' Проверяем…':' Проверить'}</button><button className="primaryBtn" onClick={syncCore} disabled={syncing||!storeId||!data?.connected}><RefreshCw size={15}/>{syncing?' В очереди…':' Обновить WB'}</button></section>
    {(error||storeError)&&<div className="healthNotice error">{error||storeError}</div>}{notice&&<div className="healthNotice">{notice}</div>}
    {data&&<><section className={`decisionGate ${data.safe_for_ai_decisions?'safe':'blocked'}`}><Activity size={23}/><div><strong>{data.safe_for_ai_decisions?'Основные данные пригодны для решений AI':'AI-решения ограничены свежестью данных'}</strong><span>{data.safe_for_ai_decisions?'Каталог, остатки и продажи находятся внутри допустимых интервалов.':'Обновите проблемные источники; система не должна строить уверенные рекомендации на устаревших фактах.'}</span></div></section>
    <section className="sourceGrid">{data.sources.map(source=>{const meta=statusMeta[source.status]||statusMeta.missing;const Icon=meta.icon;return <article className={`sourceCard ${meta.tone}`} key={source.key}><div className="sourceHead"><div className="sourceIcon"><Icon size={19}/></div><span>{meta.label}</span></div><h2>{source.label}</h2><p>{age(source.age_seconds)}</p><div className="sourceMeta"><span>Допуск: {Math.floor(source.warn_after_seconds/60)} мин</span><span>{source.record_count===null||source.record_count===undefined?'Без счётчика':`${source.record_count} записей`}</span></div><div className="usedBy">Используют: {source.required_for.join(' · ')}</div>{source.issue&&<div className="sourceIssue">{source.issue}</div>}{source.job&&<small>Задача: {source.job.status} · попыток {source.job.attempts}</small>}</article>})}</section></>}
  </section></main>
}
