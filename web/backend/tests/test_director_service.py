from app.director_service import action, build_director, compare_measurement


def live_sources():
    return [{'name': name, 'state': 'live', 'last_snapshot_at': None, 'age_seconds': 10} for name in (
        'catalog', 'stocks', 'sales_velocity_7d', 'finance_realization_sync', 'advertising_sync', 'feedbacks')]


def complete_profit(products=None):
    return {'profit_status': 'complete', 'completeness': {'cogs': True, 'tax': True}, 'products': products or []}


def test_priority_is_deterministic_and_risk_reduces_score():
    safe = action(action_id='a', kind='data_health', title='A', reason='R', evidence='E', href='/', urgency='high', confidence='high')
    risky = action(action_id='b', kind='profit', title='B', reason='R', evidence='E', href='/', urgency='high', confidence='high', risk='high')
    assert safe['priority_score'] == 60
    assert risky['priority_score'] == 50
    assert safe['provider']['estimated_cost_microusd'] == 0


def test_director_never_invents_money_effect_for_low_stock():
    result = build_director(store_id='s1', store_name='Store', sources=live_sources(), catalog_items=[],
        supply_facts=[{'nm_id': 12, 'sku': 'SKU', 'title': 'Чайник', 'stock': 3, 'avg_daily_sales': 1, 'orders_period': 7}],
        profit=complete_profit())
    item = next(row for row in result['actions'] if row['id'] == 'stock:12')
    assert item['observed_effect_kopecks'] is None
    assert item['requires_approval'] is True
    assert item['can_execute'] is False


def test_director_exposes_observed_loss_but_labels_partial_scope():
    result = build_director(store_id='s1', store_name='Store', sources=live_sources(), catalog_items=[], supply_facts=[],
        profit={'profit_status': 'partial', 'completeness': {'cogs': True, 'tax': True}, 'products': [
            {'nm_id': 7, 'title': 'Товар', 'final_profit': None, 'contribution_before_tax_ads': '-125.50'}]})
    item = next(row for row in result['actions'] if row['id'] == 'loss:7')
    assert item['observed_effect_kopecks'] == -12550
    assert item['effect_scope'] == 'observed_partial_contribution_30d'
    assert item['confidence'] == 'medium'


def test_missing_sources_become_explainable_actions_without_ai_guessing():
    sources = [{'name': name, 'state': 'missing', 'last_snapshot_at': None, 'age_seconds': None} for name in (
        'catalog', 'stocks', 'sales_velocity_7d', 'finance_realization_sync', 'advertising_sync')]
    result = build_director(store_id='s1', store_name='Store', sources=sources, catalog_items=[], supply_facts=[],
        profit={'profit_status': 'partial', 'completeness': {'cogs': False, 'tax': False}, 'products': []})
    assert result['mode'] == 'waiting'
    assert len(result['actions']) == 8
    assert all(item['provider']['label'] == 'Rules · Free' for item in result['actions'])
    assert result['automation']['writes_enabled'] is False
    source_action = next(item for item in result['actions'] if item['id'] == 'source:stocks')
    assert source_action['can_execute'] is True
    assert source_action['execution_type'] == 'read_sync'


def test_measurement_compares_same_metric_without_inventing_resolved_value():
    improved = compare_measurement(
        {'metric': 'profit_kopecks', 'baseline': -20000, 'better_when': 'higher'},
        {'metric': 'profit_kopecks', 'baseline': -5000, 'better_when': 'higher'},
    )
    assert improved['outcome'] == 'improved'
    assert improved['delta'] == 15000
    resolved = compare_measurement({'metric': 'content_issue_count', 'baseline': 2, 'better_when': 'lower'}, None)
    assert resolved['outcome'] == 'no_longer_detected'
    assert resolved['current'] is None


def test_director_turns_review_facts_into_human_only_actions():
    result = build_director(store_id='s1', store_name='Store', sources=live_sources(), catalog_items=[], supply_facts=[], profit=complete_profit(), feedback_items=[
        {'feedback_id': 'a', 'rating': 2, 'answered': False}, {'feedback_id': 'b', 'rating': 5, 'answered': True},
    ])
    low = next(item for item in result['actions'] if item['id'] == 'reviews:low-rating')
    unanswered = next(item for item in result['actions'] if item['id'] == 'reviews:unanswered')
    assert low['measurement']['baseline'] == 1
    assert unanswered['measurement']['baseline'] == 1
    assert low['can_execute'] is False and unanswered['can_execute'] is False
