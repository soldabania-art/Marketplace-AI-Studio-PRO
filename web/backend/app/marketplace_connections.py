from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from .config import get_settings
from .db import get_db
from .fbo_service import fetch_wb_slots
from .models import MarketplaceConnection, User
from .security import get_current_user

router = APIRouter()

class WbTokenBody(BaseModel):
    token: str = Field(min_length=20, max_length=4096)

def cipher() -> Fernet:
    key = get_settings().marketplace_token_key
    if not key:
        raise HTTPException(503, 'Шифрование токенов маркетплейса не настроено на сервере.')
    try:
        return Fernet(key.encode())
    except Exception:
        raise HTTPException(503, 'Ключ шифрования маркетплейса настроен неверно.')

def decrypt_connection(row: MarketplaceConnection) -> str:
    try:
        return cipher().decrypt(row.encrypted_token.encode()).decode()
    except InvalidToken:
        raise HTTPException(503, 'Не удалось расшифровать токен магазина.')

@router.post('/integrations/wildberries')
async def connect_wb(body: WbTokenBody, user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    token = body.token.strip()
    try:
        await fetch_wb_slots(token)
    except Exception:
        raise HTTPException(400, 'WB не принял токен. Проверьте токен и его доступ.')
    row = db.query(MarketplaceConnection).filter(MarketplaceConnection.user_id==user.id, MarketplaceConnection.marketplace=='wildberries').first()
    encrypted = cipher().encrypt(token.encode()).decode()
    if not row:
        row = MarketplaceConnection(user_id=user.id, marketplace='wildberries', encrypted_token=encrypted)
        db.add(row)
    else:
        row.encrypted_token=encrypted; row.enabled=True
    row.token_hint = ('…'+token[-6:]) if len(token)>=6 else 'configured'
    db.commit()
    return {'ok':True,'marketplace':'wildberries','token_hint':row.token_hint}

@router.get('/integrations/wildberries')
def wb_status(user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    row=db.query(MarketplaceConnection).filter(MarketplaceConnection.user_id==user.id,MarketplaceConnection.marketplace=='wildberries',MarketplaceConnection.enabled==True).first()
    return {'connected':bool(row),'token_hint':row.token_hint if row else ''}
