'use client'

import Link from 'next/link'
import {useCallback,useEffect,useLayoutEffect,useMemo,useRef,useState} from 'react'
import {ArrowLeft,ArrowRight,CheckCircle2,CircleAlert,Clock3,Database,PauseCircle,PlayCircle,RefreshCw,ShieldCheck,XCircle} from 'lucide-react'
import {createDirectorMutationCoordinator,createDirectorRequestCoordinator,directorActionAvailability,directorViewFlags} from '../lib/directorView.mjs'
import {useActiveStore} from '../lib/useActiveStore'

const sourceNames={catalog:'Каталог',stocks:'Остатки',sales_velocity_7d:'Заказы 7 дней',finance_realization_sync:'Финансы 30 дней',advertising_sync:'Реклама 30 дней',feedbacks:'Отзывы'}
const stateNames={live:'актуально',stale:'устарело',missing:'нет данных',incomplete:'загрузка не завершена',error:'ошибка источника'}
const statusNames={proposed:'Ждёт решения',approved:'Подтверждено · не исполнено',rejected:'Отклонено',executing:'Обновляем источник',measured:'Результат измерен'}
const roleNames={owner:'Владелец',admin:'Администратор',member:'Участник'}
const rubles=kopecks=>kopecks===null||kopecks===undefined?'Не рассчитано':`${(Math.abs(kopecks)/100).toLocaleString('ru-RU',{minimumFractionDigits:2,maximumFractionDigits:2})} ₽`
const measurementText=result=>{
  const value=result?.measurement
  if(!value)return ''
  if(value.outcome==='no_longer_detected')return 'Проблема больше не определяется; числовой эффект не придуман.'
  const labels={improved:'Улучшение',unchanged:'Без изменений',worse:'Ухудшение',changed:'Состояние изменилось'}
  return `${labels[value.outcome]||value.outcome}: ${value.baseline} → ${value.current}${value.delta===null?'':` · Δ ${value.delta}`}`
}

