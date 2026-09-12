'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import {
  AlertTriangle, ArrowRight, BarChart3, Check, CheckCircle2, ChevronRight,
  CircleDashed, Clock3, Database, Eye, FileCheck2, Fingerprint, Gauge,
  LockKeyhole, Menu, Minus, PackageCheck, Pause, Play, RefreshCw, Search,
  ShieldCheck, Sparkles, Store, TrendingDown, WifiOff, X,
} from 'lucide-react'

const directionHref = (direction, screen = 'home', state = 'complete') =>
  `/design-reference?direction=${direction}&screen=${screen}&state=${state}`

const longProduct = 'Сумка-шоппер женская повседневная с внутренним карманом и усиленными ручками — коллекция «Северный ветер»'

function Mark() {
  return <span className="d01-mark" aria-hidden="true"><i/><i/><i/></span>
}

function LedgerGraphic() {
  return <svg className="ledgerGraphic" viewBox="0 0 680 420" role="img" aria-labelledby="ledger-title ledger-desc">
    <title id="ledger-title">Карта решения TROVENDI</title>
    <desc id="ledger-desc">Источники данных сходятся в проверенную проблему, решение и измеряемый результат.</desc>
    <defs>
      <pattern id="ledger-grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="currentColor" strokeOpacity=".12"/></pattern>
      <linearGradient id="ledger-line" x1="0" x2="1"><stop stopColor="#597168"/><stop offset=".62" stopColor="#10b981"/><stop offset="1" stopColor="#bbf7d0"/></linearGradient>
    </defs>
    <rect width="680" height="420" rx="28" fill="url(#ledger-grid)"/>
    <path className="ledgerPath" d="M72 92 C200 92 185 206 326 206 S478 328 610 328" fill="none" stroke="url(#ledger-line)" strokeWidth="3"/>
    <path d="M72 206H326M72 318C188 318 202 206 326 206" fill="none" stroke="currentColor" strokeOpacity=".32" strokeWidth="1.5" strokeDasharray="5 8"/>
    <g className="ledgerNode"><circle cx="72" cy="92" r="12"/><text x="72" y="61">ФИНАНСЫ WB</text><text x="72" y="126">сверено 09:42</text></g>
    <g className="ledgerNode"><circle cx="72" cy="206" r="12"/><text x="72" y="175">РЕКЛАМА</text><text x="72" y="240">полный импорт</text></g>
    <g className="ledgerNode muted"><circle cx="72" cy="318" r="12"/><text x="72" y="287">СЕБЕСТОИМОСТЬ</text><text x="72" y="352">2 SKU неизвестно</text></g>
    <g className="ledgerFocus"><circle cx="326" cy="206" r="45"/><text x="326" y="201">−18 420 ₽</text><text x="326" y="222">ПОТЕРЯ</text></g>
    <g className="ledgerNode result"><circle cx="610" cy="328" r="12"/><text x="610" y="296">РЕЗУЛЬТАТ</text><text x="610" y="362">ожидает измерения</text></g>
    <text className="ledgerCaption" x="326" y="34">TRACE / 12.09 / WB–01</text>
  </svg>
}

function SignalGraphic() {
  return <svg className="signalGraphic" viewBox="0 0 680 420" role="img" aria-labelledby="signal-title signal-desc">
    <title id="signal-title">Радар операционных сигналов</title>
    <desc id="signal-desc">Три сигнала разной срочности на координатной сетке.</desc>
    <defs><radialGradient id="pulse"><stop stopColor="#34d399" stopOpacity=".6"/><stop offset="1" stopColor="#34d399" stopOpacity="0"/></radialGradient></defs>
    <g className="signalGrid"><path d="M0 70H680M0 140H680M0 210H680M0 280H680M0 350H680M113 0V420M226 0V420M339 0V420M452 0V420M565 0V420"/></g>
    <circle cx="338" cy="210" r="156"/><circle cx="338" cy="210" r="108"/><circle cx="338" cy="210" r="58"/>
    <path className="signalSweep" d="M338 210L526 116A210 210 0 0 1 548 190Z"/>
    <g className="signalPing critical"><circle cx="460" cy="134" r="28"/><circle cx="460" cy="134" r="7"/><text x="492" y="130">МАРЖА</text><text x="492" y="148">−18 420 ₽</text></g>
    <g className="signalPing"><circle cx="245" cy="270" r="24"/><circle cx="245" cy="270" r="7"/><text x="109" y="264">ОСТАТОК</text><text x="109" y="282">9 дней</text></g>
    <g className="signalPing quiet"><circle cx="380" cy="318" r="20"/><circle cx="380" cy="318" r="6"/><text x="410" y="315">ОТЗЫВЫ</text><text x="410" y="333">актуально</text></g>
    <text className="signalCode" x="28" y="38">SIGNAL ROOM / LIVE READ</text>
  </svg>
}

