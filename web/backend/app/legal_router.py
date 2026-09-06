from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import LegalConsent, User
from .security import get_current_user

router = APIRouter(prefix="/legal")

CURRENT_DOCUMENTS = {
    "privacy": "2026-09-06",
    "personal-data-consent": "2026-09-06",
    "terms": "2026-09-06",
    "cookies": "2026-09-06",
    "billing": "2026-09-06",
    "data-management": "2026-09-06",
}


class ConsentRequest(BaseModel):
    document_code: str = Field(min_length=2, max_length=80)
    document_version: str = Field(min_length=1, max_length=40)
    accepted: bool
    source: str = Field(default="web", min_length=1, max_length=80)


@router.get("/documents")
def documents():
    return {"documents": [{"code": code, "version": version} for code, version in CURRENT_DOCUMENTS.items()]}


@router.get("/consents")
def consents(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(LegalConsent).where(LegalConsent.user_id == current_user.id).order_by(LegalConsent.accepted_at.desc())
    ).all()
    return {
        "consents": [
            {
                "document_code": row.document_code,
                "document_version": row.document_version,
                "accepted": row.accepted,
                "source": row.source,
                "accepted_at": row.accepted_at,
            }
            for row in rows
        ]
    }


@router.post("/consents", status_code=201)
def record_consent(payload: ConsentRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    expected_version = CURRENT_DOCUMENTS.get(payload.document_code)
    if expected_version is None:
        raise HTTPException(status_code=400, detail="Unknown legal document")
    if payload.document_version != expected_version:
        raise HTTPException(status_code=409, detail="Document version is no longer current")
    if not payload.accepted:
        raise HTTPException(status_code=400, detail="Only explicit acceptance can be recorded as legal consent")

    existing = db.scalar(
        select(LegalConsent).where(
            LegalConsent.user_id == current_user.id,
            LegalConsent.document_code == payload.document_code,
            LegalConsent.document_version == payload.document_version,
        )
    )
    if existing:
        return {"status": "already_recorded", "document_code": existing.document_code, "document_version": existing.document_version}

    consent = LegalConsent(
        user_id=current_user.id,
        document_code=payload.document_code,
        document_version=payload.document_version,
        accepted=True,
        source=payload.source,
    )
    db.add(consent)
    db.commit()
    return {"status": "recorded", "document_code": consent.document_code, "document_version": consent.document_version}
