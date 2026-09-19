# WB02 · ручное восстановление onboarding import

Дата реализации: 13.09.2026. База: `3d5e59a17469bf622f858889adf75e585d3a5253`.

## Граница изменения

`POST /api/v1/onboarding/import` сохраняет прежнюю часовую идемпотентность для
успешных и активных jobs. Если terminal `dead` относится к onboarding root или
continuation, сервер создаёт новый namespace только для повреждённой группы.
Для finance/advertising новый `run_id` также даёт новые ключи всем последующим
страницам. Успешные группы не перезапускаются, старые jobs и audit остаются в БД.

Три результата запроса и audit фиксируются одной транзакцией. Ошибка при
постановке любой группы откатывает весь запрос. Существующий active
`queued/running/retry` возвращается без изменения `available_at`, поэтому ручной
запрос не обходит provider `Retry-After`. Импорт остаётся read-only и не зависит
от STOP внешних записей.

Не менялись credential `401/403`, финансовый parser, WB writes, paid AI и
deployment.

## Проверки

- API regression: успешные core/advertising + dead finance continuation → только
  finance получает новый runnable root и свежий `run_id`; повтор возвращает его
  же.
- API fault injection: сбой третьего enqueue не оставляет первые два jobs.
- Active retry: ручной повтор сохраняет job ID и cooldown.
- PostgreSQL regression: два перекрывающихся запроса должны получить одну
  recovery generation; тест пропускается вне PostgreSQL и не считается локально
  пройденным.
