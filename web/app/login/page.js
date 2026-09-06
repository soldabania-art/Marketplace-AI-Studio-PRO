'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { ArrowRight, LockKeyhole, Mail, ShieldCheck, Sparkles } from 'lucide-react'

export default function LoginPage() {
  const router = useRouter()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setError('')
    setLoading(true)
    const form = new FormData(event.currentTarget)

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: form.get('email'), password: form.get('password') }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'Не удалось войти')
      router.push('/account')
      router.refresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="authShell">
      <section className="authBrandPanel">
        <div className="brand authBrand"><div className="brandMark"><Sparkles size={20} /></div><div><strong>Marketplace AI</strong><span>Studio Cloud</span></div></div>
        <div className="authPitch">
          <span className="eyebrow">AI OPERATING SYSTEM ДЛЯ СЕЛЛЕРОВ</span>
          <h1>Управляйте WB и Ozon из одного AI-центра.</h1>
          <p>Прибыль, карточки, SEO, реклама, отзывы и остатки — в одной системе с безопасной автоматизацией.</p>
          <div className="authTrust"><ShieldCheck size={19} /><span>Ключи маркетплейсов хранятся только на сервере и подключаются после регистрации.</span></div>
        </div>
      </section>

      <section className="authFormPanel">
        <div className="authCard">
          <span className="eyebrow">ДОБРО ПОЖАЛОВАТЬ</span>
          <h2>Войти в аккаунт</h2>
          <p className="authLead">Продолжите работу с вашими магазинами и AI Director.</p>
          <form onSubmit={submit}>
            <label>Email<div className="authInput"><Mail size={18}/><input name="email" type="email" placeholder="you@company.ru" autoComplete="email" required /></div></label>
            <label>Пароль<div className="authInput"><LockKeyhole size={18}/><input name="password" type="password" placeholder="••••••••" autoComplete="current-password" required /></div></label>
            <div className="authRow"><span /><Link href="/forgot-password">Забыли пароль?</Link></div>
            {error && <div className="authError">{error}</div>}
            <button className="authPrimary" type="submit" disabled={loading}>{loading ? 'Входим…' : <>Войти <ArrowRight size={18}/></>}</button>
          </form>
          <div className="authDivider"><span>или</span></div>
          <p className="authSwitch">Нет аккаунта? <Link href="/register">Создать бесплатно</Link></p>
          <Link className="authBack" href="/">← Вернуться на главную</Link>
        </div>
      </section>
    </main>
  )
}
