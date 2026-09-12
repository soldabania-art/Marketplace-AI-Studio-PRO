# TROVENDI: архитектурный аудит 12.09.2026

Исследован исходный коммит **f090a4b3006ff72351d7c37696ae3d7c228e7805**. Этот отчёт фиксирует состояние до исправлений из backlog.

## 1. Решение

**Одобрено:** направление AI Commerce OS, web-first, Wildberries как первая полная вертикаль, общий контур для продавца/новичка/агентства, интеграции РФ/СНГ, полноценная сеть фулфилментов и документное хранилище.

**Не одобрено:** объявление готовности к широкому коммерческому запуску, неограниченный автопилот, заявления о работающих сотнях партнёров или полном Ozon-контуре. Сильный задел уже существует, но декларативные политики местами не подключены к реальным точкам исполнения.

Следующему разработчику передаётся [упорядоченный backlog](DEVELOPER_BACKLOG.md), а не задача «добавлять всё дальше». Первые изменения — CI, STOP, права на AI, достоверность финансов. Расширение запрещённых возможностей до закрытия их gates не считается прогрессом.

## 2. Объём и пределы проверки

| Проверка | Результат |
| --- | --- |
| Полное дерево исходников | 354 файла, каждый скачан и сверен по Git blob SHA |
| Состав | 174 Python, 125 JavaScript, 24 CSS, 17 Markdown, 3 MJS и служебные файлы |
| Python syntax | Все 174 файла разобраны AST |
| Архитектура | Проверены продуктовые документы, структура всех модулей, маршрутов, моделей и цепочки из 27 миграций; подробно рассмотрены критические бизнес-пути |
| Backend CI | 149 passed, 3 warnings; [run 34683401279](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/actions/runs/34683401279), event=push, head=f090a4b |
| Frontend CI | Next.js build success в том же run |
| Локальный frontend unit | 4/4 CSV tests через node --test |
| Изолированные проверки функций | Воспроизведены шесть неверных результатов ниже, без AI, WB и production DB |
| Vercel | GitHub commit status success; настройки проекта недоступны, 403; connector не вернул доступных teams |
| Runtime/инфраструктура | Нет подтверждения живого worker, migrations, backup restore, billing, scanner и production e2e |
| Полный локальный backend/build | Не запускались повторно: установка зависимостей недоступна; результаты suite/build выше взяты из CI |

Это статический архитектурный аудит с отдельными воспроизведениями, не полный pentest, не юридическое заключение и не сертификация каждой интеграции. Все файлы охвачены инвентаризацией; не заявляется построчная ручная проверка каждого CSS, lockfile или legacy UI.

В предыдущей переписке указано 147 тестов и что документы не опубликованы. На проверенном SHA это неточно: CI показывает 149; уже существуют DocumentVault UI/API, защищённый download, scan callback и миграция 0027.

## 3. Что сохраняем

- Store/workspace isolation через серверную membership-проверку; encrypted marketplace tokens; revocable sessions, TOTP MFA и step-up.
- Детерминированный Profit Center, integer kopecks, provenance, source hashes, immutable cost-import preview с отдельным commit.
- Сохранённые AI-generations, fact hashes, отдельные text/media publication records и live preflight карточки.
- PostgreSQL-backed jobs, idempotency keys, retries, отдельный worker и уже реализованный Redis limiter.
- Director с правилами без платы за AI, явными решениями и измерениями.
- Deny-by-default registry, поддержка из одобренных документов и эскалация инцидентов.
- Каталог интеграций с planned/discovery status; частный документный сейф с карантином.
- Модульное приложение вместо преждевременных микросервисов. Legacy desktop сохраняем, но не развиваем как параллельный продукт.

## 4. Фактическая готовность модулей

«Код есть» и «production подтверждён» — разные состояния. Ни один внешний сценарий не получает production-статус только на основании этого аудита.

