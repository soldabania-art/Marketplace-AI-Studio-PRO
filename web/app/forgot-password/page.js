'use client'

import Link from 'next/link'
import { useState } from 'react'
import { ArrowRight, Mail } from 'lucide-react'
import BrandLogo from '../../components/BrandLogo'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setMessage('')
    try {
      const response = await fetch('/api/auth/password-reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'request', email }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'Не удалось отправить инструкцию')
      setMessage('Если аккаунт существует, инструкция по восстановлению будет отправлена на указанный email.')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return <main className="authShell simpleAuth"><section className="authFormPanel"><div className="authCard"><BrandLogo className="authMiniBrand" /><span className="eyebrow">ВОССТАНОВЛЕНИЕ ДОСТУПА</span><h2>Забыли пароль?</h2><p className="authLead">Введите email аккаунта. Мы отправим безопасную одноразовую ссылку для создания нового пароля.</p><form onSubmit={submit}><label>Email<div className="authInput"><Mail size={18}/><input type="email" placeholder="you@company.ru" required value={email} onChange={(e)=>setEmail(e.target.value)}/></div></label><button className="authPrimary" type="submit" disabled={loading}>{loading ? 'Отправляем…' : 'Отправить ссылку'} <ArrowRight size={18}/></button></form>{message && <p className="authLead" style={{color:'#7ee2b8',marginTop:16}}>{message}</p>}{error && <p className="authLead" style={{color:'#ff8c96',marginTop:16}}>{error}</p>}<p className="authSwitch"><Link href="/login">← Вернуться ко входу</Link></p></div></section></main>
}
