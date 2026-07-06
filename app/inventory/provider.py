from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InventoryLookupResult:
    matched_vendor: str | None
    source: str
    host_count: int | None = None
    vendor_tag: str | None = None
    lookup_value: str | None = None
    oid: str | None = None
    note: str = ""


class InventoryProvider(Protocol):
    async def lookup_vendor(self, olt_ip: str) -> InventoryLookupResult: ...
