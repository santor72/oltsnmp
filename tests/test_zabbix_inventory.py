from __future__ import annotations

import time
import unittest

from app.core.registry import VendorRegistry
from app.inventory.zabbix import ZabbixInventory


class FakeProvider:
    vendor_tags = ("zte", "zte-olt", "zteolt-2.1")
    default_cli_fallback_access = "telnet"

    async def get_onu(self, query):  # pragma: no cover
        raise NotImplementedError

    async def get_onus(self, olt_ip, board_id, pon_id):  # pragma: no cover
        raise NotImplementedError

    async def get_onus_new(self, olt_ip, board_id, pon_id):  # pragma: no cover
        raise NotImplementedError

    async def get_onu_cli(self, query, access):  # pragma: no cover
        raise NotImplementedError


class FakeZabbixAPI:
    def __init__(self, url: str) -> None:
        self.url = url
        self.hostinterface = self
        self.host = self

    def login(self, token: str) -> None:
        self.token = token

    def logout(self) -> None:
        return None

    def get(self, *args, **kwargs):
        if kwargs.get("filter") == {"ip": "10.5.0.21"}:
            return [{"hostid": "10839"}]
        if kwargs.get("hostids") == "10839":
            return [{
                "hostid": "10839",
                "host": "OLT_Petrovskoe",
                "name": "OLT_Petrovskoe",
                "tags": [{"tag": "vendor", "value": "zte"}, {"tag": "vendor", "value": "zte-olt"}],
                "inheritedTags": [{"tag": "vendor", "value": "zteolt-2.1"}],
            }]
        return []


class SlowZabbixAPI(FakeZabbixAPI):
    def get(self, *args, **kwargs):
        time.sleep(0.05)
        return super().get(*args, **kwargs)


class ZabbixInventoryTest(unittest.IsolatedAsyncioTestCase):
    async def test_lookup_vendor_tag(self) -> None:
        inventory = ZabbixInventory(
            registry=VendorRegistry([FakeProvider()]),
            zabbix_url="http://zabbix.local",
            zabbix_token="token",
            zabbix_api_factory=FakeZabbixAPI,
        )
        result = await inventory.lookup_vendor("10.5.0.21")
        self.assertEqual(result.source, "zabbix")
        self.assertEqual(result.matched_vendor, "zte")
        self.assertEqual(result.vendor_tag, "zte-olt")

    async def test_lookup_miss(self) -> None:
        inventory = ZabbixInventory(
            registry=VendorRegistry([FakeProvider()]),
            zabbix_url="http://zabbix.local",
            zabbix_token="token",
            zabbix_api_factory=FakeZabbixAPI,
        )
        result = await inventory.lookup_vendor("192.0.2.1")
        self.assertIsNone(result.matched_vendor)
        self.assertEqual(result.host_count, 0)
        self.assertEqual(result.note, "zabbix host lookup returned 0 hosts")

    async def test_lookup_timeout(self) -> None:
        inventory = ZabbixInventory(
            registry=VendorRegistry([FakeProvider()]),
            zabbix_url="http://zabbix.local",
            zabbix_token="token",
            timeout=0.001,
            zabbix_api_factory=SlowZabbixAPI,
        )
        result = await inventory.lookup_vendor("10.5.0.21")
        self.assertIsNone(result.matched_vendor)
        self.assertIn("timed out", result.note)


if __name__ == "__main__":
    unittest.main()
