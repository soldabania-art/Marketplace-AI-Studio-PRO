import pytest
from fastapi import HTTPException

from app.director_router import _read_sync_group, _transition, _validate_control


def test_director_decision_is_append_only_for_one_recommendation():
    assert _transition('proposed', 'approve') == 'approved'
    assert _transition('approved', 'approve') == 'approved'
    with pytest.raises(HTTPException) as error:
        _transition('approved', 'reject')
    assert error.value.status_code == 409


def test_emergency_stop_is_immediate_but_resume_requires_phrase():
    _validate_control(True, '')
    with pytest.raises(HTTPException) as error:
        _validate_control(False, 'возобновить')
    assert error.value.status_code == 422
    _validate_control(False, '  возобновить trovendi  ')


def test_executor_allowlist_contains_only_read_sync_actions():
    read_only = {'can_execute': True, 'execution_type': 'read_sync'}
    assert _read_sync_group('source:stocks', read_only) == 'analytics'
    assert _read_sync_group('source:finance_realization_sync', read_only) == 'profit'
    assert _read_sync_group('source:feedbacks', read_only) == 'feedbacks'
    with pytest.raises(HTTPException):
        _read_sync_group('content:42', {'can_execute': True, 'execution_type': 'marketplace_write'})
    with pytest.raises(HTTPException):
        _read_sync_group('source:unknown', read_only)
