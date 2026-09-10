import uuid
from fastapi.testclient import TestClient
from app.db import Base,SessionLocal,engine
from app.main import app
from app.models import VaultDocument

Base.metadata.create_all(bind=engine)
client=TestClient(app)

def _account():
    email=f'vault-{uuid.uuid4().hex}@example.com';response=client.post('/api/v1/auth/register',json={'email':email,'password':'StrongPass123!','workspace_name':'Vault Test'});headers={'Authorization':f"Bearer {response.json()['access_token']}"};store_id=client.get('/api/v1/stores',headers=headers).json()['stores'][0]['id'];return headers,store_id

def test_upload_authorization_is_scoped_hashed_and_quarantined():
    headers,store_id=_account();other_headers,other_store=_account();payload={'store_id':store_id,'display_name':'Чек заказа','content_type':'application/pdf','byte_size':128,'subject_type':'buyer','document_type':'fiscal_receipt','external_reference':'ORDER-SECRET-42'}
    authorized=client.post('/api/v1/document-vault/uploads/authorize',headers=headers,json=payload);assert authorized.status_code==201;document=authorized.json()['document'];assert 'ORDER-SECRET-42' not in str(document);assert authorized.json()['storage_path'].startswith('vault/')
    finalized=client.post(f"/api/v1/document-vault/documents/{document['id']}/finalize",headers=headers,json={'content_sha256':'a'*64,'byte_size':128});assert finalized.status_code==200;assert finalized.json()['document']['status']=='quarantined';assert finalized.json()['document']['download_available'] is False
    assert client.get(f'/api/v1/document-vault/documents?store_id={other_store}',headers=headers).status_code==404
    assert other_headers
    db=SessionLocal();row=db.get(VaultDocument,document['id']);assert row.external_reference_sha256 and row.external_reference_sha256!='ORDER-SECRET-42';db.close()

def test_executable_upload_is_denied_before_storage():
    headers,store_id=_account();response=client.post('/api/v1/document-vault/uploads/authorize',headers=headers,json={'store_id':store_id,'display_name':'installer','content_type':'application/x-msdownload','byte_size':128,'subject_type':'seller','document_type':'other'});assert response.status_code==422

def test_signed_scan_result_unlocks_download_and_wrong_signature_is_denied():
    import hashlib,hmac,json
    from app.config import get_settings
    headers,store_id=_account();payload={'store_id':store_id,'display_name':'Акт.pdf','content_type':'application/pdf','byte_size':128,'subject_type':'fulfillment','document_type':'act'}
    document=client.post('/api/v1/document-vault/uploads/authorize',headers=headers,json=payload).json()['document']
    client.post(f"/api/v1/document-vault/documents/{document['id']}/finalize",headers=headers,json={'content_sha256':'b'*64,'byte_size':128})
    body={'document_id':document['id'],'content_sha256':'b'*64,'verdict':'clean','scanner':'test-scanner'};raw=json.dumps(body,separators=(',',':')).encode();settings=get_settings();old=settings.document_scan_webhook_secret;settings.document_scan_webhook_secret='scan-test-secret'
    try:
        assert client.post('/api/v1/document-vault/scan-results',content=raw,headers={'Content-Type':'application/json','X-Document-Scan-Signature':'sha256=wrong'}).status_code==401
        signature='sha256='+hmac.new(b'scan-test-secret',raw,hashlib.sha256).hexdigest();result=client.post('/api/v1/document-vault/scan-results',content=raw,headers={'Content-Type':'application/json','X-Document-Scan-Signature':signature});assert result.status_code==200;assert result.json()['document']['download_available'] is True
        authorized=client.get(f"/api/v1/document-vault/documents/{document['id']}/download-authorize",headers=headers);assert authorized.status_code==200;assert authorized.json()['content_sha256']=='b'*64
    finally:settings.document_scan_webhook_secret=old
