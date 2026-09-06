from datetime import datetime, timezone
import calendar, requests


COSTS_URL = 'https://api.openai.com/v1/organization/costs'


def month_window(now=None):
    now = now or datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())


def organization_costs(admin_key, budget_usd=0.0, timeout=60):
    """Return official organization costs for the current month.

    OpenAI's organization Costs API requires an Admin API key. The public API does not
    expose a prepaid-credit-balance endpoint, so `remaining_usd` is deliberately an
    estimate against the user-configured monthly budget, not a claimed billing balance.
    """
    key = (admin_key or '').strip()
    if not key:
        raise RuntimeError('Для просмотра расходов OpenAI нужен Admin API key. Обычный project API key не даёт доступ к Organization Costs API.')
    start, end = month_window()
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    params = {'start_time': start, 'end_time': end, 'bucket_width': '1d', 'limit': 31}
    total = 0.0; currency = 'usd'; buckets = 0; page = None
    while True:
        query = dict(params)
        if page: query['page'] = page
        r = requests.get(COSTS_URL, headers=headers, params=query, timeout=timeout)
        if r.status_code in (401, 403):
            raise RuntimeError('OpenAI Admin API key не принят или у него нет прав на Organization Costs API.')
        if not r.ok:
            raise RuntimeError(f'OpenAI Costs API {r.status_code}: {(r.text or "")[:500]}')
        data = r.json() if r.content else {}
        for bucket in data.get('data') or []:
            buckets += 1
            for item in bucket.get('results') or []:
                amount = item.get('amount') or {}
                try: total += float(amount.get('value') or 0)
                except Exception: pass
                currency = str(amount.get('currency') or currency).lower()
        if not data.get('has_more') or not data.get('next_page'):
            break
        page = data.get('next_page')
    try: budget = max(0.0, float(budget_usd or 0))
    except Exception: budget = 0.0
    return {
        'spent_usd': total,
        'budget_usd': budget,
        'remaining_usd': max(0.0, budget - total) if budget > 0 else None,
        'currency': currency,
        'buckets': buckets,
        'source': 'OpenAI Organization Costs API',
        'remaining_kind': 'configured_budget_estimate' if budget > 0 else 'not_available',
    }
