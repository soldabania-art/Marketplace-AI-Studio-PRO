"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDashed,
  Clock3,
  Eye,
  FileCheck2,
  Fingerprint,
  Gauge,
  LockKeyhole,
  Menu,
  Pause,
  RefreshCw,
  ShieldCheck,
  Store,
  WifiOff,
  X,
} from "lucide-react";

const routeHref = (screen = "home", state = "complete") =>
  `/design-reference?variant=control&screen=${screen}&state=${state}`;

const studyHref = (variant) => `/design-reference?variant=${variant}`;

const longProduct =
  "Сумка-шоппер женская повседневная с внутренним карманом и усиленными ручками — коллекция «Северный ветер»";

function Mark() {
  return (
    <svg className="d01-mark" viewBox="0 0 40 40" aria-hidden="true">
      <path className="markFrame" d="M3.5 3.5h33v33h-33z" />
      <path className="markTrace" d="M9 12h8v16h6V12h8" />
      <circle cx="9" cy="12" r="2.5" />
      <circle cx="31" cy="12" r="2.5" />
      <circle className="markResult" cx="20" cy="30" r="3" />
    </svg>
  );
}

function LedgerGraphic() {
  return (
    <svg
      className="ledgerGraphic"
      viewBox="0 0 680 420"
      role="img"
      aria-labelledby="ledger-title ledger-desc"
    >
      <title id="ledger-title">Карта решения TROVENDI</title>
      <desc id="ledger-desc">
        Источники данных сходятся в проверенную проблему, решение и измеряемый
        результат.
      </desc>
      <defs>
        <pattern
          id="ledger-grid"
          width="28"
          height="28"
          patternUnits="userSpaceOnUse"
        >
          <path
            d="M28 0H0V28"
            fill="none"
            stroke="currentColor"
            strokeOpacity=".12"
          />
        </pattern>
        <linearGradient id="ledger-line" x1="0" x2="1">
          <stop stopColor="#71D7F7" />
          <stop offset=".58" stopColor="#345CFF" />
          <stop offset="1" stopColor="#FFFFFF" />
        </linearGradient>
      </defs>
      <rect width="680" height="420" rx="28" fill="url(#ledger-grid)" />
      <text className="ledgerEyebrow" x="36" y="34">
        ИСТОЧНИКИ
      </text>
      <text className="ledgerEyebrow" x="336" y="34">
        РЕШЕНИЕ
      </text>
      <text className="ledgerEyebrow" x="554" y="34">
        РЕЗУЛЬТАТ
      </text>
      <path
        className="ledgerPath"
        pathLength="1"
        d="M120 104C226 104 221 210 338 210S451 316 540 316"
        fill="none"
        stroke="url(#ledger-line)"
        strokeWidth="3"
      />
      <path
        className="ledgerBranch"
        d="M120 210H338M120 316C226 316 224 210 338 210"
        fill="none"
        stroke="currentColor"
        strokeOpacity=".32"
        strokeWidth="1.5"
        strokeDasharray="5 8"
      />
      <g className="ledgerNode">
        <circle cx="120" cy="104" r="11" />
        <text x="36" y="96">
          ФИНАНСЫ WB
        </text>
        <text x="36" y="116">
          сверено 09:42
        </text>
      </g>
      <g className="ledgerNode">
        <circle cx="120" cy="210" r="11" />
        <text x="36" y="202">
          РЕКЛАМА
        </text>
        <text x="36" y="222">
          полный импорт
        </text>
      </g>
      <g className="ledgerNode muted">
        <circle cx="120" cy="316" r="11" />
        <text x="36" y="308">
          СЕБЕСТОИМОСТЬ
        </text>
        <text x="36" y="328">
          2 SKU неизвестно
        </text>
      </g>
      <g className="ledgerFocus">
        <circle className="focusOrbit" cx="338" cy="210" r="61" />
        <circle cx="338" cy="210" r="47" />
        <text x="338" y="204">
          18 420 ₽
        </text>
        <text x="338" y="224">
          РАСХОД · ДЕМО
        </text>
      </g>
      <g className="ledgerDecision">
        <rect x="418" y="102" width="182" height="66" rx="2" />
        <text x="434" y="127">
          СЛЕДУЮЩИЙ ШАГ
        </text>
        <text x="434" y="149">
          Проверить 2 кампании →
        </text>
      </g>
      <g className="ledgerNode result">
        <circle cx="540" cy="316" r="11" />
        <text x="564" y="309">
          ЭФФЕКТ ДЕЙСТВИЯ
        </text>
        <text x="564" y="329">
          ещё не измерен
        </text>
      </g>
      <text className="ledgerCaption" x="338" y="390">
        TROVENDI TRACE · ФАКТ → РЕШЕНИЕ → ИЗМЕРЕНИЕ
      </text>
    </svg>
  );
}