function DirectionSwitcher({ direction }) {
  return <div className="directionSwitch" aria-label="Визуальные направления">
    <Link href={directionHref('ledger')} aria-current={direction === 'ledger' ? 'page' : undefined}><span>01</span> Operational Ledger <small>рекомендуем</small></Link>
    <Link href={directionHref('signal')} aria-current={direction === 'signal' ? 'page' : undefined}><span>02</span> Signal Room</Link>
  </div>
}

function ConceptIntro({ direction }) {
  const ledger = direction === 'ledger'
  return <section className="conceptIntro">
    <div>
      <span className="conceptIndex">D01 / НАПРАВЛЕНИЕ {ledger ? '01' : '02'}</span>
      <h1>{ledger ? <>Спокойная точность.<br/><em>Каждое решение оставляет след.</em></> : <>Живой пульт.<br/><em>Сигнал раньше отчёта.</em></>}</h1>
      <p>{ledger
        ? 'Редакционная композиция соединяет финансовый реестр и карту доказательств. Воздух, крупные цифры и строгие линии делают сложные решения понятными без ощущения «ещё одной SaaS-панели».'
        : 'Более контрастная диспетчерская: плотная сетка, радар сигналов и моноширинные служебные подписи. Хорошо передаёт скорость, но создаёт выше когнитивную нагрузку в ежедневной работе.'}</p>
      <div className="conceptReasons">
        <span><Check/> {ledger ? 'Фокус на доказательстве и деньгах' : 'Максимальная оперативность'}</span>
        <span><Check/> {ledger ? 'Лучше для длинных сессий и mobile' : 'Сильный технологичный характер'}</span>
        <span><Minus/> {ledger ? 'Не имитирует банковский терминал' : 'Плотнее и тревожнее'}</span>
      </div>
      {ledger && <Link className="d01-primary" href={directionHref('ledger', 'home')}><Play/> Открыть связанный прототип</Link>}
    </div>
    <div className="conceptCanvas">{ledger ? <LedgerGraphic/> : <SignalGraphic/>}<div className="canvasLabel"><span>Синтетические данные</span><b>{ledger ? 'РЕКОМЕНДАЦИЯ' : 'АЛЬТЕРНАТИВА'}</b></div></div>
  </section>
}

function ProductHeader({ screen }) {
  return <header className="prototypeHeader">
    <Link href={directionHref('ledger', 'home')} className="protoBrand"><Mark/><span>TROVENDI<small>AI COMMERCE OS</small></span></Link>
    <nav aria-label="Сценарий прототипа">
      <Link href={directionHref('ledger', 'home')} aria-current={screen === 'home' ? 'page' : undefined}>Главная</Link>
      <Link href={directionHref('ledger', 'connect', 'partial')} aria-current={screen === 'connect' ? 'page' : undefined}>Подключение</Link>
      <Link href={directionHref('ledger', 'director', 'partial')} aria-current={screen === 'director' ? 'page' : undefined}>AI Director</Link>
    </nav>
    <div className="protoTools"><span className="demoFlag"><Eye/> ДЕМО</span><button aria-label="Открыть меню"><Menu/></button></div>
  </header>
}

function TraceRail({ active = 1 }) {
  const labels = ['Данные', 'Проблема', 'Решение', 'Контроль']
  return <div className="traceRail" aria-label="Контур решения">{labels.map((label, index) => <div className={index <= active ? 'active' : ''} key={label}><span>{String(index + 1).padStart(2, '0')}</span><b>{label}</b></div>)}</div>
}

