'use client'

import Link from 'next/link'
import { useCallback,useEffect,useMemo,useState } from 'react'
import { ArrowLeft,BrainCircuit,CheckCircle2,CircleAlert,DatabaseZap,LockKeyhole,RefreshCw,ShieldCheck,Sparkles,Workflow } from 'lucide-react'
import { useActiveStore } from '../lib/useActiveStore'

const agentIcons={director:BrainCircuit,finance:DatabaseZap,content:Sparkles,supply:Workflow,data_health:RefreshCw,support:CircleAlert,security:ShieldCheck}
const riskNames={low:'низкий',medium:'средний',critical:'критический контроль'}
const capabilityNames={
  'plan.read':'читать план','recommend.read':'читать рекомендации','delegate.read_only':'ставить задачи только на чтение',
  'profit.read':'читать расчёты','profit.explain':'объяснять прибыль','scenario.calculate':'считать сценарии',
  'facts.read':'читать подтверждённые факты','copy.draft':'готовить текст','visual_brief.draft':'готовить визуальный план',
  'stock.read':'читать остатки','forecast.calculate':'считать прогноз','supply_plan.draft':'готовить план поставки',
  'source_health.read':'проверять источники','read_sync.enqueue':'запускать синхронизацию чтения',
  'knowledge.read':'читать проверенную базу','incident.create':'создавать инцидент','emergency_stop.link':'давать безопасный путь к STOP',
  'policy.evaluate':'проверять политику','execution.deny':'блокировать исполнение','audit.verify':'проверять аудит',
}