function ProductHeader({ screen }) {
  return (
    <header className="prototypeHeader">
      <Link href={routeHref("home")} className="protoBrand">
        <Mark />
        <span>
          TROVENDI<small>AI COMMERCE OS</small>
        </span>
      </Link>
      <nav aria-label="Сценарий прототипа">
        <Link
          href={routeHref("home")}
          aria-current={screen === "home" ? "page" : undefined}
        >
          Главная
        </Link>
        <Link
          href={routeHref("connect", "partial")}
          aria-current={screen === "connect" ? "page" : undefined}
        >
          Подключение
        </Link>
        <Link
          href={routeHref("director", "partial")}
          aria-current={screen === "director" ? "page" : undefined}
        >
          AI Director
        </Link>
      </nav>
      <div className="protoTools">
        <span className="demoFlag">
          <Eye /> ДЕМО-ДАННЫЕ
        </span>
        <details className="protoMenu">
          <summary aria-label="Открыть меню">
            <Menu />
          </summary>
          <div>
            <b>Маршрут демонстрации</b>
            <Link href={routeHref("home")}>Обещание продукта</Link>
            <Link href={routeHref("connect", "partial")}>
              Полнота подключения
            </Link>
            <Link href={routeHref("director", "partial")}>
              Решение Director
            </Link>
            <small>Локально, без запросов к WB</small>
          </div>
        </details>
      </div>
    </header>
  );
}

function TraceRail({ active = 1 }) {
  const labels = ["Данные", "Проблема", "Решение", "Контроль"];
  return (
    <div className="traceRail" aria-label="Контур решения">
      {labels.map((label, index) => (
        <div className={index <= active ? "active" : ""} key={label}>
          <span>{String(index + 1).padStart(2, "0")}</span>
          <b>{label}</b>
        </div>
      ))}
    </div>
  );
}