function HomeScreen() {
  return <>
    <section className="protoHero">
      <div className="protoHeroCopy"><span className="overline">ОПЕРАЦИОННАЯ СИСТЕМА ДЛЯ ПРОДАВЦА WB</span><h2>Не смотреть на бизнес.<br/><em>Управлять тем, что съедает прибыль.</em></h2><p>TROVENDI соединяет проверенные данные магазина, решение владельца и результат исполнения в один прослеживаемый контур.</p><div className="heroActions"><Link className="d01-primary" href={directionHref('ledger', 'connect', 'partial')}>Подключить магазин <ArrowRight/></Link><Link className="textLink" href={directionHref('ledger', 'director', 'complete')}>Посмотреть пример решения</Link></div><div className="trustLine"><ShieldCheck/><span>Ни одного изменения без вашего подтверждения</span><i/><span>Wildberries — первый проверяемый контур</span></div></div>
      <div className="decisionPlate"><div className="plateTop"><span>TRACE / WB–01</span><b><i/> НУЖНО РЕШЕНИЕ</b></div><div className="plateNumber"><small>ПОДТВЕРЖДЁННАЯ ПОТЕРЯ</small><strong>−18 420,00 ₽</strong><span>за 30 дней</span></div><div className="plateRows"><div><span>Источник</span><b>Финансы WB + реклама</b><CheckCircle2/></div><div><span>Причина</span><b>Расход без подтверждённой выручки</b><CheckCircle2/></div><div><span>Действие</span><b>Проверить 2 кампании</b><Clock3/></div></div><Link href={directionHref('ledger', 'director', 'complete')}>Разобрать доказательства <ArrowRight/></Link></div>
    </section>
    <TraceRail active={1}/>
    <section className="capabilityLedger"><div className="sectionTitle"><span>01 / ВОЗМОЖНОСТИ</span><h3>Один контур вместо пяти вкладок</h3><p>Каждый модуль показывает происхождение данных, ограничения и следующий безопасный шаг.</p></div><div className="ledgerTable" role="table" aria-label="Возможности TROVENDI"><div className="ledgerHead" role="row"><span>Сигнал</span><span>Что проверяем</span><span>Результат</span><span/></div>{[
      ['01','Прибыль','Финансы, реклама, себестоимость','Детерминированный расчёт'],
      ['02','Остатки','Снимки и скорость заказов','Риск дефицита, не обещание'],
      ['03','Карточки','Только подтверждённые атрибуты','Preview перед публикацией'],
    ].map(row=><Link href={row[0] === '01' ? directionHref('ledger','director','complete') : directionHref('ledger','connect','partial')} role="row" key={row[0]}>{row.map((value,index)=><span key={value} className={index===0?'rowNo':''}>{value}</span>)}<ChevronRight/></Link>)}</div></section>
  </>
}

const sourceRows = [
  {name:'Каталог и карточки',detail:'1 248 товаров',state:'ready',updated:'сегодня, 09:44'},
  {name:'Остатки по складам',detail:'18 620 единиц',state:'ready',updated:'сегодня, 09:41'},
  {name:'Финансы и реализации',detail:'01 авг — 11 сен',state:'partial',updated:'87% · импорт идёт'},
  {name:'Рекламные расходы',detail:'46 кампаний',state:'error',updated:'соединение разорвано'},
]

