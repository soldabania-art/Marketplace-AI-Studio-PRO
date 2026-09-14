'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { RefreshCcw, RotateCcw, ShieldCheck, UserPlus, X } from 'lucide-react'
import { BrandMark } from '../../components/BrandLogo'
import { createPlatformAdminLoader, projectManagerGrantPayload, queueBarWidth } from '../../lib/platformAdmin.mjs'
import styles from './admin.module.css'

const PLAN_LABELS = { trial: 'Trial', pro: 'PRO', business: 'Business' }
const JOB_LABELS={queued:'В очереди',running:'В работе',succeeded:'Готово',retry:'Повтор',dead:'Dead',canceled:'Отменено'}

export default function AdminPage() {
  const [overview, setOverview] = useState(null)
  const [users, setUsers] = useState([])
  const [jobs,setJobs]=useState(null)
  const [team,setTeam]=useState([])
  const [platformRole,setPlatformRole]=useState(null)
  const [detailErrors,setDetailErrors]=useState({})
  const [grantUserId,setGrantUserId]=useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [jobBusy,setJobBusy]=useState('')
  const [accessBusy,setAccessBusy]=useState(false)
  const dataLoader=useRef(null)
  const pageLoadSequence=useRef(0)
  if(!dataLoader.current)dataLoader.current=createPlatformAdminLoader((...args)=>fetch(...args))

  async function load() {
    const sequence=++pageLoadSequence.current
    setLoading(true)
    setError('')
    setOverview(null);setUsers([]);setJobs(null);setTeam([]);setPlatformRole(null);setDetailErrors({});setGrantUserId('')
    try {
      const data=await dataLoader.current.load()
      if(!data)return
      setPlatformRole(data.role)
      setOverview(data.overview)
      setDetailErrors(data.detailErrors||{})
      if(data.role==='owner'){setUsers(data.users);setJobs(data.jobs);setTeam(data.team)}
    } catch (e) {
      if(sequence===pageLoadSequence.current)setError(e.message)
    } finally {
      if(sequence===pageLoadSequence.current)setLoading(false)
    }
  }

  useEffect(() => { load();return()=>dataLoader.current?.cancel() }, [])

  async function reconcileUnknownMutation() {
    await load()
    setError('Результат действия неизвестен. Запрошена сверка; проверьте актуальный список перед следующим действием.')
  }

  function unknownMutationError(error) {
    return error?.unknown === true || error instanceof TypeError || error instanceof SyntaxError
  }

  async function patch(payload) {
    setError('')
    try{
      const response=await fetch('/api/admin',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      const result=await response.json()
      if(!response.ok){if([401,403].includes(response.status))await load();if([503,504].includes(response.status))throw Object.assign(new Error(),{unknown:true});throw new Error(result.error||'Действие не выполнено')}
      await load()
    }catch(e){if(unknownMutationError(e))await reconcileUnknownMutation();else setError(e.message||'Действие не выполнено')}
  }

  async function requeue(jobId){
    setError('');setJobBusy(jobId)
    try{
      const response=await fetch('/api/admin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'requeue_job',job_id:jobId})})
      const result=await response.json();if(!response.ok){if([401,403].includes(response.status))await load();if([503,504].includes(response.status))throw Object.assign(new Error(),{unknown:true});throw new Error(result.error||'Job не удалось вернуть в очередь')}
      await load()
    }catch(e){if(unknownMutationError(e))await reconcileUnknownMutation();else setError(e.message||'Job не удалось вернуть в очередь')}finally{setJobBusy('')}
  }

  async function grantProjectManager(){
    if(!grantUserId)return
    setError('');setAccessBusy(true)
    try{
      const response=await fetch('/api/admin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(projectManagerGrantPayload(grantUserId))})
      const result=await response.json()
      if(!response.ok){if([401,403].includes(response.status))await load();if([503,504].includes(response.status))throw Object.assign(new Error(),{unknown:true});throw new Error(result.error||'Доступ не выдан')}
      setGrantUserId('');await load()
    }catch(e){
      if(unknownMutationError(e))await reconcileUnknownMutation()
      else setError(e.message||'Доступ не выдан')
    }finally{setAccessBusy(false)}
  }

  async function revokeAccess(member){
    if(!window.confirm(`Отозвать доступ у ${member.full_name||member.email}?`))return
    setError('');setAccessBusy(true)
    try{
      const response=await fetch(`/api/admin?user_id=${encodeURIComponent(member.user_id)}`,{method:'DELETE'})
      const result=await response.json()
      if(!response.ok){if([401,403].includes(response.status))await load();if([503,504].includes(response.status))throw Object.assign(new Error(),{unknown:true});throw new Error(result.error||'Доступ не отозван')}
      await load()
    }catch(e){
      if(unknownMutationError(e))await reconcileUnknownMutation()
      else setError(e.message||'Доступ не отозван')
    }finally{setAccessBusy(false)}
  }

  const queueProblem=jobs?(jobs.counts?.dead||0)+(jobs.stale_running||0):0
  const overviewAttention=overview?(overview.jobs.dead+overview.jobs.running_leases.stale+overview.jobs.running_leases.missing_timestamp):0
  const queueBars=overview?[
    ['В очереди',overview.jobs.queued,'coral'],['В работе',overview.jobs.running,'mint'],['На повторе',overview.jobs.retry,'lime'],['С ошибкой',overview.jobs.dead,'aubergine'],
  ]:[]
  const queueMax=Math.max(1,...queueBars.map(item=>item[1]))
  const queueTotal=queueBars.reduce((total,item)=>total+item[1],0)
  const teamIds=new Set(team.map(member=>member.user_id))
  const grantCandidates=users.filter(user=>user.is_active&&user.email_verified&&!teamIds.has(user.id))

  return (
    <main className={styles.shell}>
      <header className={styles.top}>
        <div className={styles.brand}><BrandMark size={40} /><div><strong>TROVENDI</strong><span>Platform Admin</span></div></div>
        <Link href="/account" className={styles.back}>← Личный кабинет</Link>
      </header>

      <section className={styles.content}>
        <div className={styles.heading}><span>УПРАВЛЕНИЕ ПЛАТФОРМОЙ</span><h1>Обзор для владельца и команды</h1><p>Проверяемые агрегаты аккаунтов, магазинов и фоновой очереди.</p></div>
        {loading && <div className={styles.notice}>Загружаем данные платформы…</div>}
        {error && <div className={`${styles.notice} ${styles.error}`}>{error}</div>}
        <div className={styles.utilityActions}><button onClick={load}><RefreshCcw size={14}/> Обновить доступ</button><Link href="/account#security">MFA и step-up</Link></div>

        {overview&&<>
          <section className={styles.brief} aria-labelledby="owner-today">
            <div><span className={styles.eyebrow}>{platformRole==='owner'?'Владелец платформы':'Project Manager'} · агрегированный доступ</span><h2 id="owner-today">{platformRole==='owner'?'Сегодня владельца':'Обзор проекта'}</h2><p>Данные базы на {new Date(overview.as_of).toLocaleString('ru-RU')}.</p></div>
            <button onClick={load}><RefreshCcw size={15}/> Обновить срез</button>
          </section>

          <div className={styles.overviewGrid}>
            <section className={styles.attention} aria-labelledby="problems-title">
              <span className={styles.sectionIndex}>01</span><h2 id="problems-title">Проблемы</h2>
              <strong className={styles.attentionNumber}>{overviewAttention}</strong>
              <p>{queueTotal===0?'Очередь пуста: заданий в наблюдаемых статусах нет.':overviewAttention===0?'По данным очереди наблюдаемых проблем не найдено.':'Задания с ошибками или без свежей отметки требуют внимания.'}</p>
              <dl><div><dt>Завершились ошибкой</dt><dd>{overview.jobs.dead}</dd></div><div><dt>Давно нет обновлений</dt><dd>{overview.jobs.running_leases.stale}</dd></div><div><dt>Нет отметки активности</dt><dd>{overview.jobs.running_leases.missing_timestamp}</dd></div></dl>
              <small>Текущее состояние обработчиков не проверялось.</small>
            </section>

            <section className={styles.facts} aria-labelledby="facts-title">
              <span className={styles.sectionIndex}>02</span><h2 id="facts-title">Факты платформы</h2>
              <div className={styles.factGrid}>
                <div><span>Аккаунты</span><strong>{overview.users.total}</strong><small>включены {overview.users.enabled}</small></div>
                <div><span>Новые за 7 дней</span><strong>{overview.users.new_7d}</strong><small>по дате регистрации</small></div>
                <div><span>Рабочие пространства</span><strong>{overview.operations.workspaces}</strong><small>всего записей</small></div>
                <div><span>Активные магазины</span><strong>{overview.operations.active_stores}</strong><small>магазины включены</small></div>
                <div><span>Сохранено подключение WB</span><strong>{overview.operations.connections_saved}</strong><small>не проверка провайдера</small></div>
                <div><span>Успешно за 24 часа</span><strong>{overview.jobs.succeeded_24h}</strong><small>завершённые задания</small></div>
              </div>
            </section>

            <section className={styles.queueGraphic} aria-labelledby="queue-title">
              <span className={styles.sectionIndex}>03</span><h2 id="queue-title">Очередь сейчас</h2>
              <div className={styles.bars}>{queueBars.map(([label,value,tone])=><div className={styles.barRow} key={label}><div><span>{label}</span><strong>{value}</strong></div><div className={styles.barTrack}><i className={styles[tone]} style={{width:`${queueBarWidth(value,queueMax)}%`}} /></div></div>)}</div>
              <div className={styles.queueFoot}><span>Готовы к запуску <strong>{overview.jobs.backlog.ready}</strong></span><span>Запланированы позже <strong>{overview.jobs.backlog.future_cooldown}</strong></span><span>Старейшая готовая {overview.jobs.backlog.oldest_ready_age_seconds===null?<strong>—</strong>:<strong>{overview.jobs.backlog.oldest_ready_age_seconds} сек.</strong>}</span></div>
            </section>
          </div>

          <section className={styles.unknowns}><h2>Пока неизвестно</h2><p>Выручка, регулярный доход и расходы AI ещё не подключены к обзору. Назначения менеджерам — отдельный следующий этап. Состояние провайдеров, Redis, Vercel и обработчиков здесь не проверяется.</p><small>Источник: агрегаты базы данных. Данные могут обновляться во время просмотра.</small></section>
        </>}

        {platformRole==='project_manager'&&<div className={styles.notice}>Доступен безопасный обзор платформы без данных клиентов, заданий и административных действий.</div>}

        {platformRole==='owner'&&Object.keys(detailErrors).length>0&&<div className={`${styles.notice} ${styles.error}`}>Обзор сохранён, но часть инструментов владельца временно недоступна: {Object.entries(detailErrors).map(([key,value])=>`${key}: ${value}`).join('; ')}</div>}

        {platformRole==='owner'&&<div className={styles.toolsHeading}><span>04</span><div><h2>Инструменты владельца</h2><p>Детальные разделы и существующие действия доступны только владельцу.</p></div></div>}

        {platformRole==='owner'&&detailErrors.jobs&&<section className={styles.panel}><div className={styles.panelHead}><h2>Фоновые задания</h2></div><div className={styles.sectionUnavailable}>Раздел временно недоступен. Обновите срез позже.</div></section>}
        {platformRole==='owner'&&!detailErrors.jobs&&jobs&&<section className={styles.panel}>
          <div className={styles.panelHead}><div><h2>Фоновые задания</h2><div className={styles.muted}>Очередь синхронизаций, FBO и тяжёлых операций. Payload скрыт; показываются только безопасные метаданные.</div></div><button onClick={load}><RefreshCcw size={14}/> Обновить</button></div>
          <div className={styles.stats}>
            <article className={styles.stat}><span>В очереди</span><strong>{jobs.counts?.queued||0}</strong></article>
            <article className={styles.stat}><span>В работе</span><strong>{jobs.counts?.running||0}</strong></article>
            <article className={styles.stat}><span>Retry</span><strong>{jobs.counts?.retry||0}</strong></article>
            <article className={styles.stat}><span>Dead</span><strong>{jobs.counts?.dead||0}</strong></article>
            <article className={styles.stat}><span>Зависшие leases</span><strong>{jobs.stale_running||0}</strong></article>
          </div>
          {queueProblem>0&&<div className={`${styles.notice} ${styles.error}`}>Найдено проблемных фоновых заданий: {queueProblem}. Dead/retry можно вернуть в очередь только после step-up подтверждения администратора.</div>}
          <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>Тип</th><th>Статус</th><th>Store</th><th>Попытки</th><th>Создан</th><th>Ошибка</th><th>Действие</th></tr></thead><tbody>
            {(jobs.items||[]).map(job=><tr key={job.id}><td><strong>{job.job_type}</strong><div className={styles.muted}>{job.id.slice(0,8)} · priority {job.priority}</div></td><td>{JOB_LABELS[job.status]||job.status}</td><td className={styles.muted}>{job.store_id?job.store_id.slice(0,8):'—'}</td><td>{job.attempts}/{job.max_attempts}</td><td className={styles.muted}>{job.created_at?new Date(job.created_at).toLocaleString('ru-RU'):'—'}</td><td className={styles.muted}>{job.last_error||'—'}</td><td>{['dead','retry','canceled'].includes(job.status)&&<button disabled={jobBusy===job.id} onClick={()=>requeue(job.id)}><RotateCcw size={14}/>{jobBusy===job.id?' Возвращаем…':' Повторить'}</button>}</td></tr>)}
          </tbody></table></div>
        </section>}

        {platformRole==='owner'&&detailErrors.users&&<section className={styles.panel}><div className={styles.panelHead}><h2>Пользователи и подписки</h2></div><div className={styles.sectionUnavailable}>Раздел временно недоступен. Обновите срез позже.</div></section>}
        {platformRole==='owner'&&!detailErrors.users&&<section className={styles.panel}>
          <div className={styles.panelHead}><h2>Пользователи и подписки</h2><button onClick={load}><RefreshCcw size={14}/> Обновить</button></div>
          <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>Пользователь</th><th>Магазин</th><th>Роль</th><th>Тариф</th><th>Статус</th><th>Создан</th><th>Управление</th></tr></thead><tbody>
            {users.map((user) => <tr key={user.id}><td><strong>{user.full_name || 'Без имени'}</strong><div className={styles.muted}>{user.email}</div></td><td>{user.workspace_name || '—'}</td><td>{user.role || '—'}</td><td>{PLAN_LABELS[user.plan_code] || user.plan_code}</td><td className={user.is_active ? styles.active : styles.inactive}>{user.is_active ? 'Активен' : 'Отключён'}</td><td className={styles.muted}>{user.created_at ? new Date(user.created_at).toLocaleDateString('ru-RU') : '—'}</td><td><div className={styles.actions}>{user.workspace_id && <select value={user.plan_code} onChange={(e) => patch({ action: 'set_plan', workspace_id: user.workspace_id, plan_code: e.target.value })}><option value="trial">Trial</option><option value="pro">PRO</option><option value="business">Business</option></select>}<button className={!user.is_active ? '' : styles.danger} onClick={() => patch({ action: 'set_user_status', user_id: user.id, active: !user.is_active })}>{user.is_active ? 'Отключить' : 'Включить'}</button></div></td></tr>)}
          </tbody></table></div>
        </section>}

        {platformRole==='owner'&&detailErrors.team&&<section className={`${styles.panel} ${styles.teamPanel}`}><div className={styles.panelHead}><h2>Команда и доступ</h2></div><div className={styles.sectionUnavailable}>Раздел временно недоступен. Обновите срез позже.</div></section>}
        {platformRole==='owner'&&!detailErrors.team&&<section className={`${styles.panel} ${styles.teamPanel}`}>
          <div className={styles.panelHead}><div><h2>Команда и доступ</h2><div className={styles.muted}>Project Manager видит только общие показатели без данных клиентов и фоновых заданий.</div></div></div>
          {detailErrors.users?<div className={styles.sectionUnavailable}>Выдача доступа недоступна, пока список пользователей не загружен.</div>:<div className={styles.grantRow}><select aria-label="Пользователь для доступа Project Manager" value={grantUserId} onChange={event=>setGrantUserId(event.target.value)}><option value="">Выберите подтверждённого пользователя</option>{grantCandidates.map(user=><option key={user.id} value={user.id}>{user.full_name||user.email} · {user.email}</option>)}</select><button disabled={!grantUserId||accessBusy} onClick={grantProjectManager}><UserPlus size={14}/> Выдать доступ PM</button></div>}
          <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>Участник</th><th>Доступ</th><th>Статус</th><th>Действие</th></tr></thead><tbody>{team.map(member=><tr key={member.user_id}><td><strong>{member.full_name||'Без имени'}</strong><div className={styles.muted}>{member.email}</div></td><td>{member.role==='owner'?'Владелец платформы':'Project Manager'}</td><td className={member.is_active?styles.active:styles.inactive}>{member.is_active?'Активен':'Отключён'}</td><td><button disabled={accessBusy} className={styles.danger} onClick={()=>revokeAccess(member)}><X size={14}/> Отозвать</button></td></tr>)}</tbody></table></div>
        </section>}

        {platformRole&&<div className={styles.adminHint}><ShieldCheck size={14}/> Права проверяются сервером. Изменения доступа, тарифов, статуса пользователя и ручной replay job требуют MFA и свежего step-up подтверждения владельца.</div>}
      </section>
    </main>
  )
}