export default function DailyDirectorWorkspace(){
  const {storeId,storeName,loading:storeLoading,error:storeError,role,canManageStore}=useActiveStore()
  const [data,setData]=useState(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [decisionBusy,setDecisionBusy]=useState('')
  const [controlBusy,setControlBusy]=useState(false)
  const [stopReason,setStopReason]=useState('Остановлено владельцем из интерфейса TROVENDI')
  const [resumeConfirmation,setResumeConfirmation]=useState('')
  const currentStoreRef=useRef(storeId)
  currentStoreRef.current=storeId
  const requestCoordinator=useMemo(()=>createDirectorRequestCoordinator(fetch),[])
  const mutationCoordinator=useMemo(()=>createDirectorMutationCoordinator(),[])

  useLayoutEffect(()=>{
    mutationCoordinator.enterContext(storeId)
  },[mutationCoordinator,storeId])

  const load=useCallback(async targetStoreId=>{
    if(!targetStoreId){setData(null);setBusy(false);return}
    setBusy(true);setError('');setData(null)
    const result=await requestCoordinator.load(targetStoreId)
    if(currentStoreRef.current!==targetStoreId||result.kind==='superseded')return
    if(result.kind==='error')setError(result.error)
    else setData(result.data)
    setBusy(false)
  },[requestCoordinator])

  useEffect(()=>{
    setData(null);setError('');setNotice('');setDecisionBusy('');setControlBusy(false);setResumeConfirmation('')
    if(storeId)load(storeId)
    else setBusy(false)
    return ()=>requestCoordinator.cancel()
  },[load,requestCoordinator,storeId])

  async function mutate(url,options,fallback,token){
    try{
      const response=await fetch(url,options)
      const payload=await response.json()
      if(!response.ok)throw new Error(payload.error||fallback)
      if(!mutationCoordinator.accepts(token))return
      setNotice(payload.message);await load(token.storeId)
    }catch(mutationError){
      if(mutationCoordinator.accepts(token))setNotice(mutationError.message)
    }
  }

  async function decide(item,decision){
    const targetStoreId=storeId
    const token=mutationCoordinator.start('action')
    setDecisionBusy(item.id);setNotice('')
    await mutate(`/api/director/actions/${encodeURIComponent(item.id)}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:targetStoreId,decision,note:''})},'Не удалось записать решение',token)
    if(mutationCoordinator.finish(token))setDecisionBusy('')
  }

  async function changeControl(stopped){
    const targetStoreId=storeId
    const token=mutationCoordinator.start('control')
    setControlBusy(true);setNotice('')
    await mutate('/api/director/control',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:targetStoreId,stopped,reason:stopReason,confirmation:stopped?'':resumeConfirmation})},'Не удалось изменить режим',token)
    const clearConfirmation=mutationCoordinator.accepts(token)
    if(mutationCoordinator.finish(token))setControlBusy(false)
    if(clearConfirmation)setResumeConfirmation('')
  }

  async function runAction(item,operation){
    const targetStoreId=storeId
    const token=mutationCoordinator.start('action')
    setDecisionBusy(item.id);setNotice('')
    await mutate(`/api/director/actions/${encodeURIComponent(item.id)}/${operation}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:targetStoreId})},'Действие не выполнено',token)
    if(mutationCoordinator.finish(token))setDecisionBusy('')
  }

  const visibleData=data?.store_id===storeId?data:null
  const flags=directorViewFlags(visibleData,canManageStore)
  const degraded=flags.missing||flags.stale||flags.incomplete||flags.sourceError
  const questions=useMemo(()=>visibleData?[
    ['Что случилось',visibleData.summary.what_happened],
    ['Где теряем деньги',visibleData.summary.money_losses.observed_kopecks===null?'Подтверждённый убыток не найден или данных недостаточно.':`${rubles(visibleData.summary.money_losses.observed_kopecks)} обнаруженного убытка`],
    ['Что сделать сегодня',`${visibleData.summary.today_actions} задач в порядке приоритета`],
    ['Что безопасно',`${visibleData.summary.safe_actions} диагностических действий без изменения WB`],
    ['Что подтвердить',`${visibleData.summary.approval_required} действий ожидают решения владельца`],
    ['Что изменилось',visibleData.summary.measured_changes],
  ]:[],[visibleData])

  return <main className="workPage directorPage directorB">
    <div className="workHead directorBHead"><Link href="/" className="directorBTextButton"><ArrowLeft/> На главную</Link><button className="directorBTextButton" onClick={()=>load(storeId)} disabled={busy||!storeId}><RefreshCw/>{busy?' Проверяем…':' Обновить факты'}</button></div>
    <section className="directorBHero"><div><span>DAILY AI DIRECTOR / ФАКТЫ МАГАЗИНА</span><h1>Решение начинается<br/>с <em>проверенных данных.</em></h1><p>Очередь строится существующими правилами для одного выбранного магазина. Director не добавляет факты, суммы или внешние действия от себя.</p></div><aside><small>АКТИВНЫЙ КОНТЕКСТ</small><strong>{storeLoading?'Загружаем магазин…':storeName||'Магазин не выбран'}</strong><span>{role?`Доступ: ${roleNames[role]||'Участник'}`:'Доступ ещё не определён'}</span><b data-mode={visibleData?.mode||'waiting'}>{visibleData?.mode==='live'?'Источники готовы':visibleData?.mode==='partial'?'Часть данных ограничена':'Ожидаем факты'}</b></aside></section>

    {(storeError||notice)&&<div className="directorBNotice"><CircleAlert/>{storeError||notice}</div>}
    {!storeLoading&&!storeId&&<section className="directorBState"><Database/><h2>Магазин не выбран</h2><p>Выберите доступный магазин в верхней панели. До выбора Director не загружает общую или чужую очередь.</p></section>}
    {busy&&!visibleData&&<section className="directorBState" aria-live="polite"><RefreshCw className="directorBSpin"/><h2>Проверяем факты выбранного магазина</h2><p>Предыдущий контекст очищен. На экране появится только ответ для «{storeName||'выбранного магазина'}».</p></section>}
    {error&&!busy&&<section className="directorBState directorBError" role="alert"><CircleAlert/><h2>Director не загрузил очередь</h2><p>{error}</p><button onClick={()=>load(storeId)}>Повторить запрос</button></section>}

    {visibleData&&<>
      <section className="directorBContext"><div><span>Магазин</span><strong>{visibleData.store_name||storeName}</strong></div><div><span>Режим доступа</span><strong>{flags.readOnly?'Только просмотр по роли':'Решения доступны'}</strong></div><div><span>Метод</span><strong>{visibleData.actions[0]?.provider?.label||'Нет задач для оценки'}</strong></div><div><span>Последний расчёт</span><strong>{visibleData.generated_at?new Date(visibleData.generated_at).toLocaleString('ru-RU'):'Нет отметки времени'}</strong></div></section>
      {flags.readOnly&&<div className="directorBNotice"><ShieldCheck/><div><b>Доступен только просмотр</b><span>Очередь и подтверждающие данные доступны. Управлять решениями, обновлением источников, измерением и STOP может владелец или администратор.</span></div></div>}
      {flags.stopped&&<div className="directorBStop" role="alert"><PauseCircle/><div><b>STOP активен для {visibleData.store_name||storeName}</b><span>Новые внешние записи запрещены. Чтение, диагностика и решения без исполнения остаются доступны.</span></div></div>}
      {degraded&&<div className="directorBNotice"><Clock3/><div><b>Очередь ограничена состоянием источников</b><span>Нет данных: {flags.missing?'да':'нет'} · устарели: {flags.stale?'да':'нет'} · загрузка не завершена: {flags.incomplete?'да':'нет'} · ошибка: {flags.sourceError?'да':'нет'}</span></div></div>}

      <section className="directorBQuestions">{questions.map(([title,value],index)=><article key={title}><span>0{index+1}</span><small>{title}</small><p>{value||'Данные отсутствуют'}</p></article>)}</section>

      <section className="directorBPanel directorBSources"><header><div><span>01 / ИСТОЧНИКИ</span><h2>Из чего построена очередь</h2></div><small>Статус рассчитан по срокам обновления каждого источника</small></header><div>{visibleData.sources.map(source=><article data-state={source.state} key={source.name}>{source.state==='live'?<CheckCircle2/>:source.state==='error'?<CircleAlert/>:<Clock3/>}<div><b>{sourceNames[source.name]||source.name}</b><span>{stateNames[source.state]||`неизвестное состояние: ${source.state}`}</span></div><small>{source.last_snapshot_at?new Date(source.last_snapshot_at).toLocaleString('ru-RU'):'Снимка нет'}</small></article>)}</div></section>

      <section className="directorBPanel directorBQueue"><header><div><span>02 / ОЧЕРЕДЬ</span><h2>Задачи по влиянию и риску</h2></div><small>{visibleData.ranking.formula}</small></header>{flags.empty?<div className="directorBEmpty"><CheckCircle2/><b>Подтверждённых задач сейчас нет</b><span>Director не создаёт рекомендации без фактов.</span></div>:<div className="directorBTasks">{visibleData.actions.map((item,index)=><DirectorTask key={item.id} item={item} index={index} canManageStore={canManageStore} busy={decisionBusy===item.id} onDecide={decide} onRun={runAction}/>)}</div>}</section>

      <section className={`directorBControl ${flags.stopped?'isStopped':''}`}><div>{flags.stopped?<PauseCircle/>:<PlayCircle/>}<div><span>03 / STOP</span><h2>{flags.stopped?'Внешние исполнения остановлены':'Контур внешних записей под контролем'}</h2><p>{flags.stopped?(visibleData.control.reason||'Причина не указана'):visibleData.automation.note} Уже принятый внешней системой запрос этим переключателем не отменяется.</p></div></div>{canManageStore?<div className="directorBControlFields"><input value={stopReason} maxLength={1000} onChange={event=>setStopReason(event.target.value)} aria-label="Причина изменения режима"/>{flags.stopped&&<input value={resumeConfirmation} onChange={event=>setResumeConfirmation(event.target.value)} placeholder="Введите ВОЗОБНОВИТЬ TROVENDI" aria-label="Подтверждение возобновления"/>}<button onClick={()=>changeControl(!flags.stopped)} disabled={controlBusy||(flags.stopped&&resumeConfirmation.trim().toUpperCase()!=='ВОЗОБНОВИТЬ TROVENDI')}>{flags.stopped?'Возобновить':'Включить STOP'}</button></div>:<span className="directorBReadOnly">Управление доступно владельцу или администратору</span>}</section>

      {(visibleData.tracked_actions||[]).length>0&&<section className="directorBPanel directorBTracked"><header><div><span>04 / ИЗМЕРЕНИЕ</span><h2>Ранее принятые действия</h2></div></header><div>{visibleData.tracked_actions.map(item=>{const access=directorActionAvailability(item,canManageStore);return <article key={item.id}><b>{item.title}</b><span>{statusNames[item.status]||item.status}</span><p>{item.result?.measurement?measurementText(item.result):'Результат ещё не измерен по свежим данным.'}</p>{access.canMeasure&&<button onClick={()=>runAction(item,'measure')} disabled={decisionBusy===item.id}><Clock3/> Измерить снова</button>}</article>})}</div></section>}

      <section className="directorBPanel directorBAudit"><header><div><span>05 / АУДИТ</span><h2>Последние события магазина</h2></div></header>{visibleData.audit.length?<div>{visibleData.audit.map(event=><article key={event.id}><time>{new Date(event.created_at).toLocaleString('ru-RU')}</time><b>{event.event_type}</b><small>{event.payload?.reason||event.payload?.note||event.entity_id}</small></article>)}</div>:<p>Событий пока нет. Первое подтверждение или STOP появится здесь.</p>}</section>
    </>}
  </main>
}