| Направление | Реально найдено | Главный незакрытый разрыв |
| --- | --- | --- |
| Public entry | Landing, планы, выбор каналов/модулей, purchase intent | Выбор модулей не равен модульным серверным правам и итоговому workspace UX |
| Auth/MFA | Accounts, sessions, TOTP, recovery tokens, step-up | Email delivery отсутствует; concurrency и multi-workspace flow требуют проверки |
| Billing | PLAN_CATALOG, subscription events, entitlement snapshot | Checkout всегда 503; нет provider webhook adapter |
| WB | Catalog/stocks/sales/finance/ads/reviews readers, text/media update | Безопасность реальных записей, строгий import contract, reconciliation |
| Ozon и новые каналы | Planned catalog; Ozon в desktop | Web read/write parity отсутствует |
| Profit | Store ledgers, costs, tax reserve, CSV preview/commit | Неверные данные могут стать нулём; mutable costs, SQL bounds и source reconciliation |
| Card Factory | Copy/image generation, Blob, preview и WB update | Недостаточное grounding, бюджеты, STOP, asset ownership и identity verification |
| Beginner | Photo → confirmed facts → draft/economics → saved project | Общие paid visuals, budgets; new-card create не равен update nm_id |
| Director | Persisted rules queue, decisions, read-sync, measurement | Несогласованная freshness, общий Action lifecycle и STOP |
| Agent network | Typed registry, work orders и reviewed learning candidates | Это control-plane foundation, не работающая сеть автономных исполнителей |
| Ads/SEO/Inventory/Reports/Autopilot | Отдельные route shells через StudioSection | Кнопки объясняют будущую функцию; операционные очереди не реализованы |
| Reviews | Snapshot и сохранённый AI-анализ/черновики | Scheduler feedbacks, budgets, workflow ответа; auto-reply выключен |
| FBO | Slots, watch, worker, детерминированный supply calculation | Regional allocation/физические поставки/масштаб не подтверждены |
| Fulfillment | Partner/facility/connection catalog, Protocol | Нет живого адаптера, partner workspace, custody/reservations/orders/settlements |
| Documents | Private upload metadata/finalize, scan callback, protected download | Transport 25 МБ, scan job/retry, document ACL/relationships и retention |
| Support | Incident intake, evidence bundle, approved lexical knowledge | Нет полноценной очереди исполнения человеком и гарантии эскалации всех формулировок |
| Community | community_access в active paid plans | Нет форума, модерации и API |
| CIS/Manufacturer/Wholesale/Android | Принятая целевая архитектура | Discovery/последующие этапы, не текущие продаваемые функции |

## 5. Findings: код и воспроизведение

### F01 — STOP не подключён к Card Factory writes · P0 · T02

В [director_router.py](backend/app/director_router.py) set_automation_control записывает AutomationControl. В [card_factory_router.py](backend/app/card_factory_router.py) publish_card/publish_media нет чтения этого контроля; wb_content writer также его не проверяет. Registry запретов агентов не распространяется автоматически на самостоятельный publisher.

Следствие: STOP нельзя представлять как глобальную гарантию. Нужен общий gate непосредственно перед отправкой, а не только состояние UI.

### F02 — paid read_only проходит AI gate · P0 · T03

В [trial_service.py](backend/app/trial_service.py) ensure_ai_access отклоняет только expired/exhausted. Paid entitlement возвращает status=read_only, и эта ветка проходит. Изолированный запуск исходной функции с paid read_only snapshot вернул его без исключения. Это проверка функции, не имитация успешного production HTTP запроса.

В Card Factory наличие предыдущей генерации включает allow_exhausted=True, затем создаётся новая генерация вместо чтения cached result. Общий серверный entitlement должен быть проверен до каждого нового provider call.

### F03 — ошибки финансового источника превращаются в валидные данные · P0 · T04

[wb_finance.py](backend/app/wb_finance.py): _kopecks({"forPay":"broken"},"forPay") возвращает 0; _rows с неизвестной формой ответа возвращает []. [marketplace_sync.py](backend/app/marketplace_sync.py) использует not rows как признак полного импорта.

В рекламном импорте нормализация неожиданного payload также может вернуть пустой список; sync затем удаляет строки текущего batch, которых нет в seen. Это опасная комбинация tolerant parser и destructive reconciliation. Пустой контрактный ответ, пропущенные данные и parse error должны различаться.

### F04 — grounding проверяет ссылки и числа, но не истинность свойств · P0 · T05

[ai_card_factory.py](backend/app/ai_card_factory.py) validate_grounding принимает результат «Сумка из натуральной кожи», «сертифицированная», «водонепроницаемая» при единственном исходном факте «Сумка» и корректном used_fact_ids. Это воспроизведено исходной функцией без AI.

Также наличие числа где-то в source_text не доказывает его связь с конкретным размером/объёмом. Нужны типизированные утверждения, field-level grounding, серверная схема и отдельный gate неподтверждённых claims.

### F05 — неверная идентификация опубликованного изображения · P0 · T06

[card_factory_router.py](backend/app/card_factory_router.py) _media_verification_result проверяет прежний prefix и число фото. Исходные [original] и свежие [original, unrelated-image] дают applied. Это подтверждает появление элемента, но не нашего изображения.

