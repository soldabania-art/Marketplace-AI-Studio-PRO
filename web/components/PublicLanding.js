'use client'

import Link from 'next/link'
import {useEffect,useState} from 'react'
import {ArrowRight,Check,FileCheck2,Gauge,LockKeyhole,Menu,ShieldCheck,Store,Workflow} from 'lucide-react'
import {PUBLIC_CHANNELS,PUBLIC_MODULES,buildRegistrationIntent,planForScale,restorePublicSelection} from '../lib/publicSelection.mjs'

function PublicMark(){
  return <svg className="publicMark" viewBox="0 0 48 48" aria-hidden="true"><path d="M5 8h14l5 8 5-8h14L32 24l11 16H29l-5-8-5 8H5l11-16z"/><circle cx="24" cy="24" r="4"/></svg>
}

function PublicBrand(){
  return <span className="publicBrand"><PublicMark/><span>TROVENDI<small>DECISION PLATFORM</small></span></span>
}

const steps=[
  ['01','Данные магазина','Источники и полнота'],
  ['02','Проблема','Подтверждённый сигнал'],
  ['03','Решение','Выбор владельца'],
  ['04','Выполнение','Только разрешённое действие'],
  ['05','Измерение','Наблюдаемый результат'],
]

const plans=[
  {name:'Пробный запуск',price:'0 ₽',note:'3 дня · до 5 карточек',items:['Один проект магазина','Тексты, SEO и экономика','Без публикации и автодействий'],href:'/register',cta:'Начать бесплатно'},
  {name:'PRO',price:'4 990 ₽',note:'в месяц',items:['До 3 магазинов','AI Card Factory и Profit Center','AI Director с подтверждением'],href:'/pricing',cta:'Посмотреть PRO',featured:true},
  {name:'Business',price:'12 990 ₽',note:'в месяц',items:['До 10 магазинов','Командные роли','Расширенный контроль и отчёты'],href:'/pricing',cta:'Посмотреть Business'},
]

