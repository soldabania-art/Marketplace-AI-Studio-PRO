import Link from 'next/link'
import { Check } from 'lucide-react'
import BrandLogo from '../../components/BrandLogo'

const plans = [
  { code:'trial', name: 'Пробный запуск', price: '0 ₽', note: '3 дня с первого AI-анализа', features: ['До 5 текстовых карточек', '1 магазин и 1 пользователь', 'Фото, тексты, SEO и экономика', 'Без генерации изображений, публикации и автодействий'] },
  { code:'pro', name: 'PRO', price: '4 990 ₽', note: 'в месяц', featured: true, features: ['До 3 магазинов', 'До 3 пользователей', 'Расширенный AI', 'AI Card Factory', 'Profit Center', 'Закрытый форум TROVENDI', 'Assisted Autopilot'] },
  { code:'business', name: 'Business', price: '12 990 ₽', note: 'в месяц', features: ['До 10 магазинов', 'До 10 пользователей', 'Приоритетный AI', 'Расширенный автопилот', 'Командные роли', 'Расширенные отчёты', 'Закрытый форум TROVENDI'] },
]

export default function PricingPage() {
  return <main className="pricingPage"><div className="pricingWrap">
    <Link href="/" aria-label="TROVENDI"><BrandLogo className="pricingBrand" /></Link>
    <div className="pricingHero"><span className="eyebrow">ТАРИФЫ</span><h1>Выберите масштаб автоматизации</h1><p>Пробный запуск начинается с первого успешного AI-анализа и не требует оплаты. PRO и Business ведут на оформление подписки через защищённого платёжного провайдера.</p></div>
    <section className="pricingGrid">{plans.map(plan => <article key={plan.name} className={`pricingCard ${plan.featured?'featured':''}`}><span className="eyebrow">{plan.featured?'РЕКОМЕНДУЕМ':'ТАРИФ'}</span><h2>{plan.name}</h2><div className="pricingPrice">{plan.price}</div><div className="pricingNote">{plan.note}</div><div className="pricingFeatures">{plan.features.map(item=><div key={item}><Check size={16}/>{item}</div>)}</div>{plan.code==='trial'?<Link className="pricingButton secondary" href="/register">Начать бесплатно</Link>:<Link className="pricingButton" href={`/checkout?plan=${plan.code}`}>Выбрать {plan.name}</Link>}</article>)}</section>
    <p className="pricingBack"><Link href="/account">← Вернуться в личный кабинет</Link></p>
  </div></main>
}