function ConnectScreen({ state }) {
  const loading = state === 'loading'
  return <section className="connectLayout">
    <aside className="connectIntro"><span className="overline">ШАГ 01 / ИСТОЧНИК</span><h2>Подключение без слепой зоны</h2><p>Сначала проверяем доступ, затем показываем полноту каждого набора. Неполный импорт никогда не становится нулём.</p><div className="securityNote"><LockKeyhole/><div><b>Ключ остаётся на сервере</b><span>В этом прототипе никакие данные не отправляются.</span></div></div><TraceRail active={0}/></aside>
    <div className="connectPanel"><div className="panelHead"><div><span>WILDBERRIES / ДЕМО</span><h3>ООО «Северный Контур — официальный магазин товаров для города и путешествий»</h3></div><span className="statusTag neutral"><CircleDashed/> ПРОВЕРКА</span></div>
      <div className="credentialDemo"><label>API-токен <span>только чтение</span></label><div><Fingerprint/><span>•••• •••• •••• 94AF</span><b><Check/> формат проверен</b></div></div>
      <div className="completeness"><div className="completenessHead"><div><span>ПОЛНОТА ДАННЫХ</span><strong>{loading ? '—' : '72%'}</strong></div><p>{loading ? 'Получаем карту источников…' : 'Director будет доступен в частичном режиме. Денежные выводы по рекламе пока заблокированы.'}</p></div><div className="sourceTable" aria-busy={loading}>{loading ? [1,2,3,4].map(i=><div className="sourceSkeleton" key={i}><i/><i/><i/></div>) : sourceRows.map(row=><div key={row.name}><span className={`sourceIcon ${row.state}`}>{row.state==='ready'?<Check/>:row.state==='partial'?<RefreshCw/>:<WifiOff/>}</span><span><b>{row.name}</b><small>{row.detail}</small></span><span className={`sourceState ${row.state}`}>{row.updated}</span></div>)}</div></div>
      {!loading && <div className="connectAlert" role="status"><AlertTriangle/><div><b>Импорт неполный</b><span>Реклама недоступна. Мы сохранили прежние подтверждённые строки и исключили их из нового расчёта до успешной сверки.</span></div></div>}
      <div className="panelActions"><Link className="quietButton" href={directionHref('ledger','connect','loading')}><RefreshCw/> Показать загрузку</Link><Link className="d01-primary" href={directionHref('ledger','director','partial')}>Открыть частичный Director <ArrowRight/></Link></div>
    </div>
  </section>
}

const directorStates = [
  ['complete','Полные'],['partial','Неполные'],['loading','Загрузка'],['error','Ошибка'],['unknown','Не подтверждено'],
]

function StateSwitcher({ state }) {
  return <div className="stateSwitcher" aria-label="Состояние демонстрации">{directorStates.map(([key,label])=><Link key={key} href={directionHref('ledger','director',key)} aria-current={state===key?'true':undefined}>{label}</Link>)}</div>
}

