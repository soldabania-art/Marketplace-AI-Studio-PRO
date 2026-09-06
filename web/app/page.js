'use client'

import Link from 'next/link'
import { useState } from 'react'
import { BarChart3,Bell,Bot,Boxes,BrainCircuit,CircleDollarSign,FileText,Gauge,Megaphone,PackageSearch,Search,Settings,ShieldCheck,Sparkles,Star,TrendingDown,TrendingUp,WandSparkles } from 'lucide-react'

const metrics=[{label:'Выручка сегодня',value:'482 640 ₽',delta:'+14,8%',tone:'good'},{label:'Чистая прибыль',value:'127 430 ₽',delta:'+21,3%',tone:'good'},{label:'Реклама',value:'41 280 ₽',delta:'ДРР 8,6%',tone:'neutral'},{label:'Заказы',value:'327',delta:'+38',tone:'good'}]
const actions=[{severity:'critical',icon:TrendingDown,title:'SKU 18374629 уходит в убыток',text:'Реклама выросла на 37%, а маржа стала отрицательной. Потеря за 24 часа: 4 320 ₽.',effect:'+9 800 ₽/нед',action:'Исправить рекламу'},{severity:'warning',icon:Search,title:'У 6 карточек просело SEO',text:'AI нашёл новые поисковые кластеры и подготовил обновлённые заголовки и описание.',effect:'+11–18% трафика',action:'Обновить SEO'},{severity:'growth',icon:TrendingUp,title:'3 товара готовы к масштабированию',text:'Высокая маржа, стабильная конверсия и запас на 21 день. Можно безопасно увеличить трафик.',effect:'+74 000 ₽/мес',action:'Запустить рост'}]
const nav=[['Обзор',Gauge],['AI Director',BrainCircuit],['Profit Center',CircleDollarSign],['Товары',Boxes],['AI Card Factory',WandSparkles],['SEO',Search],['Реклама',Megaphone],['Отзывы',Star],['Остатки',PackageSearch],['Отчёты',FileText],['Автопилот',Bot]]
const sectionCopy={
'Обзор':['ПАНЕЛЬ УПРАВЛЕНИЯ','Доброе утро 👋','Сводка ключевых показателей и приоритетов магазина.'],
'AI Director':['AI DIRECTOR','План действий AI','Приоритеты по прибыли, рискам и росту.'],
'Profit Center':['ФИНАНСЫ','Profit Center','Юнит-экономика, маржа, реклама и прибыль.'],
'Товары':['КАТАЛОГ','Товары','Карточки WB/Ozon и состояние ассортимента.'],
'AI Card Factory':['AI КОНТЕНТ','AI Card Factory','Создание текста, SEO и визуальной концепции карточек.'],
'SEO':['ПОИСК','SEO и запросы','Поисковые кластеры, позиции и точки роста.'],
'Реклама':['РЕКЛАМА','Рекламный центр','ДРР, расходы, кампании и рекомендации AI.'],
'Отзывы':['РЕПУТАЦИЯ','Отзывы','Анализ отзывов и подготовка ответов.'],
'Остатки':['СКЛАД','Остатки','Запасы, дефицит и прогноз пополнения.'],
'Отчёты':['АНАЛИТИКА','Отчёты','Экспорт и управленческие отчёты.'],
'Автопилот':['АВТОМАТИЗАЦИЯ','Автопилот','Контроль разрешённых автоматических действий.']}