export default function PublicLanding(){
  const [channel,setChannel]=useState('wb')
  const [selectedModules,setSelectedModules]=useState(PUBLIC_MODULES.map(item=>item.code))
  const [scale,setScale]=useState(3)
  const selected=PUBLIC_CHANNELS[channel]
  const recommendedPlan=planForScale[scale]
  const isImplemented=selected.availability==='implemented'
  const intentHref=buildRegistrationIntent({channel:isImplemented?channel:'wb',modules:selectedModules,stores:scale,plan:recommendedPlan,interest:isImplemented?'':channel})

  useEffect(()=>{
    const params=new URLSearchParams(window.location.search)
    if(!['plan','channel','stores','modules','interest'].some(key=>params.has(key)))return
    const restored=restorePublicSelection(params)
    setChannel(restored.channel)
    setSelectedModules(restored.modules)
    setScale(restored.stores)
  },[])

  function toggleModule(code){
    setSelectedModules(current=>current.includes(code)?(current.length===1?current:current.filter(item=>item!==code)):[...current,code])
  }

  return <main className="publicLanding">
    <header className="publicNav">
      <Link href="/" aria-label="TROVENDI — главная"><PublicBrand/></Link>
      <nav aria-label="Публичная навигация"><a href="#capabilities">Возможности</a><a href="#channels">Площадки</a><a href="#bundle">Выбор</a><a href="#pricing">Тарифы</a></nav>
      <div className="publicNavActions"><Link className="publicLogin" href="/login">Войти</Link><a className="publicStart" href="#bundle">Выбрать набор</a></div>
      <details className="publicMenu"><summary aria-label="Открыть меню"><Menu/></summary><div><a href="#capabilities">Возможности</a><a href="#channels">Площадки</a><a href="#bundle">Выбор</a><Link href="/login">Войти</Link></div></details>
    </header>

    <section className="publicHero">
      <div className="publicHeroCopy">
        <span>ДЛЯ ДЕЙСТВУЮЩИХ ПРОДАВЦОВ WILDBERRIES</span>
        <h1>Видеть потери.<br/>Выбирать действие.<br/><em>Доводить до результата.</em></h1>
        <p>TROVENDI собирает подтверждённые данные магазина, показывает ограничения и сохраняет контроль от решения владельца до измерения.</p>
        <div className="publicHeroActions"><a className="publicPrimary" href="#bundle">Выбрать возможности <ArrowRight/></a><Link className="publicSecondary" href="/login">Уже есть аккаунт</Link><span><ShieldCheck/> Выбор не выдаёт права доступа</span></div>
      </div>
      <aside className="publicDecision" aria-label="Как работает контур решения">
        <div><span>TRACE / WB–01</span><b>КОНТУР РЕШЕНИЯ</b></div>
        <small>СЛЕДУЮЩИЙ БЕЗОПАСНЫЙ ШАГ</small>
        <strong>Проверить данные</strong>
        <p>Сначала полнота источников, затем предложение и отдельное подтверждение владельца.</p>
        <dl><div><dt>Данные</dt><dd>Проверяются</dd></div><div><dt>Действие</dt><dd>Не отправлено</dd></div><div><dt>Эффект</dt><dd>Ещё не измерен</dd></div></dl>
        <a href="#capabilities">Посмотреть возможности <ArrowRight/></a>
      </aside>
    </section>

    <section className="publicTrace" aria-labelledby="trace-title">
      <div className="publicSectionTitle"><span>01 / DECISION TRACE</span><h2 id="trace-title">От данных к измерению — без скрытой автономии.</h2><p>Каждый этап остаётся видимым. Результат появляется только после действия и новых фактических данных.</p></div>
      <ol>{steps.map(([key,label,value],index)=><li key={key}><span>{key}</span><div><small>{label}</small><b>{value}</b></div>{index<steps.length-1&&<i aria-hidden="true"/>}</li>)}</ol>
    </section>

    <section className="publicSection" id="capabilities">
      <div className="publicSectionTitle"><span>02 / ВОЗМОЖНОСТИ</span><h2>Рабочие контуры отделены от планов.</h2><p>Статус написан текстом. Наличие карточки на странице не означает доступ или production-готовность.</p></div>
      <div className="publicCapabilityGrid">
        {PUBLIC_MODULES.map((item,index)=><article key={item.code} className={index===2?'featured':''}><small>{String(index+1).padStart(2,'0')} / МОДУЛЬ</small>{index===2?<Gauge/>:index===3?<Workflow/>:<FileCheck2/>}<h3>{item.label}</h3><p>{item.note}</p><b>{item.status}</b></article>)}
      </div>
    </section>

    <section className="publicSection publicChannels" id="channels">
      <div className="publicSectionTitle"><span>03 / ПЛОЩАДКИ</span><h2>Выберите площадку по фактическому статусу.</h2><p>Wildberries можно выбрать для дальнейшей настройки после входа. Остальные площадки остаются запланированными и не выглядят подключёнными.</p></div>
      <div className="publicChannelLayout">
        <div className="publicChannelPicker" role="list" aria-label="Площадки">{Object.entries(PUBLIC_CHANNELS).map(([key,item],index)=><button type="button" aria-pressed={channel===key} onClick={()=>setChannel(key)} key={key}><span>{String(index+1).padStart(2,'0')}</span><b>{item.label}</b><em data-status={item.availability}>{item.status}</em></button>)}</div>
        <article className="publicChannelDetail"><span>{selected.status}</span><h3>{selected.title}</h3><p>{selected.text}</p><ul>{selected.items.map(item=><li key={item}><Check/>{item}</li>)}</ul><a href="#bundle">{isImplemented?'Продолжить с Wildberries':'Сохранить интерес к запланированной интеграции'} <ArrowRight/></a></article>
      </div>
    </section>

    <section className="publicSection publicBundle" id="bundle">
      <div className="publicSectionTitle"><span>04 / ВАШ НАБОР</span><h2>Соберите маршрут до регистрации.</h2><p>Это только заявка на набор. URL передаёт выбор в регистрацию; серверные права появляются исключительно после проверки аккаунта, тарифа и entitlement.</p></div>
      <div className="publicBundleGrid">
        <div className="publicBundleOptions"><h3>Возможности</h3><div>{PUBLIC_MODULES.map(item=><button type="button" aria-pressed={selectedModules.includes(item.code)} onClick={()=>toggleModule(item.code)} key={item.code}><span>{selectedModules.includes(item.code)&&<Check/>}</span><b>{item.label}</b><small>{item.status}</small></button>)}</div><h3>Количество магазинов</h3><div className="publicScale">{[1,3,10].map(value=><button type="button" aria-pressed={scale===value} onClick={()=>setScale(value)} key={value}><b>{value}</b><span>{value===1?'магазин':value<5?'магазина':'магазинов'}</span></button>)}</div></div>
        <aside className="publicBundleSummary"><span>ЗАПРОШЕННЫЙ МАРШРУТ</span><h3>{recommendedPlan==='business'?'Business':'PRO'}</h3><dl><div><dt>Площадка</dt><dd>{selected.label}</dd></div><div><dt>Функции</dt><dd>{selectedModules.length} из {PUBLIC_MODULES.length}</dd></div><div><dt>Масштаб</dt><dd>до {scale} магазинов</dd></div><div><dt>Доступ</dt><dd>не выдан</dd></div></dl><Link href={intentHref}>Перейти к регистрации <ArrowRight/></Link><small>{isImplemented?'Выбор сохранится в форме регистрации. PRO — желаемый план, не оплата и не активный тариф.':'Сохранится интерес к запланированной интеграции. PRO — желаемый план, не оплата и не активный тариф.'}</small></aside>
      </div>
    </section>

    <section className="publicSection publicPricing" id="pricing"><div className="publicSectionTitle"><span>05 / ТАРИФЫ</span><h2>Условия сохранены без изменений.</h2><p>Выбор тарифа также не выдаёт доступ: он остаётся запросом до серверной проверки.</p></div><div className="publicPlans">{plans.map(plan=><article className={plan.featured?'featured':''} key={plan.name}>{plan.featured&&<span>ОПТИМАЛЬНЫЙ</span>}<h3>{plan.name}</h3><strong>{plan.price}</strong><small>{plan.note}</small><ul>{plan.items.map(item=><li key={item}><Check/>{item}</li>)}</ul><Link href={plan.href}>{plan.cta}<ArrowRight/></Link></article>)}</div></section>

    <section className="publicSecurity"><div><span><LockKeyhole/> БЕЗОПАСНОСТЬ — УСЛОВИЕ ДОСТУПА</span><h2>Публичный выбор — не полномочие.</h2><p>Авторизация, membership, workspace, store и entitlement проверяются сервером. Публичная страница не подключает магазин и не выполняет внешние действия.</p></div><div><b><ShieldCheck/> Вход и восстановление сохранены</b><b><ShieldCheck/> MFA перед ключами магазина</b><b><ShieldCheck/> Права только после server gate</b><b><ShieldCheck/> STOP для автоматизаций</b></div></section>

    <section className="publicFinal"><Store/><h2>Начните с понятного набора. Доступ включится только после проверок.</h2><div><a className="publicPrimary" href="#bundle">Выбрать набор</a><Link className="publicSecondary" href="/login">Войти</Link></div></section>
    <footer className="publicFooter"><PublicBrand/><span>© 2026 TROVENDI · AI Commerce OS</span><div><Link href="/forgot-password">Восстановить доступ</Link><Link href="/legal/privacy">Конфиденциальность</Link><Link href="/legal/terms">Условия</Link></div></footer>
  </main>
}
