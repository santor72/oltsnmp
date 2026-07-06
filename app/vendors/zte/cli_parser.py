from __future__ import annotations

from pathlib import Path

from app.models import ONUCLIDetails, ONUCLIInfo
from app.transformers import get_last_down_duration, get_uptime_duration


TEMPLATE_DIR = Path(__file__).resolve().parent / "textfsm_templates"


def _parse_with_template(template_name: str, text: str) -> list[dict[str, str]]:
    try:
        import textfsm  # type: ignore
    except ImportError as exc:
        raise RuntimeError("textfsm is required. Install dependencies from python_fastapi/requirements.txt") from exc

    template_path = TEMPLATE_DIR / template_name
    with template_path.open("r", encoding="utf-8") as handle:
        parser = textfsm.TextFSM(handle)
        rows = parser.ParseText(text)
    return [dict(zip(parser.header, row, strict=False)) for row in rows]


def parse_onu_cli_outputs(
    board_id: int,
    pon_id: int,
    onu_id: int,
    olt_timezone: str,
    info_output: str,
    olt_rx_output: str,
    onu_rx_output: str,
    state_output: str,
    eth_output: str,
    model_output: str,
) -> ONUCLIInfo:
    info_rows = _parse_with_template("show_pon_onu_information.textfsm", info_output)
    history_rows = _parse_with_template("show_pon_onu_information_history.textfsm", info_output)
    olt_rx_rows = _parse_with_template("show_pon_power.textfsm", olt_rx_output)
    onu_rx_rows = _parse_with_template("show_pon_power.textfsm", onu_rx_output)
    state_rows = _parse_with_template("show_gpon_onu_state.textfsm", state_output)
    eth_rows = _parse_with_template("show_gpon_remote_onu_interface_eth.textfsm", eth_output)
    model_rows = _parse_with_template("show_gpon_remote_onu_model.textfsm", model_output)

    info = info_rows[0] if info_rows else {}
    history = history_rows[-1] if history_rows else {}
    state = state_rows[-1] if state_rows else {}
    eth = eth_rows[0] if eth_rows else {}
    model = model_rows[0] if model_rows else {}
    last_authpass_time = history.get("AUTHPASS_TIME", "")
    last_offline_time = history.get("OFFLINE_TIME", "")
    last_offline_cause = history.get("CAUSE", "")
    duration_offline = "" if last_offline_time.startswith("0000-00-00") else last_offline_time
    status = state.get("PHASE_STATE", "") or info.get("STATE", "")
    onu_type = info.get("ONU_TYPE_REPORTED", "") or info.get("ONU_TYPE_CONFIGURED", "")
    rx_power = onu_rx_rows[-1].get("RX_POWER", "") if onu_rx_rows else ""
    cli_details = ONUCLIDetails(
        interface=info.get("INTERFACE", ""),
        auth_information=info.get("AUTH_INFORMATION", ""),
        reported_onu_id=info.get("REPORTED_ONU_ID", ""),
        onu_type_configured=info.get("ONU_TYPE_CONFIGURED", ""),
        onu_type_reported=info.get("ONU_TYPE_REPORTED", ""),
        state=info.get("STATE", ""),
        hardware_version=info.get("HARDWARE_VERSION", ""),
        software_version=info.get("SOFTWARE_VERSION", ""),
        last_authpass_time=last_authpass_time,
        last_offline_time=last_offline_time,
        last_offline_cause=last_offline_cause,
        onu_rx_power=rx_power,
        phase_state=state.get("PHASE_STATE", ""),
        channel=state.get("CHANNEL", ""),
        eth_interface=eth.get("INTERFACE", ""),
        eth_speed_status=eth.get("SPEED_STATUS", ""),
        eth_operate_status=eth.get("OPERATE_STATUS", ""),
        eth_admin_status=eth.get("ADMIN_STATUS", ""),
        equipment_id=model.get("EQUIPMENT_ID", ""),
        model=model.get("MODEL", ""),
    )

    return ONUCLIInfo(
        board=board_id,
        pon=pon_id,
        onu_id=onu_id,
        name=info.get("INTERFACE", ""),
        description=model.get("MODEL", ""),
        onu_type=onu_type,
        serial_number=info.get("SN_REPORTED", ""),
        rx_power=rx_power,
        olt_rx_power=(olt_rx_rows[-1].get("RX_POWER", "") if olt_rx_rows else ""),
        status=status,
        last_online=last_authpass_time,
        last_offline=last_offline_time,
        uptime=get_uptime_duration(last_authpass_time, olt_timezone) if last_authpass_time else "",
        last_down_time_duration=get_last_down_duration(duration_offline, last_authpass_time)
        if last_authpass_time and duration_offline
        else "",
        offline_reason=last_offline_cause,
        cli_details=cli_details,
    )
