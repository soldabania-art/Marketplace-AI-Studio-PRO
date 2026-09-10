'use client'

import Link from 'next/link'
import {useState} from 'react'
import {ArrowRight,BarChart3,Boxes,BrainCircuit,Check,ChevronRight,LockKeyhole,Rocket,ShieldCheck,Sparkles,WandSparkles} from 'lucide-react'
import BrandLogo from './BrandLogo'

const channels={
  wb:{label:'Wildberries',status:'Подключается сейчас',title:'Контент, прибыль и остатки — в одном контуре',text:'TROVENDI получает данные вашего магазина через API, собирает финансовую картину и предлагает действия с доказательствами.',items:['Реальные карточки и остатки','Profit Center без двойного списания рекламы','Публикация только после подтверждения']},
  ozon:{label:'Ozon',status:'Следующий маркетплейс',title:'Единая модель данных уже предусмотрена',text:'Ozon подключим после завершения проверенной WB-версии. Мы не выдаём будущую интеграцию за работающую.',items:['Общий каталог товаров','Единая себестоимость','Общий AI Director']},
  start:{label:'Старт с нуля',status:'Доступен новичкам',title:'От одной фотографии до готового проекта карточки',text:'Пошаговый режим помогает проверить товар, подготовить контент и экономику без сложного кабинета.',items:['3 дня бесплатно','До 5 успешных карточек','Без автопубликации и опасных действий']},
}

const plans=[
  {name:'Пробный запуск',price:'0 ₽',note:'3 дня · до 5 карточек',items:['Один проект магазина','Тексты, SEO и экономика','Без публикации и автодействий'],href:'/register',cta:'Начать бесплатно'},
  {name:'PRO',price:'4 990 ₽',note:'в месяц',items:['До 3 магазинов','AI Card Factory и Profit Center','AI Director с подтверждением'],href:'/pricing',cta:'Посмотреть PRO',featured:true},
  {name:'Business',price:'12 990 ₽',note:'в месяц',items:['До 10 магазинов','Командные роли','Расширенный контроль и отчёты'],href:'/pricing',cta:'Посмотреть Business'},
]

