'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'

const STORAGE_KEY = 'mai_cookie_consent_v1'

export default function CookieConsent() {
  const [visible, setVisible] = useState(false)
  const [settings, setSettings] = useState(false)
  const [analytics, setAnalytics] = useState(false)
  const [marketing, setMarketing] = useState(false)

  useEffect(() => {
    try { setVisible(!localStorage.getItem(STORAGE_KEY)) } catch { setVisible(true) }
  }, [])

  function save(value) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, at: new Date().toISOString(), ...value })) } catch {}
    setVisible(false)
  }

  if (!visible) return null

  return <div className="cookieBanner" role="dialog" aria-label="Настройки cookie">
    <div className="cookieCopy"><strong>Настройки cookie</strong><p>Мы используем обязательные cookie для входа и безопасности. Аналитические и маркетинговые cookie включаются только с вашего согласия. Подробнее — в <Link href="/legal/cookies">политике cookie</Link>.</p></div>
    {settings && <div className="cookieSettings">
      <label><input type="checkbox" checked disabled/> Обязательные <small>Всегда включены</small></label>
      <label><input type="checkbox" checked={analytics} onChange={e=>setAnalytics(e.target.checked)}/> Аналитика</label>
      <label><input type="checkbox" checked={marketing} onChange={e=>setMarketing(e.target.checked)}/> Маркетинг</label>
    </div>}
    <div className="cookieActions">
      <button className="ghostBtn" onClick={()=>setSettings(v=>!v)}>{settings?'Скрыть настройки':'Настроить'}</button>
      <button className="ghostBtn" onClick={()=>save({analytics:false,marketing:false})}>Только обязательные</button>
      {settings && <button className="ghostBtn" onClick={()=>save({analytics,marketing})}>Сохранить выбор</button>}
      <button className="primaryBtn" onClick={()=>save({analytics:true,marketing:true})}>Принять все</button>
    </div>
  </div>
}