function DirectorScreen({ state }) {
  const loading = state === 'loading'
  const error = state === 'error'
  const partial = state === 'partial'
  const unknown = state === 'unknown'
  return <section className="directorLayout">
    <div className="directorTitle"><div><span className="overline">DAILY AI DIRECTOR / 12 СЕНТЯБРЯ</span><h2>Сегодня — одно решение,<br/><em>которое стоит проверить первым.</em></h2></div><div className="directorMeta"><span><Store/> Северный Контур…</span><b className={partial||error?'warn':''}>{error?<><WifiOff/> НЕТ СВЯЗИ</>:partial?<><AlertTriangle/> ДАННЫЕ 72%</>:<><CheckCircle2/> ДАННЫЕ 100%</>}</b></div></div>
    <StateSwitcher state={state}/>
    {error && <div className="directorError" role="alert"><WifiOff/><div><b>Связь с Wildberries прервана</b><span>Показываем последнее подтверждённое состояние от 09:44. Новые выводы и исполнения заблокированы.</span></div><button><RefreshCw/> Повторить чтение</button></div>}
    <div className="directorGrid"><main>
      {loading ? <div className="decisionCard loadingCard" aria-busy="true"><span/><span/><span/><div/><div/></div> : <article className="decisionCard"><div className="decisionRank"><span>ПРИОРИТЕТ 01</span><b>{partial?'С ограничением':'Высокое влияние'}</b></div><h3>Две рекламные кампании расходуют бюджет без подтверждённой выручки</h3><p>Детерминированная сверка нашла расход, но не нашла связанные продажи в выбранном периоде. Director предлагает проверку, а не автоматическое отключение.</p><div className="moneyFinding"><div><span>НАБЛЮДАЕМЫЙ РАСХОД</span><strong>18 420,00 ₽</strong></div><div><span>ЭФФЕКТ ДЕЙСТВИЯ</span><strong>{unknown?'Не подтверждено':'Ещё не измерен'}</strong></div></div><div className="evidenceBlock"><div className="evidenceHead"><span><FileCheck2/> ДОКАЗАТЕЛЬСТВА</span><b>3 источника</b></div><dl><div><dt>Финансовый отчёт WB</dt><dd><CheckCircle2/> подтверждён · 12.09 09:42</dd></div><div><dt>Рекламная статистика</dt><dd className={partial?'warnText':''}>{partial?<><AlertTriangle/> частично · 87%</>:<><CheckCircle2/> подтверждено · 46 кампаний</>}</dd></div><div><dt>Период сопоставления</dt><dd>30 дней · Europe/Moscow</dd></div></dl></div><div className="decisionAction"><div><span>РЕКОМЕНДОВАННОЕ ДЕЙСТВИЕ</span><b>Открыть кампании и проверить поисковые фразы</b><small>Без записи в WB · исполнитель: владелец магазина</small></div><div><button className="reject"><X/> Отклонить</button><button className="approve"><Check/> Подтвердить проверку</button></div></div></article>}
      <section className="productEvidence"><div className="sectionLine"><span>ТОВАРЫ В КОНТЕКСТЕ</span><b>2 SKU</b></div><div className="productTable"><div className="productTableHead"><span>Товар</span><span>Расход</span><span>Выручка</span><span>Достоверность</span></div><div><span><i>01</i><b>{longProduct}</b><small>WB 194028374 · арт. NORTH-BAG-042</small></span><strong>12 840 ₽</strong><strong>{partial?'—':'0 ₽'}</strong><span className="confidence"><CheckCircle2/> подтверждено</span></div><div><span><i>02</i><b>Органайзер дорожный модульный, набор 6 предметов</b><small>WB 194028411 · арт. TRAVEL-SET-006</small></span><strong>5 580 ₽</strong><strong>0 ₽</strong><span className={partial?'confidence partial':'confidence'}>{partial?<><AlertTriangle/> неполно</>:<><CheckCircle2/> подтверждено</>}</span></div></div></section>
    </main><aside className="directorAside"><div className="controlCard"><div className="sectionLine"><span>КОНТРОЛЬ</span><span className="safe"><ShieldCheck/> SAFE</span></div><h3>Исполнение остановлено по умолчанию</h3><p>Подтверждение решения не отправляет изменения в Wildberries.</p><button><Pause/> STOP доступен всегда</button></div><div className="resultCard"><div className="sectionLine"><span>РЕЗУЛЬТАТ</span><Clock3/></div><ol><li className="done"><i/><span><b>Проблема обнаружена</b><small>12.09 · 09:46</small></span></li><li className={unknown?'unknown':''}><i/><span><b>{unknown?'Внешняя запись не подтверждена':'Ожидает решения'}</b><small>{unknown?'Сначала сверка, без повтора':'Нужно действие владельца'}</small></span></li><li><i/><span><b>Измерение</b><small>После свежих данных</small></span></li></ol></div><div className="sourceMini"><div className="sectionLine"><span>СВЕЖЕСТЬ</span><Gauge/></div><div><span>Финансы</span><b>18 мин <small>суточная политика</small></b></div><div><span>Остатки</span><b className="warnText">просрочено <small>обновить</small></b></div><div><span>Реклама</span><b>{partial?'неполно':'11 мин'} <small>{partial?'87%':'актуально'}</small></b></div></div></aside></div>
  </section>
}

function Prototype({ screen, state }) {
  return <section className="prototype"><ProductHeader screen={screen}/><div className="prototypeBody">{screen==='connect'?<ConnectScreen state={state}/>:screen==='director'?<DirectorScreen state={state}/>:<HomeScreen/>}</div><footer className="protoFooter"><span>D01 · ВИЗУАЛЬНЫЙ ПРОТОТИП</span><p>Только синтетические данные. Интеграции, публикации и финансовые действия не выполняются.</p><Link href={directionHref('signal')}>Сравнить с Signal Room <ArrowRight/></Link></footer></section>
}

export default function D01DesignReference() {
  const params = useSearchParams()
  const direction = params.get('direction') === 'signal' ? 'signal' : 'ledger'
  const screen = ['home','connect','director'].includes(params.get('screen')) ? params.get('screen') : null
  const state = directorStates.some(([key])=>key===params.get('state')) ? params.get('state') : 'complete'
  return <main className={`d01 d01-${direction}`}>
    <div className="referenceBar"><div><Mark/><span><b>TROVENDI</b><small>VISUAL REFERENCE / D01</small></span></div><DirectionSwitcher direction={direction}/><Link href="/" className="exitReference">Выйти из демо <X/></Link></div>
    {!screen || direction === 'signal' ? <ConceptIntro direction={direction}/> : <Prototype screen={screen} state={state}/>}
  </main>
}