export default function PublicLanding(){
  const [channel,setChannel]=useState('wb');const selected=channels[channel]
  return <main className="publicLanding">
    <header className="publicNav"><Link href="/" aria-label="TROVENDI"><BrandLogo/></Link><nav><a href="#capabilities">Возможности</a><a href="#channels">Магазины</a><a href="#pricing">Тарифы</a><a href="#security">Безопасность</a></nav><div><Link className="publicLogin" href="/login">Войти</Link><Link className="publicStart" href="/register">Попробовать бесплатно</Link></div></header>

    <section className="publicHero"><div className="publicHeroCopy"><span className="publicPill"><Sparkles size={14}/> AI Commerce OS для продавцов</span><h1>Не ещё один сервис аналитики. <em>Центр управления магазином.</em></h1><p>Подключите Wildberries — TROVENDI соберёт реальные данные, рассчитает прибыль, улучшит карточки и подготовит безопасный план действий. Решения остаются под вашим контролем.</p><div className="publicHeroActions"><Link className="publicPrimary" href="/register"><Rocket size={18}/> Начать бесплатно</Link><Link className="publicSecondary" href="/login">Уже есть аккаунт <ArrowRight size={16}/></Link></div><small>Без карты · 3 дня · до 5 карточек · никаких автодействий</small></div><div className="publicCommand"><div className="commandTop"><span><i/> TROVENDI AI Director</span><b>Только подтверждённые данные</b></div><div className="commandMetric"><span>Сегодня важно</span><strong>3 решения</strong><small>в порядке влияния на прибыль</small></div><div className="commandActions"><div><BarChart3/><span><b>Проверить удержания WB</b><small>Обнаружено по финансовому отчёту</small></span><em>−12 480 ₽</em></div><div><Boxes/><span><b>Подготовить поставку</b><small>Остатка хватит примерно на 9 дней</small></span><ChevronRight/></div><div><WandSparkles/><span><b>Улучшить карточку</b><small>Только из подтверждённых фактов товара</small></span><ChevronRight/></div></div><p><ShieldCheck size={15}/> Ни одно изменение не отправляется без разрешения владельца</p></div></section>

    <section className="publicProof"><span>Один вход</span><span>Один каталог</span><span>Одна прибыль</span><span>Один главный AI</span><span>Все действия — с аудитом</span></section>

    <section className="publicSection" id="capabilities"><div className="publicSectionHead"><span>СИСТЕМА, А НЕ НАБОР ОТЧЁТОВ</span><h2>От фотографии товара до ежедневного управления</h2><p>Новичок получает простой маршрут. Действующий продавец — единый операционный контур.</p></div><div className="capabilityGrid"><article><Rocket/><b>Старт с нуля</b><p>Фото товара, факты, экономика и готовый проект карточки.</p></article><article><WandSparkles/><b>AI Card Factory</b><p>Заголовок, описание, SEO и визуальный план без выдуманных характеристик.</p></article><article><BarChart3/><b>Profit Center</b><p>Финансы WB, реклама, себестоимость, налоги, штрафы и удержания.</p></article><article><BrainCircuit/><b>Daily AI Director</b><p>Ранжирует проблемы и предлагает понятные действия с источниками.</p></article></div></section>

    <section className="publicSection channelSection" id="channels"><div className="publicSectionHead"><span>ВЫБЕРИТЕ СВОЙ СЦЕНАРИЙ</span><h2>Начните с того, что у вас уже есть</h2></div><div className="channelPicker">{Object.entries(channels).map(([key,item])=><button type="button" className={channel===key?'active':''} onClick={()=>setChannel(key)} key={key}><b>{item.label}</b><span>{item.status}</span></button>)}</div><div className="channelDetail"><div><span>{selected.status}</span><h3>{selected.title}</h3><p>{selected.text}</p><Link href={channel==='ozon'?'/pricing':'/register'}>{channel==='wb'?'Подключить Wildberries':channel==='start'?'Запустить первый товар':'Следить за запуском'} <ArrowRight size={16}/></Link></div><ul>{selected.items.map(item=><li key={item}><Check size={16}/>{item}</li>)}</ul></div></section>

    <section className="publicSection" id="pricing"><div className="publicSectionHead"><span>ПРОЗРАЧНЫЙ СТАРТ</span><h2>Сначала ценность, потом подписка</h2><p>Пробный режим ограничен специально: можно проверить качество, но нельзя случайно изменить магазин.</p></div><div className="publicPlans">{plans.map(plan=><article className={plan.featured?'featured':''} key={plan.name}>{plan.featured&&<span className="planFlag">ОПТИМАЛЬНЫЙ</span>}<h3>{plan.name}</h3><strong>{plan.price}</strong><small>{plan.note}</small><ul>{plan.items.map(item=><li key={item}><Check size={15}/>{item}</li>)}</ul><Link href={plan.href}>{plan.cta}<ArrowRight size={15}/></Link></article>)}</div><Link className="allPlans" href="/pricing">Сравнить тарифы и ограничения <ArrowRight size={15}/></Link></section>

    <section className="publicSecurity" id="security"><div><span><LockKeyhole size={16}/> БЕЗОПАСНОСТЬ — УСЛОВИЕ ЗАПУСКА</span><h2>AI предлагает. Владелец решает.</h2><p>Доступ разделён по организациям и магазинам. Ключи маркетплейсов не показываются в интерфейсе. Публикации требуют отдельного подтверждения, а критические действия записываются в аудит.</p></div><div><b><ShieldCheck/> Изоляция магазинов</b><b><ShieldCheck/> MFA и повторное подтверждение</b><b><ShieldCheck/> Запрет действий по умолчанию</b><b><ShieldCheck/> STOP для автоматизаций</b></div></section>

    <section className="publicFinal"><BrainCircuit size={34}/><h2>Один человек управляет бизнесом. TROVENDI помогает держать всё остальное под контролем.</h2><div><Link className="publicPrimary" href="/register">Создать аккаунт</Link><Link className="publicSecondary" href="/login">Войти</Link></div></section>
    <footer className="publicFooter"><BrandLogo/><span>© 2026 TROVENDI · AI Commerce OS</span><div><Link href="/legal/privacy">Конфиденциальность</Link><Link href="/legal/terms">Условия</Link></div></footer>
  </main>
}
