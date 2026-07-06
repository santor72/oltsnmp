from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from app.core.registry import VendorRegistry
from app.inventory.provider import InventoryLookupResult

logger = logging.getLogger(__name__)


class ZabbixInventory:
    source = "zabbix"

    def __init__(
        self,
        registry: VendorRegistry,
        zabbix_url: str,
        zabbix_token: str,
        timeout: float = 5.0,
        debug: bool = False,
        zabbix_api_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.registry = registry
        self.zabbix_url = zabbix_url
        self.zabbix_token = zabbix_token
        self.timeout = timeout
        self.debug = debug
        self.zabbix_api_factory = zabbix_api_factory

    async def lookup_vendor(self, olt_ip: str) -> InventoryLookupResult:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._lookup_vendor_sync, olt_ip),
                timeout=self.timeout,
            )
        except TimeoutError:
            result = InventoryLookupResult(
                matched_vendor=None,
                source=self.source,
                host_count=None,
                vendor_tag=None,
                lookup_value=None,
                oid=None,
                note=f"zabbix lookup timed out after {self.timeout:g} seconds",
            )
            self._debug("zabbix lookup timed out", olt_ip=olt_ip, timeout_seconds=self.timeout)
            return result

    def enabled(self) -> bool:
        return bool(self.zabbix_url and self.zabbix_token)

    def _api_factory(self) -> Callable[[str], Any]:
        if self.zabbix_api_factory is not None:
            return self.zabbix_api_factory
        try:
            from zabbix_utils import ZabbixAPI  # type: ignore
        except ImportError:
            def _missing(_: str) -> Any:
                raise RuntimeError("zabbix_utils is not installed")
            return _missing
        return ZabbixAPI

    def _lookup_vendor_sync(self, olt_ip: str) -> InventoryLookupResult:
        zapi = None
        try:
            self._debug("starting zabbix lookup", olt_ip=olt_ip, zabbix_url=self.zabbix_url)
            zapi = self._api_factory()(self.zabbix_url)
            zapi.login(token=self.zabbix_token)
            self._debug("zabbix login ok", olt_ip=olt_ip)
            interfaces = zapi.hostinterface.get(output=["hostid"], filter={"ip": olt_ip})
            self._debug("zabbix hostinterface response", olt_ip=olt_ip, interfaces=interfaces)
            host_ids = {item["hostid"] for item in interfaces if item.get("hostid")}
            if len(host_ids) != 1:
                return InventoryLookupResult(
                    matched_vendor=None,
                    source=self.source,
                    host_count=len(host_ids),
                    vendor_tag=None,
                    lookup_value=None,
                    oid=None,
                    note=f"zabbix host lookup returned {len(host_ids)} hosts",
                )

            hosts = zapi.host.get(
                hostids=list(host_ids)[0],
                output=["hostid", "host", "name"],
                selectTags="extend",
                selectInheritedTags="extend",
            )
            self._debug("zabbix host response", olt_ip=olt_ip, host_ids=list(host_ids), hosts=hosts)
            if not hosts:
                return InventoryLookupResult(
                    matched_vendor=None,
                    source=self.source,
                    host_count=1,
                    vendor_tag=None,
                    lookup_value=None,
                    oid=None,
                    note="zabbix host.get returned empty result",
                )

            tags = list(hosts[0].get("inheritedTags", [])) + list(hosts[0].get("tags", []))
            self._debug("zabbix combined tags", olt_ip=olt_ip, tags=tags)
            for tag in tags:
                if str(tag.get("tag", "")).strip().lower() != "vendor":
                    continue
                value = str(tag.get("value", "")).strip()
                if not value:
                    continue
                try:
                    matched_vendor = self.registry.get(value).vendor
                    self._debug(
                        "zabbix vendor tag matched provider",
                        olt_ip=olt_ip,
                        vendor_tag=value,
                        matched_vendor=matched_vendor,
                    )
                    return InventoryLookupResult(
                        matched_vendor=matched_vendor,
                        source=self.source,
                        host_count=len(host_ids),
                        vendor_tag=value,
                        lookup_value=value,
                        oid=None,
                        note="vendor tag found in zabbix host tags",
                    )
                except ValueError:
                    self._debug("zabbix vendor tag is unsupported", olt_ip=olt_ip, vendor_tag=value)
                    continue
            return InventoryLookupResult(
                matched_vendor=None,
                source=self.source,
                host_count=len(host_ids),
                vendor_tag=None,
                lookup_value=None,
                oid=None,
                note="zabbix host has no supported vendor tag",
            )
        except Exception as exc:
            self._debug("zabbix lookup raised exception", olt_ip=olt_ip, error=repr(exc))
            return InventoryLookupResult(
                matched_vendor=None,
                source=self.source,
                host_count=None,
                vendor_tag=None,
                lookup_value=None,
                oid=None,
                note=str(exc),
            )
        finally:
            if zapi is not None:
                try:
                    zapi.logout()
                    self._debug("zabbix logout ok", olt_ip=olt_ip)
                except Exception:
                    pass

    def _debug(self, message: str, **data: Any) -> None:
        if not self.debug:
            return
        logger.warning("zabbix_inventory: %s | %s", message, data)
