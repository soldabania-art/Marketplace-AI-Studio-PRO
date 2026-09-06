import Link from 'next/link'
import { Check, Sparkles } from 'lucide-react'

const plans = [
  { code:'trial', name: 'Trial', price: '0 ₽', note: '14 дней', features: ['1 магазин', '1 пользователь', 'AI-рекомендации', 'Базовая аналитика'] },
  { code:'pro', name: 'PRO', price: '4 990 ₽', note: 'в месяц', featured: true, features: ['До 3 магазинов', 'До 3 пользователей', 'Расширенный AI', 'AI Card Factory', 'Profit Center', 'Assisted Autopilot'] },
  { code:'business', name: 'Business', price: '12 990 ₽', note: 'в месяц', features: ['До 10 магазинов', 'До 10 пользователей', 'Приоритетный AI', 'Расширенный автопилот', 'Командные роли', 'Расширенные отчёты'] },
]

export default function PricingPage() {
  return <main className="pricingPage"><div className="pricingWrap">
    <Link href="/" className="brand pricingBrand"><div className="brandMark"><Sparkles size={20}/></div><div><strong>Marketplace AI</strong><span>Studio Cloud</span></div></Link>
    <div className="pricingHero"><span className="eyebrow">ТАРИФЫ</span><h1>Выберите масштаб автоматизации</h1><p>Trial можно запустить без оплаты. PRO и Business ведут на оформление подписки и затем на защищённую страницу платёжного провайдера.</p></div>
    <section className="pricingGrid">{plans.map(plan => <article key={plan.name} className={`pricingCard ${plan.featured?'featured':''}`}><span className="eyebrow">{plan.featured?'РЕКОМЕНДУЕМ':'ТАРИФ'}</span><h2>{plan.name}</h2><div className="pricingPrice">{plan.price}</div><div className="pricingNote">{plan.note}</div><div className="pricingFeatures">{plan.features.map(item=><div key={item}><Check size={16}/>{item}</div>)}</div>{plan.code==='trial'?<Link className="pricingButton secondary" href="/register">Начать Trial</Link>:<Link className="pricingButton" href={`/checkout?plan=${plan.code}`}>Выбрать {plan.name}</Link>}</article>)}</section>
    <p className="pricingBack"><Link href="/account">← Вернуться в личный кабинет</Link></p>
  </div></main>
}
