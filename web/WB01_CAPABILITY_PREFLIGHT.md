# WB01 · Проверка доступности источников Wildberries

**Статус:** реализовано локально; независимая приёмка, PostgreSQL и remote CI не выполнены.

**База:** `main` `3d5e59a17469bf622f858889adf75e585d3a5253`.

**Основание:** `WB_FIRST_VERIFIABLE_PILOT.md`, документный commit `9b22f42c2880b1769a24b86aeeb59a88256cce56`. Документ основания пока не интегрирован в `main`; WB01 не включает D01, D02 или D03.

## Граница

WB01 проверяет доступ сохранённого или нового кандидата-токена к read-источникам первого WB-пилота и показывает store-scoped матрицу в API/account UI. Проверка не запускает импорт, не выполняет WB write, не меняет retry/requeue, финансовый parser, тарифы или backend-контракты импортёров. В разработке и тестах используются только mock HTTP.

## Сверка с официальной документацией WB

Сверено 13.09.2026 по официальным разделам WB API: [работа с товарами](https://dev.wildberries.ru/docs/openapi/item-management), [аналитика](https://dev.wildberries.ru/docs/openapi/analytics), [финансы](https://dev.wildberries.ru/docs/openapi/documents-and-accounting), [продвижение](https://dev.wildberries.ru/docs/openapi/promotion), [общение с покупателями](https://dev.wildberries.ru/docs/openapi/customer-communication) и [токены/OAuth](https://dev.wildberries.ru/cases/139/seller-data-access-tokens-and-oauth-2-0).

Официальное руководство отдельно подтверждает: HTTP-метод не определяет read-only; read-only токен блокирует изменяющие операции, но чтение может выполняться через POST. `401` означает, что токен не принят, но не доказывает только истечение: среди причин также повреждение, отзыв и отсутствие категории. `403` означает, что токен принят, но конкретный метод ему недоступен.

| Источник / endpoint импортёра | Категория токена WB | Безопасный probe WB01 | Почему ограничен |
| --- | --- | --- | --- |
| Каталог: `POST /content/v2/get/cards/list` | Content | `cursor.limit=1`, без поисковой строки, только список карточек | Read-операция; возвращается максимум одна карточка. Первый `nmID` нужен для валидного probe истории продаж |
| Остатки: `POST /api/analytics/v1/stocks-report/wb-warehouses` | Analytics | `nmIds=[]`, `chrtIds=[]`, `limit=1`, `offset=0` | Read-отчёт; максимум одна строка |
| Продажи: `POST /api/analytics/v3/sales-funnel/products/history` | Analytics | Один фактический `nmId` из catalog probe, один день, `aggregationLevel=day` | Документация требует `nmIds` длиной 1–20; при отсутствии карточки endpoint честно остаётся `unchecked` |
| Финансы: `POST /api/finance/v1/sales-reports/detailed` | Finance | Один день, `limit=1`, `rrdId=0` | Read-отчёт; не загружается 30-дневный отчёт или следующая страница |
| Кампании: `GET /adv/v1/promotion/count` | Promotion | Один запрос списка кампаний | Нужен один фактический `advertId` для валидной проверки статистики; тело используется только в памяти и не сохраняется |
| Статистика рекламы: `GET /adv/v3/fullstats` | Promotion | Один фактический `advertId`, один день | При отсутствии кампаний endpoint остаётся `unchecked`; доступ к списку не маскирует непроверенную статистику |
| Отзывы: `GET /api/v1/feedbacks` | Feedbacks and Questions | `isAnswered=false`, `take=1`, `skip=0` | Read-операция; максимум один отзыв |

WB01 выполняет не более семи provider-запросов, каждый ограничен 2 секундами, весь синхронный preflight — 8 секундами. Proxy ждёт до 9 секунд, то есть остаётся внутри существующего общего 10-секундного потолка `backendRequest`; глобальный timeout других API не меняется. По актуальным [ограничениям Vercel Functions](https://vercel.com/docs/functions/limitations) Node.js Functions с Fluid Compute допускают 300 секунд по умолчанию, поэтому отдельная асинхронная очередь ради этого ограниченного read-only preflight не нужна. При обрыве ожидания proxy возвращает неопределённый исход, а UI перечитывает GET-состояние без автоматического повтора подключения.

Каждый вызов проходит через общий marketplace limiter. `429` публикует cooldown через существующую обработку `Retry-After`. Redirects выключены. Тела и provider errors не сохраняются; API возвращает только безопасный статус, технический reason из allowlist и время.

## Контракт статусов

Каждый endpoint получает один статус:

- `available` — WB ответил `200` или документированным пустым `204`;
- `forbidden` — WB ответил `401`, `402` или `403`; для `401` дополнительно `authentication_error=true` без утверждения «токен истёк»;
- `transient_error` — timeout/network, `429`, `5xx` или недоступный shared limiter;
- `unchecked` — валидный минимальный probe нельзя выполнить (нет карточки/кампании), исчерпан лимит запросов или WB не принял валидный probe и не подтвердил доступ.

Группы `catalog`, `analytics`, `finance`, `advertising`, `feedbacks` содержат массив endpoint-строк. Групповой статус агрегируется консервативно и не скрывает различие, например `stocks=available`, `sales=forbidden`.

Summary матрицы отделён от endpoint-статуса:

- `complete` — все endpoints доступны;
- `partial` — хотя бы один доступен, но не все;
- `temporary_failure` — ни один не подтверждён и есть временная ошибка;
- `rejected` — ни один не подтверждён и WB отказал в доступе;
- `unchecked` — проверка не выполнялась или доказательств нет.

## Сохранение и конкуренция

- `credentials_version` увеличивается при каждой замене токена и отключении.
- Матрица и `capabilities_checked_at` записываются только для точной версии credentials и поколения проверки.
- Каждый refresh атомарно увеличивает `capability_check_generation` до WB-вызовов и применяет результат только при совпадении `credentials_version`, `capability_check_generation` и `enabled=true`. Поэтому поздний ответ более старой проверки того же токена, старого токена или отключённого подключения не меняет матрицу.
- Новый токен с `complete` сохраняется после проверки.
- `partial` не заменяет текущий токен без отдельного `accept_partial=true`; account UI показывает матрицу и явное подтверждение.
- `temporary_failure`, `rejected` и `unchecked` не заменяют текущий токен даже при подтверждении partial.
- Существующие строки после миграций получают `credentials_version=1`, `capability_check_generation=0`, `capability_results=NULL`, `capabilities_checked_at=NULL`; API показывает их как `unchecked`, а не `available`.

## Права и API

- `GET /api/v1/integrations/wildberries?store_id=…` — status для участника workspace, без credentials и token hint.
- `POST /api/v1/integrations/wildberries` — проверка кандидата и контролируемое сохранение; только owner/admin + MFA + свежий step-up.
- `POST /api/v1/integrations/wildberries/check?store_id=…` — повторная проверка сохранённой версии; те же owner/admin + MFA + step-up.
- `DELETE /api/v1/integrations/wildberries?store_id=…` — действующее защищённое отключение; дополнительно инвалидирует поколение credentials и очищает матрицу.

`resolve_store` и `require_store_admin` выполняются до расшифровки/обращения к WB. Guest, foreign store, viewer/analyst, отсутствие MFA или step-up дают ноль provider-вызовов.

## Критерии приёмки

1. Фактические endpoints импортёров, категории токена и probes совпадают с актуальной официальной документацией WB.
2. Полный mock-доступ даёт семь разрешённых read-вызовов, `complete`, безопасное сохранение токена и версию credentials.
3. Частичный доступ виден по каждому endpoint; общий статус не маскирует недоступные sales или advertising statistics.
4. `401` отмечается как `authentication_error`, но UI/API не утверждают, что токен истёк; `403` остаётся отказом конкретного доступа.
5. `429` учитывает `Retry-After`; timeout/network/`5xx` имеют `transient_error`; запросы ограничены по времени и числу.
6. В mock-трассе отсутствуют WB write endpoints. Токен и тела/provider detail не попадают в response, persistence, логи или тестовый failure output.
7. Partial требует явного подтверждения; временная ошибка и полностью неуспешный кандидат не заменяют рабочий токен.
8. Более новая проверка той же версии credentials, смена токена и отключение во время проверки fencing-ом отвергают поздний результат; disconnect/rotation подтверждаются на PostgreSQL двумя независимыми сессиями.
9. Owner/admin, MFA, step-up и store isolation сохранены; неавторизованные сценарии завершаются до HTTP к WB.
10. Account UI отдельно показывает «токен сохранён», матрицу/время проверки и предупреждение, что проверка не является импортом.
11. Миграции проходят fresh install и `20260913_0029 → 20260913_0030` на PostgreSQL; existing connection получает поколение `0` и отображается `unchecked`.
12. Backend suite, frontend tests/build, remote CI и разрешённый browser preview зелёные на точном head.

## Оставшиеся gates

- PostgreSQL fresh, `20260913_0029 → 20260913_0030` и two-session concurrency не подтверждены локально без доступной тестовой PostgreSQL; соответствующие integration tests добавлены и должны пройти в обязательном PostgreSQL CI job.
- Remote CI, Vercel и browser preview не запускались. Deployment запрещён действующим ограничением.
- Реальный WB-токен и реальные WB endpoints не использовались; фактическая совместимость ответа WB остаётся runtime gate пилота.
