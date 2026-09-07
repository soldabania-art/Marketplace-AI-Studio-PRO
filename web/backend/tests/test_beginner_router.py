import base64
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.beginner_router import (
    BeginnerDraftRequest,
    ConfirmedFact,
    PhotoAnalysisRequest,
    analyze_photo,
    build_beginner_fact_set,
    generate_draft,
    sign_analysis,
)


def _data_url(raw=b"real-image-bytes"):
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode()


def test_beginner_photo_analysis_marks_facts_for_confirmation(monkeypatch):
    expected = {"product_name_guess": "Органайзер", "required_questions": ["Какой материал?"]}
    monkeypatch.setattr("app.beginner_router.analyze_product_photo", lambda image: expected)
    result = analyze_photo(PhotoAnalysisRequest(image_data_url=_data_url(b"x" * 80)), user=SimpleNamespace(id="u1"))
    assert result["analysis"] == expected
    assert result["source"] == "single_photo"
    assert result["facts_require_confirmation"] is True
    assert len(result["analysis_signature"]) == 64


def test_beginner_photo_rejects_unsupported_data_url():
    with pytest.raises(HTTPException) as exc:
        analyze_photo(PhotoAnalysisRequest(image_data_url="data:text/plain;base64," + "eA==" * 30), user=SimpleNamespace(id="u1"))
    assert exc.value.status_code == 400


def test_beginner_fact_set_contains_only_seller_confirmed_values():
    facts = build_beginner_fact_set(
        {"product_name_guess": "Другое предположение", "confidence": "medium"},
        [ConfirmedFact(label="Товар", value="Органайзер"), ConfirmedFact(label="Материал", value="Металл")],
    )
    assert [row["value"] for row in facts["facts"]] == ["Органайзер", "Металл"]
    assert "Другое предположение" not in str(facts["facts"])
    assert len(facts["sha256"]) == 64


def test_beginner_draft_rejects_changed_photo_analysis():
    original = {"confidence": "medium", "visible_facts": []}
    payload = BeginnerDraftRequest(
        analysis={"confidence": "high", "visible_facts": []},
        analysis_signature=sign_analysis(original),
        confirmed_facts=[ConfirmedFact(label="Товар", value="Органайзер"), ConfirmedFact(label="Категория", value="Хранение")],
    )
    with pytest.raises(HTTPException) as exc:
        generate_draft(payload, user=SimpleNamespace(id="u1"))
    assert exc.value.status_code == 400


def test_beginner_draft_uses_grounded_generator(monkeypatch):
    analysis = {"confidence": "high", "visible_facts": [{"label": "Цвет", "value": "Белый"}]}
    generated = {"wb_title": "Органайзер белый", "used_fact_ids": ["seller.confirmed.0"]}
    captured = {}

    def fake_generate(fact_set):
        captured.update(fact_set)
        return generated

    monkeypatch.setattr("app.beginner_router.generate_grounded_copy", fake_generate)
    payload = BeginnerDraftRequest(
        analysis=analysis,
        analysis_signature=sign_analysis(analysis),
        confirmed_facts=[ConfirmedFact(label="Товар", value="Органайзер"), ConfirmedFact(label="Категория", value="Хранение")],
    )
    result = generate_draft(payload, user=SimpleNamespace(id="u1"))
    assert result["draft"] == generated
    assert captured["source"] == "beginner_confirmed_intake"
    assert result["publish_requires_confirmation"] is True
    assert result["next_step"] == "unit_economics"
