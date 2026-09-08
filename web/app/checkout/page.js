'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { Suspense, useState } from 'react'
import { ArrowLeft, CreditCard, LockKeyhole } from 'lucide-react'

const plans={pro:{name:'PRO',price:'4 990 ₽',period:'месяц'},business:{name:'Business',price:'12 990 ₽',period:'месяц'}}

function CheckoutForm(){
 const params=useSearchParams(); const code=params.get('plan')||'pro'; const plan=plans[code]||plans.pro; const [accepted,setAccepted]=useState(false); const [message,setMessage]=useState('')
 function pay(){
   const url=code==='business'?process.env.NEXT_PUBLIC_PAYMENT_BUSINESS_URL:process.env.NEXT_PUBLIC_PAYMENT_PRO_URL
   if(url){window.location.href=url;return}
   setMessage('Платёжный провайдер ещё не подключён. После добавления production-ссылки эта кнопка сразу будет переводить клиента на защищённую оплату.')
 }
 return <main className="checkoutPage"><div className="checkoutWrap"><div className="workHead"><Link href="/pricing" className="ghostBtn"><ArrowLeft size={16}/> Тарифы</Link><span className="checkoutSecure"><LockKeyhole size={15}/> Безопасная оплата</span></div><section className="checkoutCard"><span className="eyebrow">ОФОРМЛЕНИЕ ПОДПИСКИ</span><h1>{plan.name}</h1><div className="checkoutPrice">{plan.price}<small> / {plan.period}</small></div><div className="checkoutSummary"><div><span>Тариф</span><strong>{plan.name}</strong></div><div><span>Списание</span><strong>ежемесячно</strong></div><div><span>К оплате сейчас</span><strong>{plan.price}</strong></div></div><label className="checkoutConsent"><input type="checkbox" checked={accepted} onChange={e=>setAccepted(e.target.checked)}/> Я принимаю условия подписки, оферту и правила автоматического продления.</label><button className="payBtn" disabled={!accepted} onClick={pay}><CreditCard size={18}/> Перейти к оплате</button>{message&&<div className="checkoutMessage">{message}</div>}<p className="checkoutNote">TROVENDI не хранит данные банковской карты. Оплата должна проходить на стороне подключённого платёжного провайдера.</p></section></div></main>
}

export default function CheckoutPage(){return <Suspense fallback={<main className="checkoutPage"><div className="checkoutWrap"><div className="checkoutCard">Загружаем оформление оплаты…</div></div></main>}><CheckoutForm/></Suspense>}
