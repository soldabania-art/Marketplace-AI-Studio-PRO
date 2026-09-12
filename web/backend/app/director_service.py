from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

URGENCY_WEIGHT = {'critical': 40, 'high': 30, 'medium': 20, 'low': 10}
CONFIDENCE_WEIGHT = {'high': 30, 'medium': 20, 'low': 10}
RISK_PENALTY = {'low': 0, 'medium': 5, 'high': 10}


def _money_to_kopecks(value: str | None) -> int | None:
    return None if value is None else int(Decimal(value) * 100)


def _impact_weight(observed_effect_kopecks: int | None) -> int:
    if observed_effect_kopecks is None: return 0
    amount = abs(observed_effect_kopecks)
    if amount >= 100_000: return 30
    if amount >= 25_000: return 20
    return 10 if amount > 0 else 0


def compare_measurement(baseline: dict | None, current: dict | None) -> dict:
    if not baseline:
        raise ValueError('У рекомендации нет измеримой исходной метрики.')
    if current is None:
        return {'metric': baseline['metric'], 'baseline': baseline.get('baseline'), 'current': None,
                'delta': None, 'outcome': 'no_longer_detected',
                'explanation': 'Проблема больше не определяется актуальными правилами. Числовой эффект не выдумывается.'}
    if baseline.get('metric') != current.get('metric'):
        raise ValueError('Текущая метрика несовместима с исходной рекомендацией.')
    before, after, direction = baseline.get('baseline'), current.get('baseline'), baseline.get('better_when')
    if baseline['metric'] == 'source_state':
        improved = after == direction and before != after
        return {'metric': baseline['metric'], 'baseline': before, 'current': after, 'delta': None,
                'outcome': 'improved' if improved else ('unchanged' if before == after else 'changed'),
                'explanation': 'Источник актуален.' if improved else 'Состояние источника ещё не стало актуальным.'}
    delta = after - before
    improved = delta > 0 if direction == 'higher' else delta < 0
    return {'metric': baseline['metric'], 'baseline': before, 'current': after, 'delta': delta,
            'outcome': 'improved' if improved else ('unchanged' if delta == 0 else 'worse'),
            'explanation': 'Метрика улучшилась.' if improved else ('Метрика не изменилась.' if delta == 0 else 'Метрика ухудшилась.')}


def action(*, action_id: str, kind: str, title: str, reason: str, evidence: str,
           href: str, urgency: str = 'medium', confidence: str = 'high',
           risk: str = 'low', requires_approval: bool = False,
           observed_effect_kopecks: int | None = None, effect_scope: str = 'not_calculated',
           source_refs: list[str] | None = None, can_execute: bool = False,
           execution_type: str | None = None, measurement: dict | None = None) -> dict[str, Any]:
    score = max(0, min(100, URGENCY_WEIGHT[urgency] + CONFIDENCE_WEIGHT[confidence]
                       + _impact_weight(observed_effect_kopecks) - RISK_PENALTY[risk]))
    return {
        'id': action_id, 'kind': kind, 'title': title, 'reason': reason,
        'evidence': evidence, 'href': href, 'priority_score': score,
        'priority_reason': f'Срочность {urgency} · уверенность {confidence} · риск {risk}',
        'urgency': urgency, 'confidence': confidence, 'risk': risk,
        'requires_approval': requires_approval, 'can_execute': can_execute,
        'execution_type': execution_type,
        'status': 'proposed', 'observed_effect_kopecks': observed_effect_kopecks,
        'effect_scope': effect_scope, 'source_refs': source_refs or [],
        'measurement': measurement,
        'provider': {'tier': 'free', 'label': 'Rules · Free', 'estimated_cost_microusd': 0},
    }


