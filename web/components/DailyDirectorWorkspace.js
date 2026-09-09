'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Bot, CheckCircle2, CircleAlert, Clock3, PauseCircle, PlayCircle, RefreshCw, ShieldCheck, XCircle } from 'lucide-react'
import { useActiveStore } from '../lib/useActiveStore'

const sourceNames={catalog:'Каталог',stocks:'Остатки',sales_velocity_7d:'Заказы 7 дней',finance_realization_sync:'Финансы 30 дней',advertising_sync:'Реклама 30 дней'}
const stateNames={live:'актуально',stale:'устарело',missing:'нет данных',incomplete:'загрузка не завершена'}
const statusNames={proposed:'Ждёт решения',approved:'Подтверждено · не исполнено',rejected:'Отклонено',executing:'Обновляем источник',measured:'Результат измерен'}
const rubles=kopecks=>kopecks===null||kopecks===undefined?'Не рассчитано':`${(Math.abs(kopecks)/100).toLocaleString('ru-RU',{minimumFractionDigits:2,maximumFractionDigits:2})} ₽`
const measurementText=result=>{
  const value=result?.measurement
  if(!value)return ''
  if(value.outcome==='no_longer_detected')return 'Проблема больше не определяется; числовой эффект не придуман.'
  const labels={improved:'Улучшение',unchanged:'Без изменений',worse:'Ухудшение',changed:'Состояние изменилось'}
  return `${labels[value.outcome]||value.outcome}: ${value.baseline} → ${value.current}${value.delta===null?'':` · Δ ${value.delta}`}`
}