function DirectorTask({item,index,canManageStore,busy,onDecide,onRun}){
  const access=directorActionAvailability(item,canManageStore)
  return <article className="directorBTask" data-urgency={item.urgency}><div className="directorBTaskRank"><b>{String(index+1).padStart(2,'0')}</b><span>score {item.priority_score}</span></div><div className="directorBTaskBody"><div className="directorBTaskTitle"><div><small>{item.kind} · {item.provider.label}</small><h3>{item.title}</h3></div><span>{statusNames[item.status]||item.status}</span></div><p>{item.reason}</p><blockquote><b>Факт</b>{item.evidence}</blockquote><dl><div><dt>Наблюдаемый эффект</dt><dd>{rubles(item.observed_effect_kopecks)}</dd></div><div><dt>Основание приоритета</dt><dd>{item.priority_reason}</dd></div></dl><div className="directorBTaskActions"><Link href={item.href}>Открыть источник <ArrowRight/></Link>{access.canExecute&&<button onClick={()=>onRun(item,'execute')} disabled={busy}><RefreshCw/> Обновить источник</button>}{access.canDecide&&<><button onClick={()=>onDecide(item,'reject')} disabled={busy}><XCircle/> Отклонить</button><button className="isPrimary" onClick={()=>onDecide(item,'approve')} disabled={busy}><CheckCircle2/> Принять в работу</button></>}{access.canMeasure&&<button onClick={()=>onRun(item,'measure')} disabled={busy}><Clock3/> Измерить результат</button>}</div>{access.unavailableReason&&<div className="directorBLimitation">{access.unavailableReason}</div>}{item.status==='approved'&&<div className="directorBResult">Решение зафиксировано. Внешнее исполнение не запускалось.</div>}{item.status==='executing'&&<div className="directorBResult">Запущено только чтение WB. Записи в маркетплейс нет.</div>}{item.result?.measurement&&<div className="directorBResult">{measurementText(item.result)}</div>}</div></article>
}