def build_director(*, store_id: str, store_name: str, sources: list[dict],
                   catalog_items: list[dict], supply_facts: list[dict], profit: dict,
                   feedback_items: list[dict] | None = None) -> dict:
    actions: list[dict] = []
    source_by_name = {item['name']: item for item in sources}
    missing_source_labels = {
        'catalog': ('Каталог WB ещё не загружен', '/products'),
        'stocks': ('Остатки WB ещё не загружены', '/products'),
        'sales_velocity_7d': ('История заказов WB ещё не загружена', '/products'),
        'finance_realization_sync': ('Финансовый отчёт WB не готов за 30 дней', '/profit'),
        'advertising_sync': ('Рекламная статистика WB не готова за 30 дней', '/profit'),
        'feedbacks': ('Отзывы WB ещё не загружены', '/reviews'),
    }
    for name, (title, href) in missing_source_labels.items():
        source = source_by_name.get(name) or {'state': 'missing'}
        if source['state'] in {'missing', 'stale', 'incomplete'}:
            state_label = {'missing': 'источник отсутствует', 'stale': 'превышен срок свежести источника',
                           'incomplete': 'загрузка не завершена'}[source['state']]
            actions.append(action(
                action_id=f'source:{name}', kind='data_health', title=title,
                reason='Без этого источника директор не подменяет факты прогнозом.',
                evidence=state_label, href=href,
                urgency='high' if name in {'stocks', 'finance_realization_sync'} else 'medium',
                source_refs=[name], can_execute=True, execution_type='read_sync',
                measurement={'metric': 'source_state', 'baseline': source['state'], 'better_when': 'live'},
            ))
    completeness = profit.get('completeness') or {}
    if not completeness.get('cogs'):
        actions.append(action(
            action_id='finance:missing-cogs', kind='profit', title='Подтвердите себестоимость товаров',
            reason='Без себестоимости нельзя достоверно вычислить прибыль по SKU.',
            evidence='Profit Center: себестоимость заполнена не для всех проданных товаров.',
            href='/profit', urgency='high', source_refs=['product_cost_profiles'],
        ))
    if not completeness.get('tax'):
        actions.append(action(
            action_id='finance:missing-tax', kind='profit', title='Подтвердите налоговую базу и ставку',
            reason='Итоговая прибыль остаётся частичной без подтверждённого налогового резерва.',
            evidence='Profit Center: налоговый профиль магазина не заполнен.',
            href='/profit', source_refs=['store_tax_profile'],
        ))
    for item in profit.get('products') or []:
        value = _money_to_kopecks(item.get('final_profit')); complete = value is not None
        if value is None: value = _money_to_kopecks(item.get('contribution_before_tax_ads'))
        if value is not None and value < 0:
            label = 'итоговый убыток' if complete else 'отрицательный вклад до налога и полной рекламы'
            actions.append(action(
                action_id=f"loss:{item['nm_id']}", kind='profit',
                title=f"Убыточный товар: {item.get('title') or item['nm_id']}",
                reason='Проверьте цену, расходы WB и себестоимость до любых изменений.',
                evidence=f"За 30 дней {label}: {Decimal(value) / Decimal(100):.2f} ₽.",
                href='/profit', urgency='critical', confidence='high' if complete else 'medium',
                risk='medium', requires_approval=True, observed_effect_kopecks=value,
                effect_scope='observed_final_profit_30d' if complete else 'observed_partial_contribution_30d',
                measurement={'metric': 'profit_kopecks', 'baseline': value, 'better_when': 'higher'},
                source_refs=['finance_realization_sync', 'product_cost_profiles'],
            ))
    for fact in supply_facts:
        stock = max(0, int(fact.get('stock') or 0)); velocity = max(0, float(fact.get('avg_daily_sales') or 0))
        if velocity <= 0: continue
        days_left = stock / velocity
        if stock == 0 or days_left < 7:
            nm_id = int(fact['nm_id'])
            actions.append(action(
                action_id=f'stock:{nm_id}', kind='supply',
                title=f"{'Нет остатка' if stock == 0 else 'Запас меньше 7 дней'}: {fact.get('title') or fact.get('sku') or nm_id}",
                reason='Продажи могут остановиться, если поставка не успеет до исчерпания запаса.',
                evidence=f"Остаток {stock} шт. · средний спрос {velocity:.2f} шт./день · запас {days_left:.1f} дн.",
                href='/products', urgency='critical' if stock == 0 else 'high',
                risk='medium', requires_approval=True, source_refs=['stocks', 'sales_velocity_7d'],
                measurement={'metric': 'days_of_supply', 'baseline': round(days_left, 3), 'better_when': 'higher'},
            ))
    for card in catalog_items:
        nm_id = int(card.get('nm_id') or 0); issues = []
        if not str(card.get('title') or '').strip(): issues.append('нет названия')
        if not str(card.get('description') or '').strip(): issues.append('нет описания')
        if int(card.get('photo_count') or 0) == 0: issues.append('нет фотографий')
        if issues:
            actions.append(action(
                action_id=f'content:{nm_id}', kind='content',
                title=f"Неполная карточка: {card.get('title') or card.get('vendor_code') or nm_id}",
                reason='Заполните только подтверждённые факты карточки перед генерацией и публикацией.',
                evidence='; '.join(issues).capitalize() + '.', href=f'/card-factory?nm_id={nm_id}',
                risk='medium', requires_approval=True, source_refs=['catalog'],
                measurement={'metric': 'content_issue_count', 'baseline': len(issues), 'better_when': 'lower'},
            ))
    reviews = list(feedback_items or [])
    if reviews:
        low_rating_count = sum(int(item.get('rating') or 5) <= 3 for item in reviews)
        unanswered_count = sum(not bool(item.get('answered')) for item in reviews)
        if low_rating_count:
            actions.append(action(
                action_id='reviews:low-rating', kind='reviews', title='Проверьте причины низких оценок',
                reason='Повторяющийся негатив может указывать на проблему товара, упаковки или ожиданий покупателей. Директор не делает вывод о причине без просмотра отзывов.',
                evidence=f'В сохранённом снимке {low_rating_count} отзывов с оценкой 1–3 из {len(reviews)}.',
                href='/reviews', urgency='high' if low_rating_count >= 5 else 'medium', risk='low',
                source_refs=['feedbacks'], measurement={'metric': 'low_rating_feedback_count', 'baseline': low_rating_count, 'better_when': 'lower'},
            ))
        if unanswered_count:
            actions.append(action(
                action_id='reviews:unanswered', kind='reviews', title='Проверьте отзывы без ответа',
                reason='Ответ должен быть проверен продавцом: TROVENDI не отправляет сообщения покупателям автоматически.',
                evidence=f'В сохранённом снимке {unanswered_count} отзывов без ответа продавца.',
                href='/reviews', urgency='medium', risk='low', source_refs=['feedbacks'],
                measurement={'metric': 'unanswered_feedback_count', 'baseline': unanswered_count, 'better_when': 'lower'},
            ))
    actions.sort(key=lambda item: (-item['priority_score'], item['id'])); actions = actions[:10]
    source_states = {item['state'] for item in sources}
    mode = 'live' if source_states <= {'live'} and profit.get('profit_status') == 'complete' else ('waiting' if source_states == {'missing'} else 'partial')
    loss_total = sum(abs(item['observed_effect_kopecks']) for item in actions
                     if item['kind'] == 'profit' and item['observed_effect_kopecks'] is not None and item['observed_effect_kopecks'] < 0)
    return {
        'store_id': store_id, 'store_name': store_name, 'marketplace': 'wildberries',
        'generated_at': datetime.now(timezone.utc), 'mode': mode, 'sources': sources,
        'summary': {
            'what_happened': f'Найдено {len(actions)} подтверждённых задач по подключённым источникам.',
            'money_losses': {'observed_kopecks': loss_total or None, 'scope': 'Только обнаруженные отрицательные значения; не прогноз.'},
            'today_actions': len(actions),
            'safe_actions': sum(not item['requires_approval'] for item in actions),
            'approval_required': sum(item['requires_approval'] for item in actions),
            'measured_changes': 'История выполненных действий ещё не накоплена. Результат после вчера будет доступен после запуска журнала исполнения.',
        },
        'actions': actions,
        'ranking': {'formula': 'срочность + уверенность + подтверждённый денежный масштаб − риск', 'max_actions': 10},
        'automation': {'mode': 'proposal_only', 'writes_enabled': False, 'note': 'Director ничего не меняет в WB без отдельного подтверждения.'},
    }
