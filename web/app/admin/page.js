'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { RefreshCcw, ShieldCheck } from 'lucide-react'
import { BrandMark } from '../../components/BrandLogo'
import styles from './admin.module.css'

const PLAN_LABELS = { trial: 'Trial', pro: 'PRO', business: 'Business' }

export default function AdminPage() {
  const [summary, setSummary] = useState(null)
  const [users, setUsers] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [summaryResponse, usersResponse] = await Promise.all([
        fetch('/api/admin?resource=summary', { cache: 'no-store' }),
        fetch('/api/admin?resource=users', { cache: 'no-store' }),
      ])
      const summaryPayload = await summaryResponse.json()
      const usersPayload = await usersResponse.json()
      if (!summaryResponse.ok) throw new Error(summaryPayload.error || 'Нет доступа к админ-панели')
      if (!usersResponse.ok) throw new Error(usersPayload.error || 'Не удалось загрузить пользователей')
      setSummary(summaryPayload)
      setUsers(usersPayload.items || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function patch(payload) {
    setError('')
    const response = await fetch('/api/admin', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const result = await response.json()
    if (!response.ok) {
      setError(result.error || 'Действие не выполнено')
      return
    }
    await load()
  }

  return (
    <main className={styles.shell}>
      <header className={styles.top}>
        <div className={styles.brand}>
          <BrandMark size={40} />
          <div><strong>TROVENDI</strong><span>Platform Admin</span></div>
        </div>
        <Link href="/account" className={styles.back}>← Личный кабинет</Link>
      </header>

      <section className={styles.content}>
        <div className={styles.heading}>
          <span>УПРАВЛЕНИЕ ПЛАТФОРМОЙ</span>
          <h1>Админ-панель сервиса</h1>
          <p>Пользователи, рабочие пространства, тарифы и состояние коммерческой платформы.</p>
        </div>

        {loading && <div className={styles.notice}>Загружаем данные платформы…</div>}
        {error && <div className={`${styles.notice} ${styles.error}`}>{error}</div>}

        {summary && (
          <div className={styles.stats}>
            <article className={styles.stat}><span>Пользователи</span><strong>{summary.users}</strong></article>
            <article className={styles.stat}><span>Активные</span><strong>{summary.active_users}</strong></article>
            <article className={styles.stat}><span>Рабочие пространства</span><strong>{summary.workspaces}</strong></article>
            <article className={styles.stat}><span>Trial</span><strong>{summary.trial_subscriptions}</strong></article>
            <article className={styles.stat}><span>Платные подписки</span><strong>{summary.active_subscriptions}</strong></article>
          </div>
        )}

        <section className={styles.panel}>
          <div className={styles.panelHead}>
            <h2>Пользователи и подписки</h2>
            <button onClick={load}><RefreshCcw size={14}/> Обновить</button>
          </div>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead><tr><th>Пользователь</th><th>Магазин</th><th>Роль</th><th>Тариф</th><th>Статус</th><th>Создан</th><th>Управление</th></tr></thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td><strong>{user.full_name || 'Без имени'}</strong><div className={styles.muted}>{user.email}</div></td>
                    <td>{user.workspace_name || '—'}</td>
                    <td>{user.role || '—'}</td>
                    <td>{PLAN_LABELS[user.plan_code] || user.plan_code}</td>
                    <td className={user.is_active ? styles.active : styles.inactive}>{user.is_active ? 'Активен' : 'Отключён'}</td>
                    <td className={styles.muted}>{user.created_at ? new Date(user.created_at).toLocaleDateString('ru-RU') : '—'}</td>
                    <td>
                      <div className={styles.actions}>
                        {user.workspace_id && <select value={user.plan_code} onChange={(e) => patch({ action: 'set_plan', workspace_id: user.workspace_id, plan_code: e.target.value })}><option value="trial">Trial</option><option value="pro">PRO</option><option value="business">Business</option></select>}
                        <button className={!user.is_active ? '' : styles.danger} onClick={() => patch({ action: 'set_user_status', user_id: user.id, active: !user.is_active })}>{user.is_active ? 'Отключить' : 'Включить'}</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <div className={styles.adminHint}><ShieldCheck size={14}/> Доступ к этому разделу разрешён только email-адресам из серверной переменной MARKETPLACE_ADMIN_EMAILS. Администратор не может отключить собственную учётную запись.</div>
      </section>
    </main>
  )
}
