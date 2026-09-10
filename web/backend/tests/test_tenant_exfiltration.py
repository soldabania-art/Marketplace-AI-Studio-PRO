import uuid

from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def _account():
    email = f"isolation-{uuid.uuid4().hex}@example.com"
    response = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "StrongPass123!",
        "workspace_name": "Isolation Test",
    })
    assert response.status_code == 201
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    store_id = client.get("/api/v1/stores", headers=headers).json()["stores"][0]["id"]
    return headers, store_id


def test_store_identifier_cannot_be_used_to_download_another_tenants_data():
    owner_headers, _ = _account()
    _, foreign_store = _account()

    probes = [
        f"/api/v1/seller-data/products?store_id={foreign_store}",
        f"/api/v1/profit-center?store_id={foreign_store}",
        f"/api/v1/beginner/projects?store_id={foreign_store}",
        f"/api/v1/agents/work-orders?store_id={foreign_store}",
        f"/api/v1/agents/learning?store_id={foreign_store}",
    ]
    for path in probes:
        response = client.get(path, headers=owner_headers)
        assert response.status_code == 404, path
