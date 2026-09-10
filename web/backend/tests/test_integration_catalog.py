from app.integration_catalog import PRODUCTION_GATES, public_catalog


def test_catalog_is_deny_by_default_and_connection_is_explicit():
    payload = public_catalog(["wildberries"])
    rows = {row["code"]: row for row in payload["connectors"]}
    assert rows["wildberries"]["connected"] is True
    assert rows["wildberries"]["production_ready"] is False
    assert rows["ozon"]["connected"] is False
    assert rows["1c"]["connected"] is False
    assert rows["csv"]["production_ready"] is True
    assert tuple(rows["moysklad"]["gates"]) == PRODUCTION_GATES


def test_every_connector_declares_kind_capabilities_stage_and_gate():
    for row in public_catalog()["connectors"]:
        assert row["kind"] in {"marketplace", "accounting", "logistics"}
        assert row["stage"] in {"available", "read_beta", "discovery", "planned"}
        assert row["capabilities"]
        assert row["next_gate"]