finalize_visual принимает любой host с суффиксом .blob.vercel-storage.com, отдельно проверяет pathname и позволяет повторно перезаписать result_payload. Собственный Blob store и неизменяемость версии должны подтверждаться сервером. Recovery неясного write должен оставаться read-only до установления результата.

### F06 — конфликт политики freshness · P0 · T07

Director считает любой snapshot stale после 900 секунд. Data Health определяет для finance warn_after=86400/stale_after=172800; scheduler finance по умолчанию раз в сутки, analytics раз в 1800 секунд. Finance возрастом 20 минут воспроизводимо stale в Director при штатном состоянии по политике Data Health.

Отдельный scheduler не планирует feedbacks, хотя Director их использует. Период finance требует точного совпадения rolling дат; переход дня нужно тестировать отдельно от возраста источника.

### F07 — долгие задачи и транзакционные границы · P0 для масштабирования · T08

[job_queue.py](backend/app/job_queue.py) делает running job доступной для повторного claim через lease=300 секунд; heartbeat/fencing per attempt отсутствуют. Handler может ждать rate limiter/несколько внешних запросов дольше. _finish проверяет worker_id, но не уникальную попытку.

enqueue сам вызывает commit, что разрывает атомарность вызывающего доменного изменения/аудита/задачи. В scheduler session-level advisory lock совмещён с commit через ту же Session; нужно проверить удержание конкретного соединения и release, иначе возможна утечка lock через pool. Последнее — риск по коду, не воспроизведённый PostgreSQL-инцидент.

Redis limiter уже есть в коде, несмотря на устаревшие формулировки SCALING. Проверить его настройку нужно для API и worker вместе, не только после появления второго worker.

### F08 — путь до оплаты заблокирован раньше checkout · P0 · T09/T10

[account_router.py](backend/app/account_router.py) _delivery_response всегда сообщает email_provider_not_configured. Перед paid checkout требуется verified email, но доставки нет. create_billing_checkout возвращает 503 при любой конфигурации; apply_subscription_event — сервис для уже проверенного события, не готовый webhook endpoint.

Не менять флаг billing_provider для имитации готовности. Нужен реальный sandbox путь, порядок событий и доставка сообщений.

### F09 — documents transport превышает hosting limits · P0 для документов · T11/T12

