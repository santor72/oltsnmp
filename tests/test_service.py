from __future__ import annotations

import unittest

from app.models import ONUQuery, ONUPortQuery
from app.vendors.zte.adapter import ZTEAdapter, is_timeout_error


class FakeSNMPClient:
    async def get(self, host: str, oid: str) -> object:
        return b"unused"

    async def walk(self, host: str, oid: str) -> list[tuple[str, object]]:
        return [
            (f"{oid}.2", b"onu-b"),
            (f"{oid}.1", b"onu-a"),
        ]

    async def get_many(self, host: str, oids: list[str]) -> list[object]:
        onu_id = 1 if oids[0].endswith(".1") else 2
        return [
            f"type-{onu_id}".encode(),
            f"1,SN{onu_id}".encode(),
            1000 + onu_id,
            4,
        ]


class ONUDetailServiceListTest(unittest.IsolatedAsyncioTestCase):
    async def test_get_by_board_and_pon_sorts_and_maps(self) -> None:
        service = ZTEAdapter(FakeSNMPClient(), "Asia/Jakarta")

        got = await service.get_onus("10.0.0.1", 3, 1)

        self.assertEqual([item.onu_id for item in got], [1, 2])
        self.assertEqual(got[0].name, "onu-a")
        self.assertEqual(got[0].onu_type, "type-1")
        self.assertEqual(got[0].serial_number, "SN1")
        self.assertEqual(got[0].status, "Online")


class FakeSNMPWalkClient:
    async def walk(self, host: str, oid: str) -> list[tuple[str, object]]:
        if ".500.10.2.3.3.1.2." in oid:
            return [
                (f"{oid}.2", b"onu-b"),
                (f"{oid}.1", b"onu-a"),
            ]
        if ".3.50.11.2.1.17." in oid:
            return [
                (f"{oid}.1", b"type-1"),
                (f"{oid}.2", b"type-2"),
            ]
        if ".500.10.2.3.3.1.18." in oid:
            return [
                (f"{oid}.1", b"1,SN1"),
                (f"{oid}.2", b"1,SN2"),
            ]
        if ".500.20.2.2.2.1.10." in oid:
            return [
                (f"{oid}.1.1", 1001),
                (f"{oid}.2.1", 1002),
            ]
        if ".500.10.2.3.8.1.4." in oid:
            return [
                (f"{oid}.1", 4),
                (f"{oid}.2", 7),
            ]
        return []


class FakeSNMPDetailClient:
    async def get(self, host: str, oid: str) -> object:
        if ".500.10.2.3.3.1.2." in oid:
            return b"onu-125"
        if ".3.50.11.2.1.17." in oid:
            return b"type-125"
        if ".500.10.2.3.3.1.18." in oid:
            return b"1,SN125"
        if ".500.20.2.2.2.1.10." in oid:
            return 1001
        if ".500.1.2.4.2.1.2." in oid:
            return -25304
        if ".3.50.12.1.1.14." in oid:
            return 1002
        if ".500.10.2.3.8.1.4." in oid:
            return 4
        if ".500.10.2.3.3.1.3." in oid:
            return b"desc-125"
        if ".500.10.2.3.8.1.5." in oid:
            return bytes([0x07, 0xE8, 0x01, 0x02, 0x03, 0x04, 0x05, 0x00])
        if ".500.10.2.3.8.1.6." in oid:
            return bytes([0x07, 0xE8, 0x01, 0x02, 0x01, 0x00, 0x00, 0x00])
        if ".500.10.2.3.8.1.7." in oid:
            return 9
        if ".500.10.2.3.10.1.2." in oid:
            return 1234
        raise RuntimeError(f"unexpected oid {oid}")


