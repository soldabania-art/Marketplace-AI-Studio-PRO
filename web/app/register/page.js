'use client'

import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense, useState } from 'react'
import { ArrowRight, Building2, LockKeyhole, Mail, User } from 'lucide-react'
import BrandLogo from '../../components/BrandLogo'

const planNames={pro:'PRO',business:'Business'}
const channelNames={wb:'Wildberries',start:'Старт с нуля'}
const moduleNames={cards:'AI Card Factory',profit:'Profit Center',director:'AI Director',fbo:'Smart FBO'}
const interestNames={ozon:'Ozon',yandex:'Яндекс Маркет',kaspi:'Kaspi.kz',uzum:'Uzum Market'}

function RegisterForm() {
  const router = useRouter()
  const params = useSearchParams()
  const plan = planNames[params.get('plan')] ? params.get('plan') : 'trial'
  const channel = channelNames[params.get('channel')] ? params.get('channel') : 'start'
  const stores = ['1','3','10'].includes(params.get('stores')) ? params.get('stores') : '1'
  const selectedModules = (params.get('modules')||'').split(',').filter(code=>moduleNames[code])
  const interest = interestNames[params.get('interest')] ? params.get('interest') : ''
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setError('')
    setLoading(true)
    const form = new FormData(event.currentTarget)

    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: form.get('full_name'),
          workspace_name: form.get('workspace_name'),
          email: form.get('email'),
          password: form.get('password'),
        }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'Не удалось создать аккаунт')
      router.push(plan==='trial'?'/account?setup=mfa':`/checkout?plan=${plan}&next=mfa`)
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
        <BrandLogo className="authBrand" />
        <div className="authPitch"><span className="eyebrow">СТАРТ ЗА НЕСКОЛЬКО МИНУТ</span><h1>Создайте свой AI-центр управления продажами.</h1><p>Сначала защищённый аккаунт. API-ключи магазина можно добавить только после входа и настройки MFA.</p><div className="trialBadge">{plan==='trial'?'3 дня Trial · до 5 карточек · без привязки карты':`${planNames[plan]} · до ${stores} магазинов · форум включён`}</div></div>
      </section>
      <section className="authFormPanel"><div className="authCard"><span className="eyebrow">НОВЫЙ АККАУНТ</span><h2>Регистрация</h2><p className="authLead">Создайте владельца и первое рабочее пространство.</p>{plan!=='trial'&&<div className="registrationIntent"><strong>{planNames[plan]} · {channelNames[channel]}</strong><span>{selectedModules.length?selectedModules.map(code=>moduleNames[code]).join(' · '):'Набор функций уточняется'}{interest?` · интерес: ${interestNames[interest]}`:''}</span><small>После регистрации: защищённая оплата → MFA → выбранное пространство.</small></div>}
        <form onSubmit={submit}>
          <label>Ваше имя<div className="authInput"><User size={18}/><input name="full_name" placeholder="Имя" autoComplete="name" required/></div></label>
          <label>Название компании / магазина<div className="authInput"><Building2 size={18}/><input name="workspace_name" placeholder="Мой магазин" required/></div></label>
          <label>Email<div className="authInput"><Mail size={18}/><input name="email" type="email" placeholder="you@company.ru" autoComplete="email" required/></div></label>
          <label>Пароль<div className="authInput"><LockKeyhole size={18}/><input name="password" type="password" minLength={12} maxLength={128} placeholder="Минимум 12 символов" autoComplete="new-password" required/></div></label>
          <label className="check terms"><input type="checkbox" required/> Я принимаю условия сервиса и политику конфиденциальности</label>
          {error && <div className="authError">{error}</div>}
          <button className="authPrimary" type="submit" disabled={loading}>{loading ? 'Создаём аккаунт…' : <>Создать аккаунт <ArrowRight size={18}/></>}</button>
        </form>
        <p className="authSwitch">Уже есть аккаунт? <Link href="/login">Войти</Link></p><Link className="authBack" href="/">← Вернуться на главную</Link>
      </div></section>
    </main>
  )
}

export default function RegisterPage(){
  return <Suspense fallback={<main className="authShell"><section className="authFormPanel"><div className="authCard">Загружаем выбранный набор…</div></section></main>}><RegisterForm/></Suspense>
}