export default function HomePage(){
 const [active,setActive]=useState('Обзор'); const [notice,setNotice]=useState(''); const [question,setQuestion]=useState(''); const [answer,setAnswer]=useState(''); const copy=sectionCopy[active]
 function choose(label){setActive(label);setNotice('');setAnswer('');window.scrollTo({top:0,behavior:'smooth'})}
 function action(text){setNotice(`${text}: действие подготовлено. До подключения магазина изменения не отправляются в WB/Ozon.`)}
 function ask(){if(!question.trim())return;setAnswer(`AI принял вопрос: «${question.trim()}». После подключения магазина ответ будет строиться по вашим реальным данным.`)}
 return <main className="shell"><aside className="sidebar"><div className="brand"><div className="brandMark"><Sparkles size={20}/></div><div><strong>Marketplace AI</strong><span>Studio Cloud</span></div></div>
 <nav className="nav">{nav.map(([label,Icon])=><button key={label} onClick={()=>choose(label)} className={active===label?'navItem active':'navItem'}><Icon size={18}/><span>{label}</span>{label==='AI Director'&&<b>17</b>}</button>)}</nav>
 <div className="marketplaces"><span className="eyebrow">МАРКЕТПЛЕЙСЫ</span><button className="marketRow" onClick={()=>setNotice('Wildberries ещё не подключён. Мастер безопасного подключения будет следующим этапом.')}><i className="wbDot"/>Wildberries <span>●</span></button><button className="marketRow" onClick={()=>setNotice('Ozon ещё не подключён. Мастер безопасного подключения будет следующим этапом.')}><i className="ozonDot"/>Ozon <span>●</span></button></div>
 <Link href="/account" className="settingsBtn"><Settings size={18}/> Настройки</Link></aside>
 <section className="workspace"><header className="topbar"><div><span className="eyebrow">{copy[0]}</span><h1>{copy[1]}</h1><small>{copy[2]}</small></div><div className="topActions"><button className="iconBtn" onClick={()=>setNotice('Новых системных уведомлений пока нет.')}><Bell size={19}/><span className="notificationDot"/></button><Link href="/account" className="profile"><div className="avatar">SB</div><div><strong>Мой магазин</strong><span>Аккаунт и подключения</span></div></Link></div></header>
 {notice&&<div className="panel" style={{marginBottom:16,padding:14}}>{notice}</div>}
 <section className="hero"><div><div className="heroKicker"><BrainCircuit size={17}/> AI Director</div><h2>Я проанализировал демо-данные и нашёл <em>17 возможностей</em> увеличить прибыль.</h2><p>После подключения WB/Ozon здесь появится расчёт по вашему магазину.</p></div><button className="primaryBtn" onClick={()=>choose('AI Director')}><Sparkles size={18}/> Открыть план действий</button></section>
 <section className="metricsGrid">{metrics.map(m=><article className="metricCard" key={m.label}><span>{m.label}</span><strong>{m.value}</strong><small className={m.tone}>{m.delta}</small></article>)}</section>
 <section className="contentGrid"><div className="panel opportunities"><div className="panelTitle"><div><span className="eyebrow">ПРИОРИТЕТЫ AI</span><h3>Что требует внимания</h3></div><button className="ghostBtn" onClick={()=>choose('AI Director')}>Все 17</button></div><div className="actionList">{actions.map(({severity,icon:Icon,title,text,effect,action:label})=><article className={`actionCard ${severity}`} key={title}><div className="actionIcon"><Icon size={20}/></div><div className="actionBody"><div className="actionHeader"><h4>{title}</h4><span>{effect}</span></div><p>{text}</p><button onClick={()=>action(label)}>{label}</button><button className="linkBtn" onClick={()=>setNotice(`${title}. ${text} Ожидаемый эффект: ${effect}.`)}>Подробнее</button></div></article>)}</div></div>
 <aside className="rightColumn"><div className="panel profitCard" onClick={()=>choose('Profit Center')} role="button" tabIndex={0}><div className="panelTitle compact"><div><span className="eyebrow">PROFIT CENTER</span><h3>Прибыль за 30 дней</h3></div><BarChart3 size={20}/></div><div className="profitValue">1 846 320 ₽</div><div className="profitDelta"><TrendingUp size={16}/> +18,4% к прошлому периоду</div><div className="bars">{[52,62,48,73,66,84,78,92,74,88,96,100].map((h,i)=><i key={i} style={{height:`${h}%`}}/>)}</div><div className="profitFooter"><span>Маржа <strong>26,4%</strong></span><span>ДРР <strong>9,1%</strong></span></div></div>
 <div className="panel autopilotCard"><div className="autopilotHeader"><div className="shield"><ShieldCheck size={20}/></div><div><span className="eyebrow">AUTOPILOT</span><h3>Безопасный режим</h3></div><button className="toggle on" onClick={()=>setNotice('Настройки автопилота откроются после подключения магазина.')} aria-label="Настройки автопилота"><i/></button></div><p>AI наблюдает за магазином, создаёт рекомендации и выполняет только разрешённые действия.</p><div className="autopilotStats"><span><b>42</b> действий</span><span><b>0</b> ошибок</span></div></div></aside></section>
 <section className="askAI"><div className="askIcon"><Bot size={23}/></div><div className="askCopy"><strong>Спросить AI о бизнесе</strong><span>Например: почему вчера упали продажи?</span></div><input value={question} onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>e.key==='Enter'&&ask()} placeholder="Введите вопрос…"/><button onClick={ask}><Sparkles size={18}/> Спросить AI</button></section>{answer&&<div className="panel" style={{marginTop:12,padding:16}}>{answer}</div>}
 </section></main>
}
