from dataclasses import dataclass, field
from typing import Literal


SchemaState = Literal["valid", "documented_empty", "partial", "unknown"]


@dataclass(frozen=True)
class MarketplacePageResult:
    items: list[dict]
    raw_count: int
    accepted_count: int
    rejected_count: int
    cursor: int | None
    schema_state: SchemaState
    evidence: list[dict] = field(default_factory=list)

    @property
    def safe_to_apply(self) -> bool:
        return self.schema_state in {"valid", "documented_empty"} and self.rejected_count == 0

