'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { Building2, CreditCard, KeyRound, Laptop, LogOut, MailCheck, Plus, ShieldCheck, Store as StoreIcon, Unplug, UserRound } from 'lucide-react'
import { getActiveStoreId, setActiveStoreId, STORE_EVENT } from '../../lib/useActiveStore'
import BrandLogo from '../../components/BrandLogo'
import styles from './page.module.css'

const eventNames = { login:'Вход', logout:'Выход', registration:'Регистрация', session_created:'Создана сессия', session_revoked:'Сессия завершена', mfa_challenge_created:'Запрошен второй фактор', mfa_login:'Проверка второго фактора', mfa_setup:'Настройка MFA', mfa_confirm:'Подтверждение MFA', mfa_enabled:'MFA включена', mfa_disable:'Отключение MFA', mfa_disabled:'MFA отключена', step_up:'Повторное подтверждение личности' }
const fmt = (value) => value ? new Date(value).toLocaleString('ru-RU') : '—'

export default function AccountPage() {
  const router = useRouter()
  const [account, setAccount] = useState(null)
  const [billing,setBilling]=useState(null)
  const [security, setSecurity] = useState({ sessions: [], events: [] })
  const [storesData,setStoresData]=useState({stores:[],workspaces:[]})
  const [selectedStoreId,setSelectedStoreId]=useState('')
  const [wb,setWb]=useState({connected:false})
  const [newStore,setNewStore]=useState({name:'',client_name:''})
  const [wbToken,setWbToken]=useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy,setBusy]=useState('')
  const [verifyMessage, setVerifyMessage] = useState('')
  const [verifyLoading, setVerifyLoading] = useState(false)
  const [mfa,setMfa]=useState({enabled:false,setup_pending:false,recovery_codes_remaining:0,current_session_verified:false})
  const [mfaForm,setMfaForm]=useState({password:'',code:''})
  const [mfaSecret,setMfaSecret]=useState('')
  const [recoveryCodes,setRecoveryCodes]=useState([])
  const [stepUp,setStepUp]=useState({verified:false,valid_until:null,mfa_required:false,lifetime_minutes:10})
  const [stepUpForm,setStepUpForm]=useState({password:'',code:''})

  async function loadSecurity() {
    const response = await fetch('/api/auth/security', { cache:'no-store' })
    const payload = await response.json()
    if (!response.ok) throw new Error(payload.error || 'Не удалось загрузить безопасность')
    setSecurity(payload)
  }

  async function loadMfa(){
    const response=await fetch('/api/auth/mfa',{cache:'no-store'}); const payload=await response.json()
    if(!response.ok) throw new Error(payload.error||'Не удалось загрузить MFA')
    setMfa(payload)
  }

  async function loadStepUp(){
    const response=await fetch('/api/auth/step-up',{cache:'no-store'}); const payload=await response.json()
    if(!response.ok) throw new Error(payload.error||'Не удалось проверить подтверждение личности')
    setStepUp(payload)
  }

  async function loadStores(){
    const response=await fetch('/api/stores',{cache:'no-store'})
    const payload=await response.json()
    if(!response.ok) throw new Error(payload.error||'Не удалось загрузить магазины')
    setStoresData(payload)
    const saved=getActiveStoreId()
    const next=payload.stores.find(x=>x.id===saved)?.id||payload.stores[0]?.id||''
    setSelectedStoreId(next)
    if(next&&next!==saved) setActiveStoreId(next)
    return next
  }

  async function loadWb(storeId){
    if(!storeId){setWb({connected:false});return}
    const response=await fetch(`/api/marketplace/wildberries?store_id=${encodeURIComponent(storeId)}`,{cache:'no-store'})
    const payload=await response.json()
    if(!response.ok) throw new Error(payload.error||'Не удалось проверить WB')
    setWb(payload)
  }

  useEffect(() => {
    let active = true
    Promise.all([
      fetch('/api/auth/me', { cache:'no-store' }).then(async r => { const p=await r.json(); if(!r.ok) throw new Error(p.error || 'Не удалось загрузить аккаунт'); if(active) setAccount(p) }),
      fetch('/api/billing/subscription', { cache:'no-store' }).then(async r => { const p=await r.json(); if(!r.ok) throw new Error(p.error || 'Не удалось загрузить тариф'); if(active) setBilling(p) }),
      loadSecurity(),
      loadMfa(),
      loadStepUp(),
      loadStores().then(id=>id?loadWb(id):null),
    ]).catch(e => { if(active){ setError(e.message); if(e.message === 'Требуется вход') router.replace('/login') } }).finally(() => active && setLoading(false))
    return () => { active=false }
  }, [router])

  useEffect(()=>{
    let alive=true
    async function syncStore(event){
      const next=event?.detail?.store_id||getActiveStoreId()
      if(!next||next===selectedStoreId||!storesData.stores.some(store=>store.id===next)) return
      setSelectedStoreId(next); setError(''); setBusy('switch')
      try{await loadWb(next)}catch(e){if(alive)setError(e.message)}finally{if(alive)setBusy('')}
    }
    window.addEventListener(STORE_EVENT,syncStore)
    return()=>{alive=false;window.removeEventListener(STORE_EVENT,syncStore)}
  },[selectedStoreId,storesData.stores])

  async function chooseStore(id){
    setSelectedStoreId(id); setError(''); setBusy('switch')
    setActiveStoreId(id)
    try{await loadWb(id)}catch(e){setError(e.message)}finally{setBusy('')}
  }

  async function createStore(e){
    e.preventDefault(); setError(''); setBusy('create-store')
    const workspace=storesData.workspaces.find(x=>x.can_manage_stores)||storesData.workspaces[0]
    if(!workspace){setError('Нет рабочего пространства для создания магазина.');setBusy('');return}
    try{
      const response=await fetch('/api/stores',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({workspace_id:workspace.id,...newStore})})
      const payload=await response.json(); if(!response.ok) throw new Error(payload.error||'Не удалось создать магазин')
      setNewStore({name:'',client_name:''}); await loadStores(); await chooseStore(payload.id)
    }catch(e){setError(e.message)}finally{setBusy('')}
  }

  async function connectWb(e){
    e.preventDefault(); if(!selectedStoreId)return
    setError(''); setBusy('wb')
    try{
      const response=await fetch('/api/marketplace/wildberries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({store_id:selectedStoreId,token:wbToken})})
      const payload=await response.json(); if(!response.ok) throw new Error(payload.error||'Не удалось подключить WB')
      setWb(payload); setWbToken('')
    }catch(e){setError(e.message)}finally{setBusy('')}
  }

  async function disconnectWb(){
    if(!selectedStoreId)return; setError(''); setBusy('wb')
    try{
      const response=await fetch(`/api/marketplace/wildberries?store_id=${encodeURIComponent(selectedStoreId)}`,{method:'DELETE'})
      const payload=await response.json(); if(!response.ok) throw new Error(payload.error||'Не удалось отключить WB')
      setWb({connected:false})
    }catch(e){setError(e.message)}finally{setBusy('')}
  }

  async function logout() { await fetch('/api/auth/logout', { method:'POST' }); router.replace('/login'); router.refresh() }
  async function revoke(id, current) {
    const response = await fetch('/api/auth/security', { method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:id}) })
    const payload = await response.json(); if(!response.ok){ setError(payload.error || 'Не удалось завершить сессию'); return }
    if(current){ router.replace('/login'); router.refresh(); return }
    await loadSecurity()
  }
  async function requestVerification() {
    setVerifyLoading(true); setVerifyMessage('')
    try { const response=await fetch('/api/auth/email-verification',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'request'})}); const payload=await response.json(); if(!response.ok) throw new Error(payload.error || 'Не удалось отправить подтверждение'); setVerifyMessage(payload.delivery==='email_provider_not_configured'?'Подтверждение подготовлено. Почтовый провайдер подключим перед запуском.':'Письмо с подтверждением отправлено.') } catch(e){ setVerifyMessage(e.message) } finally { setVerifyLoading(false) }
  }

  async function mfaAction(action){
    setError('');setBusy(`mfa-${action}`)
    try{
      const body={action}
      if(action==='setup'||action==='disable') body.password=mfaForm.password
      if(action==='confirm'||action==='disable') body.code=mfaForm.code
      const response=await fetch('/api/auth/mfa',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
      const payload=await response.json(); if(!response.ok) throw new Error(payload.error||'Операция MFA не выполнена')
      if(action==='setup'){setMfaSecret(payload.secret);setMfa({...mfa,setup_pending:true});setMfaForm({...mfaForm,code:''})}
      if(action==='confirm'){setRecoveryCodes(payload.recovery_codes||[]);setMfaSecret('');setMfaForm({password:'',code:''});await loadMfa();await loadSecurity()}
      if(action==='disable'){setRecoveryCodes([]);setMfaForm({password:'',code:''});await loadMfa();await loadSecurity()}
    }catch(e){setError(e.message)}finally{setBusy('')}
  }

  async function verifySensitiveActions(e){
    e.preventDefault();setError('');setBusy('step-up')
    try{
      const response=await fetch('/api/auth/step-up',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(stepUpForm)})
      const payload=await response.json();if(!response.ok)throw new Error(payload.error||'Не удалось подтвердить личность')
      setStepUpForm({password:'',code:''});await loadStepUp();await loadSecurity()
    }catch(e){setError(e.message)}finally{setBusy('')}
  }

  const selectedStore=storesData.stores.find(x=>x.id===selectedStoreId)

  return <main className={styles.shell}>
    <header className={styles.topbar}><Link href="/" aria-label="TROVENDI"><BrandLogo className={styles.brand} /></Link><div className={styles.topActions}>{account?.is_platform_admin&&<Link href="/admin" className={styles.action}>Админ-панель</Link>}<button className={styles.logout} onClick={logout}><LogOut size={17}/> Выйти</button></div></header>
    <section className={styles.content}><div className={styles.heading}><span className="eyebrow">ЛИЧНЫЙ КАБИНЕТ</span><h1>Аккаунт, магазины и безопасность</h1><p>Один аккаунт может управлять несколькими магазинами и клиентами агентства.</p></div>
    {loading&&<div className={styles.notice}>Загружаем данные аккаунта…</div>}{error&&<div className={`${styles.notice} ${styles.error}`}>{error}</div>}
    {account&&<>
    <section className={styles.storeSection}><div className={styles.sectionHead}><div><span className="eyebrow">МАГАЗИНЫ</span><h2>Выбранный магазин</h2></div><StoreIcon size={22}/></div>
      <div className={styles.storeToolbar}><select value={selectedStoreId} onChange={e=>chooseStore(e.target.value)} disabled={busy==='switch'}><option value="">Выберите магазин</option>{storesData.stores.map(s=><option value={s.id} key={s.id}>{s.client_name?`${s.client_name} · `:''}{s.name}</option>)}</select><span>{selectedStore?`Рабочий магазин: ${selectedStore.name}`:'Магазин ещё не выбран'}</span></div>
      <form className={styles.inlineForm} onSubmit={createStore}><input value={newStore.name} onChange={e=>setNewStore({...newStore,name:e.target.value})} placeholder="Название магазина" minLength={2} required/><input value={newStore.client_name} onChange={e=>setNewStore({...newStore,client_name:e.target.value})} placeholder="Клиент / бренд (необязательно)"/><button className={styles.action} disabled={busy==='create-store'}><Plus size={15}/>{busy==='create-store'?'Создаём…':'Добавить магазин'}</button></form>
    </section>

    <section className={styles.storeSection}><div className={styles.sectionHead}><div><span className="eyebrow">ИНТЕГРАЦИЯ</span><h2>Wildberries</h2></div><KeyRound size={22}/></div>
      {!selectedStore?<div className={styles.notice}>Сначала выберите или создайте магазин.</div>:wb.connected?<div className={styles.connectionOk}><div><strong>Wildberries подключён</strong><span>Токен хранится на сервере в зашифрованном виде и не возвращается в интерфейс</span></div><button className={styles.danger} onClick={disconnectWb} disabled={busy==='wb'}><Unplug size={15}/> Отключить</button></div>:<form className={styles.inlineForm} onSubmit={connectWb}><input type="password" value={wbToken} onChange={e=>setWbToken(e.target.value)} placeholder="API-токен Wildberries" minLength={20} required autoComplete="off"/><button className={styles.action} disabled={busy==='wb'}>{busy==='wb'?'Проверяем…':'Проверить и подключить WB'}</button></form>}
      <small className={styles.help}>Токен отправляется только на backend, проверяется запросом к WB и сохраняется зашифрованно. В интерфейсе полный токен больше не показывается.</small>
    </section>

    <div className={styles.grid}>
      <article className={styles.card}><div className={styles.icon}><UserRound size={20}/></div><span className="eyebrow">ПРОФИЛЬ</span><h3>{account.full_name}</h3><p>{account.email}</p><small>{account.email_verified?'Email подтверждён':'Email ожидает подтверждения'}</small>{!account.email_verified&&<button className={styles.action} onClick={requestVerification} disabled={verifyLoading}><MailCheck size={15}/> {verifyLoading?'Подготавливаем…':'Подтвердить email'}</button>}{verifyMessage&&<small className={styles.message}>{verifyMessage}</small>}</article>
      <article className={styles.card}><div className={styles.icon}><Building2 size={20}/></div><span className="eyebrow">РАБОЧЕЕ ПРОСТРАНСТВО</span><h3>{account.workspace_name}</h3><p>Роль: {account.role}</p><small>Магазинов доступно: {storesData.stores.length}</small></article>
      <article className={`${styles.card} ${styles.plan}`}><div className={styles.icon}><CreditCard size={20}/></div><span className="eyebrow">ТАРИФ</span><h3>{String(billing?.plan||account.plan_code).toUpperCase()}</h3><p>{!billing?'Загружаем статус тарифа…':billing.plan==='trial'?(billing.access_status==='not_started'?'3 дня начнутся с первой успешной карточки':`Осталось карточек: ${billing.cards_remaining} из ${billing.cards_limit}`):billing.read_only?'Подписка завершена · режим просмотра':billing.cancel_at_period_end?'Активен до конца оплаченного периода':'Подписка активна'}</p><small>{!billing?'Проверяем серверные права':billing.expires_at?`Доступ до: ${fmt(billing.expires_at)}`:billing.checkout_available?'Платёжный провайдер подключён':'Оплата пока не подключена — Trial работает без карты'}</small><Link href="/pricing" className={styles.action}>Управлять тарифом</Link></article>
      <article className={styles.card}><div className={styles.icon}><ShieldCheck size={20}/></div><span className="eyebrow">ЗАЩИТА</span><h3>Серверные сессии</h3><p>Каждый вход имеет отдельную отзывную серверную сессию. После смены пароля все устройства отключаются.</p><small>IP хранится только в виде приватного хэша</small></article>
    </div>
    <section className={styles.securitySection}><div className={styles.sectionHead}><div><span className="eyebrow">ДВУХФАКТОРНАЯ ЗАЩИТА</span><h2>Приложение-аутентификатор</h2></div><KeyRound size={22}/></div>
      {recoveryCodes.length>0?<div className={styles.recoveryBox}><strong>Сохраните резервные коды сейчас</strong><p>Каждый код работает один раз. После закрытия страницы TROVENDI больше их не покажет.</p><div className={styles.codeGrid}>{recoveryCodes.map(code=><code key={code}>{code}</code>)}</div></div>:mfa.enabled?<><div className={styles.connectionOk}><div><strong>MFA включена</strong><span>Текущая сессия подтверждена · резервных кодов: {mfa.recovery_codes_remaining}</span></div></div><form className={styles.inlineForm} onSubmit={e=>{e.preventDefault();mfaAction('disable')}}><input type="password" value={mfaForm.password} onChange={e=>setMfaForm({...mfaForm,password:e.target.value})} placeholder="Текущий пароль" autoComplete="current-password" required/><input value={mfaForm.code} onChange={e=>setMfaForm({...mfaForm,code:e.target.value})} placeholder="Код MFA или резервный код" autoComplete="one-time-code" required/><button className={styles.danger} disabled={busy==='mfa-disable'}>{busy==='mfa-disable'?'Проверяем…':'Отключить MFA'}</button></form></>:mfaSecret?<><div className={styles.setupBox}><strong>1. Добавьте TROVENDI в приложение-аутентификатор</strong><p>Введите секрет вручную. Не отправляйте его и не сохраняйте в облачных заметках.</p><code>{mfaSecret}</code></div><form className={styles.inlineForm} onSubmit={e=>{e.preventDefault();mfaAction('confirm')}}><input value={mfaForm.code} onChange={e=>setMfaForm({...mfaForm,code:e.target.value})} placeholder="2. Введите шестизначный код" inputMode="numeric" autoComplete="one-time-code" minLength={6} maxLength={6} required/><button className={styles.action} disabled={busy==='mfa-confirm'}>{busy==='mfa-confirm'?'Проверяем…':'Подтвердить и включить'}</button></form></>:<><p className={styles.sectionCopy}>При каждом новом входе потребуется одноразовый код. Для административных операций MFA обязательна.</p><form className={styles.inlineForm} onSubmit={e=>{e.preventDefault();mfaAction('setup')}}><input type="password" value={mfaForm.password} onChange={e=>setMfaForm({...mfaForm,password:e.target.value})} placeholder="Текущий пароль" autoComplete="current-password" required/><button className={styles.action} disabled={busy==='mfa-setup'}>{busy==='mfa-setup'?'Подготавливаем…':'Настроить MFA'}</button></form></>}
    </section>
    <section className={styles.securitySection}><div className={styles.sectionHead}><div><span className="eyebrow">ЧУВСТВИТЕЛЬНЫЕ ДЕЙСТВИЯ</span><h2>Повторное подтверждение личности</h2></div><ShieldCheck size={22}/></div>
      {stepUp.verified?<div className={styles.connectionOk}><div><strong>Подтверждение активно</strong><span>Можно выполнять защищённые действия до {fmt(stepUp.valid_until)}</span></div></div>:<><p className={styles.sectionCopy}>Подтверждение действует {stepUp.lifetime_minutes} минут и требуется для изменения API-ключей, публикаций в маркетплейс и административных изменений.</p><form className={styles.inlineForm} onSubmit={verifySensitiveActions}><input type="password" value={stepUpForm.password} onChange={e=>setStepUpForm({...stepUpForm,password:e.target.value})} placeholder="Текущий пароль" autoComplete="current-password" required/>{stepUp.mfa_required&&<input value={stepUpForm.code} onChange={e=>setStepUpForm({...stepUpForm,code:e.target.value})} placeholder="Новый код MFA или резервный код" autoComplete="one-time-code" required/>}<button className={styles.action} disabled={busy==='step-up'}>{busy==='step-up'?'Проверяем…':`Подтвердить на ${stepUp.lifetime_minutes} минут`}</button></form></>}
    </section>
    <section className={styles.securitySection}><div className={styles.sectionHead}><div><span className="eyebrow">УСТРОЙСТВА</span><h2>Активные сессии</h2></div><Laptop size={22}/></div><div className={styles.list}>{security.sessions.map(s=><div className={styles.row} key={s.id}><div><strong>{s.current?'Это устройство':'Другое устройство'} {s.revoked&&'· завершена'}</strong><span>{s.user_agent || 'Браузер не определён'}</span><small>Последняя активность: {fmt(s.last_seen_at)} · истекает: {fmt(s.expires_at)}</small></div>{!s.revoked&&<button className={styles.danger} onClick={()=>revoke(s.id,s.current)}>{s.current?'Выйти здесь':'Завершить'}</button>}</div>)}</div></section>
    <section className={styles.securitySection}><div className={styles.sectionHead}><div><span className="eyebrow">ЖУРНАЛ</span><h2>Последние события безопасности</h2></div><ShieldCheck size={22}/></div><div className={styles.list}>{security.events.slice(0,20).map((e,i)=><div className={styles.event} key={`${e.created_at}-${i}`}><span className={e.success?styles.ok:styles.bad}>{e.success?'OK':'!'}</span><div><strong>{eventNames[e.event_type] || e.event_type}</strong><small>{fmt(e.created_at)} · {e.user_agent || 'устройство не определено'}</small></div></div>)}</div></section></>}
    </section>
  </main>
}
