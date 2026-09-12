# Передача TROVENDI следующему разработчику

Дата: 12.09.2026. Исходный аудит: `f090a4b3006ff72351d7c37696ae3d7c228e7805`.

## Решение главного разработчика

Концепция **AI Commerce OS для РФ/СНГ одобрена**. Сохраняем одну платформу для новичка, продавца и агентства; отдельные роли партнёров-фулфилментов; общие данные, AI, согласования и документы.

**Полноценный платный запуск пока не одобрен.** Блокеры перечислены в [аудите](ARCHITECTURE_REVIEW_2026-09-12.md). Разработка и ограниченный тестовый контур могут продолжаться. Не выдавать текущее состояние за готовый автономный бизнес.

## Первая задача

Открой **T01** в [backlog](DEVELOPER_BACKLOG.md): добавь проверки PR, существующие CSV tests и migration job PostgreSQL. Сохрани рабочие Actions. Затем **T02 → T03 → T04**: общий STOP, платный read-only/Trial gate, строгий финансовый импорт. Остальные зависимости указаны в backlog. При внешнем блокере бери независимую задачу; не перепрыгивай к новым витринам.

Начальный маршрут каждого сеанса:

1. `git status --short`; проверь origin и актуальный main, не теряй чужие изменения.
2. Прочитай корневой AGENTS.md и status/dependencies задачи.
3. Проверь текущие проверки по SHA, воспроизведи дефект без внешних записей.
4. Сделай небольшой PR с причиной, результатом, regression test и оставшимися ограничениями.
5. Обнови задачу и handoff только фактами. Следующий разработчик должен продолжить без поиска истории чата.

## Что точно было проверено

- Получены все **354 файла** исходного дерева и сверены по Git blob SHA.
- 174 Python-файла синтаксически разобраны.
- [GitHub Actions run 34683401279](https://github.com/soldabania-art/Marketplace-AI-Studio-PRO/actions/runs/34683401279): frontend build success; **149 backend tests passed**, 3 warnings. Число 147 из переписки устарело.
- Локально: **4 CSV tests passed**.
- Шесть небольших проверок исходных функций воспроизвели проблемы entitlement, grounding, media verification, money parsing, response shape и freshness. Это не полный HTTP/DB e2e.
- Vercel GitHub status исходного SHA — success; прямой доступ к настройкам проекта вернул 403.
- Локальная установка FastAPI/dependencies недоступна в среде аудита. Полный backend suite и build в этой среде повторно не запускались; результат выше взят из настоящего CI.

## Команды проверки в подготовленной среде

```bash
cd web/backend
python -m pip install -r requirements.txt
python -m pytest -q
```

Для локальных тестов используй только отдельную тестовую БД и тестовые секреты. Production credentials не использовать.

```bash
cd web
npm ci
node --test tests/*.test.mjs
npm run build
```

Для миграции: `alembic upgrade head` на **отдельной** PostgreSQL test DB; проверь fresh install и upgrade previous→head. Проверку restore production выполняй по отдельному runbook и разрешённому процессу.

## Критические различия

| Что есть | Чего это не доказывает |
| --- | --- |
| Registry агентов | Исполнение каждым агентом реальных задач и независимый runtime Sentinel |
| STOP в Director | Блокировку отдельного Card Factory publisher |
| План и SQL-модель фулфилмента | Живой обмен с партнёром, резервы и приёмку |
| Hash и scan callback документов | Запуск scanner, восстановление ошибок и работа 25 МБ через Vercel |
| Ozon в desktop и маркетинге | Ozon web adapter |
| Paid entitlement service | Работающий checkout/webhook/email |
| Зелёные unit/contract tests | PostgreSQL concurrency, production e2e и ёмкость сети |

Источники решений: [дерево](PRODUCT_TREE.md), [roadmap](PRODUCT_ROADMAP.md), [backlog](DEVELOPER_BACKLOG.md), [security](SECURITY_MODEL.md). Не начинай с повторного проектирования всего продукта.