export default function DailyDirectorWorkspace(){
  const {storeId,storeName,loading:storeLoading,error:storeError}=useActiveStore()
  const [data,setData]=useState(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [decisionBusy,setDecisionBusy]=useState('')
  const [controlBusy,setControlBusy]=useState(false)
  const [stopReason,setStopReason]=useState('Остановлено владельцем из интерфейса TROVENDI')
  const [resumeConfirmation,setResumeConfirmation]=useState('')

  const load=useCallback(async()=>{
    if(!storeId){setData(null);return}
    setBusy(true);setError('')
    try{
      const response=await fetch(`/api/director?store_id=${encodeURIComponent(storeId)}`,{cache:'no-store'})
      const payload=await response.json()
      if(!response.ok)throw new Error(payload.error||'Не удалось загрузить план')
      setData(payload)
    }catch(e){setData(null);setError(e.message)}finally{setBusy(false)}
  },[storeId])

  useEffect(()=>{load()},[load])

  async function decide(item,decision){
    setDecisionBusy(item.id);setNotice('')
    try{
      const response=await fetch(`/api/director/actions/${encodeURIComponent(item.id)}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:storeId,decision,note:''})})
      const payload=await response.json()
      if(!response.ok)throw new Error(payload.error||'Не удалось записать решение')
      setNotice(payload.message);await load()
    }catch(e){setNotice(e.message)}finally{setDecisionBusy('')}
  }

  async function changeControl(stopped){
    setControlBusy(true);setNotice('')
    try{
      const response=await fetch('/api/director/control',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:storeId,stopped,reason:stopReason,confirmation:stopped?'':resumeConfirmation})})
      const payload=await response.json()
      if(!response.ok)throw new Error(payload.error||'Не удалось изменить режим')
      setNotice(payload.message);setResumeConfirmation('');await load()
    }catch(e){setNotice(e.message)}finally{setControlBusy(false)}
  }

  async function runAction(item,operation){
    setDecisionBusy(item.id);setNotice('')
    try{
      const response=await fetch(`/api/director/actions/${encodeURIComponent(item.id)}/${operation}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:storeId})})
      const payload=await response.json()
      if(!response.ok)throw new Error(payload.error||'Действие не выполнено')
      setNotice(payload.message);await load()
    }catch(e){setNotice(e.message)}finally{setDecisionBusy('')}
  }

  const questions=useMemo(()=>data?[
    ['Что случилось',data.summary.what_happened],
    ['Где теряем деньги',data.summary.money_losses.observed_kopecks===null?'Подтверждённый убыток не найден или данных недостаточно.':`${rubles(data.summary.money_losses.observed_kopecks)} обнаруженного убытка`],
    ['Что сделать сегодня',`${data.summary.today_actions} задач в порядке приоритета`],
    ['Что безопасно',`${data.summary.safe_actions} диагностических действий без изменения WB`],
    ['Что подтвердить',`${data.summary.approval_required} действий ожидают решения владельца`],
    ['Что изменилось',data.summary.measured_changes],
  ]:[],[data])

  return <main className="workPage directorPage">
    <div className="workHead"><Link href="/" className="ghostBtn"><ArrowLeft size={16}/> На главную</Link><button className="ghostBtn" onClick={load} disabled={busy||!storeId}><RefreshCw size={16}/>{busy?' Проверяем…':' Обновить факты'}</button></div>
    <section className="workHero directorHero"><div><span className="eyebrow">DAILY AI DIRECTOR · БЕЗ ВЫДУМАННЫХ ДАННЫХ</span><h1>План управления магазином</h1><p>Единая очередь по прибыли, остаткам, карточкам и состоянию источников. Решения сохраняются в журнале, но не исполняются в Wildberries автоматически.</p></div><div className={`directorMode ${data?.mode||'waiting'}`}><Bot size={20}/><span>{data?.mode==='live'?'Все источники готовы':data?.mode==='partial'?'Часть источников не готова':'Ожидаем данные'}</span></div></section>
    {(storeError||error||notice)&&<div className="sectionNotice"><CircleAlert size={17}/>{storeError||error||notice}</div>}
    <section className="workPanel directorContext"><div><span>Активный магазин</span><strong>{storeLoading?'Загружаем…':storeName||'Не выбран'}</strong></div><div><span>Режим</span><strong>{data?.control?.stopped?'STOP · исполнения запрещены':'Предложения и подтверждения'}</strong></div><div><span>Стоимость анализа</span><strong>0 ₽ · Rules Free</strong></div><div><span>Последний расчёт</span><strong>{data?.generated_at?new Date(data.generated_at).toLocaleString('ru-RU'):'—'}</strong></div></section>
    {data&&<>
      <section className={`workPanel emergencyControl ${data.control.stopped?'stopped':''}`}><div>{data.control.stopped?<PauseCircle size={24}/>:<PlayCircle size={24}/>}<div><span className="eyebrow">ГЛОБАЛЬНЫЙ КОНТРОЛЬ</span><h2>{data.control.stopped?'STOP включён':'Автоматические исполнения разрешены политикой'}</h2><p>{data.control.stopped?(data.control.reason||'Причина не указана'):'Сейчас исполнителей ещё нет. Этот переключатель заранее блокирует все будущие автоматические записи.'}</p></div></div><div className="controlFields"><input value={stopReason} maxLength={1000} onChange={event=>setStopReason(event.target.value)} aria-label="Причина изменения режима"/>{data.control.stopped&&<input value={resumeConfirmation} onChange={event=>setResumeConfirmation(event.target.value)} placeholder="Введите ВОЗОБНОВИТЬ TROVENDI" aria-label="Подтверждение возобновления"/>}<button className={data.control.stopped?'resumeBtn':'stopBtn'} onClick={()=>changeControl(!data.control.stopped)} disabled={controlBusy||!storeId||(data.control.stopped&&resumeConfirmation.trim().toUpperCase()!=='ВОЗОБНОВИТЬ TROVENDI')}>{data.control.stopped?'Возобновить':'Включить STOP'}</button></div></section>
      <section className="directorQuestions">{questions.map(([title,value],index)=><article className="workPanel" key={title}><span>0{index+1}</span><h2>{title}</h2><p>{value}</p></article>)}</section>
      <section className="workPanel directorSources"><div className="directorSectionHead"><div><span className="eyebrow">ДОКАЗАТЕЛЬНАЯ БАЗА</span><h2>Источники решения</h2></div><small>Актуальность: 15 минут</small></div><div className="directorSourceGrid">{data.sources.map(source=><div className={source.state} key={source.name}>{source.state==='live'?<CheckCircle2 size={17}/>:<Clock3 size={17}/>}<span>{sourceNames[source.name]||source.name}</span><b>{stateNames[source.state]}</b></div>)}</div></section>
      <section className="workPanel directorQueue"><div className="directorSectionHead"><div><span className="eyebrow">ЦЕНТР ПОДТВЕРЖДЕНИЙ</span><h2>Очередь по влиянию и риску</h2></div><small>{data.ranking.formula}</small></div>{data.actions.length?<div className="directorActions">{data.actions.map((item,index)=><article key={item.id} className={`directorAction ${item.urgency} ${item.status}`}><div className="directorRank"><b>{index+1}</b><span>{item.priority_score}</span></div><div className="directorActionBody"><div className="directorActionTitle"><h3>{item.title}</h3><div><span>{item.provider.label}</span>{(item.requires_approval||item.status!=='proposed')&&<span className={`approvalBadge ${item.status}`}><ShieldCheck size={13}/> {statusNames[item.status]||item.status}</span>}</div></div><p>{item.reason}</p><div className="directorEvidence">Факт: {item.evidence}</div><small>{item.priority_reason} · Денежный эффект: {rubles(item.observed_effect_kopecks)}</small><div className="directorActionButtons"><Link href={item.href} className="ghostBtn">Открыть источник</Link>{item.can_execute&&item.status==='proposed'&&<button className="safeRunBtn" onClick={()=>runAction(item,'execute')} disabled={decisionBusy===item.id}><RefreshCw size={15}/> Обновить источник</button>}{item.requires_approval&&item.status==='proposed'&&<><button className="rejectBtn" onClick={()=>decide(item,'reject')} disabled={decisionBusy===item.id}><XCircle size={15}/> Отклонить</button><button className="approveBtn" onClick={()=>decide(item,'approve')} disabled={decisionBusy===item.id}><CheckCircle2 size={15}/> Принять в работу</button></>}{['approved','executing','measured'].includes(item.status)&&item.measurement&&<button className="measureBtn" onClick={()=>runAction(item,'measure')} disabled={decisionBusy===item.id}><Clock3 size={15}/> Измерить результат</button>}</div>{item.status==='approved'&&<div className="decisionResult">Решение зафиксировано. Внешнее исполнение не запускалось.</div>}{item.status==='executing'&&<div className="decisionResult">Запущено только чтение WB. Записи в маркетплейс нет.</div>}{item.result?.measurement&&<div className={`measurementResult ${item.result.measurement.outcome}`}>{measurementText(item.result)}</div>}</div></article>)}</div>:<div className="directorEmpty"><CheckCircle2 size={28}/><b>Подтверждённых задач сейчас нет</b><span>Director не создаёт рекомендации без фактов.</span></div>}</section>
      {(data.tracked_actions||[]).length>0&&<section className="workPanel directorQueue trackedQueue"><div className="directorSectionHead"><div><span className="eyebrow">КОНТРОЛЬ РЕЗУЛЬТАТА</span><h2>Ранее принятые действия</h2></div><small>Остаются доступны после обновления источников</small></div><div className="trackedActions">{data.tracked_actions.map(item=><article key={item.id}><div><b>{item.title}</b><span>{statusNames[item.status]||item.status}</span></div><p>{item.result?.measurement?measurementText(item.result):'Результат ещё не измерен по свежим данным.'}</p><button className="measureBtn" onClick={()=>runAction(item,'measure')} disabled={decisionBusy===item.id}><Clock3 size={15}/> Измерить снова</button></article>)}</div></section>}
      <section className="workPanel directorAudit"><div className="directorSectionHead"><div><span className="eyebrow">АУДИТ</span><h2>Последние решения и переключения</h2></div><small>Неизменяемые события магазина</small></div>{data.audit.length?<div>{data.audit.map(event=><article key={event.id}><span>{new Date(event.created_at).toLocaleString('ru-RU')}</span><b>{event.event_type}</b><small>{event.payload?.reason||event.payload?.note||event.entity_id}</small></article>)}</div>:<p>Событий пока нет. Первое подтверждение или STOP появится здесь.</p>}</section>
      <div className="directorGuard"><ShieldCheck size={19}/><div><b>Контур безопасности включён</b><span>{data.automation.note} Подтверждение сохраняется отдельно от исполнения; перед будущей записью источник будет проверен повторно.</span></div></div>
    </>}
  </main>
}