function HomeScreen() {
  return (
    <>
      <section className="protoHero">
        <div className="protoHeroCopy">
          <span className="overline">
            ДЛЯ ДЕЙСТВУЮЩИХ ПРОДАВЦОВ WILDBERRIES
          </span>
          <h2>
            Прибыль теряется в деталях.
            <br />
            <em>Мы превращаем их в решения.</em>
          </h2>
          <p>
            TROVENDI находит подтверждённые проблемы в данных магазина,
            предлагает следующий шаг и сохраняет след от решения до результата.
          </p>
          <div className="heroActions">
            <Link
              className="d01-primary"
              href={routeHref("connect", "partial")}
            >
              Начать с подключения <ArrowRight />
            </Link>
            <Link className="textLink" href={routeHref("director", "complete")}>
              Посмотреть пример решения
            </Link>
          </div>
          <div className="trustLine">
            <ShieldCheck />
            <span>Ни одного изменения без вашего подтверждения</span>
            <i />
            <span>Здесь только демонстрационные данные</span>
          </div>
        </div>
        <div className="decisionPlate">
          <div className="plateTop">
            <span>TRACE / WB–01 · ДЕМО</span>
            <b>
              <i /> НУЖНО РЕШЕНИЕ
            </b>
          </div>
          <div className="plateNumber">
            <small>НАБЛЮДАЕМЫЙ РАСХОД</small>
            <strong>18 420,00 ₽</strong>
            <span>условный пример · 30 дней</span>
          </div>
          <div className="plateRows">
            <div>
              <span>Прибыль</span>
              <b>Не рассчитана при неполных данных</b>
              <AlertTriangle />
            </div>
            <div>
              <span>Проблема</span>
              <b>Расход без подтверждённой выручки</b>
              <CheckCircle2 />
            </div>
            <div>
              <span>Эффект</span>
              <b>Не измерен до выполнения</b>
              <Clock3 />
            </div>
          </div>
          <Link href={routeHref("director", "complete")}>
            Разобрать доказательства <ArrowRight />
          </Link>
        </div>
      </section>
      <section className="traceStory" aria-labelledby="trace-title">
        <div className="traceStoryCopy">
          <span className="overline">TROVENDI TRACE / КОНТУР РЕШЕНИЯ</span>
          <h3 id="trace-title">От источника до измеримого результата.</h3>
          <p>
            Каждое решение сохраняет происхождение данных, подтверждение
            владельца и ограничения измерения. Форма работает даже без цвета:
            входящие линии сходятся в решение и продолжаются к результату.
          </p>
        </div>
        <div className="traceCanvas">
          <LedgerGraphic />
          <div className="traceMobile" aria-hidden="true">
            <div>
              <span>01 · ИСТОЧНИКИ</span>
              <b>Финансы · реклама · себестоимость</b>
            </div>
            <i />
            <div>
              <span>02 · РЕШЕНИЕ</span>
              <b>Проверить две кампании</b>
            </div>
            <i />
            <div>
              <span>03 · РЕЗУЛЬТАТ</span>
              <b>Эффект ещё не измерен</b>
            </div>
          </div>
          <span className="traceCanvasNote">
            УСЛОВНЫЕ ДЕМО-ДАННЫЕ · БЕЗ ЗАПИСИ В WB
          </span>
        </div>
      </section>
      <TraceRail active={1} />
      <section className="capabilityLedger" id="capabilities">
        <div className="sectionTitle">
          <span>01 / ЧТО МОЖНО СДЕЛАТЬ</span>
          <h3>От данных — к контролируемому действию</h3>
          <p>
            Каждый модуль показывает происхождение данных, ограничения и
            следующий безопасный шаг.
          </p>
        </div>
        <div
          className="ledgerTable"
          role="table"
          aria-label="Возможности TROVENDI"
        >
          <div className="ledgerHead" role="row">
            <span>Сигнал</span>
            <span>Что проверяем</span>
            <span>Результат</span>
            <span />
          </div>
          {[
            [
              "01",
              "Прибыль",
              "Финансы, реклама, себестоимость",
              "Детерминированный расчёт",
            ],
            [
              "02",
              "Остатки",
              "Снимки и скорость заказов",
              "Риск дефицита, не обещание",
            ],
            [
              "03",
              "Карточки",
              "Только подтверждённые атрибуты",
              "Preview перед публикацией",
            ],
          ].map((row) => (
            <Link
              href={
                row[0] === "01"
                  ? routeHref("director", "complete")
                  : routeHref("connect", "partial")
              }
              role="row"
              key={row[0]}
            >
              {row.map((value, index) => (
                <span key={value} className={index === 0 ? "rowNo" : ""}>
                  {value}
                </span>
              ))}
              <ChevronRight />
            </Link>
          ))}
        </div>
      </section>
      <section
        className="marketplaceBoard"
        aria-labelledby="marketplaces-title"
      >
        <div className="sectionTitle">
          <span>02 / ПЛОЩАДКИ</span>
          <h3 id="marketplaces-title">Честная карта интеграций</h3>
          <p>
            Демонстрационный сценарий не означает production-подключение.
            Будущие площадки показаны только как план.
          </p>
        </div>
        <div className="marketplaceList">
          <Link
            href={routeHref("connect", "partial")}
            className="marketplace available"
          >
            <span className="marketMonogram">WB</span>
            <span>
              <b>Wildberries</b>
              <small>Главная → подключение → Director</small>
            </span>
            <em>
              <CheckCircle2 /> Доступно в демонстрации
            </em>
            <ArrowRight />
          </Link>
          {["Ozon", "Яндекс Маркет", "Kaspi", "Uzum"].map((name, index) => (
            <div className="marketplace planned" key={name}>
              <span className="marketMonogram">
                {String(index + 2).padStart(2, "0")}
              </span>
              <span>
                <b>{name}</b>
                <small>Интеграция не включена</small>
              </span>
              <em>
                <Clock3 /> Запланировано
              </em>
              <LockKeyhole />
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

const sourceRows = [
  {
    name: "Каталог и карточки",
    detail: "1 248 товаров",
    state: "ready",
    updated: "сегодня, 09:44",
  },
  {
    name: "Остатки по складам",
    detail: "18 620 единиц",
    state: "ready",
    updated: "сегодня, 09:41",
  },
  {
    name: "Финансы и реализации",
    detail: "01 авг — 11 сен",
    state: "partial",
    updated: "87% · импорт идёт",
  },
  {
    name: "Рекламные расходы",
    detail: "46 кампаний",
    state: "error",
    updated: "соединение разорвано",
  },
];

function ConnectScreen({ state }) {
  const loading = state === "loading";
  return (
    <section className="connectLayout">
      <aside className="connectIntro">
        <span className="overline">ШАГ 01 / ИСТОЧНИК</span>
        <h2>Подключение без слепой зоны</h2>
        <p>
          Сначала проверяем доступ, затем показываем полноту каждого набора.
          Неполный импорт никогда не становится нулём.
        </p>
        <div className="securityNote">
          <LockKeyhole />
          <div>
            <b>Ключ остаётся на сервере</b>
            <span>В этом прототипе никакие данные не отправляются.</span>
          </div>
        </div>
        <TraceRail active={0} />
      </aside>
      <div className="connectPanel">
        <div className="panelHead">
          <div>
            <span>WILDBERRIES / ДЕМО</span>
            <h3>
              ООО «Северный Контур — официальный магазин товаров для города и
              путешествий»
            </h3>
          </div>
          <span className="statusTag neutral">
            <CircleDashed /> ПРОВЕРКА
          </span>
        </div>
        <div className="credentialDemo">
          <label>
            API-токен <span>только чтение</span>
          </label>
          <div>
            <Fingerprint />
            <span>•••• •••• •••• 94AF</span>
            <b>
              <Check /> формат проверен
            </b>
          </div>
        </div>
        <div className="completeness">
          <div className="completenessHead">
            <div>
              <span>ПОЛНОТА ДАННЫХ</span>
              <strong>{loading ? "—" : "72%"}</strong>
            </div>
            <p>
              {loading
                ? "Получаем карту источников…"
                : "Director будет доступен в частичном режиме. Денежные выводы по рекламе пока заблокированы."}
            </p>
          </div>
          <div className="sourceTable" aria-busy={loading}>
            {loading
              ? [1, 2, 3, 4].map((i) => (
                  <div className="sourceSkeleton" key={i}>
                    <i />
                    <i />
                    <i />
                  </div>
                ))
              : sourceRows.map((row) => (
                  <div key={row.name}>
                    <span className={`sourceIcon ${row.state}`}>
                      {row.state === "ready" ? (
                        <Check />
                      ) : row.state === "partial" ? (
                        <RefreshCw />
                      ) : (
                        <WifiOff />
                      )}
                    </span>
                    <span>
                      <b>{row.name}</b>
                      <small>{row.detail}</small>
                    </span>
                    <span className={`sourceState ${row.state}`}>
                      {row.updated}
                    </span>
                  </div>
                ))}
          </div>
        </div>
        {!loading && (
          <div className="connectAlert" role="status">
            <AlertTriangle />
            <div>
              <b>Импорт неполный</b>
              <span>
                Реклама недоступна. Мы сохранили прежние подтверждённые строки и
                исключили их из нового расчёта до успешной сверки.
              </span>
            </div>
          </div>
        )}
        <div className="panelActions">
          <Link className="quietButton" href={routeHref("connect", "loading")}>
            <RefreshCw /> Показать загрузку
          </Link>
          <Link className="d01-primary" href={routeHref("director", "partial")}>
            Открыть частичный Director <ArrowRight />
          </Link>
        </div>
      </div>
    </section>
  );
}

const directorStates = [
  ["complete", "Полные"],
  ["partial", "Неполные"],
  ["loading", "Загрузка"],
  ["error", "Ошибка"],
  ["unknown", "Не подтверждено"],
];

function StateSwitcher({ state }) {
  return (
    <div className="stateSwitcher" aria-label="Состояние демонстрации">
      {directorStates.map(([key, label]) => (
        <Link
          key={key}
          href={routeHref("director", key)}
          aria-current={state === key ? "true" : undefined}
        >
          {label}
        </Link>
      ))}
    </div>
  );
}

function DirectorScreen({ state }) {
  const [actionStatus, setActionStatus] = useState("idle");
  const [retrying, setRetrying] = useState(false);
  const loading = state === "loading";
  const error = state === "error";
  const partial = state === "partial";
  const unknown = state === "unknown";
  return (
    <section className="directorLayout">
      <div className="directorTitle">
        <div>
          <span className="overline">DAILY DIRECTOR / ДЕМО · 12 СЕНТЯБРЯ</span>
          <h2>
            Проверить расход
            <br className="desktopBreak" />
            <em> без подтверждённой выручки.</em>
          </h2>
        </div>
        <div className="directorMeta">
          <span>
            <Store /> Северный Контур…
          </span>
          <b className={partial || error || unknown ? "warn" : ""}>
            {error ? (
              <>
                <WifiOff /> НЕТ СВЯЗИ
              </>
            ) : partial ? (
              <>
                <AlertTriangle /> ДАННЫЕ 72%
              </>
            ) : unknown ? (
              <>
                <CircleDashed /> СТАТУС НЕ ПОДТВЕРЖДЁН
              </>
            ) : (
              <>
                <CheckCircle2 /> ДАННЫЕ 100%
              </>
            )}
          </b>
        </div>
      </div>
      <StateSwitcher state={state} />
      {error && (
        <div className="directorError" role="alert">
          <WifiOff />
          <div>
            <b>Связь с Wildberries прервана</b>
            <span>
              Показываем последнее подтверждённое состояние от 09:44. Новые
              выводы и исполнения заблокированы.
            </span>
          </div>
          <button
            type="button"
            onClick={() => setRetrying(true)}
            disabled={retrying}
          >
            <RefreshCw />{" "}
            {retrying ? "Проверяем локально…" : "Повторить чтение"}
          </button>
        </div>
      )}
      <div className="directorGrid">
        <main>
          {loading ? (
            <div className="decisionCard loadingCard" aria-busy="true">
              <span />
              <span />
              <span />
              <div />
              <div />
            </div>
          ) : (
            <article className="decisionCard">
              <div className="demoDataRibbon">
                <Eye /> Все суммы и проценты условные
              </div>
              <div className="decisionRank">
                <span>ПРИОРИТЕТ 01</span>
                <b>{partial ? "С ограничением" : "Высокое влияние"}</b>
              </div>
              <h3>
                Две рекламные кампании расходуют бюджет без подтверждённой
                выручки
              </h3>
              <p>
                Детерминированная сверка нашла расход, но не нашла связанные
                продажи в выбранном периоде. Director предлагает проверку, а не
                автоматическое отключение.
              </p>
              <div className="moneyFinding">
                <div>
                  <span>НАБЛЮДАЕМЫЙ РАСХОД</span>
                  <strong>18 420,00 ₽</strong>
                  <small>демо · не равно потере прибыли</small>
                </div>
                <div>
                  <span>ПРИБЫЛЬ ЗА ПЕРИОД</span>
                  <strong>{partial ? "Не рассчитана" : "146 300 ₽"}</strong>
                  <small>
                    {partial ? "недостаточно данных" : "условный пример"}
                  </small>
                </div>
                <div>
                  <span>ЭФФЕКТ ДЕЙСТВИЯ</span>
                  <strong>
                    {unknown ? "Не подтверждено" : "Ещё не измерен"}
                  </strong>
                  <small>не приписан AI</small>
                </div>
              </div>
              <div className="evidenceBlock">
                <div className="evidenceHead">
                  <span>
                    <FileCheck2 /> ДОКАЗАТЕЛЬСТВА
                  </span>
                  <b>3 источника</b>
                </div>
                <dl>
                  <div>
                    <dt>Финансовый отчёт WB</dt>
                    <dd>
                      <CheckCircle2 /> подтверждён · 12.09 09:42
                    </dd>
                  </div>
                  <div>
                    <dt>Рекламная статистика</dt>
                    <dd className={partial ? "warnText" : ""}>
                      {partial ? (
                        <>
                          <AlertTriangle /> частично · 87%
                        </>
                      ) : (
                        <>
                          <CheckCircle2 /> подтверждено · 46 кампаний
                        </>
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>Период сопоставления</dt>
                    <dd>30 дней · Europe/Moscow</dd>
                  </div>
                </dl>
              </div>
              <div className="decisionAction">
                <div>
                  <span>РЕКОМЕНДОВАННОЕ ДЕЙСТВИЕ</span>
                  <b>Открыть кампании и проверить поисковые фразы</b>
                  <small>
                    Без записи в WB · исполнитель: владелец магазина
                  </small>
                </div>
                <div>
                  <button
                    type="button"
                    className="reject"
                    onClick={() => setActionStatus("rejected")}
                  >
                    <X /> Отклонить
                  </button>
                  <button
                    type="button"
                    className="approve"
                    onClick={() => setActionStatus("approved")}
                  >
                    <Check /> Подтвердить проверку
                  </button>
                </div>
              </div>
              <div className="inlineControl">
                <ShieldCheck />
                <span>
                  <b>Контроль исполнения рядом с действием</b>
                  <small>
                    Подтверждение создаёт только локальную демо-задачу. Записи в
                    WB нет; STOP доступен.
                  </small>
                </span>
                <button type="button">
                  <Pause /> STOP
                </button>
              </div>
              {actionStatus !== "idle" && (
                <div className={`demoReaction ${actionStatus}`} role="status">
                  {actionStatus === "approved" ? <CheckCircle2 /> : <X />}
                  <span>
                    <b>
                      {actionStatus === "approved"
                        ? "Проверка добавлена в демо-контроль"
                        : "Рекомендация отклонена в демо"}
                    </b>
                    <small>
                      Это локальная реакция интерфейса — внешнее действие не
                      выполнялось.
                    </small>
                  </span>
                </div>
              )}
            </article>
          )}
          <section className="productEvidence">
            <div className="sectionLine">
              <span>ТОВАРЫ В КОНТЕКСТЕ</span>
              <b>2 SKU</b>
            </div>
            <div className="productTable">
              <div className="productTableHead">
                <span>Товар</span>
                <span>Расход</span>
                <span>Выручка</span>
                <span>Достоверность</span>
              </div>
              <div>
                <span>
                  <i>01</i>
                  <b>{longProduct}</b>
                  <small>WB 194028374 · арт. NORTH-BAG-042</small>
                </span>
                <strong>12 840 ₽</strong>
                <strong>{partial ? "—" : "0 ₽"}</strong>
                <span className="confidence">
                  <CheckCircle2 /> подтверждено
                </span>
              </div>
              <div>
                <span>
                  <i>02</i>
                  <b>Органайзер дорожный модульный, набор 6 предметов</b>
                  <small>WB 194028411 · арт. TRAVEL-SET-006</small>
                </span>
                <strong>5 580 ₽</strong>
                <strong>0 ₽</strong>
                <span className={partial ? "confidence partial" : "confidence"}>
                  {partial ? (
                    <>
                      <AlertTriangle /> неполно
                    </>
                  ) : (
                    <>
                      <CheckCircle2 /> подтверждено
                    </>
                  )}
                </span>
              </div>
            </div>
          </section>
        </main>
        <aside className="directorAside">
          <div className="controlCard desktopControl">
            <div className="sectionLine">
              <span>КОНТРОЛЬ</span>
              <span className="safe">
                <ShieldCheck /> SAFE
              </span>
            </div>
            <h3>Исполнение остановлено по умолчанию</h3>
            <p>Подтверждение решения не отправляет изменения в Wildberries.</p>
            <button>
              <Pause /> STOP доступен всегда
            </button>
          </div>
          <div className="resultCard">
            <div className="sectionLine">
              <span>РЕЗУЛЬТАТ</span>
              <Clock3 />
            </div>
            <ol>
              <li className="done">
                <i />
                <span>
                  <b>Проблема обнаружена</b>
                  <small>12.09 · 09:46</small>
                </span>
              </li>
              <li className={unknown ? "unknown" : ""}>
                <i />
                <span>
                  <b>
                    {unknown
                      ? "Внешняя запись не подтверждена"
                      : "Ожидает решения"}
                  </b>
                  <small>
                    {unknown
                      ? "Сначала сверка, без повтора"
                      : "Нужно действие владельца"}
                  </small>
                </span>
              </li>
              <li>
                <i />
                <span>
                  <b>Измерение</b>
                  <small>После свежих данных</small>
                </span>
              </li>
            </ol>
          </div>
          <div className="sourceMini">
            <div className="sectionLine">
              <span>СВЕЖЕСТЬ</span>
              <Gauge />
            </div>
            <div>
              <span>Финансы</span>
              <b>
                18 мин <small>суточная политика</small>
              </b>
            </div>
            <div>
              <span>Остатки</span>
              <b className="warnText">
                просрочено <small>обновить</small>
              </b>
            </div>
            <div>
              <span>Реклама</span>
              <b>
                {partial ? "неполно" : "11 мин"}{" "}
                <small>{partial ? "87%" : "актуально"}</small>
              </b>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}

function Prototype({ screen, state }) {
  return (
    <section className="prototype">
      <ProductHeader screen={screen} />
      <div className="prototypeBody">
        {screen === "connect" ? (
          <ConnectScreen state={state} />
        ) : screen === "director" ? (
          <DirectorScreen state={state} />
        ) : (
          <HomeScreen />
        )}
      </div>
      <footer className="protoFooter">
        <span>D01 · ВИЗУАЛЬНЫЙ ПРОТОТИП</span>
        <p>
          Только синтетические данные. Интеграции, публикации и финансовые
          действия не выполняются.
        </p>
        <Link href={routeHref("home")}>
          В начало маршрута <ArrowRight />
        </Link>
      </footer>
    </section>
  );
}

const decisionStory = [
  {
    key: "01",
    label: "Данные магазина",
    value: "Финансы WB · реклама · себестоимость",
    note: "Сверено 09:42 · полнота 87%",
    state: "partial",
  },
  {
    key: "02",
    label: "Проблема",
    value: "Расход без подтверждённой выручки",
    note: "18 420 ₽ · наблюдаемый расход",
    state: "verified",
  },
  {
    key: "03",
    label: "Решение владельца",
    value: "Проверить две рекламные кампании",
    note: "Подтверждение обязательно",
    state: "decision",
  },
  {
    key: "04",
    label: "Выполнение",
    value: "Ожидает действия владельца",
    note: "STOP доступен · записи в WB нет",
    state: "waiting",
  },
  {
    key: "05",
    label: "Измерение",
    value: "Эффект ещё не измерен",
    note: "После свежих данных",
    state: "unknown",
  },
];

function StudyMark({ variant }) {
  if (variant === "b") {
    return (
      <svg className="studyMark" viewBox="0 0 48 48" aria-hidden="true">
        <path d="M5 8h14l5 8 5-8h14L32 24l11 16H29l-5-8-5 8H5l11-16z" />
        <circle cx="24" cy="24" r="4" />
      </svg>
    );
  }
  return (
    <svg className="studyMark" viewBox="0 0 48 48" aria-hidden="true">
      <path d="M5 5h38v38H5zM14 15h20M24 15v20M16 35h16" />
      <circle cx="24" cy="35" r="4" />
    </svg>
  );
}

function StudyNavigation({ variant }) {
  return (
    <header className="studyNav">
      <Link className="studyBrand" href={studyHref(variant)}>
        <StudyMark variant={variant} />
        <span>
          TROVENDI<small>VISUAL STUDY · D01</small>
        </span>
      </Link>
      <nav aria-label="Сравнение арт-направлений">
        <Link
          href={studyHref("a")}
          aria-current={variant === "a" ? "page" : undefined}
        >
          <span>A</span> Монументальная точность
        </Link>
        <Link
          href={studyHref("b")}
          aria-current={variant === "b" ? "page" : undefined}
        >
          <span>B</span> Технологическая платформа
        </Link>
        <Link href={routeHref("home")}>
          Контроль <ArrowRight />
        </Link>
      </nav>
    </header>
  );
}

function MonumentalGraphic() {
  return (
    <section className="studyStory monumentalStory" aria-labelledby="story-a">
      <div className="studySectionHead">
        <span>КОНТУР РЕШЕНИЯ / 01—05</span>
        <h2 id="story-a">Каждый вывод оставляет проверяемый след.</h2>
        <p>
          Не обещание роста, а последовательность фактов, решения и измерения.
        </p>
      </div>
      <ol className="monumentalLedger">
        {decisionStory.map((item) => (
          <li key={item.key} data-state={item.state}>
            <span>{item.key}</span>
            <div>
              <small>{item.label}</small>
              <b>{item.value}</b>
              <em>{item.note}</em>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function PlatformGraphic() {
  return (
    <section className="studyStory platformStory" aria-labelledby="story-b">
      <div className="platformStoryTitle">
        <span>DECISION SYSTEM / LIVE TRACE</span>
        <h2 id="story-b">Данные становятся управляемым действием.</h2>
        <p>Пять понятных состояний одного решения — без скрытой автономии.</p>
      </div>
      <ol className="platformOrbit">
        {decisionStory.map((item, index) => (
          <li
            key={item.key}
            className={`orbitStep step${index + 1}`}
            data-state={item.state}
          >
            <span>{item.key}</span>
            <div>
              <small>{item.label}</small>
              <b>{item.value}</b>
              <em>{item.note}</em>
            </div>
            {index < decisionStory.length - 1 && <i aria-hidden="true" />}
          </li>
        ))}
      </ol>
    </section>
  );
}

function StudyMobileDirector({ variant }) {
  const [status, setStatus] = useState("idle");
  return (
    <section
      className="studyMobile"
      aria-label={`Mobile Director, направление ${variant.toUpperCase()}`}
    >
      <div className="mobileDirectorTop">
        <span>DAILY DIRECTOR · ДЕМО</span>
        <b>
          <AlertTriangle /> ДАННЫЕ 87%
        </b>
      </div>
      <div className="mobileDirectorIndex">01 / РЕШЕНИЕ ДНЯ</div>
      <h1>Проверить расход без подтверждённой выручки.</h1>
      <p>
        Две кампании расходуют бюджет. Director предлагает проверку, а не
        автоматическое отключение.
      </p>
      <div className="mobileAmount">
        <small>НАБЛЮДАЕМЫЙ РАСХОД</small>
        <strong>18 420,00 ₽</strong>
        <span>условные демо-данные · не равно потере прибыли</span>
      </div>
      <div className="mobileFacts">
        <div>
          <CheckCircle2 />
          <span>
            <small>ПРОБЛЕМА</small>
            <b>Подтверждена</b>
          </span>
        </div>
        <div>
          <CircleDashed />
          <span>
            <small>ЭФФЕКТ</small>
            <b>Не измерен</b>
          </span>
        </div>
      </div>
      <div className="mobileRecommendation">
        <small>СЛЕДУЮЩИЙ ШАГ</small>
        <b>Открыть кампании и проверить поисковые фразы</b>
        <span>Исполнитель: владелец · без записи в WB</span>
      </div>
      <div className="mobileActions">
        <button
          type="button"
          className="studyReject"
          onClick={() => setStatus("rejected")}
        >
          Отклонить
        </button>
        <button
          type="button"
          className="studyApprove"
          onClick={() => setStatus("approved")}
        >
          Подтвердить <ArrowRight />
        </button>
      </div>
      <div className="mobileControl">
        <ShieldCheck />
        <span>
          <b>Контроль рядом с действием</b>
          <small>STOP доступен всегда</small>
        </span>
        <button type="button">
          <Pause /> STOP
        </button>
      </div>
      {status !== "idle" && (
        <div className={`studyReaction ${status}`} role="status">
          {status === "approved"
            ? "Демо-задача добавлена в контроль"
            : "Рекомендация отклонена локально"}
        </div>
      )}
    </section>
  );
}

function ArtDirection({ variant }) {
  const isA = variant === "a";
  return (
    <main className={`artStudy study${variant.toUpperCase()}`}>
      <StudyNavigation variant={variant} />
      <div className="studyDesktop">
        <section className="studyHero">
          <div className="studyHeroCopy">
            <span className="studyKicker">
              ДЛЯ ДЕЙСТВУЮЩИХ ПРОДАВЦОВ WILDBERRIES
            </span>
            <h1>
              {isA ? (
                <>
                  Решения,
                  <br />
                  которые выдерживают <em>проверку.</em>
                </>
              ) : (
                <>
                  Видеть потери.
                  <br />
                  Выбирать действие.
                  <br />
                  <em>Доводить до результата.</em>
                </>
              )}
            </h1>
            <p>
              TROVENDI находит подтверждённые проблемы магазина, показывает
              доказательства и сохраняет контроль от решения владельца до
              измерения.
            </p>
            <div className="studyHeroActions">
              <button type="button">
                Начать с подключения <ArrowRight />
              </button>
              <span>
                <ShieldCheck /> Без действия без подтверждения
              </span>
            </div>
          </div>
          <aside className="studyDecisionPreview">
            <div className="studyDecisionHead">
              <span>TRACE / WB–01 · ДЕМО</span>
              <b>НУЖНО РЕШЕНИЕ</b>
            </div>
            <small>НАБЛЮДАЕМЫЙ РАСХОД</small>
            <strong>18 420,00 ₽</strong>
            <p>Две кампании без подтверждённой выручки</p>
            <dl>
              <div>
                <dt>Данные</dt>
                <dd>87% · неполно</dd>
              </div>
              <div>
                <dt>Действие</dt>
                <dd>Проверить кампании</dd>
              </div>
              <div>
                <dt>Эффект</dt>
                <dd>Ещё не измерен</dd>
              </div>
            </dl>
            <button type="button">
              Открыть доказательства <ArrowRight />
            </button>
          </aside>
        </section>
        {isA ? <MonumentalGraphic /> : <PlatformGraphic />}
        <footer className="studyFooter">
          <span>НАПРАВЛЕНИЕ {variant.toUpperCase()} · ИЗОЛИРОВАННЫЙ ЭТЮД</span>
          <p>Только синтетические данные · внешние действия не выполняются</p>
        </footer>
      </div>
      <StudyMobileDirector variant={variant} />
    </main>
  );
}

export default function D01DesignReference() {
  const params = useSearchParams();
  const variant = ["a", "b", "control"].includes(params.get("variant"))
    ? params.get("variant")
    : "a";
  const screen = ["home", "connect", "director"].includes(params.get("screen"))
    ? params.get("screen")
    : "home";
  const state = directorStates.some(([key]) => key === params.get("state"))
    ? params.get("state")
    : "complete";
  if (variant !== "control") return <ArtDirection variant={variant} />;
  return (
    <main className="d01 d01-final has-prototype">
      <Prototype screen={screen} state={state} />
    </main>
  );
}
