"""Typed, deny-by-default agent network for TROVENDI.

The registry is deliberately code-reviewed and immutable at runtime. Models may
propose work, but only declared capabilities can reach deterministic services.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy

from fastapi import HTTPException


REGISTRY_VERSION = 1

_AGENTS = {
    "director": {
        "name": "Главный мозг · AI Director",
        "purpose": "Планирует работу, выбирает разрешённую способность и собирает доказательства.",
        "parent": None,
        "capabilities": ["plan.read", "recommend.read", "delegate.read_only"],
        "risk_ceiling": "medium",
        "external_writes": False,
        "learning_mode": "reviewed_candidates_only",
    },
    "finance": {
        "name": "Finance Agent",
        "purpose": "Объясняет подтверждённые расчёты Profit Center и считает сценарии через типизированный сервис.",
        "parent": "director",
        "capabilities": ["profit.read", "profit.explain", "scenario.calculate"],
        "risk_ceiling": "medium",
        "external_writes": False,
        "learning_mode": "reviewed_candidates_only",
    },
    "content": {
        "name": "Content Agent",
        "purpose": "Создаёт черновики только из подтверждённого набора фактов.",
        "parent": "director",
        "capabilities": ["facts.read", "copy.draft", "visual_brief.draft"],
        "risk_ceiling": "medium",
        "external_writes": False,
        "learning_mode": "reviewed_candidates_only",
    },
    "supply": {
        "name": "Supply Agent",
        "purpose": "Считает риск дефицита и готовит черновик плана поставки.",
        "parent": "director",
        "capabilities": ["stock.read", "forecast.calculate", "supply_plan.draft"],
        "risk_ceiling": "medium",
        "external_writes": False,
        "learning_mode": "reviewed_candidates_only",
    },
    "data_health": {
        "name": "Data Health Agent",
        "purpose": "Проверяет свежесть источников и ставит в очередь только разрешённые read-sync задания.",
        "parent": "director",
        "capabilities": ["source_health.read", "read_sync.enqueue"],
        "risk_ceiling": "low",
        "external_writes": False,
        "learning_mode": "reviewed_candidates_only",
    },
    "support": {
        "name": "Support Agent",
        "purpose": "Отвечает по проверенной базе и создаёт внутренние инциденты без прав на магазин.",
        "parent": "director",
        "capabilities": ["knowledge.read", "incident.create", "emergency_stop.link"],
        "risk_ceiling": "medium",
        "external_writes": False,
        "learning_mode": "reviewed_candidates_only",
    },
    "security": {
        "name": "Security Sentinel",
        "purpose": "Независимо проверяет политику, блокирует опасные запросы и проверяет аудит.",
        "parent": None,
        "capabilities": ["policy.evaluate", "execution.deny", "audit.verify"],
        "risk_ceiling": "critical",
        "external_writes": False,
        "learning_mode": "policy_changes_require_code_review",
        "deny_only": True,
    },
}

_GOAL_ROUTES = {
    "profit_review": {"agent_key": "finance", "capability": "profit.explain", "label": "Проверить прибыль"},
    "content_improvement": {"agent_key": "content", "capability": "copy.draft", "label": "Улучшить карточку"},
    "stock_risk": {"agent_key": "supply", "capability": "supply_plan.draft", "label": "Проверить риск дефицита"},
    "source_health": {"agent_key": "data_health", "capability": "source_health.read", "label": "Проверить источники"},
    "support": {"agent_key": "support", "capability": "knowledge.read", "label": "Разобрать вопрос"},
}

_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
_LONG_SECRET = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_-]{32,}(?![A-Za-z0-9])")


def registry_checksum() -> str:
    body = json.dumps({"version": REGISTRY_VERSION, "agents": _AGENTS}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def public_network() -> dict:
    agents = deepcopy(_AGENTS)
    return {
        "version": REGISTRY_VERSION,
        "sha256": registry_checksum(),
        "master_agent": "director",
        "security_veto": "security",
        "agents": [{"key": key, **value} for key, value in agents.items()],
        "goal_routes": [{"goal_type": key, **value} for key, value in _GOAL_ROUTES.items()],
        "rules": {
            "deny_by_default": True,
            "external_writes_enabled": False,
            "arbitrary_sql_allowed": False,
            "runtime_self_modification_allowed": False,
            "raw_customer_data_training_allowed": False,
        },
    }


def route_goal(goal_type: str) -> dict:
    route = _GOAL_ROUTES.get(goal_type)
    if route is None:
        raise HTTPException(422, "Этот тип задачи не поддерживается безопасным маршрутизатором.")
    require_capability(route["agent_key"], route["capability"])
    return deepcopy(route)


def require_capability(agent_key: str, capability: str, *, external_write: bool = False, security_denied: bool = False) -> dict:
    agent = _AGENTS.get(agent_key)
    if agent is None:
        raise HTTPException(404, "Агент не зарегистрирован.")
    if capability not in agent["capabilities"]:
        raise HTTPException(403, "Эта способность не разрешена политикой агента.")
    if security_denied:
        raise HTTPException(423, "Security Sentinel заблокировал выполнение.")
    if external_write and not agent["external_writes"]:
        raise HTTPException(403, "Внешние изменения запрещены текущей версией политики.")
    if agent.get("deny_only") and capability != "execution.deny":
        return deepcopy(agent)
    return deepcopy(agent)


def sanitize_learning_note(value: str) -> str:
    note = " ".join((value or "").strip().split())[:1000]
    note = _BEARER.sub("[REDACTED_TOKEN]", note)
    note = _EMAIL.sub("[REDACTED_EMAIL]", note)
    note = _LONG_SECRET.sub("[REDACTED_SECRET]", note)
    return note


def learning_payload_hash(*, agent_key: str, signal: str, source_type: str, source_id: str, note: str) -> str:
    payload = {"agent_key": agent_key, "signal": signal, "source_type": source_type, "source_id": source_id, "note": note}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
