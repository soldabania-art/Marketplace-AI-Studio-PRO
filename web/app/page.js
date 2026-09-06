'use client'

import {
  BadgeDollarSign,
  BarChart3,
  Bell,
  Bot,
  Boxes,
  BrainCircuit,
  CircleDollarSign,
  FileText,
  Gauge,
  Megaphone,
  PackageSearch,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Star,
  TrendingDown,
  TrendingUp,
  WandSparkles
} from 'lucide-react'

const metrics = [
  { label: 'Выручка сегодня', value: '482 640 ₽', delta: '+14,8%', tone: 'good' },
  { label: 'Чистая прибыль', value: '127 430 ₽', delta: '+21,3%', tone: 'good' },
  { label: 'Реклама', value: '41 280 ₽', delta: 'ДРР 8,6%', tone: 'neutral' },
  { label: 'Заказы', value: '327', delta: '+38', tone: 'good' }
]

const actions = [
  {
    severity: 'critical',
    icon: TrendingDown,
    title: 'SKU 18374629 уходит в убыток',
    text: 'Реклама выросла на 37%, а маржа стала отрицательной. Потеря за 24 часа: 4 320 ₽.',
    effect: '+9 800 ₽/нед',
    action: 'Исправить рекламу'
  },
  {
    severity: 'warning',
    icon: Search,
    title: 'У 6 карточек просело SEO',
    text: 'AI нашёл новые поисковые кластеры и подготовил обновлённые заголовки и описание.',
    effect: '+11–18% трафика',
    action: 'Обновить SEO'
  },
  {
    severity: 'growth',
    icon: TrendingUp,
    title: '3 товара готовы к масштабированию',
    text: 'Высокая маржа, стабильная конверсия и запас на 21 день. Можно безопасно увеличить трафик.',
    effect: '+74 000 ₽/мес',
    action: 'Запустить рост'
  }
]

const nav = [
  ['Обзор', Gauge],
  ['AI Director', BrainCircuit],
  ['Profit Center', CircleDollarSign],
  ['Товары', Boxes],
  ['AI Card Factory', WandSparkles],
  ['SEO', Search],
  ['Реклама', Megaphone],
  ['Отзывы', Star],
  ['Остатки', PackageSearch],
  ['Отчёты', FileText],
  ['Автопилот', Bot],
]

export default function HomePage() {
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark"><Sparkles size={20} /></div>
          <div>
            <strong>Marketplace AI</strong>
            <span>Studio Cloud</span>
          </div>
        </div>

        <nav className="nav">
          {nav.map(([label, Icon], index) => (
            <button key={label} className={index === 0 ? 'navItem active' : 'navItem'}>
              <Icon size={18} />
              <span>{label}</span>
              {label === 'AI Director' && <b>17</b>}
            </button>
          ))}
        </nav>

        <div className="marketplaces">
          <span className="eyebrow">МАРКЕТПЛЕЙСЫ</span>
          <div className="marketRow"><i className="wbDot" />Wildberries <span>●</span></div>
          <div className="marketRow"><i className="ozonDot" />Ozon <span>●</span></div>
        </div>

        <button className="settingsBtn"><Settings size={18} /> Настройки</button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">ПАНЕЛЬ УПРАВЛЕНИЯ</span>
            <h1>Доброе утро 👋</h1>
          </div>
          <div className="topActions">
            <button className="iconBtn"><Bell size={19} /><span className="notificationDot" /></button>
            <div className="profile">
              <div className="avatar">SB</div>
              <div><strong>Мой магазин</strong><span>WB + Ozon</span></div>
            </div>
          </div>
        </header>

        <section className="hero">
          <div>
            <div className="heroKicker"><BrainCircuit size={17} /> AI Director</div>
            <h2>Я проанализировал ваш бизнес и нашёл <em>17 возможностей</em> увеличить прибыль.</h2>
            <p>Потенциальный эффект от рекомендованных действий: <strong>+126 800 ₽ в месяц</strong></p>
          </div>
          <button className="primaryBtn"><Sparkles size={18} /> Открыть план действий</button>
        </section>

        <section className="metricsGrid">
          {metrics.map((m) => (
            <article className="metricCard" key={m.label}>
              <span>{m.label}</span>
              <strong>{m.value}</strong>
              <small className={m.tone}>{m.delta}</small>
            </article>
          ))}
        </section>

        <section className="contentGrid">
          <div className="panel opportunities">
            <div className="panelTitle">
              <div><span className="eyebrow">ПРИОРИТЕТЫ AI</span><h3>Что требует внимания</h3></div>
              <button className="ghostBtn">Все 17</button>
            </div>

            <div className="actionList">
              {actions.map(({ severity, icon: Icon, title, text, effect, action }) => (
                <article className={`actionCard ${severity}`} key={title}>
                  <div className="actionIcon"><Icon size={20} /></div>
                  <div className="actionBody">
                    <div className="actionHeader"><h4>{title}</h4><span>{effect}</span></div>
                    <p>{text}</p>
                    <button>{action}</button>
                    <button className="linkBtn">Подробнее</button>
                  </div>
                </article>
              ))}
            </div>
          </div>

          <aside className="rightColumn">
            <div className="panel profitCard">
              <div className="panelTitle compact"><div><span className="eyebrow">PROFIT CENTER</span><h3>Прибыль за 30 дней</h3></div><BarChart3 size={20} /></div>
              <div className="profitValue">1 846 320 ₽</div>
              <div className="profitDelta"><TrendingUp size={16} /> +18,4% к прошлому периоду</div>
              <div className="bars">
                {[52, 62, 48, 73, 66, 84, 78, 92, 74, 88, 96, 100].map((h, i) => <i key={i} style={{height: `${h}%`}} />)}
              </div>
              <div className="profitFooter"><span>Маржа <strong>26,4%</strong></span><span>ДРР <strong>9,1%</strong></span></div>
            </div>

            <div className="panel autopilotCard">
              <div className="autopilotHeader"><div className="shield"><ShieldCheck size={20} /></div><div><span className="eyebrow">AUTOPILOT</span><h3>Безопасный режим</h3></div><div className="toggle on"><i /></div></div>
              <p>AI наблюдает за магазином, создаёт рекомендации и автоматически выполняет только разрешённые безопасные действия.</p>
              <div className="autopilotStats"><span><b>42</b> действий</span><span><b>0</b> ошибок</span></div>
            </div>
          </aside>
        </section>

        <section className="askAI">
          <div className="askIcon"><Bot size={23} /></div>
          <div className="askCopy"><strong>Спросить AI о бизнесе</strong><span>Например: почему вчера упали продажи?</span></div>
          <input placeholder="Введите вопрос…" />
          <button><Sparkles size={18} /> Спросить AI</button>
        </section>
      </section>
    </main>
  )
}
