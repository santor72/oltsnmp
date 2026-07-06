from __future__ import annotations

import unittest

from app.vendors.zte.cli_parser import parse_onu_cli_outputs


INFO_OUTPUT = """ONU interface:                  gpon-onu_1/1/1:125
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
   1   2026-05-10 13:54:30    2026-05-11 13:38:22     DyingGasp
  10   2026-06-25 17:37:46    0000-00-00 00:00:00
"""

OLT_RX_OUTPUT = """Onu                 Rx power
------------------------------------
gpon-onu_1/1/1:125  -25.304(dbm)
"""

ONU_RX_OUTPUT = """Onu                 Rx power
------------------------------------
gpon-onu_1/1/1:125  -22.292(dbm)
"""

STATE_OUTPUT = """OnuIndex   Admin State  OMCC State  Phase State  Channel
--------------------------------------------------------------
1/1/1:125   enable       enable      working      1(GPON)
"""

ETH_OUTPUT = """Interface      : eth_0/1
Speed status   : full-1000
Operate status : enable
Admin status   : unlock
"""

MODEL_OUTPUT = """Equipment ID:              POINT-ONU-XPON1G-APC
Model:                     POINT-ONU-XPON
"""


class CLIParserTest(unittest.TestCase):
    def test_parse_onu_cli_outputs(self) -> None:
        got = parse_onu_cli_outputs(
            board_id=1,
            pon_id=1,
            onu_id=125,
            olt_timezone="Asia/Jakarta",
            info_output=INFO_OUTPUT,
            olt_rx_output=OLT_RX_OUTPUT,
            onu_rx_output=ONU_RX_OUTPUT,
            state_output=STATE_OUTPUT,
            eth_output=ETH_OUTPUT,
            model_output=MODEL_OUTPUT,
        )

        self.assertEqual(got.name, "gpon-onu_1/1/1:125")
        self.assertEqual(got.serial_number, "GPON1D94C835")
        self.assertEqual(got.cli_details.reported_onu_id, "93")
        self.assertEqual(got.last_online, "2026-06-25 17:37:46")
        self.assertEqual(got.last_offline, "0000-00-00 00:00:00")
        self.assertEqual(got.olt_rx_power, "-25.304")
        self.assertEqual(got.rx_power, "-22.292")
        self.assertEqual(got.status, "working")
        self.assertEqual(got.cli_details.channel, "1(GPON)")
        self.assertEqual(got.cli_details.eth_interface, "eth_0/1")
        self.assertEqual(got.cli_details.model, "POINT-ONU-XPON")


if __name__ == "__main__":
    unittest.main()
