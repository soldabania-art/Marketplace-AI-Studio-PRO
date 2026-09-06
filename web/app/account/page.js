'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { Building2, CreditCard, LogOut, MailCheck, ShieldCheck, Sparkles, UserRound } from 'lucide-react'
import styles from './page.module.css'

export default function AccountPage() {
  const router = useRouter()
  const [account, setAccount] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [verifyMessage, setVerifyMessage] = useState('')
  const [verifyLoading, setVerifyLoading] = useState(false)

  useEffect(() => {
    let active = true
    fetch('/api/auth/me', { cache: 'no-store' })
      .then(async (response) => {
        const payload = await response.json()
        if (!response.ok) throw new Error(payload.error || 'Не удалось загрузить аккаунт')
        if (active) setAccount(payload)
      })
      .catch((e) => {
        if (!active) return
        setError(e.message)
        if (e.message === 'Требуется вход') router.replace('/login')
      })
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [router])

  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST' })
    router.replace('/login')
    router.refresh()
  }

  async function requestVerification() {
    setVerifyLoading(true)
    setVerifyMessage('')
    try {
      const response = await fetch('/api/auth/email-verification', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'request' }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'Не удалось отправить подтверждение')
      setVerifyMessage(payload.delivery === 'email_provider_not_configured'
        ? 'Подтверждение подготовлено. Почтовый провайдер подключим перед запуском.'
        : 'Письмо с подтверждением отправлено.')
    } catch (e) {
      setVerifyMessage(e.message)
    } finally {
      setVerifyLoading(false)
    }
  }

  return (
    <main className={styles.shell}>
      <header className={styles.topbar}>
        <Link href="/" className={`brand ${styles.brand}`}><div className="brandMark"><Sparkles size={20}/></div><div><strong>Marketplace AI</strong><span>Studio Cloud</span></div></Link>
        <div style={{display:'flex',gap:10,alignItems:'center'}}>
          {account?.is_platform_admin && <Link href="/admin" className={styles.action}>Админ-панель</Link>}
          <button className={styles.logout} onClick={logout}><LogOut size={17}/> Выйти</button>
        </div>
      </header>

      <section className={styles.content}>
        <div className={styles.heading}><span className="eyebrow">ЛИЧНЫЙ КАБИНЕТ</span><h1>Аккаунт и подписка</h1><p>Управление рабочим пространством, тарифом и безопасностью.</p></div>
        {loading && <div className={styles.notice}>Загружаем данные аккаунта…</div>}
        {error && !loading && <div className={`${styles.notice} ${styles.error}`}>{error}</div>}
        {account && (
          <div className={styles.grid}>
            <article className={styles.card}><div className={styles.icon}><UserRound size={20}/></div><span className="eyebrow">ПРОФИЛЬ</span><h3>{account.full_name}</h3><p>{account.email}</p><small>{account.email_verified ? 'Email подтверждён' : 'Email ожидает подтверждения'}</small>{!account.email_verified && <button className={styles.action} style={{marginTop:12}} onClick={requestVerification} disabled={verifyLoading}><MailCheck size={15}/> {verifyLoading ? 'Подготавливаем…' : 'Подтвердить email'}</button>}{verifyMessage && <small style={{display:'block',marginTop:10}}>{verifyMessage}</small>}</article>
            <article className={styles.card}><div className={styles.icon}><Building2 size={20}/></div><span className="eyebrow">РАБОЧЕЕ ПРОСТРАНСТВО</span><h3>{account.workspace_name}</h3><p>Роль: {account.role}</p><small>WB/Ozon подключаются отдельным безопасным шагом</small></article>
            <article className={`${styles.card} ${styles.plan}`}><div className={styles.icon}><CreditCard size={20}/></div><span className="eyebrow">ТАРИФ</span><h3>{String(account.plan_code).toUpperCase()}</h3><p>Статус: {account.subscription_status}</p><Link href="/pricing" className={styles.action}>Управлять тарифом</Link></article>
            <article className={styles.card}><div className={styles.icon}><ShieldCheck size={20}/></div><span className="eyebrow">БЕЗОПАСНОСТЬ</span><h3>Серверная сессия</h3><p>Токен входа хранится в HttpOnly cookie и недоступен JavaScript в браузере.</p><small>{account.is_platform_admin ? 'У вас есть доступ к управлению платформой' : 'Далее добавим управление устройствами и активными сессиями'}</small></article>
          </div>
        )}
      </section>
    </main>
  )
}