export default function AgentNetworkWorkspace(){
  const {storeId,storeName,loading:storeLoading,error:storeError}=useActiveStore()
  const [data,setData]=useState(null)
  const [orders,setOrders]=useState([])
  const [busy,setBusy]=useState(false)
  const [submitting,setSubmitting]=useState(false)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [goalType,setGoalType]=useState('profit_review')
  const [instruction,setInstruction]=useState('')

  const load=useCallback(async()=>{
    if(!storeId){setData(null);return}
    setBusy(true);setError('')
    try{
      const [networkResponse,ordersResponse]=await Promise.all([
        fetch(`/api/agents/network?store_id=${encodeURIComponent(storeId)}`,{cache:'no-store'}),
        fetch(`/api/agents/work-orders?store_id=${encodeURIComponent(storeId)}`,{cache:'no-store'}),
      ])
      const [networkPayload,ordersPayload]=await Promise.all([networkResponse.json(),ordersResponse.json()])
      if(!networkResponse.ok)throw new Error(networkPayload.error||'Не удалось загрузить сеть агентов')
      if(!ordersResponse.ok)throw new Error(ordersPayload.error||'Не удалось загрузить задачи агентов')
      setData(networkPayload);setOrders(ordersPayload.items||[])
    }catch(e){setData(null);setOrders([]);setError(e.message)}finally{setBusy(false)}
  },[storeId])

  useEffect(()=>{load()},[load])

  const director=useMemo(()=>data?.agents?.find(agent=>agent.key===data.master_agent),[data])
  const security=useMemo(()=>data?.agents?.find(agent=>agent.key===data.security_veto),[data])
  const specialists=useMemo(()=>data?.agents?.filter(agent=>agent.parent===data.master_agent)||[],[data])

  async function submitWorkOrder(event){
    event.preventDefault()
    if(!storeId||instruction.trim().length<3)return
    setSubmitting(true);setNotice('');setError('')
    try{
      const response=await fetch('/api/agents/work-orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:storeId,goal_type:goalType,instruction})})
      const payload=await response.json()
      if(!response.ok)throw new Error(payload.error||'Не удалось поставить задачу')
      setNotice(payload.message);setInstruction('');await load()
    }catch(e){setError(e.message)}finally{setSubmitting(false)}
  }

  return <main className="workPage agentPage">
    <div className="workHead"><Link href="/" className="ghostBtn"><ArrowLeft size={16}/> На главную</Link><button className="ghostBtn" onClick={load} disabled={busy||!storeId}><RefreshCw size={16}/>{busy?' Проверяем…':' Проверить политику'}</button></div>
    <section className="workHero agentHero"><div><span className="eyebrow">TROVENDI AGENT CONTROL PLANE</span><h1>Один владелец. Один главный мозг. Контролируемая команда AI.</h1><p>AI Director распределяет только разрешённые задачи. Каждый специалист ограничен своей ролью, а независимый Security Sentinel может запретить выполнение и не подчиняется Director.</p></div><div className="agentPolicySeal"><ShieldCheck size={26}/><div><b>Zero Trust</b><span>запрещено по умолчанию</span></div></div></section>
    {(storeError||error||notice)&&<div className="sectionNotice"><CircleAlert size={17}/>{storeError||error||notice}</div>}
    <section className="workPanel agentContext"><div><span>Активный магазин</span><strong>{storeLoading?'Загружаем…':storeName||'Не выбран'}</strong></div><div><span>Версия политики</span><strong>{data?`v${data.version} · ${data.sha256.slice(0,10)}`:'—'}</strong></div><div><span>Внешние изменения</span><strong className="blocked">ЗАПРЕЩЕНЫ</strong></div><div><span>Глобальный STOP</span><strong className={data?.control?.stopped?'blocked':'safe'}>{data?.control?.stopped?'ВКЛЮЧЁН':'готов'}</strong></div></section>
    {data&&<>
      <section className="agentTopology">
        <article className="workPanel agentCard director"><AgentTitle agent={director}/><p>{director?.purpose}</p><Capabilities items={director?.capabilities}/><div className="agentBoundary"><LockKeyhole size={15}/> Не может добавить себе инструмент или обойти политику.</div></article>
        <div className="agentConnector"><span>ставит типизированные задачи</span><i/></div>
        <div className="specialistGrid">{specialists.map(agent=><article className="workPanel agentCard" key={agent.key}><AgentTitle agent={agent}/><p>{agent.purpose}</p><Capabilities items={agent.capabilities}/></article>)}</div>
      </section>
      <section className="workPanel securitySentinel"><div className="sentinelIcon"><ShieldCheck size={30}/></div><div><span className="eyebrow">НЕЗАВИСИМЫЙ КОНТУР</span><h2>{security?.name}</h2><p>{security?.purpose} Его запрет не может отменить AI Director, пользовательское подтверждение или политика магазина.</p></div><Capabilities items={security?.capabilities}/></section>
      <section className="workPanel workOrderPanel"><div className="workOrderHead"><div><span className="eyebrow">КОМАНДНЫЙ ЦЕНТР</span><h2>Поставить задачу главному мозгу</h2><p>Director сам выбирает ответственного по фиксированному безопасному маршруту. Сейчас создаётся проверяемый план без внешнего исполнения.</p></div><span className="readOnlyBadge"><LockKeyhole size={13}/> только план</span></div><form onSubmit={submitWorkOrder}><select value={goalType} onChange={event=>setGoalType(event.target.value)} aria-label="Тип задачи">{(data.goal_routes||[]).map(route=><option key={route.goal_type} value={route.goal_type}>{route.label}</option>)}</select><input value={instruction} minLength={3} maxLength={2000} onChange={event=>setInstruction(event.target.value)} placeholder="Например: проверь, почему снизилась прибыль по товару…" aria-label="Задача AI Director"/><button disabled={submitting||instruction.trim().length<3}>{submitting?'Назначаем…':'Поставить задачу'}</button></form>{orders.length>0&&<div className="workOrderList">{orders.slice(0,6).map(order=><article key={order.id}><span>{order.assigned_agent_key}</span><div><b>{order.instruction}</b><small>{order.capability} · политика v{order.policy_version} · внешняя запись запрещена</small></div><em>{order.status==='planned'?'назначено':order.status}</em></article>)}</div>}</section>
      <section className="agentSafetyGrid"><article className="workPanel"><CheckCircle2 size={21}/><h2>Как агенты учатся</h2><p>Обратная связь очищается от токенов и персональных данных, сохраняется как кандидат и не меняет поведение автоматически. Продвижение возможно только после проверки, тестов и новой версии политики.</p></article><article className="workPanel"><LockKeyhole size={21}/><h2>Что невозможно сейчас</h2><p>Нет произвольного SQL, самоизменения кода, обучения на сырых данных клиентов и записи во внешние системы. Это реальные серверные запреты, а не обещание в промпте.</p></article></section>
      <div className="agentGuard"><ShieldCheck size={18}/><span>Владелец управляет решениями через AI Director, но безопасность имеет право только усилить ограничение. Ослабление требует отдельной проверяемой версии.</span><Link href="/director">Открыть AI Director</Link></div>
    </>}
  </main>
}

function AgentTitle({agent}){
  if(!agent)return null
  const Icon=agentIcons[agent.key]||Workflow
  return <div className="agentTitle"><span><Icon size={20}/></span><div><h2>{agent.name}</h2><small>{riskNames[agent.risk_ceiling]||agent.risk_ceiling} риск · без внешней записи</small></div></div>
}

function Capabilities({items=[]}){return <div className="agentCapabilities">{items.map(item=><span key={item}>{capabilityNames[item]||item}</span>)}</div>}
