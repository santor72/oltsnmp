from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


DATE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

STATUS_MAP = {
    1: "Logging",
    2: "LOS",
    3: "Synchronization",
    4: "Online",
    5: "Dying Gasp",
    6: "Auth Failed",
    7: "Offline",
}

OFFLINE_REASON_MAP = {
    1: "Unknown",
    2: "LOS",
    3: "LOSi",
    4: "LOFi",
    5: "sfi",
    6: "loai",
    7: "loami",
    8: "AuthFail",
    9: "PowerOff",
    10: "deactiveSucc",
    11: "deactiveFail",
    12: "Reboot",
    13: "Shutdown",
}


def extract_onu_id(oid: str) -> str:
    last = oid.split(".")[-1]
    return last if last.isdigit() else ""


def extract_name(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="ignore")
    if isinstance(value, str):
        return value
    return "Unknown"


def extract_serial_number(value: object) -> str:
    serial = extract_name(value)
    return serial[2:] if serial.startswith("1,") else serial


def convert_power(value: object) -> str:
    int_value: int | None = None

    if isinstance(value, int):
        int_value = value
    elif isinstance(value, bytes):
        try:
            int_value = int(value.decode(errors="ignore").strip())
        except ValueError:
            int_value = None
    elif isinstance(value, str):
        try:
            int_value = int(value.strip())
        except ValueError:
            int_value = None
    else:
        pretty = getattr(value, "prettyPrint", None)
        if callable(pretty):
            try:
                int_value = int(pretty().strip())
            except ValueError:
                int_value = None

    if int_value is None:
        raise ValueError("value is not an integer")

    return f"{(float(int_value) * 0.002) - 30.0:.2f}"


def convert_olt_rx_power(value: object) -> str:
    int_value: int | None = None

    if isinstance(value, int):
        int_value = value
    elif isinstance(value, bytes):
        try:
            int_value = int(value.decode(errors="ignore").strip())
        except ValueError:
            int_value = None
    elif isinstance(value, str):
        try:
            int_value = int(value.strip())
        except ValueError:
            int_value = None
    else:
        pretty = getattr(value, "prettyPrint", None)
        if callable(pretty):
            try:
                int_value = int(pretty().strip())
            except ValueError:
                int_value = None

    if int_value is None:
        raise ValueError("value is not an integer")

    return f"{float(int_value) / 1000.0:.3f}"


def extract_status(value: object) -> str:
    return STATUS_MAP.get(value, "Unknown") if isinstance(value, int) else "Unknown"


def extract_last_offline_reason(value: object) -> str:
    return OFFLINE_REASON_MAP.get(value, "Unknown") if isinstance(value, int) else "Unknown"


def extract_gpon_optical_distance(value: object) -> str:
    return str(value) if isinstance(value, int) else "Unknown"


def convert_byte_array_to_datetime(value: object) -> str:
    if not isinstance(value, bytes):
        raise ValueError("unexpected SNMP value type for datetime")
    if len(value) != 8:
        raise ValueError("invalid byte array length: expected 8 bytes")

    year = int.from_bytes(value[0:2], byteorder="big")
    month = value[2]
    day = value[3]
    hour = value[4]
    minute = value[5]
    second = value[6]

    dt = datetime(year, month, day, hour, minute, second, tzinfo=UTC)
    return dt.strftime(DATE_TIME_FORMAT)


def convert_duration_to_string(total_seconds: int) -> str:
    days, remainder = divmod(total_seconds, 24 * 3600)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days} days {hours} hours {minutes} minutes {seconds} seconds"


def get_uptime_duration(last_online: str, olt_timezone: str) -> str:
    if not last_online.strip():
        return ""

    try:
        tz = ZoneInfo(olt_timezone or "Asia/Jakarta")
    except Exception:
        tz = ZoneInfo("Asia/Jakarta")

    last_online_dt = datetime.strptime(last_online, DATE_TIME_FORMAT).replace(tzinfo=tz)
    now_dt = datetime.now(tz)
    duration_seconds = max(0, int((now_dt - last_online_dt).total_seconds()))
    return convert_duration_to_string(duration_seconds)


def get_last_down_duration(last_offline: str, last_online: str) -> str:
    if not last_offline.strip() or not last_online.strip():
        return ""

    last_offline_dt = datetime.strptime(last_offline, DATE_TIME_FORMAT)
    last_online_dt = datetime.strptime(last_online, DATE_TIME_FORMAT)
    duration_seconds = int((last_online_dt - last_offline_dt).total_seconds())
    return convert_duration_to_string(duration_seconds)
