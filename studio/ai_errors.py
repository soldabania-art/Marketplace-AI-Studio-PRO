import json


class OpenAIQuotaError(RuntimeError):
    pass


class OpenAIAuthError(RuntimeError):
    pass


def _payload(response):
    try:
        data=response.json()
        return data if isinstance(data,dict) else {}
    except Exception:
        return {}


def raise_openai_error(response, prefix='OpenAI'):
    """Convert OpenAI HTTP failures into short, user-facing Russian errors."""
    if response.ok:
        return
    data=_payload(response)
    err=data.get('error') if isinstance(data,dict) else None
    err=err if isinstance(err,dict) else {}
    code=str(err.get('code') or '')
    kind=str(err.get('type') or '')
    message=str(err.get('message') or '')
    status=int(getattr(response,'status_code',0) or 0)

    if status==429 and (code in ('credit_balance_exhausted','insufficient_quota') or kind=='insufficient_quota' or 'credits' in message.lower()):
        raise OpenAIQuotaError(
            'На OpenAI API закончился баланс. AI-запросы временно остановлены, чтобы программа не запускала платный пакет снова. '
            'Пополните API-баланс в OpenAI Platform → Billing, затем повторите операцию.'
        )
    if status in (401,403):
        raise OpenAIAuthError(
            'OpenAI отклонил API-ключ. Проверьте ключ в «Подключения» и доступ проекта к выбранной модели.'
        )
    if status==429:
        raise RuntimeError('OpenAI временно ограничил частоту запросов. Подождите немного и повторите операцию.')
    if status>=500:
        raise RuntimeError(f'{prefix} временно недоступен (HTTP {status}). Повторите позже.')

    detail=message.strip() or (getattr(response,'text','') or '')[:500]
    raise RuntimeError(f'{prefix} HTTP {status}: {detail}')


def friendly_ai_error(error):
    text=str(error or '').strip()
    low=text.lower()
    if 'credit_balance_exhausted' in low or 'insufficient_quota' in low or 'no credits remaining' in low:
        return ('На OpenAI API закончился баланс. Пополните API-баланс в OpenAI Platform → Billing. '
                'После пополнения повторите AI-операцию.')
    if '401' in low or 'invalid_api_key' in low:
        return 'OpenAI API-ключ недействителен. Проверьте ключ в разделе «Подключения».'
    return text[:1200] if text else 'Неизвестная ошибка AI'
