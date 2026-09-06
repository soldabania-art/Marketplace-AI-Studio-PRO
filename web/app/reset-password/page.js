'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { Suspense, useState } from 'react'
import { KeyRound, Sparkles } from 'lucide-react'

function ResetPasswordForm() {
  const params = useSearchParams()
  const [token, setToken] = useState(params.get('token') || '')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setError('')
    setMessage('')
    if (password !== confirm) {
      setError('Пароли не совпадают')
      return
    }
    setLoading(true)
    try {
      const response = await fetch('/api/auth/password-reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'confirm', token, new_password: password }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'Не удалось изменить пароль')
      setMessage('Пароль изменён. Теперь можно войти с новым паролем.')
      setPassword('')
      setConfirm('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return <section className="authFormPanel"><div className="authCard"><div className="brand authMiniBrand"><div className="brandMark"><Sparkles size={20}/></div><div><strong>Marketplace AI</strong><span>Studio Cloud</span></div></div><span className="eyebrow">НОВЫЙ ПАРОЛЬ</span><h2>Восстановление доступа</h2><p className="authLead">Ссылка одноразовая и ограничена по времени. После успешной смены старый токен больше не действует.</p><form onSubmit={submit}><label>Код восстановления<div className="authInput"><KeyRound size={18}/><input value={token} onChange={(e)=>setToken(e.target.value)} required placeholder="Токен из письма"/></div></label><label>Новый пароль<div className="authInput"><input type="password" minLength={8} maxLength={128} value={password} onChange={(e)=>setPassword(e.target.value)} required placeholder="Минимум 8 символов"/></div></label><label>Повторите пароль<div className="authInput"><input type="password" minLength={8} maxLength={128} value={confirm} onChange={(e)=>setConfirm(e.target.value)} required placeholder="Повторите пароль"/></div></label><button className="authPrimary" type="submit" disabled={loading}>{loading ? 'Сохраняем…' : 'Установить новый пароль'}</button></form>{message && <p className="authLead" style={{color:'#7ee2b8',marginTop:16}}>{message}</p>}{error && <p className="authLead" style={{color:'#ff8c96',marginTop:16}}>{error}</p>}<p className="authSwitch"><Link href="/login">Перейти ко входу</Link></p></div></section>
}

export default function ResetPasswordPage() {
  return <main className="authShell simpleAuth"><Suspense fallback={<section className="authFormPanel"><div className="authCard"><p className="authLead">Загружаем форму восстановления…</p></div></section>}><ResetPasswordForm /></Suspense></main>
}
