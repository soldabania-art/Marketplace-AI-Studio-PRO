'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { Building2, CreditCard, Laptop, LogOut, MailCheck, ShieldCheck, Sparkles, UserRound } from 'lucide-react'
import styles from './page.module.css'

const eventNames = { login:'Вход', logout:'Выход', registration:'Регистрация', session_created:'Создана сессия', session_revoked:'Сессия завершена' }
const fmt = (value) => value ? new Date(value).toLocaleString('ru-RU') : '—'

export default function AccountPage() {
  const router = useRouter()
  const [account, setAccount] = useState(null)
  const [security, setSecurity] = useState({ sessions: [], events: [] })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [verifyMessage, setVerifyMessage] = useState('')
  const [verifyLoading, setVerifyLoading] = useState(false)

  async function loadSecurity() {
    const response = await fetch('/api/auth/security', { cache:'no-store' })
    const payload = await response.json()
    if (!response.ok) throw new Error(payload.error || 'Не удалось загрузить безопасность')
    setSecurity(payload)
  }

  useEffect(() => {
    let active = true
    Promise.all([
      fetch('/api/auth/me', { cache:'no-store' }).then(async r => { const p=await r.json(); if(!r.ok) throw new Error(p.error || 'Не удалось загрузить аккаунт'); if(active) setAccount(p) }),
      loadSecurity(),
    ]).catch(e => { if(active){ setError(e.message); if(e.message === 'Требуется вход') router.replace('/login') } }).finally(() => active && setLoading(false))
    return () => { active=false }
  }, [router])

  async function logout() { await fetch('/api/auth/logout', { method:'POST' }); router.replace('/login'); router.refresh() }
  async function revoke(id, current) {
    const response = await fetch('/api/auth/security', { method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:id}) })
    const payload = await response.json(); if(!response.ok){ setError(payload.error || 'Не удалось завершить сессию'); return }
    if(current){ router.replace('/login'); router.refresh(); return }
    await loadSecurity()
  }
  async function requestVerification() {
    setVerifyLoading(true); setVerifyMessage('')
    try { const response=await fetch('/api/auth/email-verification',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'request'})}); const payload=await response.json(); if(!response.ok) throw new Error(payload.error || 'Не удалось отправить подтверждение'); setVerifyMessage(payload.delivery==='email_provider_not_configured'?'Подтверждение подготовлено. Почтовый провайдер подключим перед запуском.':'Письмо с подтверждением отправлено.') } catch(e){ setVerifyMessage(e.message) } finally { setVerifyLoading(false) }
  }

  return <main className={styles.shell}>
    <header className={styles.topbar}><Link href="/" className={`brand ${styles.brand}`}><div className="brandMark"><Sparkles size={20}/></div><div><strong>Marketplace AI</strong><span>Studio Cloud</span></div></Link><div className={styles.topActions}>{account?.is_platform_admin&&<Link href="/admin" className={styles.action}>Админ-панель</Link>}<button className={styles.logout} onClick={logout}><LogOut size={17}/> Выйти</button></div></header>
    <section className={styles.content}><div className={styles.heading}><span className="eyebrow">ЛИЧНЫЙ КАБИНЕТ</span><h1>Аккаунт и безопасность</h1><p>Рабочее пространство, тариф, активные устройства и журнал входов.</p></div>
    {loading&&<div className={styles.notice}>Загружаем данные аккаунта…</div>}{error&&!loading&&<div className={`${styles.notice} ${styles.error}`}>{error}</div>}
    {account&&<><div className={styles.grid}>
      <article className={styles.card}><div className={styles.icon}><UserRound size={20}/></div><span className="eyebrow">ПРОФИЛЬ</span><h3>{account.full_name}</h3><p>{account.email}</p><small>{account.email_verified?'Email подтверждён':'Email ожидает подтверждения'}</small>{!account.email_verified&&<button className={styles.action} onClick={requestVerification} disabled={verifyLoading}><MailCheck size={15}/> {verifyLoading?'Подготавливаем…':'Подтвердить email'}</button>}{verifyMessage&&<small className={styles.message}>{verifyMessage}</small>}</article>
      <article className={styles.card}><div className={styles.icon}><Building2 size={20}/></div><span className="eyebrow">РАБОЧЕЕ ПРОСТРАНСТВО</span><h3>{account.workspace_name}</h3><p>Роль: {account.role}</p><small>WB/Ozon подключаются отдельным безопасным шагом</small></article>
      <article className={`${styles.card} ${styles.plan}`}><div className={styles.icon}><CreditCard size={20}/></div><span className="eyebrow">ТАРИФ</span><h3>{String(account.plan_code).toUpperCase()}</h3><p>Статус: {account.subscription_status}</p><Link href="/pricing" className={styles.action}>Управлять тарифом</Link></article>
      <article className={styles.card}><div className={styles.icon}><ShieldCheck size={20}/></div><span className="eyebrow">ЗАЩИТА</span><h3>Серверные сессии</h3><p>Каждый вход имеет отдельную отзывную серверную сессию. После смены пароля все устройства отключаются.</p><small>IP хранится только в виде приватного хэша</small></article>
    </div>
    <section className={styles.securitySection}><div className={styles.sectionHead}><div><span className="eyebrow">УСТРОЙСТВА</span><h2>Активные сессии</h2></div><Laptop size={22}/></div><div className={styles.list}>{security.sessions.map(s=><div className={styles.row} key={s.id}><div><strong>{s.current?'Это устройство':'Другое устройство'} {s.revoked&&'· завершена'}</strong><span>{s.user_agent || 'Браузер не определён'}</span><small>Последняя активность: {fmt(s.last_seen_at)} · истекает: {fmt(s.expires_at)}</small></div>{!s.revoked&&<button className={styles.danger} onClick={()=>revoke(s.id,s.current)}>{s.current?'Выйти здесь':'Завершить'}</button>}</div>)}</div></section>
    <section className={styles.securitySection}><div className={styles.sectionHead}><div><span className="eyebrow">ЖУРНАЛ</span><h2>Последние события безопасности</h2></div><ShieldCheck size={22}/></div><div className={styles.list}>{security.events.slice(0,20).map((e,i)=><div className={styles.event} key={`${e.created_at}-${i}`}><span className={e.success?styles.ok:styles.bad}>{e.success?'OK':'!'}</span><div><strong>{eventNames[e.event_type] || e.event_type}</strong><small>{fmt(e.created_at)} · {e.user_agent || 'устройство не определено'}</small></div></div>)}</div></section></>}
    </section>
  </main>
}
