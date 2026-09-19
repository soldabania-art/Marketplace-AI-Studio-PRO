'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { useMemo, useState } from 'react'
import BrandLogo from '../../components/BrandLogo'
import { createEmailConfirmation } from '../../lib/accountMail.mjs'

export default function EmailConfirmation() {
  const params = useSearchParams()
  const token = params.get('token') || ''
  return <ConfirmationForm key={token} token={token} />
}

function ConfirmationForm({ token }) {
  const confirmation = useMemo(() => createEmailConfirmation(token, (...args) => fetch(...args)), [token])
  const [busy, setBusy] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [error, setError] = useState('')

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    const result = await confirmation.confirm()
    setConfirmed(result.confirmed === true)
    setError(result.error || '')
    setBusy(false)
  }

  return <section className="authFormPanel"><div className="authCard">
    <BrandLogo className="authMiniBrand" />
    <span className="eyebrow">ПОДТВЕРЖДЕНИЕ EMAIL</span>
    <h1>{confirmed ? 'Email подтверждён' : 'Подтвердите ваш email'}</h1>
    {confirmed ? <p className="authLead" role="status">Теперь можно продолжить настройку аккаунта.</p> : <>
      <p className="authLead">Нажмите кнопку, чтобы подтвердить адрес, на который пришло письмо. Простое открытие ссылки ничего не меняет.</p>
      {token ? <form onSubmit={submit}><button className="authPrimary" disabled={busy} type="submit">{busy ? 'Подтверждаем…' : 'Подтвердить email'}</button></form> : <p role="alert">В ссылке нет кода подтверждения. Запросите новое письмо в аккаунте.</p>}
    </>}
    {error && <p className="authLead" role="alert">{error}</p>}
    <p className="authSwitch"><Link href="/account">Открыть аккаунт</Link></p>
    <p className="authSwitch"><Link href="/login">Перейти ко входу</Link></p>
  </div></section>
}
