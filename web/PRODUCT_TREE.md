# TROVENDI — дерево продукта

Версия стратегии: **12.09.2026**. Проверенный baseline `main`: `00ad0318abe7cebe353015afdb7f68847054f960`.
Концепция одобрена для разработки; production-готовность и коммерческий запуск не утверждены. Доказательства — [аудит](ARCHITECTURE_REVIEW_2026-09-12.md); ближайшие задачи — [backlog](DEVELOPER_BACKLOG.md).

## 0. Фокус первого этапа

**Первичный клиент:** действующий продавец Wildberries с регулярными продажами, сотрудниками и операционными расходами. Beginner Studio, агентства и новые рынки остаются в дереве, но не определяют ближайший релиз.

**Обещание:** TROVENDI помогает находить потери прибыли, принимать решения и контролировать их выполнение между магазином, командой и фулфилментом.

**Проверяемый маршрут:**

1. Подключить магазин.
2. Получить данные и увидеть полноту, свежесть и ограничения.
3. Увидеть детерминированный финансовый результат и подтверждённые проблемы.
4. Получить приоритетные задачи с исходными данными и доказательствами.
5. Подтвердить только разрешённое действие.
6. Увидеть исполнителя, статус, затраты, способ измерения и наблюдаемый результат.

AI работает только поверх проверенных данных. Денежные расчёты выполняют детерминированные сервисы. Интерфейс и API обязаны различать подтверждённый факт, предположение и неизвестное значение. Изменение прибыли нельзя приписывать AI-действию без достаточной причинной доказательности.

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

| Горизонт | Результат | Основные задачи и gates |
| --- | --- | --- |
| Ближайший релиз | Надёжный Wildberries: достоверная экономика, ежедневные задачи, безопасное подтверждённое выполнение | Независимая приёмка T02/T04; затем T05; далее T06–T08, T13, T16–T17 по зависимостям |
| Следующий этап | Подписка с проверяемыми лимитами, AI unit economics и платный пилот; документы и read-only пилот фулфилментов | T09–T12, T14–T15, T18–T20, T22; коммерческие критерии из backlog |
| После доказанного WB-контура | Ozon, затем один зарубежный рынок после отдельной проверки спроса | Отдельные discovery и capability gates; не массовое подключение стран |
| Отложено | Продукт для новичка без продаж, собственный конструктор магазинов, массовые страны, собственные склады, кредитование/расчёты, неограниченная автономная реклама, собственная базовая AI-модель | Сохранить существующие функции; не расширять и не создавать экраны-заглушки |

Документы и роли фулфилментов проектируются для сотен партнёров, но сначала доказываются в ограниченном read-only пилоте. Тарифные цены остаются гипотезами до коммерческой проверки.

## 7. Физическая структура разработки

Сохраняем `web/app`, `web/components`, `web/lib`, `web/backend/app` и Alembic. Выделять доменные сервисы постепенно по выполняемой задаче: identity, billing, AI, actions, commerce, integrations, fulfillment, documents, support. Не переносить всё в новую структуру одновременно.

[PRODUCT_ROADMAP](PRODUCT_ROADMAP.md) хранит весь принятый scope и историю; раздел 0 фиксирует новое решение. [DEVELOPER_BACKLOG](DEVELOPER_BACKLOG.md) задаёт следующий проверяемый шаг. [SECURITY_MODEL](SECURITY_MODEL.md), [AI_ORCHESTRATION_AND_SCALE](AI_ORCHESTRATION_AND_SCALE.md), [EXPANSION_STRATEGY](EXPANSION_STRATEGY.md) остаются тематическими контрактами.
