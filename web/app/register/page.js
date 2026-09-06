'use client'

import Link from 'next/link'
import { ArrowRight, Building2, LockKeyhole, Mail, Sparkles, User } from 'lucide-react'

export default function RegisterPage() {
  return (
    <main className="authShell">
      <section className="authBrandPanel">
        <div className="brand authBrand"><div className="brandMark"><Sparkles size={20}/></div><div><strong>Marketplace AI</strong><span>Studio Cloud</span></div></div>
        <div className="authPitch"><span className="eyebrow">СТАРТ ЗА НЕСКОЛЬКО МИНУТ</span><h1>Создайте свой AI-центр управления продажами.</h1><p>Сначала аккаунт и рабочее пространство. WB/Ozon подключим отдельным безопасным шагом после входа.</p><div className="trialBadge">14 дней Trial · без привязки карты на старте</div></div>
      </section>
      <section className="authFormPanel"><div className="authCard"><span className="eyebrow">НОВЫЙ АККАУНТ</span><h2>Регистрация</h2><p className="authLead">Создайте владельца и первое рабочее пространство.</p>
        <form onSubmit={(e) => e.preventDefault()}>
          <label>Ваше имя<div className="authInput"><User size={18}/><input placeholder="Имя" required/></div></label>
          <label>Название компании / магазина<div className="authInput"><Building2 size={18}/><input placeholder="Мой магазин" required/></div></label>
          <label>Email<div className="authInput"><Mail size={18}/><input type="email" placeholder="you@company.ru" required/></div></label>
          <label>Пароль<div className="authInput"><LockKeyhole size={18}/><input type="password" minLength={8} placeholder="Минимум 8 символов" required/></div></label>
          <label className="check terms"><input type="checkbox" required/> Я принимаю условия сервиса и политику конфиденциальности</label>
          <button className="authPrimary" type="submit">Создать аккаунт <ArrowRight size={18}/></button>
        </form>
        <p className="authSwitch">Уже есть аккаунт? <Link href="/login">Войти</Link></p><Link className="authBack" href="/">← Вернуться на главную</Link>
      </div></section>
    </main>
  )
}
