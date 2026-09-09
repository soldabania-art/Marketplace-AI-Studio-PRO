import pytest
from fastapi import HTTPException

from app.director_router import _transition, _validate_control


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
