# TROVENDI — дерево продукта

Версия архитектуры: **12.09.2026**. Проверенный baseline: `f090a4b`.
Концепция одобрена для разработки; production-готовность не утверждена. Доказательства — [аудит](ARCHITECTURE_REVIEW_2026-09-12.md); ближайшие задачи — [backlog](DEVELOPER_BACKLOG.md).

## 1. Как читать дерево

- **Код / частично:** путь или часть логики есть; это не гарантия работающего production.
- **Shell:** страница существует, операция не реализована.
- **План:** принятая часть концепции без готового исполнения.
- **Внешний gate:** нужны проверенный provider/runtime/договор/данные.
- **Production подтверждён:** присваивается только отдельной capability со ссылкой на датированную проверку exact SHA.

Старое обозначение «live foundation» заменено более точным состоянием. У каталогов интеграций должны отдельно храниться declared, implemented, certified и enabled capabilities.

## 2. Продуктовые ветви

| Ветвь первого уровня | Подветви | Текущий статус и ближайший результат |
| --- | --- | --- |
| Вход и активация | Public landing; выбор маркетплейсов, модулей и масштаба; тариф; account/email; платёж; MFA; выбранное рабочее пространство | Код / частично. T09/T10/T16: работающий путь и честная доступность |
| Beginner Studio | Фото → подтверждённые факты → экономика → текст/визуалы → preview → доступная публикация/экспорт → Director | Код / частично. T21: общий сохраняемый проект; new-card create — отдельная capability |
| Seller workspace | Один или несколько магазинов; цели; operating profile; context; подключённый набор | Код / частично. T13/T16: workspace/store и права без смешения |
| Agency workspace | Клиенты; назначения сотрудников; роли; portfolio; client portal; white label; bulk approvals | План поверх общих организаций и stores; не отдельный финансовый engine |
| AI Director | Очередь по фактам; объяснения; решения; план; handoff в модуль; измерение | Код / частично. T02/T07/T16: общий STOP и согласованная freshness |
| AI platform | Capability registry; Rules/Free, Economy, Premium; router; budget; jobs; prompts/evals; reviewed learning; Sentinel | Registry и generation persistence есть; T05/T15: реальный runtime contract |
| Товары и контент | Canonical products/variants/listings; фактология; Card Factory; SEO; версии; локализация | WB-код и частичные UI. T05/T06/T18: facts, immutable assets, canonical ID |
| Финансы | Source ledgers; profit; COGS; tax reserve; рекламные затраты; сверка; штрафы; claims; отчёты | Код / частично. T04/T17: строгий импорт и воспроизводимые периоды |
| Продвижение | Реклама; ставки/лимиты; reviews; SEO/search; competitor intelligence; Growth Lab/A-B; external traffic | Ads readers/reviews есть; остальные очереди частично или план |
| Запасы и поставки | Складские остатки; demand/cover; FBO slots; supply plan; FBS; reservations; возвраты | WB/FBO foundation. Физический ledger и подтверждённое распределение — план |
| Сеть фулфилментов | Каталог → partner onboarding → договор и grants → facilities → интеграция → приёмка/резерв/заказ/возврат → тарифы/сверка | Каталог/модели есть. T19 read-only pilot, затем T20 operations |
| Документы и доказательства | Seller/partner/order/buyer документы; версии; private storage; scan; links; search; export; retention/hold | Код / частично. T11/T12 до продажи готового сейфа |
| Integration Hub | WB → Ozon → ЯМ/Kaspi/Uzum; 1С/МойСклад/Saby/Контур; WMS/fulfillment; CSV/XLSX; EDI/OFD | WB и CSV foundation; остальные по adapter gates T18 |
| Поддержка и сообщество | Контекстная помощь; incidents/human queue; база знаний; paid forum; verified profiles/partnerships | Support foundation; T22. Форум план, доступ всем активным paid |
| Управление платформой | Auth/MFA/RBAC; billing; admin; audit; secrets; data health; worker/queue; backups; observability | Код / инфраструктурные gates T01/T08/T13/T14 |
| Каналы уведомлений | In-app; Web Push/PWA; Telegram; Android camera/alerts/approve/STOP | Web Push foundation; остальные план на общем API/event model |
| Расширение РФ/СНГ | Multi-currency/FX; country/route profiles; localization; seller-of-record; Manufacturer BOM; wholesale/D2C | Discovery и последовательные пилоты после сверенного ядра |

## 3. Главный пользовательский маршрут

Публичная страница доступна без входа. На ней видны функции, каналы, тарифы и что доступно сейчас. Пользователь сохраняет выбор, создаёт account, подтверждает email и оплачивает выбранный доступ через провайдера. Права выдаёт только проверенное серверное событие. Затем MFA и вход в выбранный store/workspace. Trial пропускает платёж, но не защиту marketplace credentials.

