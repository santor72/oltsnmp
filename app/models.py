from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ONUCLIDetails(BaseModel):
    interface: str = ""
    auth_information: str = ""
    reported_onu_id: str = ""
    onu_type_configured: str = ""
    onu_type_reported: str = ""
    state: str = ""
    hardware_version: str = ""
    software_version: str = ""
    last_authpass_time: str = ""
    last_offline_time: str = ""
    last_offline_cause: str = ""
    onu_rx_power: str = ""
    phase_state: str = ""
    channel: str = ""
    eth_interface: str = ""
    eth_speed_status: str = ""
    eth_operate_status: str = ""
    eth_admin_status: str = ""
    equipment_id: str = ""
    model: str = ""


class ONUCustomerInfo(BaseModel):
    board: int
    pon: int
    onu_id: int
    name: str
    description: str = ""
    onu_type: str = ""
    serial_number: str = ""
    rx_power: str = ""
    olt_rx_power: str = ""
    tx_power: str = ""
    status: str = ""
    last_online: str = ""
    last_offline: str = ""
    uptime: str = ""
    last_down_time_duration: str = ""
    offline_reason: str = Field(default="")
    gpon_optical_distance: str = ""
    cli_details: Optional[ONUCLIDetails] = None


class ONUQuery(BaseModel):
    olt_ip: str
    board_id: int
    pon_id: int
    onu_id: int


class ONUPortQuery(BaseModel):
    olt_ip: str
    port: str
    onu_id: int


class ONUInfoPerBoard(BaseModel):
    board: int
    pon: int
    onu_id: int
    name: str
    onu_type: str = ""
    serial_number: str = ""
    rx_power: str = ""
    status: str = ""


class ONUCLIInfo(BaseModel):
    board: int
    pon: int
    onu_id: int
    name: str = ""
    description: str = ""
    onu_type: str = ""
    serial_number: str = ""
    rx_power: str = ""
    olt_rx_power: str = ""
    tx_power: str = ""
    status: str = ""
    last_online: str = ""
    last_offline: str = ""
    uptime: str = ""
    last_down_time_duration: str = ""
    offline_reason: str = ""
    gpon_optical_distance: str = ""
    cli_details: ONUCLIDetails


class ONUDebugCLIOutput(BaseModel):
    command: str
    output: str


class ONUDebugOIDOutput(BaseModel):
    field: str
    oid: str


class ONUDebugInfo(BaseModel):
    onu: ONUCustomerInfo
    snmp_oids: list[ONUDebugOIDOutput]
    cli_outputs: list[ONUDebugCLIOutput]


class CacheInvalidateResult(BaseModel):
    deleted: int
    keys: list[str]
