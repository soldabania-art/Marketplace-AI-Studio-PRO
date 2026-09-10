import pytest

from app.review_ai import build_review_fact_set, validate_review_analysis


def test_review_fact_set_is_stable_bounded_and_has_no_buyer_identity():
    source = [{"feedback_id": "f1", "nm_id": 1, "rating": 2, "text": "Сломано", "user_name": "Секрет", "answered": False}]
    facts = build_review_fact_set(source)
    assert facts["reviews"][0]["feedback_id"] == "f1"
    assert "user_name" not in facts["reviews"][0]
    assert len(facts["sha256"]) == 64


def test_analysis_references_only_known_feedback_and_blocks_promises():
    facts = build_review_fact_set([{"feedback_id": "f1", "nm_id": 1, "rating": 2, "text": "Сломано"}])
    validate_review_analysis({"summary": "Есть проблема", "themes": [{"title": "Брак", "explanation": "Упомянут брак", "feedback_ids": ["f1"]}], "drafts": [{"feedback_id": "f1", "draft": "Спасибо за обратную связь. Проверим описанную проблему."}]}, facts)
    with pytest.raises(ValueError):
        validate_review_analysis({"summary": "", "themes": [], "drafts": [{"feedback_id": "other", "draft": "Возврат денег гарантирован"}]}, facts)
    answered = build_review_fact_set([{"feedback_id": "f2", "nm_id": 2, "rating": 4, "text": "Нормально", "answered": True}])
    with pytest.raises(ValueError):
        validate_review_analysis({"summary": "", "themes": [], "drafts": [{"feedback_id": "f2", "draft": "Спасибо за отзыв, мы всё проверим."}]}, answered)
