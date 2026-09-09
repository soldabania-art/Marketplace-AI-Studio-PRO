'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { Suspense, useState } from 'react'
import { ArrowLeft, CreditCard, LockKeyhole } from 'lucide-react'

const plans={pro:{name:'PRO',price:'4 990 ₽',period:'месяц'},business:{name:'Business',price:'12 990 ₽',period:'месяц'}}

function CheckoutForm(){
 const params=useSearchParams(); const requested=params.get('plan')||'pro'; const code=plans[requested]?requested:'pro'; const plan=plans[code]; const [accepted,setAccepted]=useState(false); const [message,setMessage]=useState(''); const [busy,setBusy]=useState(false)
 async function pay(){
   setBusy(true);setMessage('')
   try{
     const response=await fetch('/api/billing/checkout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan_code:code,accepted_terms:accepted})})
     const payload=await response.json()
     if(!response.ok) throw new Error(payload.error||'Не удалось начать оплату')
     if(!payload.checkout_url) throw new Error('Платёжный провайдер не вернул защищённую страницу оплаты.')
     window.location.assign(payload.checkout_url)
   }catch(error){setMessage(error.message)}finally{setBusy(false)}
 }
 return <main className="checkoutPage"><div className="checkoutWrap"><div className="workHead"><Link href="/pricing" className="ghostBtn"><ArrowLeft size={16}/> Тарифы</Link><span className="checkoutSecure"><LockKeyhole size={15}/> Безопасная оплата</span></div><section className="checkoutCard"><span className="eyebrow">ОФОРМЛЕНИЕ ПОДПИСКИ</span><h1>{plan.name}</h1><div className="checkoutPrice">{plan.price}<small> / {plan.period}</small></div><div className="checkoutSummary"><div><span>Тариф</span><strong>{plan.name}</strong></div><div><span>Списание</span><strong>ежемесячно</strong></div><div><span>К оплате сейчас</span><strong>{plan.price}</strong></div></div><label className="checkoutConsent"><input type="checkbox" checked={accepted} onChange={e=>setAccepted(e.target.checked)}/> Я принимаю условия подписки, оферту и правила автоматического продления.</label><button className="payBtn" disabled={!accepted||busy} onClick={pay}><CreditCard size={18}/> {busy?'Открываем защищённую оплату…':'Перейти к оплате'}</button>{message&&<div className="checkoutMessage" role="alert">{message}</div>}<p className="checkoutNote">TROVENDI не хранит данные банковской карты. Платные права включаются только после подтверждения платежа сервером провайдера.</p></section></div></main>
}

export default function CheckoutPage(){return <Suspense fallback={<main className="checkoutPage"><div className="checkoutWrap"><div className="checkoutCard">Загружаем оформление оплаты…</div></div></main>}><CheckoutForm/></Suspense>}
