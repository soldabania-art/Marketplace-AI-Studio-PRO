'use client'

import Link from 'next/link'
import { ArrowRight, Mail, Sparkles } from 'lucide-react'

export default function ForgotPasswordPage() {
  return <main className="authShell simpleAuth"><section className="authFormPanel"><div className="authCard"><div className="brand authMiniBrand"><div className="brandMark"><Sparkles size={20}/></div><div><strong>Marketplace AI</strong><span>Studio Cloud</span></div></div><span className="eyebrow">ВОССТАНОВЛЕНИЕ ДОСТУПА</span><h2>Забыли пароль?</h2><p className="authLead">Введите email аккаунта. Мы отправим безопасную ссылку для создания нового пароля.</p><form onSubmit={(e)=>e.preventDefault()}><label>Email<div className="authInput"><Mail size={18}/><input type="email" placeholder="you@company.ru" required/></div></label><button className="authPrimary" type="submit">Отправить ссылку <ArrowRight size={18}/></button></form><p className="authSwitch"><Link href="/login">← Вернуться ко входу</Link></p></div></section></main>
}