[upload route](app/api/document-vault/route.js) принимает multipart до 25 000 000 bytes через Vercel Function; [download route](app/api/document-vault/[document_id]/download/route.js) буферизует файл целиком. Лимит обычного request/response body Vercel Function — 4,5 МБ: [официальная документация](https://vercel.com/docs/functions/limitations), проверена 12.09.2026. Отдельное решение требуется и для загрузки, и для защищённой выдачи.

[document_vault_router.py](backend/app/document_vault_router.py) не ставит scan job; внешний scanner пока только ожидается. После verdict=error scan_status перестаёт быть pending, и следующий callback отвергается; duplicate callback также 409. Требуются job/retry/event identity. Загрузка проверяет membership, но не write role; partner_id проверяется на существование, не на связь с магазином. Это не доказательство утечки чужого файла, но незавершённая модель document authorization.

### F10 — multi-workspace и исходящие запросы · P0 · T13

billing_subscription/purchase_intent/activation выбирают первый Membership без явного workspace context. Для пользователя с несколькими организациями это неоднозначно.

[push_router.py](backend/app/push_router.py) проверяет лишь HTTPS и netloc endpoint; worker затем делает исходящую доставку. Нужен outbound policy для адресов/redirects/DNS и доверенных push служб. Реальные внутренние адреса в ходе аудита не вызывались.

### F11 — AI стоимость и исполнение не соответствуют целевой политике · P1/launch gate · T15

Веб-генерация напрямую использует OpenAI; desktop ai_router не является web router. begin_generation не резервирует budget и не дедуплицирует новую работу. Default token prices=0, а complete_generation хранит estimated_cost=0: «цена неизвестна» не должна выглядеть как бесплатный вызов.

fail_generation сохраняет str(error), public_generation отдаёт его пользователю. Нужны redacted public error и отдельная диагностика. Долгие генерации синхронны, не используют общую durable queue.

### F12 — рабочий UI частично имитирует функции · P1 · T16/T21

[app/page.js](app/page.js) показывает статические dashboardActions; ask() лишь возвращает строку «AI принял вопрос» без сервиса. Пять операционных страниц используют [StudioSection](components/StudioSection.js), где кнопка показывает текст о будущей интеграции.

Public entry нужно сохранить; главный authenticated путь должен вести к реальной очереди Director. В исходном blueprint Dashboard/KPI и 17 пунктов навигации конкурируют с action-first концепцией; новое дерево устраняет противоречие.

### F13 — историческая прибыль и большие объёмы · P1 · T17

[profit_center_router.py](backend/app/profit_center_router.py) загружает все financial/ads rows магазина через .all(), затем фильтрует период Python-кодом. Последний ProductCostProfile применяется к историческим net units. Текущая цена затрат может изменить прошлый расчёт; закрытый отчёт и сценарный перерасчёт не разделены.

Список products строится из financial rows: SKU с рекламным расходом без продаж может присутствовать в total, но отсутствовать в SKU-очереди. Нужны versioned costs, bounded SQL и reconciliation bridge. Точные правила стоимости возврата должны быть подтверждены, не придуманы AI.

### F14 — безопасность расширений пока декларативна · P1/P2 · T18–T20/T22

FulfillmentAdapter содержит часть методов, но не весь объявленный набор capabilities. limit=500 partners/5000 facilities — это truncation ответа, не архитектурное доказательство обслуживаемой сети. Нет ledger приёмки/резервов/отгрузок, тарифа по версии, partner access и settlement reconciliation.

Support создаёт тикет, но не полноценный маршрут обработки человеком. Классификация после redaction/truncation требует regression case с риском за пределами первых 1000 символов. Эти задачи должны иметь собственные acceptance criteria.

### F15 — CI не покрывает заявленные гарантии · P0 · T01/T14

Workflow срабатывает на push в main/web-cloud, а не pull_request. CSV tests не подключены к workflow. Backend CI использует SQLite; нет migration job PostgreSQL, browser e2e или concurrency tests. Тесты успешны, но не доказывают названные гарантии. Некоторые старые demo routes остаются в router.py; /director объявлен дважды в разных routers, фактический порядок сейчас выбирает authenticated route. Это следует упорядочить в T16 с route-contract test.

## 6. Обновлённое архитектурное направление

1. Один модульный backend; типизированные доменные сервисы вместо вызовов router→router в новых разработках.
2. Общие Workspace/Store/Connection/Product identities. nm_id — внешний WB ID, не универсальная идентичность товара.
3. Общий Action lifecycle для ручных и будущих AI-записей: evidence → proposal → approval → dispatch gate → execution → verification → measurement; компенсация только если физически/технически возможна.
4. Общие jobs/outbox/inbox, ограничение расходов и rate limits. UI request не держит всю долгую операцию.
5. Сеть фулфилментов: partner catalog, partner identity, seller agreement и store/facility grants — отдельные сущности. Физические события неизменяемы и идемпотентны.
6. Document Vault — общий слой доказательств с private storage, версиями, связями и правами. Public marketplace assets отделены от деловых документов.
7. Все денежные контракты готовы к currency/minor units и versioned rules; полноценная мультивалютная экономика следует после сверенного WB.
8. Frontend: общий authenticated shell с выбранным контекстом, STOP, реальными возможностями и основной очередью; дополнительные отчёты раскрываются по задаче.

Целевое дерево — в [PRODUCT_TREE](PRODUCT_TREE.md). Физический перенос всех файлов сейчас не нужен. Сначала исправления контракта и regression tests, затем последовательное выделение доменных границ.

## 7. Release gates

- **Внутренний/контролируемый read-only пилот:** допускается с выключенными платными/внешними действиями, видимыми ограничениями данных и ответственным оператором.
- **Платная WB-вертикаль:** закрыты применимые P0, email/billing, бюджеты и проверенный runtime; новая карточка и update имеют отдельные capability gates.
- **Документы/партнёрский пилот:** закрыты transport, scan lifecycle, ACL и relationship gates. Если они не закрыты, модуль не продаётся как готовый.
- **Сеть сотен фулфилментов:** только после пилота, ledger/reconciliation, изоляции партнёров, pagination, recovery и теста нагрузки в реальной целевой конфигурации.
- **Автономные действия:** отдельный gate на каждый action type; STOP, лимит, policy, контроль источников и исхода проверены. Registry flag не заменяет этого.
- **Расширение СНГ:** сохраняется как архитектурный план, с country/API/contract discovery. Юридическая или налоговая применимость настоящим аудитом не устанавливается.

## 8. Передача

Первым закрывается T01, далее T02/T03/T04. Зависимости, допустимый объём и приёмка каждой задачи указаны в backlog. Последующий исполнитель не получает разрешения считать весь проект готовым; он получает одобренную концепцию и проверяемый порядок доведения до рабочего продукта.
