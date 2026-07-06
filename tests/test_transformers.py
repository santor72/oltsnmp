from __future__ import annotations

import unittest

from app.transformers import (
    convert_byte_array_to_datetime,
    convert_olt_rx_power,
    convert_power,
    extract_last_offline_reason,
    extract_serial_number,
    extract_status,
    get_last_down_duration,
)


class TransformersTest(unittest.TestCase):
    def test_convert_power(self) -> None:
        self.assertEqual(convert_power(1000), "-28.00")
        self.assertEqual(convert_power(b"1000"), "-28.00")
        self.assertEqual(convert_power("1000"), "-28.00")
        self.assertEqual(convert_olt_rx_power(-25304), "-25.304")

    def test_extract_serial_number(self) -> None:
        self.assertEqual(extract_serial_number(b"1,ZTEG12345678"), "ZTEG12345678")

    def test_extract_status(self) -> None:
        self.assertEqual(extract_status(4), "Online")

    def test_extract_last_offline_reason(self) -> None:
        self.assertEqual(extract_last_offline_reason(9), "PowerOff")

    def test_convert_byte_array_to_datetime(self) -> None:
        raw = bytes([0x07, 0xE8, 0x01, 0x02, 0x03, 0x04, 0x05, 0x00])
        self.assertEqual(convert_byte_array_to_datetime(raw), "2024-01-02 03:04:05")

    def test_get_last_down_duration(self) -> None:
        self.assertEqual(
            get_last_down_duration("2024-01-02 03:00:00", "2024-01-02 04:30:15"),
            "0 days 1 hours 30 minutes 15 seconds",
        )


if __name__ == "__main__":
    unittest.main()
