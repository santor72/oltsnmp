from __future__ import annotations

from dataclasses import dataclass


BASE_OID_1 = ".1.3.6.1.4.1.3902.1082"
BASE_OID_2 = ".1.3.6.1.4.1.3902.1012"
SNMP_OID_SUFFIX = ".1"

ONU_ID_NAME_PREFIX = ".500.10.2.3.3.1.2"
ONU_TYPE_PREFIX = ".3.50.11.2.1.17"
ONU_SERIAL_NUMBER_PREFIX = ".500.10.2.3.3.1.18"
ONU_RX_POWER_PREFIX = ".500.20.2.2.2.1.10"
OLT_RX_POWER_PREFIX = ".500.1.2.4.2.1.2"
ONU_TX_POWER_PREFIX = ".3.50.12.1.1.14"
ONU_STATUS_PREFIX = ".500.10.2.3.8.1.4"
ONU_IP_ADDRESS_PREFIX = ".3.50.16.1.1.10"
ONU_DESCRIPTION_PREFIX = ".500.10.2.3.3.1.3"
ONU_LAST_ONLINE_PREFIX = ".500.10.2.3.8.1.5"
ONU_LAST_OFFLINE_PREFIX = ".500.10.2.3.8.1.6"
ONU_LAST_OFFLINE_REASON_PREFIX = ".500.10.2.3.8.1.7"
ONU_GPON_OPTICAL_DISTANCE_PREFIX = ".500.10.2.3.10.1.2"

ONU_ID_IF_INDEX_BASE = 285278208
ONU_ID_SLOT_STRIDE = 256
ONU_ID_INCREMENT = 1
ONU_TYPE_IF_INDEX_BASE = 268435456
ONU_TYPE_SLOT_STRIDE = 65536
ONU_TYPE_INCREMENT = 256

MAX_BOARD_ID = 30
MAX_PON_ID = 16


@dataclass(frozen=True)
class BoardPonOID:
    onu_id_name_oid: str
    onu_type_oid: str
    onu_serial_number_oid: str
    onu_rx_power_oid: str
    olt_rx_power_oid: str
    onu_tx_power_oid: str
    onu_status_oid: str
    onu_ip_address_oid: str
    onu_description_oid: str
    onu_last_online_oid: str
    onu_last_offline_oid: str
    onu_last_offline_reason_oid: str
    onu_gpon_optical_distance_oid: str


def generate_board_pon_oids(board_id: int, pon_id: int) -> BoardPonOID:
    if board_id < 1 or board_id > MAX_BOARD_ID:
        raise ValueError(f"invalid board_id: {board_id} (must be 1-{MAX_BOARD_ID})")
    if pon_id < 1 or pon_id > MAX_PON_ID:
        raise ValueError(f"invalid pon_id: {pon_id} (must be 1-{MAX_PON_ID})")

    onu_id_suffix = ONU_ID_IF_INDEX_BASE + board_id * ONU_ID_SLOT_STRIDE + pon_id * ONU_ID_INCREMENT
    onu_type_suffix = ONU_TYPE_IF_INDEX_BASE + board_id * ONU_TYPE_SLOT_STRIDE + pon_id * ONU_TYPE_INCREMENT

    return BoardPonOID(
        onu_id_name_oid=f"{ONU_ID_NAME_PREFIX}.{onu_id_suffix}",
        onu_type_oid=f"{ONU_TYPE_PREFIX}.{onu_type_suffix}",
        onu_serial_number_oid=f"{ONU_SERIAL_NUMBER_PREFIX}.{onu_id_suffix}",
        onu_rx_power_oid=f"{ONU_RX_POWER_PREFIX}.{onu_id_suffix}",
        olt_rx_power_oid=f"{OLT_RX_POWER_PREFIX}.{onu_id_suffix}",
        onu_tx_power_oid=f"{ONU_TX_POWER_PREFIX}.{onu_type_suffix}",
        onu_status_oid=f"{ONU_STATUS_PREFIX}.{onu_id_suffix}",
        onu_ip_address_oid=f"{ONU_IP_ADDRESS_PREFIX}.{onu_type_suffix}",
        onu_description_oid=f"{ONU_DESCRIPTION_PREFIX}.{onu_id_suffix}",
        onu_last_online_oid=f"{ONU_LAST_ONLINE_PREFIX}.{onu_id_suffix}",
        onu_last_offline_oid=f"{ONU_LAST_OFFLINE_PREFIX}.{onu_id_suffix}",
        onu_last_offline_reason_oid=f"{ONU_LAST_OFFLINE_REASON_PREFIX}.{onu_id_suffix}",
        onu_gpon_optical_distance_oid=f"{ONU_GPON_OPTICAL_DISTANCE_PREFIX}.{onu_id_suffix}",
    )
