"""Canonical contract for partner adapters. A partner can add an adapter without changing marketplace modules."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

CAPABILITIES=frozenset({'catalog','inventory','reservations','inbound_shipments','outbound_orders','returns','tariffs','webhooks','documents'})

@dataclass(frozen=True)
class PartnerContext:
    partner_code: str
    connection_id: str
    store_id: str
    secret_reference: str

class FulfillmentAdapter(Protocol):
    code: str
    async def health(self, context: PartnerContext) -> dict: ...
    async def inventory(self, context: PartnerContext, *, cursor: str | None = None) -> dict: ...
    async def inbound_shipments(self, context: PartnerContext, *, cursor: str | None = None) -> dict: ...
    async def returns(self, context: PartnerContext, *, cursor: str | None = None) -> dict: ...

def assert_capabilities(values: list[str]) -> list[str]:
    unique=sorted(set(values))
    unknown=set(unique)-CAPABILITIES
    if unknown:raise ValueError(f'Unsupported fulfillment capabilities: {sorted(unknown)}')
    return unique
