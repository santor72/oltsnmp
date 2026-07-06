from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from app.core.registry import VendorRegistry
from app.inventory.provider import InventoryProvider


@dataclass(frozen=True)
class VendorResolution:
    requested_vendor: str | None
    resolved_vendor: str
    source: str
    zabbix_enabled: bool
    zabbix_host_count: int | None = None
    zabbix_vendor_tag: str | None = None
    inventory_lookup_value: str | None = None
    inventory_oid: str | None = None
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class VendorResolver:
    def __init__(
        self,
        registry: VendorRegistry,
        default_vendor: str,
        inventory: InventoryProvider | None = None,
    ) -> None:
        self.registry = registry
        self.default_vendor = default_vendor
        self.inventory = inventory

    async def resolve(self, olt_ip: str, explicit_vendor: str | None = None) -> str:
        return (await self.resolve_details(olt_ip, explicit_vendor)).resolved_vendor

    async def resolve_details(self, olt_ip: str, explicit_vendor: str | None = None) -> VendorResolution:
        if explicit_vendor:
            resolved_vendor = self.registry.get(explicit_vendor).vendor
            return VendorResolution(
                requested_vendor=explicit_vendor,
                resolved_vendor=resolved_vendor,
                source="explicit",
                zabbix_enabled=self.inventory is not None,
                note="vendor provided in request",
            )

        if self.inventory is not None:
            lookup = await self.inventory.lookup_vendor(olt_ip)
            if lookup.matched_vendor:
                return VendorResolution(
                    requested_vendor=None,
                    resolved_vendor=lookup.matched_vendor,
                    source=lookup.source,
                    zabbix_enabled=True,
                    zabbix_host_count=lookup.host_count,
                    zabbix_vendor_tag=lookup.vendor_tag,
                    inventory_lookup_value=lookup.lookup_value,
                    inventory_oid=lookup.oid,
                    note=lookup.note,
                )

            default_vendor = self.registry.get(self.default_vendor).vendor
            return VendorResolution(
                requested_vendor=None,
                resolved_vendor=default_vendor,
                source="default",
                zabbix_enabled=True,
                zabbix_host_count=lookup.host_count,
                zabbix_vendor_tag=lookup.vendor_tag,
                inventory_lookup_value=lookup.lookup_value,
                inventory_oid=lookup.oid,
                note=lookup.note,
            )

        default_vendor = self.registry.get(self.default_vendor).vendor
        return VendorResolution(
            requested_vendor=None,
            resolved_vendor=default_vendor,
            source="default",
            zabbix_enabled=False,
            note="fallback to default vendor",
        )
