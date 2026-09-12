"""Deterministic, privacy-minimised incident intake for Support Agent P1A."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from sqlalchemy import select

from .agent_network import sanitize_learning_note


_FORCED = (
    ("security", re.compile(r"(?i)\b(взлом|утечк|доступ|токен|парол|аккаунт.*чуж|phish|hack)")),
    ("legal_or_billing", re.compile(r"(?i)\b(возврат денег|refund|чарджбек|персональн.*данн|юрист|налог|договор|суд)")),
    ("external_write", re.compile(r"(?i)\b(само.*(опублик|измени|списал)|неожиданн.*(публик|измен|списан)|внешн.*измен)")),
    ("financial_loss", re.compile(r"(?i)\b(убыт|потер[яи].*ден|списал[ои].*ден|деньги пропал|маржа.*минус)")),
)
_INCIDENT = re.compile(r"(?i)\b(ошибк|не работает|синхрон|публикац|расч[её]т|неверн|сбой|завис)")


def classify_support_message(value: str) -> dict:
    text = value or ""
    for reason, pattern in _FORCED:
        if pattern.search(text):
            return {"category": "incident" if reason not in {"security", "legal_or_billing"} else reason,
                    "severity": "critical" if reason in {"security", "financial_loss", "external_write"} else "high",
                    "forced_escalation_reason": reason, "human_review_required": True}
    if _INCIDENT.search(text):
        return {"category": "incident", "severity": "medium", "forced_escalation_reason": "", "human_review_required": True}
    return {"category": "product_help", "severity": "low", "forced_escalation_reason": "", "human_review_required": False}


def sanitize_support_description(value: str) -> str:
    # Uses the policy redactor shared with the agent control plane, then strips
    # common card/payment sequences that must never enter a ticket or prompt.
    text = sanitize_learning_note(value)
    return re.sub(r"(?<!\d)(?:\d[ -]?){12,19}(?!\d)", "[REDACTED_PAYMENT]", text)


def request_hash(*, category: str, description: str, correlation_id: str) -> str:
    payload = {"category": category, "description": description, "correlation_id": correlation_id}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def evidence_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

def document_checksum(*, title: str, body: str, source_url: str, version: int) -> str:
    data={'title': title.strip(), 'body': body.strip(), 'source_url': source_url.strip(), 'version': version}
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def _terms(value: str) -> set[str]:
    terms=set()
    for token in re.findall(r"[\wа-яё]{3,}", (value or '').lower()):
        terms.add(token)
        # Conservative Russian noun normalization for exact deterministic
        # retrieval: прибыль/прибыли share "прибыл" without a fuzzy model.
        if len(token)>=6 and re.fullmatch(r"[а-яё]+",token) and token[-1] in {'и','ь'}:
            terms.add(token[:-1])
    return terms

def grounded_product_help(db, question: str) -> dict:
    from .models import KnowledgeDocument
    now=datetime.now(timezone.utc); query=_terms(question)
    rows=db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.status=='approved', KnowledgeDocument.effective_at<=now, (KnowledgeDocument.expires_at.is_(None) | (KnowledgeDocument.expires_at>now)))).all()
    ranked=sorted(((len(query & _terms(f'{row.title} {row.body}')),row) for row in rows),key=lambda item:(-item[0],item[1].slug,item[1].version))[:3]
    rows=[row for score,row in ranked if score]
    if not rows:return {'answer':'Пока нет одобренного материала, на который можно опереться. Вопрос не передаётся модели без источника; при риске или сбое зарегистрируйте инцидент.','citations':[],'grounded':False}
    return {'answer':'\n\n'.join(f'«{row.title}»: {" ".join(row.body.split())[:700]}' for row in rows),'citations':[{'id':row.id,'title':row.title,'version':row.version,'source_url':row.source_url or None,'reviewed_at':row.reviewed_at,'expires_at':row.expires_at} for row in rows],'grounded':True}
