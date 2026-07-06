from __future__ import annotations

from app.inventory.provider import InventoryLookupResult, InventoryProvider


class InventoryChain:
    source = "inventory-chain"

    def __init__(self, providers: list[InventoryProvider]) -> None:
        self.providers = providers

    async def lookup_vendor(self, olt_ip: str) -> InventoryLookupResult:
        last_result: InventoryLookupResult | None = None
        for provider in self.providers:
            result = await provider.lookup_vendor(olt_ip)
            if result.matched_vendor:
                return result
            last_result = result
        return last_result or InventoryLookupResult(
            matched_vendor=None,
            source=self.source,
            note="inventory chain has no providers",
        )
