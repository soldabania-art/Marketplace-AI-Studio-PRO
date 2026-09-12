'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { RefreshCcw, RotateCcw, ShieldCheck } from 'lucide-react'
import { BrandMark } from '../../components/BrandLogo'
import styles from './admin.module.css'

const PLAN_LABELS = { trial: 'Trial', pro: 'PRO', business: 'Business' }
const JOB_LABELS={queued:'В очереди',running:'В работе',succeeded:'Готово',retry:'Повтор',dead:'Dead',canceled:'Отменено'}

export default function AdminPage() {
  const [summary, setSummary] = useState(null)
  const [users, setUsers] = useState([])
  const [jobs,setJobs]=useState({items:[],counts:{},stale_running:0,oldest_ready_at:null})
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [jobBusy,setJobBusy]=useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [summaryResponse, usersResponse, jobsResponse] = await Promise.all([
        fetch('/api/admin?resource=summary', { cache: 'no-store' }),
        fetch('/api/admin?resource=users', { cache: 'no-store' }),
        fetch('/api/admin?resource=jobs', { cache: 'no-store' }),
      ])
      const [summaryPayload,usersPayload,jobsPayload]=await Promise.all([summaryResponse.json(),usersResponse.json(),jobsResponse.json()])
      if (!summaryResponse.ok) throw new Error(summaryPayload.error || 'Нет доступа к админ-панели')
      if (!usersResponse.ok) throw new Error(usersPayload.error || 'Не удалось загрузить пользователей')
      if (!jobsResponse.ok) throw new Error(jobsPayload.error || 'Не удалось загрузить фоновые задания')
      setSummary(summaryPayload)
      setUsers(usersPayload.items || [])
      setJobs(jobsPayload)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function patch(payload) {
    setError('')
    const response = await fetch('/api/admin', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    const result = await response.json()
    if (!response.ok) { setError(result.error || 'Действие не выполнено'); return }
    await load()
  }

  async function requeue(jobId){
    setError('');setJobBusy(jobId)
    try{
      const response=await fetch('/api/admin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'requeue_job',job_id:jobId})})
      const result=await response.json();if(!response.ok)throw new Error(result.error||'Job не удалось вернуть в очередь')
      await load()
    }catch(e){setError(e.message)}finally{setJobBusy('')}
  }

  const queueProblem=(jobs.counts?.dead||0)+(jobs.stale_running||0)

  return (
    <main className={styles.shell}>
      <header className={styles.top}>
        <div className={styles.brand}><BrandMark size={40} /><div><strong>TROVENDI</strong><span>Platform Admin</span></div></div>
        <Link href="/account" className={styles.back}>← Личный кабинет</Link>
      </header>

      <section className={styles.content}>
        <div className={styles.heading}><span>УПРАВЛЕНИЕ ПЛАТФОРМОЙ</span><h1>Админ-панель сервиса</h1><p>Пользователи, подписки и здоровье фоновой инфраструктуры.</p></div>
        {loading && <div className={styles.notice}>Загружаем данные платформы…</div>}
        {error && <div className={`${styles.notice} ${styles.error}`}>{error}</div>}

        {summary && <div className={styles.stats}>
          <article className={styles.stat}><span>Пользователи</span><strong>{summary.users}</strong></article>
          <article className={styles.stat}><span>Активные</span><strong>{summary.active_users}</strong></article>
          <article className={styles.stat}><span>Рабочие пространства</span><strong>{summary.workspaces}</strong></article>
          <article className={styles.stat}><span>Trial</span><strong>{summary.trial_subscriptions}</strong></article>
          <article className={styles.stat}><span>Платные подписки</span><strong>{summary.active_subscriptions}</strong></article>
        </div>}

        <section className={styles.panel}>
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
        </section>

        <section className={styles.panel}>
          <div className={styles.panelHead}><h2>Пользователи и подписки</h2><button onClick={load}><RefreshCcw size={14}/> Обновить</button></div>
          <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>Пользователь</th><th>Магазин</th><th>Роль</th><th>Тариф</th><th>Статус</th><th>Создан</th><th>Управление</th></tr></thead><tbody>
            {users.map((user) => <tr key={user.id}><td><strong>{user.full_name || 'Без имени'}</strong><div className={styles.muted}>{user.email}</div></td><td>{user.workspace_name || '—'}</td><td>{user.role || '—'}</td><td>{PLAN_LABELS[user.plan_code] || user.plan_code}</td><td className={user.is_active ? styles.active : styles.inactive}>{user.is_active ? 'Активен' : 'Отключён'}</td><td className={styles.muted}>{user.created_at ? new Date(user.created_at).toLocaleDateString('ru-RU') : '—'}</td><td><div className={styles.actions}>{user.workspace_id && <select value={user.plan_code} onChange={(e) => patch({ action: 'set_plan', workspace_id: user.workspace_id, plan_code: e.target.value })}><option value="trial">Trial</option><option value="pro">PRO</option><option value="business">Business</option></select>}<button className={!user.is_active ? '' : styles.danger} onClick={() => patch({ action: 'set_user_status', user_id: user.id, active: !user.is_active })}>{user.is_active ? 'Отключить' : 'Включить'}</button></div></td></tr>)}
          </tbody></table></div>
        </section>

        <div className={styles.adminHint}><ShieldCheck size={14}/> Чтение доступно только platform-admin. Изменение тарифов, статуса пользователя и ручной replay job требуют свежего step-up подтверждения администратора.</div>
      </section>
    </main>
  )
}
