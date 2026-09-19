from app.wb_capability_preflight import import_group_availability, unchecked_capabilities


def _matrix(**states):
    return {"sources": [
        {"key": key, "status": states.get(key, "available"), "endpoints": []}
        for key in ("catalog", "analytics", "finance", "advertising", "feedbacks")
    ]}


def test_unchecked_connection_never_becomes_an_automatic_import_retry():
    assert {row["state"] for row in import_group_availability(unchecked_capabilities()).values()} == {"blocked"}


def test_partial_matrix_keeps_unrelated_source_groups_available():
    groups = import_group_availability(_matrix(finance="forbidden", advertising="transient_error"))
    assert groups["core"]["state"] == "available"
    assert groups["finance"]["state"] == "blocked"
    assert groups["advertising"]["state"] == "deferred"
