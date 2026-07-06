from __future__ import annotations

import asyncio
import csv
import logging
from pathlib import Path

from app.core.registry import VendorRegistry
from app.inventory.provider import InventoryLookupResult
from app.snmp_client import SNMPClient

logger = logging.getLogger(__name__)

SYS_OBJECT_ID_OID = ".1.3.6.1.2.1.1.2.0"
PLATFORMS_CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "platforms.csv"


class SNMPPlatformInventory:
    source = "snmp"

    def __init__(
        self,
        registry: VendorRegistry,
        snmp_client: SNMPClient,
        csv_path: Path = PLATFORMS_CSV_PATH,
        debug: bool = False,
    ) -> None:
        self.registry = registry
        self.snmp_client = snmp_client
        self.csv_path = csv_path
        self.debug = debug
        self._platforms = self._load_platforms(csv_path)

    async def lookup_vendor(self, olt_ip: str) -> InventoryLookupResult:
        try:
            raw_value = await self.snmp_client.get(olt_ip, SYS_OBJECT_ID_OID)
            sysobjectid = self._normalize_oid(raw_value)
            self._debug("snmp sysobjectid received", olt_ip=olt_ip, oid=SYS_OBJECT_ID_OID, sysobjectid=sysobjectid)
        except Exception as exc:
            self._debug("snmp sysobjectid lookup failed", olt_ip=olt_ip, oid=SYS_OBJECT_ID_OID, error=repr(exc))
            return InventoryLookupResult(
                matched_vendor=None,
                source=self.source,
                oid=SYS_OBJECT_ID_OID,
                note=str(exc),
            )

        for platform in self._platforms:
            if platform["snmp_sysobjectid"] != sysobjectid:
                continue

            full_name = platform["full_name"]
            vendor = platform["vendor"]
            try:
                matched_vendor = self.registry.get(full_name).vendor
                self._debug(
                    "snmp platform matched by full_name",
                    olt_ip=olt_ip,
                    sysobjectid=sysobjectid,
                    full_name=full_name,
                    matched_vendor=matched_vendor,
                )
                return InventoryLookupResult(
                    matched_vendor=matched_vendor,
                    source=self.source,
                    lookup_value=full_name,
                    oid=sysobjectid,
                    note="matched by platforms.csv full_name",
                )
            except ValueError:
                pass

            try:
                matched_vendor = self.registry.get(vendor).vendor
                self._debug(
                    "snmp platform matched by vendor",
                    olt_ip=olt_ip,
                    sysobjectid=sysobjectid,
                    vendor=vendor,
                    matched_vendor=matched_vendor,
                )
                return InventoryLookupResult(
                    matched_vendor=matched_vendor,
                    source=self.source,
                    lookup_value=vendor,
                    oid=sysobjectid,
                    note="matched by platforms.csv vendor",
                )
            except ValueError:
                self._debug(
                    "snmp platform found but vendor unsupported",
                    olt_ip=olt_ip,
                    sysobjectid=sysobjectid,
                    full_name=full_name,
                    vendor=vendor,
                )
                return InventoryLookupResult(
                    matched_vendor=None,
                    source=self.source,
                    lookup_value=vendor,
                    oid=sysobjectid,
                    note="platform found in csv but vendor is unsupported",
                )

        self._debug("snmp sysobjectid not found in csv", olt_ip=olt_ip, sysobjectid=sysobjectid)
        return InventoryLookupResult(
            matched_vendor=None,
            source=self.source,
            oid=sysobjectid,
            note="sysobjectid not found in platforms.csv",
        )

    @staticmethod
    def _load_platforms(csv_path: Path) -> list[dict[str, str]]:
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            items: list[dict[str, str]] = []
            for row in reader:
                items.append(
                    {
                        "full_name": str(row.get("full_name", "")).strip().lower(),
                        "vendor": str(row.get("vendor", "")).strip().lower(),
                        "snmp_sysobjectid": str(row.get("snmp_sysobjectid", "")).strip().lstrip("."),
                    }
                )
            return items

    @staticmethod
    def _normalize_oid(value: object) -> str:
        text = str(value).strip()
        if text.startswith("SNMPv2-SMI::enterprises."):
            suffix = text.removeprefix("SNMPv2-SMI::enterprises.")
            return f"1.3.6.1.4.1.{suffix}".strip(".")
        return text.strip(".")

    def _debug(self, message: str, **data: object) -> None:
        if not self.debug:
            return
        logger.warning("snmp_platform_inventory: %s | %s", message, data)
