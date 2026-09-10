from app.wb_feedbacks import normalize_feedback, normalize_feedback_page


def test_normalize_feedback_keeps_business_facts_and_drops_buyer_identity():
    source = {"id": "fb-1", "text": "Текст", "pros": "Плюс", "cons": "Минус", "productValuation": 2, "createdDate": "2026-09-10T10:00:00Z", "userName": "Секретное имя", "matchingSize": "ok", "productDetails": {"nmId": 42, "productName": "Товар", "supplierArticle": "SKU"}, "answer": {"text": "Ответ", "createDate": "2026-09-10T11:00:00Z"}}
    row = normalize_feedback(source)
    assert row["feedback_id"] == "fb-1"
    assert row["nm_id"] == 42
    assert row["rating"] == 2
    assert row["answered"] is True
    assert "userName" not in row
    assert "matchingSize" not in row


def test_normalize_feedback_page_rejects_invalid_rows_and_reads_counter():
    rows, count = normalize_feedback_page({"data": {"countUnanswered": 7, "feedbacks": [{"id": "", "productDetails": {}}, {"id": "ok", "productValuation": 9, "productDetails": {"nmId": "15"}}]}})
    assert count == 7
    assert rows == [{"feedback_id": "ok", "nm_id": 15, "vendor_code": "", "product_name": "", "rating": 5, "text": "", "pros": "", "cons": "", "created_at": None, "answered": False, "answer_text": "", "answer_created_at": None}]
