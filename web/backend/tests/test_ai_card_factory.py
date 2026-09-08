from types import SimpleNamespace

import pytest

from app.ai_card_factory import _metadata, build_fact_set, validate_grounding


def _card():
    return {
        "nm_id": 123,
        "vendor_code": "SKU-1",
        "title": "Органайзер",
        "brand": "Home Brand",
        "subject_name": "Органайзеры",
        "description": "Органайзер для хранения",
        "photo_count": 2,
        "photos": [{"big": "https://example.test/1.jpg"}],
        "characteristics": [
            {"id": 8, "name": "Материал", "value": ["хлопок"]},
            {"id": 3, "name": "Ширина", "value": 30},
        ],
        "sizes": [],
        "updated_at": "2026-09-07T10:00:00Z",
    }


def test_fact_set_is_stable_and_contains_only_source_card_facts():
    first = build_fact_set(_card())
    second = build_fact_set(_card())
    assert first["sha256"] == second["sha256"]
    assert first["nm_id"] == 123
    assert {row["id"] for row in first["facts"]} >= {"card.title", "card.brand", "characteristic.3", "characteristic.8"}
    assert "orders" not in str(first).lower()


def test_grounding_rejects_unknown_fact_reference():
    fact_set = build_fact_set(_card())
    result = {
        "wb_title": "Органайзер Home Brand",
        "ozon_title": "Органайзер Home Brand",
        "description": "Органайзер для хранения из хлопка.",
        "seo_phrases": ["органайзер"],
        "visual_plan": ["Показать товар крупным планом"],
        "used_fact_ids": ["characteristic.999"],
    }
    with pytest.raises(ValueError, match="неподтверждённые"):
        validate_grounding(result, fact_set)


def test_grounding_rejects_invented_numbers():
    fact_set = build_fact_set(_card())
    result = {
        "wb_title": "Органайзер 50 см",
        "ozon_title": "Органайзер 50 см",
        "description": "Органайзер из хлопка шириной 50 см.",
        "seo_phrases": ["органайзер"],
        "visual_plan": ["Показать товар"],
        "used_fact_ids": ["card.title", "characteristic.8"],
    }
    with pytest.raises(ValueError, match="числа"):
        validate_grounding(result, fact_set)


def test_generation_metadata_tracks_usage_and_estimated_cost():
    settings = SimpleNamespace(openai_model="cheap-model", openai_input_microusd_per_million_tokens=1_000_000, openai_output_microusd_per_million_tokens=2_000_000)
    metadata = _metadata({"id": "response-1", "model": "actual-model", "usage": {"input_tokens": 2, "output_tokens": 1}}, settings)
    assert metadata == {"response_id": "response-1", "model": "actual-model", "usage": {"input_tokens": 2, "output_tokens": 1}, "estimated_cost_microusd": 4}
