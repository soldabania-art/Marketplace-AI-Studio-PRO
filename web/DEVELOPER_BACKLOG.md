# TROVENDI — очередь разработки после аудита

Дата: 12.09.2026. Проверенный `main`: `3d5e59a17469bf622f858889adf75e585d3a5253`. [Решение и доказательства](ARCHITECTURE_REVIEW_2026-09-12.md).

Концепция одобрена; коммерческий запуск не одобрен. Первичный клиент — действующий продавец Wildberries. Ближайший процесс: подключение → полнота данных → детерминированная экономика → подтверждённые проблемы → задачи с доказательствами → разрешённое действие → статус и результат.

Фактическое состояние issues на момент обновления: #1–#8 и #37–#39 закрыты; #9–#22, #44 и D01/#46 открыты. T02–T08C последовательно интегрированы и проверены на общем `main`. Текущий ограниченный приоритет владельца — D01/#46 в открытом PR #47; Operational Ledger проходит визуальную доработку без переноса на остальные экраны. Внешний блокер не разрешает обходить security gate.

| Состояние | Задачи |
| --- | --- |
| Закрыто и интегрировано | [T01 / #1](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/1) — [T08 / #8](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/8), включая #37–#39 |
| Текущая задача | [D01 / #46](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/46) — ограниченный визуальный эталон |
| Открыто, выполнять по зависимостям | T09–T22; notification follow-up #44 остаётся отдельной задачей |


| ID | Приоритет | Задача | Зависимости | GitHub |
| --- | --- | --- | --- | --- |
| T01 | P0 | Сделать CI обязательной проверкой PR и миграций PostgreSQL | — | [Issue #1](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/1) |
| T02 | P0 | Подключить Emergency STOP ко всем внешним публикациям | T01 | [Issue #2](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/2) |
| T03 | P0 | Закрыть доступ просроченных тарифов к новой AI-генерации | T01 | [Issue #3](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/3) |
| T04 | P0 | Запретить превращение некорректных финансовых данных в ноль | T01 | [Issue #4](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/4) |
| T05 | P0 | Проверять утверждения AI по фактам, а не только ID и числам | T03 | [Issue #5](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/5) |
| T06 | P0 | Зафиксировать неизменяемые AI-активы и честную проверку медиа | T02, T05 | [Issue #6](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/6) |
| T07 | P0 | Объединить свежесть, покрытие периода и планирование обновлений | T04 | [Issue #7](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/7) |
| T08 | P0 | Обеспечить владение долгими задачами и атомарную запись событий | T01 | [Issue #8](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/8) |
| T09 | P0 | Реализовать доставку email для подтверждения и восстановления | T01 | [Issue #9](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/9) |
| T10 | P0 | Завершить оплату и активацию выбранного набора | T03, T09 | [Issue #10](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/10) |
| T11 | P0 | Исправить транспорт документов размером до 25 МБ | T01 | [Issue #11](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/11) |
| T12 | P1 | Завершить жизненный цикл документов и права партнёров | T11, T08 | [Issue #12](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/12) |
| T13 | P0 | Закрыть границы доступа и исходящих сетевых запросов | T01 | [Issue #13](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/13) |
| T14 | P0 | Подтвердить готовность production API, worker, БД и восстановления | T02, T03, T04, T06, T07, T08, T09, T10, T11, T13, T12, T15, T17 | [Issue #14](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/14) |
| T15 | P1 | Ввести AI budgets, provider routing и асинхронные генерации | T03, T05, T08 | [Issue #15](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/15) |
| T16 | P1 | Собрать рабочий интерфейс вокруг реальной очереди Director | T02, T07 | [Issue #16](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/16) |
| T17 | P1 | Сделать Profit Center воспроизводимым по периодам и версиям затрат | T04, T07 | [Issue #17](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/17) |
| T18 | P1 | Ввести канонические товары и контракт исполнения интеграций | T04, T08, T13 | [Issue #18](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/18) |
| T19 | P1 | Запустить read-only пилот сети фулфилментов | T12, T13, T18 | [Issue #19](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/19) |
| T20 | P2 | Реализовать операционный контур фулфилмента по состояниям | T19, T17, T02 | [Issue #20](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/20) |
| T21 | P1 | Довести Beginner Studio до честного сохраняемого результата | T03, T05, T15 | [Issue #21](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/21) |
| T22 | P1 | Сделать поддержку полноценной очередью обработки инцидентов | T13 | [Issue #22](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/22) |

## Горизонты поставки и коммерческие проверки

| Горизонт | Проверяемый результат |
| --- | --- |
| Ближайший релиз | Надёжный WB, достоверная экономика, ежедневные доказательные задачи и безопасное исполнение |
| Следующий этап | Подписка и лимиты, учёт AI-себестоимости, платный пилот, документы и ограниченный пилот фулфилментов |
| Позднее | Ozon; затем один зарубежный рынок после отдельной проверки спроса |
| Отложено | Beginner-first без продаж, конструктор магазинов, массовые страны, собственные склады, кредитование/расчёты, неограниченная автономная реклама, собственная базовая AI-модель |

Коммерческие workstreams не заменяют продуктовые gates и не содержат придуманных результатов:

- **CV01 · Интервью.** Подготовить скрипт и таблицу фиксации для действующих WB-продавцов. Критерий: роль и объём операций подтверждены, текущий процесс потерь описан на реальном примере, цена проблемы и доступ к решению отделены от мнения. Контакты без отдельного поручения не инициировать.
- **CV02 · Платный пилот.** Подготовить границы, длительность, данные, поддержку, stop-критерии и согласие на измерение. Критерий старта: клиент, сумма и тариф зафиксированы договором/офертой; любые цены до этого — гипотезы. CI не является разрешением коммерческого запуска.
- **CV03 · AI unit economics.** Для каждой генерации учитывать provider/model, токены или единицы, стоимость, кэш/повтор, лимит подписки и связанную задачу. Критерий: стоимость на активированный магазин и полезную завершённую задачу воспроизводима без LLM-оценки.
- **CV04 · Активация и продление.** Определить события: магазин подключён, полнота данных достаточна, первая подтверждённая проблема просмотрена, задача одобрена, выполнение завершено, результат измерен, подписка продлена. Критерий: события tenant-scoped, дедуплицированы и не содержат секретов.

Будущий реестр результатов для каждой задачи хранит: проблему и исходные данные; рекомендацию; подтверждение и исполнителя; статус выполнения; затраты; метод измерения; наблюдаемый результат; ограничения вывода. Нельзя записывать рост прибыли как эффект AI без достаточной доказательности.

## T01 · P0 · Сделать CI обязательной проверкой PR и миграций PostgreSQL

**Статус:** CLOSED · [GitHub #1](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/1). **Зависимости:** нет.

**Файлы:** .github/workflows/web-cloud.yml; web/package.json; web/backend/migrations; web/backend/tests.

**Работа:** Добавить pull_request для main; запускать существующие node --test tests/*.test.mjs. Добавить отдельный PostgreSQL job: миграция пустой БД и upgrade с предыдущей ревизии до head. Для security/write изменений запускать интеграционные проверки на PostgreSQL. Сохранить Node 24 и существующие backend/frontend jobs. Проверить доступность защиты main; отсутствие прав отметить как инфраструктурный блокер.

**Приёмка:** PR запускает frontend build, 149+ backend tests, 4+ CSV tests и PostgreSQL migrations; намеренно падающий тест делает PR красным. Все проверки относятся к точному head SHA. Не отключены тесты и не добавлен continue-on-error.

**Граница:** Только CI и необходимые тестовые fixtures; не обновлять одновременно все зависимости.

## T02 · P0 · Подключить Emergency STOP ко всем внешним публикациям

**Статус:** CLOSED · интегрировано merge SHA `0652d810b5a1f6b521e27c04826c8a2cd035849f` · [PR #28](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/pull/28) · [GitHub #2](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/2). **Зависимости:** T01.

**Файлы:** web/backend/app/card_factory_router.py; director_router.py; models.py; web/components/DailyDirectorWorkspace.js.

**Работа:** Создать общий серверный preflight для внешних записей. publish_card и publish_media обязаны проверять store/workspace STOP перед отправкой, включая повторную попытку после ошибки. STOP должен быть виден во всём рабочем интерфейсе; чтение и диагностику разрешить. Зафиксировать семантику: новые отправки блокируются; уже принятый провайдером запрос нельзя обещать отменить.

**Приёмка:** При stopped=true оба publish endpoint возвращают отказ и mock WB writer имеет 0 вызовов. Проверены STOP после prepare, STOP во время долгого preflight, прямой запрос в обход UI, другой tenant, явное resume. Аудит содержит отказ и точную область STOP.

**Граница:** Не включать автономные записи, не менять политику подтверждения публикаций.

## T03 · P0 · Закрыть доступ просроченных тарифов к новой AI-генерации

**Статус:** CLOSED · [GitHub #3](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/3). **Зависимости:** T01.

**Файлы:** web/backend/app/trial_service.py; billing_service.py; card_factory_router.py; beginner_router.py.

**Работа:** Использовать единый entitlement snapshot для каждого нового AI-вызова. ensure_ai_access сейчас пропускает paid read_only; регенерация существующего товара при allow_exhausted не должна разрешать бесконечную новую работу. Отличить чтение сохранённой версии от новой генерации. Сохранить договор Trial: пять успешных карточек, 72 часа, ошибки не расходуют квоту.

**Приёмка:** Expired/past_due/canceled paid и исчерпанный Trial не вызывают AI; чтение истории доступно. Активный paid работает. Проверены повторная генерация, оба beginner endpoint, отказ провайдера, конкурентные резервации и освобождение квоты без сброса чужого успешного запуска.

**Граница:** Не менять цены и не подключать платёжного провайдера.

## T04 · P0 · Запретить превращение некорректных финансовых данных в ноль

**Статус:** CLOSED · интегрировано merge SHA `0e4e6ea40aa201e4ad1beda75710a2b0d3566ead` · [PR #29](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/pull/29) · [GitHub #4](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/4). **Зависимости:** T01.

**Файлы:** web/backend/app/wb_finance.py; wb_promotion.py; marketplace_sync.py; profit_center_router.py.

**Работа:** Различить документированное пустое значение, реальный ноль и ошибку парсинга. Неизвестная форма ответа и отброшенные строки не должны означать complete=True. Добавить типизированный результат страницы с raw/accepted/rejected count, cursor и состоянием схемы. Некорректный ответ рекламы не должен удалять сохранённые строки как якобы пустой отчёт.

**Приёмка:** malformed money, неизвестная схема HTTP 200, отсутствующий rrdId, non-finite число и частично неверная страница приводят к incomplete/error с evidence. Корректный документированный пустой ответ завершает импорт. Предыдущие данные не стираются при ошибке схемы.

**Граница:** Не угадывать семантику WB: зафиксировать текущую официальную схему и обезличенные fixtures.

## T05 · P0 · Проверять утверждения AI по фактам, а не только ID и числам

**Статус:** CLOSED · интегрировано merge SHA `13ac300248ce11927545abd896273ce006d97ed6` · [PR #32](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/pull/32) · [GitHub #5](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/5). **Зависимости:** T03.

**Файлы:** web/backend/app/ai_card_factory.py; beginner_router.py; review_ai.py; web/backend/tests/test_ai_card_factory.py.

**Работа:** Ввести утверждения со ссылкой на конкретный подтверждённый атрибут; серверно валидировать форму ответа и соответствие материала, функций, состава, комплекта, сертификатов и единиц. Не считать used_fact_ids доказательством всего текста. Неоднозначные утверждения остаются на ручной проверке и блокируют готовность к публикации.

**Приёмка:** Фикстура с единственным фактом «Сумка» и выдуманными «натуральная кожа», «сертифицированная», «водонепроницаемая» отклонена. Проверены перестановка чисел между свойствами, отрицания, prompt injection и законное перефразирование. Human preview сохранён; тесты без платных AI вызовов.

**Граница:** Не объявлять семантическую проверку безошибочной и не решать задачу одним усиленным prompt.

## T06 · P0 · Зафиксировать неизменяемые AI-активы и честную проверку медиа

**Статус:** CLOSED · интегрировано merge SHA `a64818aa7da948a5d3a0ad546310935d413b52a6` · [PR #34](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/pull/34) · [GitHub #6](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/6). **Зависимости:** T02, T05.

**Файлы:** web/backend/app/card_factory_router.py; ai_generation_service.py; web/app/api/card-factory/generate-visual/route.js.

**Работа:** Привязать finalize к конкретному доверенному store/host/object, generation и серверно полученному digest; повторная finalize не меняет версию. Любой *.blob.vercel-storage.com не равен собственному хранилищу. Рост числа фото подтверждает только структурное изменение, а не идентичность публикации. Ввести явный partial/unverified результат, если API не позволяет доказать актив. Не повторять неясный write без сверки.

**Приёмка:** Чужой Blob host, несоответствие URL/path/hash и повторная подмена отклонены. Добавление постороннего фото не даёт applied для нашего актива. Timeout-after-accept не вызывает слепого дубля; процесс, умерший в submitting, имеет read-only recovery. Существующие фото сохранены.

**Граница:** Проверить контракт WB без отправки изменений в реальные карточки в тестах.

## T07 · P0 · Объединить свежесть, покрытие периода и планирование обновлений

**Статус:** CLOSED · принят head `e19cf107f902fde2a88aff54c335c63b5deebad8` · интегрировано merge SHA `700436f7161972ea1b2dcf9ff83fbdeb975ae822` · [PR #36](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/pull/36) · [GitHub #7](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/7). **Зависимости:** T04.

**Файлы:** web/backend/app/data_health.py; director_router.py; sync_scheduler.py; seller_data_router.py; smart_fbo_router.py; reviews_router.py.

**Работа:** Использовать один реестр freshness/coverage policies во всех модулях вместо 900 секунд в Director. Учитывать текущий период финансов, переход даты, часовой пояс и незавершённый импорт. Добавить автоматическое обновление feedbacks: сейчас scheduler его не планирует. Повторный recovery run должен иметь корректные уникальные ключи всех страниц.

**Приёмка:** Finance возрастом 20 минут при штатной суточной политике не stale; просроченные stocks stale одинаково в UI/Director. Полночь и неполный новый период не становятся complete. Отзывы обновляются без открытого браузера. Один активный sync не размножается по разным входным endpoint.

**Граница:** Не исправлять проблему частым polling всех источников каждые 15 минут.

## T08 · P0 · Обеспечить владение долгими задачами и атомарную запись событий

**Статус:** CLOSED · [GitHub #8](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/8). **Зависимости:** T01.

**Файлы:** web/backend/app/job_queue.py; sync_scheduler.py; marketplace_sync.py; fbo_monitor.py; rate_limit.py; migrations.

**Работа:** Разделить enqueue и commit вызывающего сервиса, добавить outbox/атомарную границу изменения и задания. Для длительных jobs добавить heartbeat и fencing token/attempt identity; stale worker не может завершить новую попытку. Проверить session-level advisory locks на закреплённом соединении: commit внутри lease не должен возвращать его в pool. Общий Redis limiter для API и worker.

**Приёмка:** Два PostgreSQL worker не выполняют живую задачу повторно после 300 секунд; crash восстанавливается, stale completion отвергнут. Сбой между записью состояния и заданием не теряет работу. Нет утечки advisory locks в pool. Redis failure блокирует соответствующие provider calls; проверены 429 и replay.

**Граница:** Без Kafka и массового выделения микросервисов; разбить на PR heartbeat, transaction boundary, scheduler locks.

### T08A · CLOSED · Heartbeat и владение попыткой

[GitHub #37](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/37). Добавить независимый heartbeat, attempt identity/fencing и crash recovery. Два PostgreSQL worker должны доказать, что живая задача не перехватывается, умершая восстанавливается, а старый worker не меняет статус, доменный результат или дочерние jobs новой попытки. STOP и read-before-retry для неизвестной внешней записи сохраняются.

### T08B · CLOSED · Транзакционная граница/outbox

[GitHub #38](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/38). Принят head `b179d4f1fafc32fda14be2aa81e39b60cbe63c1e`, интегрирован [PR #43](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/pull/43), merge `1c880be00b6bc8117767c3ee4564f986086c3767`; [push CI success](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/actions/runs/34702338087). Enqueue и доменные изменения используют caller-owned atomic transaction.

### T08C · CLOSED · Advisory locks и Redis limiter

[GitHub #39](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/39). После дополнительной regression-проверки принят head `9b4946aedfda95ebf103a4a7621d911a03c53c5c`, интегрирован [PR #45](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/pull/45), merge `3d5e59a17469bf622f858889adf75e585d3a5253`; [push CI success](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/actions/runs/34704306856). #39 и эпик #8 закрыты. Production Redis/worker rollout и exactly-once HTTP не заявлены.

## T09 · P0 · Реализовать доставку email для подтверждения и восстановления

**Статус:** OPEN · [GitHub #9](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/9). **Зависимости:** T01.

**Файлы:** web/backend/app/account_router.py; config.py; job_queue.py; web/app/account/page.js; tests.

**Работа:** Подключить адаптер транзакционной почты через очередь; хранить только необходимые секреты серверно. _delivery_response сейчас всегда сообщает email_provider_not_configured. Развести delivery accepted/sent/failed; не раскрывать существование аккаунта. Токены одноразовые, consume атомарный; возврат development_token только test/development.

**Приёмка:** В тестовом почтовом контуре пользователь получает ссылку, подтверждает email, восстанавливает пароль; повтор и конкурентное использование токена отвергнуты. Ошибка доставки даёт наблюдаемый retry и понятный интерфейс без ложного «отправлено».

**Граница:** Выбор/договор/доступ провайдера записать отдельным внешним блокером; не просить секреты в чате.

## T10 · P0 · Завершить оплату и активацию выбранного набора

**Статус:** OPEN · [GitHub #10](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/10). **Зависимости:** T03, T09.

**Файлы:** web/backend/app/billing_service.py; account_router.py; schemas.py; web/components/PublicLanding.js; web/app/checkout/page.js; web/app/activation/page.js.

**Работа:** После выбора RF/CIS провайдера реализовать sandbox checkout и native signature verification webhook. Проверять amount/currency/workspace/plan/provider subscription, порядок событий и replay. Сохранить выбранные модули как серверные права/навигацию по согласованному правилу; сейчас это purchase intent, а не модульная авторизация. community_access — всем активным платным тарифам.

**Приёмка:** Сквозной sandbox путь: выбор → account → verified email → checkout → verified event → MFA → нужный магазин/набор. Redirect не активирует доступ; чужой/старый/повторный webhook не повышает права. Cancel/refund/period-end согласованы; цена и срок показаны до подтверждения.

**Граница:** Не принимать реальные платежи до T14; договор и фискализация — внешние подтверждённые зависимости, не выдумывать.

## T11 · P0 · Исправить транспорт документов размером до 25 МБ

**Статус:** OPEN · [GitHub #11](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/11). **Зависимости:** T01.

**Файлы:** web/app/api/document-vault/route.js; web/app/api/document-vault/[document_id]/download/route.js; web/components/DocumentVaultWorkspace.js; web/backend/app/document_vault_router.py; web/next.config.mjs.

**Работа:** Выбрать авторизованную прямую загрузку в private object storage или отдельный backend transport; двоичные 25 МБ не должны проходить через Vercel Function request. Выдавать короткое разрешение на один объект после auth/store/role/size/type checks; сервер проверяет объект перед finalize. Download также не должен буферизовать 25 МБ в ограниченный ответ функции. CSP разрешает только нужные hosts.

**Приёмка:** В preview реально проходят 1, 5 и 25 МБ, 25 МБ+1 отклонён. Чужой tenant, просроченное разрешение, MIME/hash mismatch и quarantine не дают скачать. Хранилище остаётся private; секреты не попадают в браузер. Вариант скачивания сохраняет auth, аудит и проверку целостности.

**Граница:** Не понижать приватность и не маскировать проблему увеличением maxDuration/bodySizeLimit.

## T12 · P1 · Завершить жизненный цикл документов и права партнёров

**Статус:** OPEN · [GitHub #12](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/12). **Зависимости:** T11, T08.

**Файлы:** web/backend/app/document_vault_router.py; models.py; migrations; web/DOCUMENT_VAULT.md.

**Работа:** Связать finalize с durable scan job/outbox; подпись callback — только часть протокола. Добавить идемпотентный duplicate callback, retry scan error, re-scan version, очистку orphan upload. Ввести document permissions и связь с разрешённым FulfillmentConnection/договором, а не только существующим partner_id. Версии, связи с заказом/поставкой, retention/legal hold, аудит и управляемый экспорт.

**Приёмка:** Дубликат scan event безопасен; error можно повторить; infected недоступен. Analyst без write прав не загружает/не меняет документ. Чужая partner связь отвергнута. Hold блокирует удаление, новая версия сохраняет старую. Зафиксирована матрица seller/partner/buyer доступа.

**Граница:** Это эпик: выполнять отдельными PR scan lifecycle, permissions/links, retention/export. Конкретные сроки хранения утверждаются отдельно по юрисдикции.

## T13 · P0 · Закрыть границы доступа и исходящих сетевых запросов

**Статус:** OPEN · [GitHub #13](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/13). **Зависимости:** T01.

**Файлы:** web/backend/app/store_access.py; account_router.py; push_router.py; fbo_worker.py; data_health_incidents.py; security.py; tests.

**Работа:** Явно выбирать workspace для billing/activation вместо первого Membership. Уточнить matrix owner/admin/operator/analyst, особенно AI-spend, documents, watch и store-level writes. Push endpoint сейчас проверяет лишь HTTPS/netloc: ограничить допустимые сервисы/адреса и redirects, запретить loopback/private/link-local и DNS rebinding. Проверить происхождение IP через доверенный proxy и rate limits.

**Приёмка:** Пользователь с двумя workspace не получает тариф/активацию другого выбранного магазина. Analyst не выполняет запрещённые операции. Тесты unsafe push endpoints выполняются только с mock network и дают 0 исходящих вызовов. MFA/recovery single-use выдерживает concurrent calls.

**Граница:** Не вводить новый auth framework и не считать скрытую UI-кнопку серверной защитой.

## T14 · P0 · Подтвердить готовность production API, worker, БД и восстановления

**Статус:** OPEN · [GitHub #14](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/14). **Зависимости:** T02, T03, T04, T06, T07, T08, T09, T10, T11, T13, T12, T15, T17.

**Файлы:** web/backend/DEPLOYMENT.md; SCALING.md; web/DATABASE_SECURITY_RUNBOOK.md; web/backend/app/main.py; deployment evidence.

**Работа:** На доступном staging/production проверить связь frontend→API, отдельный worker heartbeat, migration revision, private PostgreSQL/TLS/runtime role, backups и restore drill, Redis limiter, email, billing sandbox, private documents/scanner и AI quota. Добавить readiness по фактическим обязательным зависимостям; SELECT 1 недостаточен. Сверить region/data flow с утверждённой политикой.

**Приёмка:** Есть датированный evidence record с exact SHA, средой, результатами canary и recovery. End-to-end тест без реальных финансовых/marketplace writes. Нет заявления «24/7», «500 фулфилментов работают», «production ready» без наблюдений и нагрузочного отчёта.

**Граница:** Не менять DNS, production secrets, договоры или схему доступа ради зелёной проверки. Недоступная инфраструктура остаётся BLOCKED_EXTERNAL.

## T15 · P1 · Ввести AI budgets, provider routing и асинхронные генерации

**Статус:** OPEN · [GitHub #15](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/15). **Зависимости:** T03, T05, T08.

**Файлы:** web/backend/app/ai_generation_service.py; ai_card_factory.py; review_ai.py; agent_network.py; config.py; models.py; migrations.

**Работа:** Единый provider adapter и capability routing для текста/vision/images. Бесплатный Rules режим не вызывает paid API; Local/Free, Economy, Premium видны до вызова и в результате. Атомарно резервировать дневной бюджет и лимит concurrency, хранить estimated/actual/unknown cost отдельно. input/model/prompt/facts/policy hash для cache/idempotency; durable jobs и bounded retries.

**Приёмка:** Нет скрытого paid fallback из Free. Два конкурентных запроса не превышают budget. Незаданная цена показывается unknown, а не 0. Reload/timeout не создаёт второй оплаченный вызов. Ключи и raw provider exception не возвращаются в public_generation. Offline eval артефакт привязан к версии.

**Граница:** Флаг Sentinel сам по себе не считается работающим контролем. Один адаптер за PR, без замены всех доменных сервисов.

## T16 · P1 · Собрать рабочий интерфейс вокруг реальной очереди Director

**Статус:** OPEN · [GitHub #16](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/16). **Зависимости:** T02, T07.

**Файлы:** web/app/page.js; web/app/layout.js; web/components/StudioSection.js; DailyDirectorWorkspace.js; GlobalStoreSelector.js; web/lib/useActiveStore.js.

**Работа:** Сделать Director главным рабочим экраном, KPI вторичными. Общие Store/Workspace context, STOP, provider/budget, approval queue и contextual support. Убрать локальную имитацию «AI принял вопрос»: подключить проверенный ответ либо честно обозначить недоступность. Для SEO/ads/inventory/reports/autopilot показывать stage до клика. Выбранный публично набор отображается явно.

**Приёмка:** У магазина без источников нет фальшивых задач/денег/AI ответа. При переключении магазина старые данные и pending действия очищаются. Loading/empty/error/stale/read-only доступны. Smoke: guest, trial, paid, expired, два магазина, STOP, мобильная ширина. Сохранён текущий graphite/emerald бренд.

**Граница:** Не строить новый дизайн целиком и не переименовывать deployment IDs/cookies.

## T17 · P1 · Сделать Profit Center воспроизводимым по периодам и версиям затрат

**Статус:** OPEN · [GitHub #17](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/17). **Зависимости:** T04, T07.

**Файлы:** web/backend/app/profit_center_router.py; marketplace_sync.py; models.py; migrations; web/components/ProfitCenterWorkspace.js.

**Работа:** Версионировать затраты/налоговые допущения с effective dates и идентификатором отчёта; текущий mutable COGS не должен молча менять закрытую историю. Учитывать SKU с рекламой без продаж, возвраты и нераспределённые расходы. Фильтрацию period и агрегаты перенести в SQL, добавить pagination и индексы. Сверка с источниками отделена от бухгалтерского отчёта.

**Приёмка:** Изменение COGS сегодня не меняет зафиксированный прошлый период без явного пересчёта. SKU без продаж с расходом виден. Итог совпадает с суммой SKU и unallocated bridge. Проверены refund-only период, correction, currency mismatch, полный/неполный импорт. Есть EXPLAIN/нагрузочный fixture.

**Граница:** Эпик из отдельных PR cost versions, reconciliation cases, bounded queries; не выдумывать финансовые правила.

## T18 · P1 · Ввести канонические товары и контракт исполнения интеграций

**Статус:** OPEN · [GitHub #18](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/18). **Зависимости:** T04, T08, T13.

**Файлы:** web/backend/app/integration_catalog.py; marketplace_connections.py; marketplace_sync.py; fulfillment_adapters.py; models.py; migrations.

**Работа:** Добавить CanonicalProduct/Variant, MarketplaceListing и external ID mapping с tenant/store/connection namespace. nm_id остаётся WB external ID. Канонический контракт Money(currency/minor units), quantity/unit, warehouse, order/return, source event и cursor/version. Каталог capabilities разделяет declared/implemented/certified/enabled. Сохранить WB адаптер за этим контрактом.

**Приёмка:** Один canonical SKU связан с двумя listings без конфликта внешних ID. Idempotent replay и capability negotiation проверены. WB не регрессирует. Добавление фиктивного тестового адаптера не требует менять Profit/Director. Тестовая интеграция никогда не объявлена production.

**Граница:** Постепенная миграция с backward-compatible mapping; не переписывать весь backend и не включать Ozon только по наличию desktop-кода.

## T19 · P1 · Запустить read-only пилот сети фулфилментов

**Статус:** OPEN · [GitHub #19](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/19). **Зависимости:** T12, T13, T18.

**Файлы:** web/backend/app/fulfillment_router.py; fulfillment_adapters.py; models.py; web/components/FulfillmentHubWorkspace.js; migrations.

**Работа:** Разделить platform catalog партнёров, partner workspace/membership и конкретное разрешение seller↔partner↔facility. Нужны договор/capabilities, secret reference, read-only health/inventory/documents adapter, cursor, quarantine, reconciliation и disconnect. Реализовать пагинацию каталога и отдельную выборку facilities; limit(500)/limit(5000) не доказательство масштаба.

**Приёмка:** Один реальный или контрактный sandbox партнёр проходит подключение, импорт, сверку и отзыв доступа. Склад с несколькими продавцами не раскрывает чужие данные. Повторный webhook идемпотентен. Нагрузочный fixture 500 партнёров/5000 объектов не теряет элементы при pagination.

**Граница:** Начать с одного конкретного адаптера и read-only. Физические отгрузки, деньги и partner onboarding commitments пока выключены.

## T20 · P2 · Реализовать операционный контур фулфилмента по состояниям

**Статус:** OPEN · [GitHub #20](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/20). **Зависимости:** T19, T17, T02.

**Файлы:** web/backend/app/fulfillment_adapters.py; models.py; migrations; web/components/FulfillmentHubWorkspace.js; web/DOCUMENT_VAULT.md.

**Работа:** Эпик: inbound draft/accepted/receiving/discrepancy/received; immutable stock movements и reservation ledger; outbound reserve/pick/pack/ship/deliver; cancel/return/quarantine/claim. Связать versioned tariff quote, подтверждение сторон, документы, custody evidence и settlement reconciliation. Общий Action/approval/audit, serial events, retry/dead-letter. Multi-currency и route policy расширяются через уже принятую архитектуру.

**Приёмка:** Отдельные PR с контрактными тестами: приёмка с недостачей; два заказа на последнюю единицу без oversell; частичная отгрузка; отмена после pick; возврат; повтор и out-of-order event; сверка тарифа/акта/списания. AI не создаёт факт физической приёмки и не меняет ledger напрямую.

**Граница:** Не брать эпик одним PR. До реализации каждого подраздела создать дочернюю задачу с конкретной схемой и state transitions.

## T21 · P1 · Довести Beginner Studio до честного сохраняемого результата

**Статус:** OPEN · [GitHub #21](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/21). **Зависимости:** T03, T05, T15.

**Файлы:** web/backend/app/beginner_router.py; web/components/BeginnerLaunchWorkspace.js; CardFactoryWorkspace.js; models.py.

**Работа:** Связать beginner project с canonical product/fact version и общей историей генераций/активов. Сохранять paid visuals через общий pipeline, не терять работу после reload. Создание новой marketplace карточки — отдельная capability от update существующего nm_id: до её сертификации показывать export/draft, а не обещание готовой публикации.

**Приёмка:** Один проект проходит photo → confirmed facts → сохранённый draft/economics → reload без потери → доступный реальный следующий шаг. Trial ошибки не расходуют карту. Paid генерация учитывает budget. Не подключённый marketplace/new-card write честно unavailable.

**Граница:** Не копировать второй AI engine и не подменять новую карточку обновлением чужого/случайного nm_id.

## T22 · P1 · Сделать поддержку полноценной очередью обработки инцидентов

**Статус:** OPEN · [GitHub #22](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/22). **Зависимости:** T13.

**Файлы:** web/backend/app/support_service.py; support_router.py; admin_router.py; web/components/SupportWorkspace.js.

**Работа:** Добавить назначение уполномоченному сотруднику, статусы, комментарии, уведомления и историю решения; служебный доступ scoped/time-bound/audited. Улучшить retrieval: stop words, актуальная версия slug, релевантность, набор eval вопросов. Классифицировать риск до усечения 1000 символов; проверить синонимы потерь/неожиданных записей.

**Приёмка:** Инцидент реально виден оператору, имеет статус и закрывается с аудитом. Риск в конце длинного сообщения не теряется. Не совпадающий вопрос не получает случайную статью. Пользователь видит источник/версию, никто не обещает SLA без реальной службы.

**Граница:** Без автоматической отправки претензий, возврата денег или обучения на частных обращениях.

## После ближайшей очереди

Эти направления приняты, но ещё не являются готовыми задачами на один PR. Следующий разработчик сначала создаёт ограниченную задачу с schema/API/fixtures и acceptance, затем пишет код.

| Направление | Входной gate | Первый ограниченный результат |
| --- | --- | --- |
| Ozon web | T18, сверенный WB | Read-only catalog adapter + health/cursor/isolation; затем отдельные stocks/orders/finance задачи |
| 1С / МойСклад | T18, T17 | Один источник COGS → существующий immutable preview/commit; затем certified reconciliation |
| Реклама / SEO / цены | T02/T04/T05/T15/T16 | Отдельные read-only очереди по источникам; каждый write type получает самостоятельный gate |
| Остатки / FBS | T18/T20 | Версионированный план и reservation-safe stock; без фальшивых warehouse allocations |
| Claims / marketplace rules | T12/T17/T22 | Evidence pack и versioned source; отправка только отдельным подтверждённым executor |
| Agency | T13/T18 | Назначение сотрудника на конкретный client/store, отрицательные тесты доступа; затем portfolio |
| Paid community | T10/T13/T22 | Auth + active paid community_access + moderation, затем guides/Q&A; не выдавать raw store economics |
| Android / Telegram | Общие events/auth/STOP | Alerts/deep links, затем read-only mobile view и отдельные approvals |
| Kazakhstan / Kaspi | Discovery по EXPANSION_STRATEGY | Контрактный read-only settlement pilot и multi-currency reconciliation |
| Uzum / ЯМ / другие | Capability/API discovery + T18 | По одному подтверждённому adapter contract |
| Manufacturer / wholesale / D2C | T17/T18/T20 | Versioned BOM или quote/reservations MVP; не второй accounting engine |
| Market Intelligence / A-B | Правомерный источник + T15/T17 | Источник/метод/период/неопределённость, затем experiment с метрикой и выборкой |

## Шаблон отчёта исполнителя

- Задача/PR и точный SHA.
- Что изменилось для пользователя и почему.
- Воспроизведение до и результат после; команды/CI links.
- Миграция, риск и recovery (если применимо).
- Остаток и конкретный внешний блокер.
- Следующая задача с выполненными зависимостями.

Не писать «всё готово», если готов только каталог, prompt, frontend shell или локальный mock. Не закрывать эпик по одной миграции.


## Последняя интеграция

T08C принят и интегрирован последним: [PR #45](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/pull/45), итоговый `main` `3d5e59a17469bf622f858889adf75e585d3a5253`, [push CI](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/actions/runs/34704306856) и Vercel success.

По повторному приоритету владельца активен только [D01/#46](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/46): два направления и связанный визуальный prototype на синтетических данных. До приёмки эталона не распространять его на весь продукт. T09–T22 и #44 сохраняются в очереди. `MARKETPLACE_ASSET_BLOB_HOSTS` остаётся BLOCKED_EXTERNAL до получения точного hostname выделенного public Blob store; значение не угадывать. GitHub Ruleset также остаётся BLOCKED_EXTERNAL до подтверждённого включения; CLOSED T01 не заменяет эту инфраструктурную проверку.
