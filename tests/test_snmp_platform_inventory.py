from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.registry import VendorRegistry
from app.inventory.snmp_platform import SNMPPlatformInventory


class FakeProvider:
    vendor_tags = ("zte", "zteolt-2.1")
    default_cli_fallback_access = "telnet"

    async def get_onu(self, query):  # pragma: no cover
        raise NotImplementedError

    async def get_onus(self, olt_ip, board_id, pon_id):  # pragma: no cover
        raise NotImplementedError

    async def get_onus_new(self, olt_ip, board_id, pon_id):  # pragma: no cover
        raise NotImplementedError

    async def get_onu_cli(self, query, access):  # pragma: no cover
        raise NotImplementedError


class FakeSNMPClient:
    def __init__(self, value: object) -> None:
        self.value = value

    async def get(self, host: str, oid: str) -> object:
        return self.value


class SNMPPlatformInventoryTest(unittest.IsolatedAsyncioTestCase):
    async def test_matches_by_vendor_when_full_name_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "platforms.csv"
            csv_path.write_text(
                ",full_name,name,vendor,snmp_sysobjectid\n"
                "0,ZTE C300,C300,ZTE,1.3.6.1.4.1.3902.1082.1001.320.2.1\n",
                encoding="utf-8",
            )
            inventory = SNMPPlatformInventory(
                registry=VendorRegistry([FakeProvider()]),
                snmp_client=FakeSNMPClient("1.3.6.1.4.1.3902.1082.1001.320.2.1"),
                csv_path=csv_path,
            )
            result = await inventory.lookup_vendor("10.5.0.21")
            self.assertEqual(result.source, "snmp")
            self.assertEqual(result.matched_vendor, "zte")
            self.assertEqual(result.lookup_value, "zte")

    async def test_normalizes_enterprises_notation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "platforms.csv"
            csv_path.write_text(
                ",full_name,name,vendor,snmp_sysobjectid\n"
                "0,ZTE C300,C300,ZTE,1.3.6.1.4.1.3902.1082.1001.320.2.1\n",
                encoding="utf-8",
            )
            inventory = SNMPPlatformInventory(
                registry=VendorRegistry([FakeProvider()]),
                snmp_client=FakeSNMPClient("SNMPv2-SMI::enterprises.3902.1082.1001.320.2.1"),
                csv_path=csv_path,
            )
            result = await inventory.lookup_vendor("10.5.0.21")
            self.assertEqual(result.matched_vendor, "zte")
            self.assertEqual(result.oid, "1.3.6.1.4.1.3902.1082.1001.320.2.1")

    async def test_returns_miss_when_oid_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "platforms.csv"
            csv_path.write_text(
                ",full_name,name,vendor,snmp_sysobjectid\n"
                "0,ZTE C300,C300,ZTE,1.3.6.1.4.1.3902.1082.1001.320.2.1\n",
                encoding="utf-8",
            )
            inventory = SNMPPlatformInventory(
                registry=VendorRegistry([FakeProvider()]),
                snmp_client=FakeSNMPClient("1.3.6.1.4.1.9.1.2494"),
                csv_path=csv_path,
            )
            result = await inventory.lookup_vendor("10.5.0.21")
            self.assertIsNone(result.matched_vendor)
            self.assertEqual(result.note, "sysobjectid not found in platforms.csv")


if __name__ == "__main__":
    unittest.main()
