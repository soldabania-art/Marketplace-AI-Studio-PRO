import pytest
from fastapi import HTTPException

from app.agent_network import public_network, require_capability, sanitize_learning_note


def test_registry_has_one_master_and_independent_security_veto():
    network = public_network()
    assert network["master_agent"] == "director"
    assert network["security_veto"] == "security"
    assert network["rules"]["deny_by_default"] is True
    assert network["rules"]["external_writes_enabled"] is False
    assert network["rules"]["runtime_self_modification_allowed"] is False
    assert len(network["sha256"]) == 64


def test_agent_capabilities_are_deny_by_default_and_never_allow_current_external_writes():
    assert require_capability("finance", "profit.explain")["external_writes"] is False
    with pytest.raises(HTTPException) as unknown:
        require_capability("finance", "sql.execute")
    assert unknown.value.status_code == 403
    with pytest.raises(HTTPException) as external:
        require_capability("content", "copy.draft", external_write=True)
    assert external.value.status_code == 403
    with pytest.raises(HTTPException) as veto:
        require_capability("director", "recommend.read", security_denied=True)
    assert veto.value.status_code == 423


def test_learning_note_redacts_common_secrets_and_personal_email():
    note = sanitize_learning_note("user@example.com Bearer abcdefghijklmnopqrstuvwxyz token_abcdefghijklmnopqrstuvwxyz123456")
    assert "user@example.com" not in note
    assert "abcdefghijklmnopqrstuvwxyz" not in note
    assert "[REDACTED_EMAIL]" in note
    assert "[REDACTED_TOKEN]" in note

