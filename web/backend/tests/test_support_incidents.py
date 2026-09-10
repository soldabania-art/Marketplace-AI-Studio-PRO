import uuid

from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def _account():
    email = f"support-{uuid.uuid4().hex}@example.com"
    response = client.post('/api/v1/auth/register', json={'email': email, 'password': 'StrongPass123!', 'workspace_name': 'Support Test'})
    assert response.status_code == 201
    headers = {'Authorization': f"Bearer {response.json()['access_token']}"}
    store_id = client.get('/api/v1/stores', headers=headers).json()['stores'][0]['id']
    return headers, store_id


def test_forced_security_incident_is_redacted_idempotent_and_store_scoped():
    headers, store_id = _account()
    second_headers, second_store = _account()
    payload = {'store_id': store_id, 'description': 'Кажется, был взлом. Bearer abcdefghijklmnopqrstuvwxyz user@example.com', 'correlation_id': 'req-42'}
    created = client.post('/api/v1/support/incidents', headers=headers, json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body['category'] == 'security'
    assert body['severity'] == 'critical'
    assert body['forced_escalation_reason'] == 'security'
    assert 'Bearer' not in body['description'] and 'user@example.com' not in body['description']
    assert body['evidence']['sha256']
    assert body['emergency_stop']['available'] is True

    repeated = client.post('/api/v1/support/incidents', headers=headers, json=payload)
    assert repeated.status_code == 201 and repeated.json()['id'] == body['id']

    hidden = client.get(f'/api/v1/support/incidents?store_id={second_store}', headers=headers)
    assert hidden.status_code == 404
    own = client.get(f'/api/v1/support/incidents?store_id={store_id}', headers=headers)
    assert own.status_code == 200 and own.json()['items'][0]['id'] == body['id']
    assert second_headers


def test_product_help_does_not_create_fake_support_ticket():
    headers, store_id = _account()
    response = client.post('/api/v1/support/incidents', headers=headers, json={
        'store_id': store_id, 'description': 'Где открыть отчёт по прибыли?'
    })
    assert response.status_code == 422
