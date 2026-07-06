from __future__ import annotations

import unittest

from app.vendors.zte.oid import generate_board_pon_oids


class GenerateBoardPonOIDsTest(unittest.TestCase):
    def test_board_1_pon_1_matches_go_formula(self) -> None:
        got = generate_board_pon_oids(1, 1)
        self.assertEqual(got.onu_id_name_oid, ".500.10.2.3.3.1.2.285278465")
        self.assertEqual(got.onu_type_oid, ".3.50.11.2.1.17.268501248")

    def test_board_3_pon_16_matches_c300_formula(self) -> None:
        got = generate_board_pon_oids(3, 16)
        self.assertEqual(got.onu_serial_number_oid, ".500.10.2.3.3.1.18.285278992")
        self.assertEqual(got.onu_tx_power_oid, ".3.50.12.1.1.14.268636160")
        self.assertEqual(got.olt_rx_power_oid, ".500.1.2.4.2.1.2.285278992")


if __name__ == "__main__":
    unittest.main()
