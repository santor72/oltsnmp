from __future__ import annotations

from app.core.registry import VendorRegistry
from app.models import ONUCLIInfo, ONUCustomerInfo, ONUDebugInfo, ONUInfoPerBoard, ONUQuery, ONUPortQuery
from app.vendors.zte.adapter import is_timeout_error


class OnuService:
    def __init__(self, registry: VendorRegistry) -> None:
        self.registry = registry

    async def get_onu(self, query: ONUQuery, vendor: str | None = None) -> ONUCustomerInfo:
        provider = self.registry.get(vendor).provider
        try:
            return await provider.get_onu(query)
        except RuntimeError as exc:
            if not is_timeout_error(exc):
                raise
            fallback = await provider.get_onu_cli(query, access=provider.default_cli_fallback_access)
            return ONUCustomerInfo.model_validate(fallback.model_dump())

    async def get_onup(self, query: ONUPortQuery, vendor: str | None = None) -> ONUCustomerInfo:
        provider = self.registry.get(vendor).provider
        try:
            return await provider.get_onup(query)
        except RuntimeError as exc:
            if not is_timeout_error(exc):
                raise
            fallback = await provider.get_onup_cli(query, access=provider.default_cli_fallback_access)
            return ONUCustomerInfo.model_validate(fallback.model_dump())

    async def get_onu_debug(self, query: ONUPortQuery, vendor: str | None = None) -> ONUDebugInfo:
        provider = self.registry.get(vendor).provider
        return await provider.get_onu_debug(query)

    async def get_onus(self, olt_ip: str, port: str, vendor: str | None = None) -> list[ONUInfoPerBoard]:
        provider = self.registry.get(vendor).provider
        return await provider.get_onus(olt_ip, port)

    async def get_onus_new(self, olt_ip: str, port: str, vendor: str | None = None) -> list[ONUInfoPerBoard]:
        provider = self.registry.get(vendor).provider
        return await provider.get_onus_new(olt_ip, port)

    async def get_onu_cli(self, query: ONUQuery, access: str, vendor: str | None = None) -> ONUCLIInfo:
        provider = self.registry.get(vendor).provider
        return await provider.get_onu_cli(query, access)

    async def get_onup_cli(self, query: ONUPortQuery, access: str, vendor: str | None = None) -> ONUCLIInfo:
        provider = self.registry.get(vendor).provider
        return await provider.get_onup_cli(query, access)
