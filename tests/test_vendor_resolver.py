from __future__ import annotations

import unittest

from app.core.registry import VendorRegistry
from app.core.vendor_resolver import VendorResolver
from app.inventory.provider import InventoryLookupResult


class FakeProvider:
    vendor_tags = ("zte", "zteolt-2.1")
    default_cli_fallback_access = "telnet"

    async def get_onu(self, query):  # pragma: no cover
        raise NotImplementedError

    async def get_onus(self, olt_ip, port):  # pragma: no cover
        raise NotImplementedError

    async def get_onus_new(self, olt_ip, port):  # pragma: no cover
        raise NotImplementedError

    async def get_onu_cli(self, query, access):  # pragma: no cover
        raise NotImplementedError


class FakeInventory:
    def __init__(self, result: InventoryLookupResult) -> None:
        self.result = result

    async def lookup_vendor(self, olt_ip: str) -> InventoryLookupResult:
        return self.result


class VendorResolverTest(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_vendor_wins(self) -> None:
        resolver = VendorResolver(
            registry=VendorRegistry([FakeProvider()]),
            default_vendor="zte",
        )
        got = await resolver.resolve("10.5.0.21", "zteolt-2.1")
        self.assertEqual(got, "zte")
        details = await resolver.resolve_details("10.5.0.21", "zteolt-2.1")
        self.assertEqual(details.source, "explicit")
        self.assertEqual(details.resolved_vendor, "zte")

    async def test_resolve_from_inventory(self) -> None:
        resolver = VendorResolver(
            registry=VendorRegistry([FakeProvider()]),
            default_vendor="zte",
            inventory=FakeInventory(
                InventoryLookupResult(
                    matched_vendor="zte",
                    source="zabbix",
                    host_count=1,
                    vendor_tag="zteolt-2.1",
                    lookup_value="zteolt-2.1",
                    note="vendor tag found in zabbix host tags",
                )
            ),
        )
        got = await resolver.resolve("10.5.0.21", None)
        self.assertEqual(got, "zte")
        details = await resolver.resolve_details("10.5.0.21", None)
        self.assertEqual(details.source, "zabbix")
        self.assertEqual(details.zabbix_vendor_tag, "zteolt-2.1")
        self.assertEqual(details.inventory_lookup_value, "zteolt-2.1")

    async def test_fallback_to_default_vendor_when_inventory_misses(self) -> None:
        resolver = VendorResolver(
            registry=VendorRegistry([FakeProvider()]),
            default_vendor="zte",
            inventory=FakeInventory(
                InventoryLookupResult(
                    matched_vendor=None,
                    source="zabbix",
                    host_count=0,
                    vendor_tag=None,
                    lookup_value=None,
                    note="zabbix host lookup returned 0 hosts",
                )
            ),
        )
        got = await resolver.resolve("192.0.2.1", None)
        self.assertEqual(got, "zte")
        details = await resolver.resolve_details("192.0.2.1", None)
        self.assertEqual(details.source, "default")
        self.assertEqual(details.zabbix_host_count, 0)
        self.assertEqual(details.note, "zabbix host lookup returned 0 hosts")


if __name__ == "__main__":
    unittest.main()