Внутри магазина главный экран — **реальная очередь AI Director** с одной следующей задачей в Guided mode и evidence/альтернативами в Expert mode. KPI — контекст к решениям и вторичный обзор. У каждого результата видны источник, время, магазин, провайдер/режим и стоимость либо «неизвестна». STOP доступен постоянно. Инциденты поддержки и форум — разные функции.

## 4. Общее дерево данных и полномочий

| Родитель | Дочерние сущности | Граница |
| --- | --- | --- |
| User | Memberships, sessions, MFA | Пользователь может состоять в нескольких организациях |
| Workspace | Clients при Agency, Stores, subscription, budgets | Explicit context; первый Membership не является выбором пользователя |
| Store | MarketplaceConnections, canonical products, source records, actions | Каждая операция разрешается сервером |
| Product / Variant | MarketplaceListings и partner mappings | WB nm_id — внешний ID; не универсальный ключ |
| Partner organization | Memberships, facilities, adapter/credentials | Изолированный домен партнёра |
| Seller ↔ Partner agreement | Store/facility grants, capabilities, тарифные версии | Разрешены только указанные операции и данные |
| Operation / Order / Shipment | Immutable events, stock movements, reservations, claims | Физический факт не выводится из текста AI |
| Business entity | Document links и document versions | Tenant + role + relationship + scan/retention |
| Action | Evidence, proposal/hash, decision, execution, verification, measurement | Один договор исполнения для ручных и AI writes |

Это целевая модель; существующие таблицы покрывают лишь часть строк. Новые сущности вводятся миграциями, не отмечаются реализованными заранее.

## 5. Сеть фулфилментов: обязательная детализация

| Подветвь | Что должно быть внутри |
| --- | --- |
| Партнёр и площадки | Проверенный контрагент, страны, timezone, facility, поддерживаемые операции, версия интеграции |
| Подключение продавца | Договор, согласие сторон, scope stores/facilities, secret reference, test/read-only, отзыв доступа |
| Товары и остатки | Canonical SKU mapping, единицы, owner stock, available/reserved/quarantine, cursor и сверка |
| Приёмка | Заявка, подтверждение, фактические количества, расхождения, акт и доказательства |
| Заказы и отгрузки | Резерв, сборка, упаковка, частичная отгрузка, carrier milestones, отмена |
| Возвраты и claims | Приём возврата, состояние, карантин, повторная продажа/списание, претензия |
| Тарифы и расчёты | Версия тарифа, quote, согласование, акт, начисление, сверка и dispute |
| Документы | Ссылки на договор/операцию, immutable versions, scan, permissions, hold/retention |
| Надёжность | Signed events, inbox/outbox, duplicate/out-of-order handling, retry, reconciliation, audit |
| Масштаб | Pagination, индексы, rate limits, worker isolation, monitoring и реальная нагрузочная проверка |

500 записей каталога не означают 500 работающих интеграций. Первый gate — один read-only партнёр; затем физические операции на контролируемом пилоте; затем измеренное масштабирование.

## 6. Очерёдность

| Этап | Результат | Основные задачи |
| --- | --- | --- |
| A. Контроль изменений | Проверки PR и PostgreSQL | T01 |
| B. Достоверность и безопасность | STOP, entitlements, import/facts/media/freshness, jobs и access | T02–T08, T13 |
| C. Готовая платная WB-вертикаль | Email, billing, budgets, runtime, понятный UX и сверка | T09/T10/T14–T17/T21/T22 |
| D. Документы и общий integration contract | Private transport/lifecycle, canonical IDs | T11/T12/T18 |
| E. Фулфилменты | Read-only пилот, затем operations/ledger | T19/T20 |
| F. Расширение | Ozon, 1С/МойСклад, agency, paid community, Android | Следующие ограниченные задачи после gates ядра |
| G. СНГ/производство/опт | Казахстанский read-only пилот; затем остальные направления | Discovery по EXPANSION_STRATEGY |

Этапы C/D можно вести независимо там, где зависимости закрыты. Форум сохраняется для каждого активного платного пользователя; его нельзя обещать уже работающим. Операции 1С и других источников используют тот же preview/commit для затрат.

## 7. Физическая структура разработки

Сохраняем `web/app`, `web/components`, `web/lib`, `web/backend/app` и Alembic. Выделять доменные сервисы постепенно по выполняемой задаче: identity, billing, AI, actions, commerce, integrations, fulfillment, documents, support. Не переносить всё в новую структуру одновременно.

[PRODUCT_ROADMAP](PRODUCT_ROADMAP.md) хранит весь принятый scope и историю; раздел 0 фиксирует новое решение. [DEVELOPER_BACKLOG](DEVELOPER_BACKLOG.md) задаёт следующий проверяемый шаг. [SECURITY_MODEL](SECURITY_MODEL.md), [AI_ORCHESTRATION_AND_SCALE](AI_ORCHESTRATION_AND_SCALE.md), [EXPANSION_STRATEGY](EXPANSION_STRATEGY.md) остаются тематическими контрактами.