class FakeCLIClient:
    async def run_commands(self, host: str, commands: list[str], access: str) -> dict[str, str]:
        assert access in {"ssh", "telnet"}
        return {
            commands[0]: """ONU interface:                  gpon-onu_1/1/1:125
Auth information:               sn(GPON1D94C835)
SN reported:                    GPON1D94C835
ONU ID:                         93
ONU type configured:            CDATA
ONU type reported:              POINT-ONU-XPON
State :                         working
Hardware version:               F690.1B
Software version:               V1.3.8
------------------------------------------
       Authpass Time          OfflineTime             Cause
  10   2026-06-25 17:37:46    0000-00-00 00:00:00
""",
            commands[1]: "gpon-onu_1/1/1:125  -25.304(dbm)\n",
            commands[2]: "gpon-onu_1/1/1:125  -22.292(dbm)\n",
            commands[3]: "1/1/1:125   enable       enable      working      1(GPON)\n",
            commands[4]: "Interface      : eth_0/1\nSpeed status   : full-1000\nOperate status : enable\nAdmin status   : unlock\n",
            commands[5]: "Equipment ID:              POINT-ONU-XPON1G-APC\nModel:                     POINT-ONU-XPON\n",
        }


class FakeSNMPTimeoutClient:
    async def get(self, host: str, oid: str) -> object:
        raise RuntimeError("Request timeout")


class FakeSNMPDebugClient:
    async def get(self, host: str, oid: str) -> object:
        if ".500.10.2.3.3.1.2.285278730.46" in oid:
            return b"onu-46"
        if ".3.50.11.2.1.17." in oid:
            return b"type-46"
        if ".500.10.2.3.3.1.18.285278730.46" in oid:
            return b"1,SN46"
        if ".500.20.2.2.2.1.10.285278730.46.1" in oid:
            return 1001
        if ".500.1.2.4.2.1.2." in oid:
            return 1002
        if ".3.50.12.1.1.14." in oid:
            return 1003
        if ".500.10.2.3.8.1.4.285278730.46" in oid:
            return 4
        if ".500.10.2.3.3.1.3.285278730.46" in oid:
            return b"desc-46"
        if ".500.10.2.3.8.1.5.285278730.46" in oid:
            return bytes([0x07, 0xE8, 0x01, 0x02, 0x03, 0x04, 0x05, 0x00])
        if ".500.10.2.3.8.1.6.285278730.46" in oid:
            return bytes([0x07, 0xE8, 0x01, 0x02, 0x01, 0x00, 0x00, 0x00])
        if ".500.10.2.3.8.1.7.285278730.46" in oid:
            return 9
        if ".500.10.2.3.10.1.2.285278730.46" in oid:
            return 1234
        raise RuntimeError(f"unexpected oid {oid}")


class FakeONUDebugCLIClient:
    async def run_commands(self, host: str, commands: list[str], access: str) -> dict[str, str]:
        assert access == "telnet"
        return {
            commands[0]: "detail-info output",
            commands[1]: "attenuation output",
        }


class ONUDetailServiceWalkListTest(unittest.IsolatedAsyncioTestCase):
    async def test_get_by_board_and_pon_new_merges_walk_tables(self) -> None:
        service = ZTEAdapter(FakeSNMPWalkClient(), "Asia/Jakarta")

        got = await service.get_onus_new("10.0.0.1", 1, 5)

        self.assertEqual([item.onu_id for item in got], [1, 2])
        self.assertEqual(got[0].name, "onu-a")
        self.assertEqual(got[0].onu_type, "type-1")
        self.assertEqual(got[0].serial_number, "SN1")
        self.assertEqual(got[0].status, "Online")
        self.assertEqual(got[1].status, "Offline")


