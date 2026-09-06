'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { Building2, CreditCard, LogOut, ShieldCheck, Sparkles, UserRound } from 'lucide-react'

export default function AccountPage() {
  const router = useRouter()
  const [account, setAccount] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

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

  return (
    <main className="accountShell">
      <header className="accountTopbar">
        <Link href="/" className="brand accountBrand"><div className="brandMark"><Sparkles size={20}/></div><div><strong>Marketplace AI</strong><span>Studio Cloud</span></div></Link>
        <button className="accountLogout" onClick={logout}><LogOut size={17}/> Выйти</button>
      </header>

      <section className="accountContent">
        <div className="accountHeading"><span className="eyebrow">ЛИЧНЫЙ КАБИНЕТ</span><h1>Аккаунт и подписка</h1><p>Управление рабочим пространством, тарифом и безопасностью.</p></div>
        {loading && <div className="accountNotice">Загружаем данные аккаунта…</div>}
        {error && !loading && <div className="accountNotice error">{error}</div>}
        {account && (
          <div className="accountGrid">
            <article className="accountCard"><div className="accountIcon"><UserRound size={20}/></div><span className="eyebrow">ПРОФИЛЬ</span><h3>{account.full_name}</h3><p>{account.email}</p><small>{account.email_verified ? 'Email подтверждён' : 'Email ожидает подтверждения'}</small></article>
            <article className="accountCard"><div className="accountIcon"><Building2 size={20}/></div><span className="eyebrow">РАБОЧЕЕ ПРОСТРАНСТВО</span><h3>{account.workspace_name}</h3><p>Роль: {account.role}</p><small>WB/Ozon подключаются отдельным безопасным шагом</small></article>
            <article className="accountCard planCard"><div className="accountIcon"><CreditCard size={20}/></div><span className="eyebrow">ТАРИФ</span><h3>{String(account.plan_code).toUpperCase()}</h3><p>Статус: {account.subscription_status}</p><Link href="/pricing" className="accountAction">Управлять тарифом</Link></article>
            <article className="accountCard"><div className="accountIcon"><ShieldCheck size={20}/></div><span className="eyebrow">БЕЗОПАСНОСТЬ</span><h3>Серверная сессия</h3><p>Токен входа хранится в HttpOnly cookie и недоступен JavaScript в браузере.</p><small>Следующий этап — подтверждение email и управление устройствами</small></article>
          </div>
        )}
      </section>
    </main>
  )
}
