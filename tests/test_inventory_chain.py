from __future__ import annotations

import unittest

from app.inventory.chain import InventoryChain
from app.inventory.provider import InventoryLookupResult


class FakeInventory:
    def __init__(self, result: InventoryLookupResult) -> None:
        self.result = result

    async def lookup_vendor(self, olt_ip: str) -> InventoryLookupResult:
        return self.result


class InventoryChainTest(unittest.IsolatedAsyncioTestCase):
    async def test_chain_returns_first_match(self) -> None:
        chain = InventoryChain(
            [
                FakeInventory(InventoryLookupResult(matched_vendor=None, source="zabbix", note="miss")),
                FakeInventory(InventoryLookupResult(matched_vendor="zte", source="snmp", lookup_value="zte")),
            ]
        )
        result = await chain.lookup_vendor("10.5.0.21")
        self.assertEqual(result.source, "snmp")
        self.assertEqual(result.matched_vendor, "zte")

    async def test_chain_returns_last_miss_if_no_matches(self) -> None:
        chain = InventoryChain(
            [
                FakeInventory(InventoryLookupResult(matched_vendor=None, source="zabbix", note="miss")),
                FakeInventory(InventoryLookupResult(matched_vendor=None, source="snmp", note="still miss")),
            ]
        )
        result = await chain.lookup_vendor("10.5.0.21")
        self.assertEqual(result.source, "snmp")
        self.assertEqual(result.note, "still miss")


if __name__ == "__main__":
    unittest.main()
