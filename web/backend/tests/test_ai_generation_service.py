from app.ai_generation_service import stable_hash


def test_generation_input_hash_is_stable_and_order_independent():
    assert stable_hash({"b": 2, "a": 1}) == stable_hash({"a": 1, "b": 2})
    assert stable_hash({"a": 1}) != stable_hash({"a": 2})
