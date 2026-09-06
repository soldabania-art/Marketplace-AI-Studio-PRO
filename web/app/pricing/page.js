import Link from 'next/link'
import { Check, Sparkles } from 'lucide-react'

const plans = [
  { name: 'Trial', price: '0 ₽', note: '14 дней', features: ['1 магазин', '1 пользователь', 'AI-рекомендации', 'Базовая аналитика'] },
  { name: 'PRO', price: '4 990 ₽', note: 'в месяц', featured: true, features: ['До 3 магазинов', 'До 3 пользователей', 'Расширенный AI', 'AI Card Factory', 'Profit Center', 'Assisted Autopilot'] },
  { name: 'Business', price: '12 990 ₽', note: 'в месяц', features: ['До 10 магазинов', 'До 10 пользователей', 'Приоритетный AI', 'Расширенный автопилот', 'Командные роли', 'Расширенные отчёты'] },
]

export default function PricingPage() {
  return <main style={{minHeight:'100vh',padding:'48px 24px',background:'radial-gradient(circle at 50% 0%,rgba(91,168,255,.1),transparent 30%),#07111f'}}>
    <div style={{maxWidth:1180,margin:'0 auto'}}>
      <Link href="/" className="brand" style={{padding:0,display:'inline-flex'}}><div className="brandMark"><Sparkles size={20}/></div><div><strong>Marketplace AI</strong><span>Studio Cloud</span></div></Link>
      <div style={{textAlign:'center',maxWidth:720,margin:'64px auto 36px'}}><span className="eyebrow">ТАРИФЫ</span><h1 style={{fontSize:42,letterSpacing:'-.04em',margin:'10px 0'}}>Выберите масштаб автоматизации</h1><p style={{color:'#8ea0b8',lineHeight:1.6}}>Оплата пока не активирована. Тарифы уже заложены в систему, подключение платёжного провайдера будет отдельным production-этапом.</p></div>
      <section style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(250px,1fr))',gap:16}}>
        {plans.map(plan => <article key={plan.name} style={{border:`1px solid ${plan.featured?'rgba(159,122,234,.45)':'#1c2a3f'}`,borderRadius:20,padding:26,background:plan.featured?'linear-gradient(145deg,rgba(56,43,85,.48),#0d1726)':'#0d1726'}}>
          <span className="eyebrow">{plan.featured?'РЕКОМЕНДУЕМ':'ТАРИФ'}</span><h2 style={{fontSize:24,margin:'8px 0'}}>{plan.name}</h2><div style={{fontSize:34,fontWeight:850,letterSpacing:'-.04em'}}>{plan.price}</div><div style={{color:'#72859d',fontSize:12,marginTop:4}}>{plan.note}</div>
          <div style={{borderTop:'1px solid #1c2a3f',marginTop:22,paddingTop:18,display:'grid',gap:11}}>{plan.features.map(item=><div key={item} style={{display:'flex',alignItems:'center',gap:9,color:'#b7c5d7',fontSize:13}}><Check size={16} color="#42e7a4"/>{item}</div>)}</div>
          <button disabled style={{width:'100%',marginTop:24,padding:'12px 14px',borderRadius:10,border:'1px solid #26364d',background:'#101c2d',color:'#70839a',fontWeight:800}}>Оплата скоро</button>
        </article>)}
      </section>
      <p style={{textAlign:'center',color:'#64778e',fontSize:12,marginTop:28}}><Link href="/account">← Вернуться в личный кабинет</Link></p>
    </div>
  </main>
}