class ONUDetailServiceDetailTest(unittest.IsolatedAsyncioTestCase):
    async def test_get_by_board_pon_onu_uses_direct_get_for_name_leaf(self) -> None:
        service = ZTEAdapter(FakeSNMPDetailClient(), "Asia/Jakarta")

        got = await service.get_onu(
            ONUQuery(olt_ip="10.0.0.1", board_id=1, pon_id=1, onu_id=125)
        )

        self.assertEqual(got.onu_id, 125)
        self.assertEqual(got.name, "onu-125")
        self.assertEqual(got.onu_type, "type-125")
        self.assertEqual(got.serial_number, "SN125")
        self.assertEqual(got.olt_rx_power, "-25.304")

    async def test_get_by_board_pon_onu_cli(self) -> None:
        service = ZTEAdapter(FakeSNMPDetailClient(), "Asia/Jakarta", cli_transport=FakeCLIClient())

        got = await service.get_onu_cli(
            ONUQuery(olt_ip="10.0.0.1", board_id=1, pon_id=1, onu_id=125),
            access="telnet",
        )

        self.assertEqual(got.name, "gpon-onu_1/1/1:125")
        self.assertEqual(got.olt_rx_power, "-25.304")
        self.assertEqual(got.rx_power, "-22.292")
        self.assertEqual(got.status, "working")
        self.assertEqual(got.cli_details.phase_state, "working")

    async def test_get_by_port_onu_uses_direct_get_for_name_leaf(self) -> None:
        service = ZTEAdapter(FakeSNMPDetailClient(), "Asia/Jakarta")

        got = await service.get_onup(
            ONUPortQuery(olt_ip="10.0.0.1", port="gpon-olt_1/1/1", onu_id=125)
        )

        self.assertEqual(got.onu_id, 125)
        self.assertEqual(got.name, "onu-125")
        self.assertEqual(got.onu_type, "type-125")
        self.assertEqual(got.serial_number, "SN125")
        self.assertEqual(got.olt_rx_power, "-25.304")

    async def test_get_by_port_onu_cli(self) -> None:
        service = ZTEAdapter(FakeSNMPDetailClient(), "Asia/Jakarta", cli_transport=FakeCLIClient())

        got = await service.get_onup_cli(
            ONUPortQuery(olt_ip="10.0.0.1", port="gpon-olt_1/1/1", onu_id=125),
            access="telnet",
        )

        self.assertEqual(got.name, "gpon-onu_1/1/1:125")
        self.assertEqual(got.olt_rx_power, "-25.304")
        self.assertEqual(got.rx_power, "-22.292")
        self.assertEqual(got.status, "working")
        self.assertEqual(got.cli_details.phase_state, "working")

    async def test_timeout_on_port_name_get_is_runtime_error(self) -> None:
        service = ZTEAdapter(FakeSNMPTimeoutClient(), "Asia/Jakarta")

        with self.assertRaises(RuntimeError):
            await service.get_onup(
                ONUPortQuery(olt_ip="10.0.0.1", port="gpon-olt_1/1/1", onu_id=125)
            )

    async def test_timeout_on_name_get_is_runtime_error(self) -> None:
        service = ZTEAdapter(FakeSNMPTimeoutClient(), "Asia/Jakarta")

        with self.assertRaises(RuntimeError):
            await service.get_onu(
                ONUQuery(olt_ip="10.0.0.1", board_id=1, pon_id=1, onu_id=125)
            )

    async def test_get_onu_debug_returns_cli_outputs(self) -> None:
        service = ZTEAdapter(FakeSNMPDebugClient(), "Asia/Jakarta", cli_transport=FakeONUDebugCLIClient())

        got = await service.get_onu_debug(
            ONUPortQuery(olt_ip="10.0.0.1", port="1/2/10", onu_id=46)
        )

        self.assertEqual(got.onu.onu_id, 46)
        self.assertEqual(got.onu.name, "onu-46")
        self.assertEqual(
            got.snmp_oids[0],
            type(got.snmp_oids[0])(field="name", oid=".1.3.6.1.4.1.3902.1082.500.10.2.3.3.1.2.285278730.46"),
        )
        self.assertIn("tx_power", {item.field for item in got.snmp_oids})
        self.assertEqual([item.command for item in got.cli_outputs], [
            "sh gpon onu detail-info gpon-onu_1/2/10:46",
            "sh pon power attenuation gpon-onu_1/2/10:46",
        ])
        self.assertEqual(got.cli_outputs[0].output, "detail-info output")


class TimeoutHelperTest(unittest.TestCase):
    def test_is_timeout_error(self) -> None:
        self.assertTrue(is_timeout_error(RuntimeError("Request timeout")))
        self.assertTrue(is_timeout_error("No SNMP response received before timeout"))
        self.assertFalse(is_timeout_error("ONU not found"))


if __name__ == "__main__":
    unittest.main()
