# Передача TROVENDI следующему разработчику

Дата: 14.09.2026. Проверенный `main`: `c20fa75cfee90cca136e9a019d4cf552f19bb9bb`.

## Текущее интеграционное состояние — 19.09.2026

Авторитетное состояние для следующего шага: `main` — `c20fa75cfee90cca136e9a019d4cf552f19bb9bb`; D01/#46 уже интегрирован и закрыт. Общая backend-ветка `codex/backend-integration-reviewed` подготовлена для отдельного [PR #61](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/pull/61), exact head до этого документационного обновления — `c49cc5f8c4f08e3d470a190721f1841206d8911a`.

PR #61 объединяет только подготовленные совместимые блоки: WB01/WB02, T09A/T09B, T10A, CTRL01/CTRL02 и #58. Его exact-head [CI #35435657915](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/actions/runs/35435657915) зелёный: frontend, backend, реальный PostgreSQL fresh migration, upgrade от CTRL01 predecessor к объединённой голове и PostgreSQL integration/concurrency suite. [Vercel](https://vercel.com/soldabania-5646/marketplace-ai-studio-pro/FmszcXGYYLdgGKVTRBuupDwRQr8V) exact head success. Это не разрешение на merge: PR остаётся draft для независимой приёмки.

D02 остаётся отдельным draft [PR #59](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/pull/59), D03 — отдельным draft [PR #60](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/pull/60); их изменения не включены в #61. Не создавать реальных WB-операций, платных AI-вызовов, писем или платежей. Browser проверил только публичную загрузку Preview #61; account/admin требуют авторизованного контекста, а изолированных fixture-аккаунтов нет, поэтому role/MFA/browser acceptance не заявляются выполненными и protection не обходилась.

## Решение и клиентский фокус

Концепция одобрена для продолжения разработки; широкий коммерческий запуск не одобрен. Первый платящий клиент — действующий продавец Wildberries с регулярными продажами, командой и операционными расходами.

Обещание: TROVENDI помогает находить потери прибыли, принимать решения и контролировать выполнение между магазином, командой и фулфилментом.

Проверяемый маршрут: подключить магазин → показать полноту данных → рассчитать деньги и подтвердить проблемы → выдать приоритетные задачи с доказательствами → получить разрешение на действие → показать статус, затраты и измеренный результат. Деньги рассчитываются детерминированно; AI работает по проверенным данным; факт, предположение и неизвестное различаются явно.

## Фактическое состояние и очередь

- PR #28/T02 слит в `main`: merge SHA `0652d810b5a1f6b521e27c04826c8a2cd035849f`; issue #2 закрыт с доказательствами.
- PR #29/T04 слит следом: merge SHA `0e4e6ea40aa201e4ad1beda75710a2b0d3566ead`; issue #4 закрыт с доказательствами.
- PR #30 со стратегией слит: промежуточный `main` `ac0bd409f39168376b162bba5e8ff16052a1dca3`.
- PR #31 обновил handoff/backlog после интеграции T02/T04: merge SHA `3b0b450adb38e9e518b0d10de83ce249fa19d8fe`.
- PR #32/T05 принят на head `336506a95ffd4d2ec307f8a68a16dfc16296f631` и слит: merge SHA `13ac300248ce11927545abd896273ce006d97ed6`; issue #5 закрыт с доказательствами.
- PR #34/T06 принят на head `6773a3916cc5589c38d3b6a7cc11fd60ad6f3db0` и слит: merge SHA `a64818aa7da948a5d3a0ad546310935d413b52a6`; issue #6 закрыт с доказательствами.
- PR #36/T07 принят после дополнительной проверки полноты на head `e19cf107f902fde2a88aff54c335c63b5deebad8` и слит: merge SHA `700436f7161972ea1b2dcf9ff83fbdeb975ae822`; issue #7 закрыт.
- T08A/#37 принят на `63c11d1460131514b2d94c3598e9c626727ae5d2` и интегрирован PR #41: `7f43ce131f879c353842890524b9c030374e4010`. PR #40 с документацией также слит.
- T08B/#38 принят на `b179d4f1fafc32fda14be2aa81e39b60cbe63c1e` и интегрирован PR #43: merge `1c880be00b6bc8117767c3ee4564f986086c3767`. PR #42 с handoff/backlog также слит; issue #38 закрыта.
- T08C/#39 принят на `9b4946aedfda95ebf103a4a7621d911a03c53c5c` и интегрирован PR #45: merge `3d5e59a17469bf622f858889adf75e585d3a5253`; #39 и эпик #8 закрыты.
- Итоговый [push CI](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/actions/runs/34704306856): exact head `3d5e59a17469bf622f858889adf75e585d3a5253`, frontend/backend/PostgreSQL success; Vercel commit status success.
- #1–#8, #37–#39 и D01/#46 закрыты. D01 интегрирован PR #47 в `main` `c20fa75cfee90cca136e9a019d4cf552f19bb9bb`; [push CI #34814628013](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/actions/runs/34814628013) и Vercel итогового `main` успешны. T09–T22 и #44 остаются в очереди.
- **Направление B и итоговая реализация D01 приняты на visual head `6cc2a1b10b732255a9c85267c038209da6abd0d2`.** Разрешённый documentation-only head PR #47 `cfb404f2f378e18c40613ced5b164af3980ba7db` прошёл [exact-head Web Cloud CI #34814497883](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/actions/runs/34814497883) и Vercel; PR слит только после обоих зелёных gates.
- Принятая визуальная система сохраняется без изменений: deep aubergine, coral, signal-mint, lime, X/trace-знак, асимметричная композиция, выразительная типографика и Decision Orbit. A и синяя версия на `7326b9fb759f463515948e548841804dbc23ace1` остаются контрольными.

Зелёные CI и deployment подтверждают только заявленные проверки конкретного SHA. Они не доказывают production readiness, работоспособность реального WB-сценария или готовность платного запуска.

## Горизонты

1. Ближайший релиз: надёжный Wildberries, достоверная экономика, ежедневные задачи и безопасное выполнение.
2. Следующий этап: подписка/лимиты, AI-себестоимость и платный пилот; затем документы и ограниченный read-only пилот фулфилментов.
3. Далее: Ozon; один зарубежный рынок только после отдельной проверки спроса, права доступа к данным и экономики.
4. Отложено: Beginner-first без продаж, собственный конструктор магазинов, массовые страны, собственная складская инфраструктура, кредитование/расчёты, неограниченная автономная реклама, собственная базовая AI-модель. Рабочий код не удалять ради смены приоритета; заглушки не создавать.

Сеть фулфилментов проектируется на сотни партнёров: tenant/partner scope, документы, статусы, аудит и канонические идентификаторы обязательны. До T19/T20 это архитектурный задел, а не production-обещание.

## Правила продолжения

1. Прочитать корневой `AGENTS.md`, [backlog](DEVELOPER_BACKLOG.md), [roadmap](PRODUCT_ROADMAP.md) и [дерево](PRODUCT_TREE.md).
2. Проверить актуальный `main`, открытые PR/issues, exact-SHA Actions и локальные изменения. Чужие изменения не перезаписывать.
3. Для дефекта сначала закоммитить воспроизводящий regression test, затем исправление.
4. Одна задача — один PR. Не отключать проверки и не ослаблять подтверждение, права, STOP или лимиты расходов.
5. Не вызывать реальные WB-записи, платный AI или расход рекламы в тестах.
6. Не сливать собственный PR до независимой приёмки главного архитектора.
7. Отчёт: риск, PR/head SHA, воспроизведение до, результат после, фактические проверки, ограничения, следующее действие. Actions, Vercel и клиентский сценарий указывать отдельно.

## Коммерческая проверка

Подготовить, но не проводить без отдельного поручения: интервью действующих WB-продавцов, критерии платного пилота, учёт AI unit economics, события активации и продления. Цены остаются гипотезами. Результаты интервью и продаж не выдумывать.

Для будущего реестра результата сохранять проблему/входные данные, рекомендацию, подтверждение/исполнителя, статус, затраты, метод измерения, наблюдаемый результат и ограничения причинного вывода.

## Команды безопасной проверки

```bash
cd web/backend
python -m pip install -r requirements.txt
python -m pytest -q
```

```bash
cd web
npm ci
node --test tests/*.test.mjs
npm run build
```

PostgreSQL migrations проверять на отдельной тестовой БД: fresh install и previous→head. Production credentials, клиентские данные и реальные внешние записи не использовать.

Источники: [аудит](ARCHITECTURE_REVIEW_2026-09-12.md), [дерево](PRODUCT_TREE.md), [roadmap](PRODUCT_ROADMAP.md), [backlog](DEVELOPER_BACKLOG.md), [security](SECURITY_MODEL.md).

## Итог интеграции и следующий gate

T02, T04, T05, T06, T07 и весь T08 (A/B/C) приняты и интегрированы последовательно; их совместная работа подтверждена CI итогового `main`. Это не подтверждает production rollout Redis/workers или exactly-once внешнего HTTP. Реальный WB, рекламный бюджет и платный AI в проверках не использовались.

D01 завершён: [PR #47](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/pull/47) слит, [issue #46](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/46) закрыта с доказательствами, итоговый `main` — `c20fa75cfee90cca136e9a019d4cf552f19bb9bb`. Это не меняет границ production readiness.

**Browser acceptance infrastructure (not integrated):** отдельная временная ветка объединяет exact heads D02/#59 `017a766de74076544b905369705f563cb2feb6b2`, D03/#60 `1ab343dc889d0882236679ca941e1512194d20fd` и backend/#61 `25da973885a3d1bdf19f2626cc84a17c6bfd2a35` с локальными PostgreSQL/Redis, штатным login/MFA/step-up и Playwright Chromium. [Контракт стенда](E2E_BROWSER_ACCEPTANCE.md) отделяет реальные server checks от mock-only D03 visual states. Exact CI этого нового head — обязательный следующий gate; Vercel deployment для стенда не требуется.

**PR #62 — фактический статус 19.09.2026:** [draft PR #62](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/pull/62) на head `48ddac79de142099d82fc133841d9144417516b6`. Исправление стенда убрало пароль и MFA-секрет из tracked fixtures: на каждом изолированном Actions run они генерируются в `$GITHUB_ENV` и не входят в evidence. Локально на интеграционном дереве прошли 30 targeted frontend contract tests (0 skipped) и `npm run build`; это не заменяет E2E. Для exact head workflow run отсутствует: `pull_request` path/jobs допустимы, close/reopen и новый push не создали run, а доступная интеграция GitHub не предоставляет `workflow_dispatch`. Поэтому PostgreSQL/Redis/FastAPI/Next/Chromium, JSON/HTML report, 1440/1280/390 screenshots и diagnostics **не выполнены и не созданы**. Не менять `web-cloud`, `main` или protections ради запуска; следующий gate — разрешённый Actions dispatch/runner exact head, затем inspection artifacts. PR не сливать.

[D02/#48](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/issues/48) перенесён на этот точный `main` без D03 и опубликован в `codex/d02-public-entry`; открыт отдельный draft [PR #59](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/pull/59). Начальный перенесённый head `cfca8b9738b4f645924d8d6831db86695beeb2a4` содержит только семь D02-файлов; [exact-head Web Cloud CI #34815025642](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/actions/runs/34815025642) и Vercel deployment успешны. Публичная главная и выбор перенесены в принятое направление B, auth URL сохранены, query регистрации нормализуется по allowlist, а выбранные площадка, модули и количество магазинов сохраняются при возврате из регистрации к `/#bundle`. Выбор остаётся только запросом, будущая площадка — интересом к запланированной интеграции. Локально ранее были зелёными 25 frontend-тестов, Next.js production build и backend suite на изолированной test DB: 244 passed, 22 skipped.

Первый запуск backend suite выполнен командой `python -m pytest -q` из `web/backend` без отдельного `MARKETPLACE_DATABASE_URL`, то есть на существующей untracked `web/backend/marketplace_cloud.db`. Упал ровно тест `tests/test_support_incidents.py::test_product_help_requires_approved_current_source_and_returns_citation`. Сообщение assertion: `assert (200 == 200 and True is False)` для проверки `missing.status_code == 200 and missing.json()['grounded'] is False`: ответ имел HTTP 200, но `grounded=true` вместо ожидаемого `false`. Повторный успех suite на отдельной чистой SQLite с явно заданным `MARKETPLACE_DATABASE_URL` подтверждает только невоспроизведение при изолированном состоянии; он **не доказывает устранение или точную первопричину первого сбоя**. Production-код ради этого наблюдения не изменялся.

**D02 остаётся draft и не принят:** разрешённый Browser открыл Vercel Preview, но тот перенаправил на `https://vercel.com/login` из-за защиты deployment. Доступной Vercel-сессии проекта нет; protection bypass не использовался. HTTP smoke и статический анализ не заменяют browser verification. Поэтому ещё не выполнены настоящие проверки 1440/1280/390, обычного и некорректного query, будущей площадки, cookie «Только обязательные» и сохранённого consent, клавиатуры, reduced motion, длинных названий, console/runtime errors и overflow. Не подтверждён маршрут выбор → регистрация → назад к `/#bundle` с восстановлением площадки, модулей и количества магазинов в видимых элементах. Реальные screenshots и запись маршрута не созданы.

Следующий gate: предоставить Browser разрешённый доступ к Preview без обхода Vercel protection, выполнить весь browser-набор, сохранить evidence в ветке, затем дождаться exact-head CI/Vercel evidence head и только после этого перевести PR #59 в ready for независимую приёмку. D02 не сливать и #48 не закрывать.

При обновлении workers сначала прекратить захват старой версией и завершить либо остановить старые обработчики; смешивание workers без fencing с новой версией недопустимо. Затем выполнить миграцию, развернуть API/workers и проверить heartbeat/recovery. Неизвестный результат уже отправленного HTTP требует сверки. Подробности — [deployment](backend/DEPLOYMENT.md). Runtime rollout не подтверждён.

`MARKETPLACE_ASSET_BLOB_HOSTS` остаётся **BLOCKED_EXTERNAL**: нужен точный hostname выделенного public Blob store. Hostname не угадывать; отсутствие настройки должно оставаться fail-closed.

GitHub Ruleset с обязательными merge checks остаётся **BLOCKED_EXTERNAL** до подтверждённого включения в настройках репозитория. Закрытый T01 подтверждает конфигурацию workflow, но не доказывает активную защиту branch ruleset.
