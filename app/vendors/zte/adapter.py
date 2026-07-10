from __future__ import annotations

from typing import Callable

from app.models import ONUCLIInfo, ONUCustomerInfo, ONUDebugCLIOutput, ONUDebugInfo, ONUDebugOIDOutput, ONUInfoPerBoard, ONUQuery, ONUPortQuery
from app.snmp_client import SNMPClient
from app.transformers import (
    convert_byte_array_to_datetime,
    convert_olt_rx_power,
    convert_power,
    extract_gpon_optical_distance,
    extract_last_offline_reason,
    extract_name,
    extract_onu_id,
    extract_serial_number,
    extract_status,
    get_last_down_duration,
    get_uptime_duration,
)
from app.vendors.zte.cli_parser import parse_onu_cli_outputs
from app.vendors.zte.cli_transport import ZTECLITransport
from app.vendors.zte.oid import (
    BASE_OID_1,
    BASE_OID_2,
    SNMP_OID_SUFFIX,
    generate_board_pon_oids,
    generate_onup_oids,
    parse_onup_port,
)


def is_timeout_error(exc: Exception | str) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in ("timeout", "timed out", "no snmp response received"))


def _normalize_snmp_value(value: object) -> object:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        pass
    try:
        return bytes(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(value)


def _onup_missing_default(field: str) -> str:
    if field in {"rx_power", "olt_rx_power", "tx_power", "gpon_optical_distance"}:
        return "0"
    return ""


class ZTEAdapter:
    @property
    def vendor_tags(self) -> tuple[str, ...]:
        return ("zte", "zteolt-2.1")

    def __init__(self, snmp_client: SNMPClient, olt_timezone: str, cli_transport: object | None = None) -> None:
        self.snmp_client = snmp_client
        self.olt_timezone = olt_timezone
        self.cli_transport = cli_transport

    @property
    def default_cli_fallback_access(self) -> str:
        return ZTECLITransport.default_fallback_access

    async def get_onu(self, query: ONUQuery) -> ONUCustomerInfo:
        board_oids = generate_board_pon_oids(query.board_id, query.pon_id)
        name_oid = f"{BASE_OID_1}{board_oids.onu_id_name_oid}.{query.onu_id}"

        try:
            raw_name = await self.snmp_client.get(query.olt_ip, name_oid)
        except Exception as exc:
            if is_timeout_error(exc):
                raise RuntimeError(str(exc)) from exc
            raise LookupError(
                f"ONU not found for board_id={query.board_id}, pon_id={query.pon_id}, onu_id={query.onu_id}"
            ) from exc

        detail = ONUCustomerInfo(
            board=query.board_id,
            pon=query.pon_id,
            onu_id=query.onu_id,
            name=extract_name(_normalize_snmp_value(raw_name)),
        )
        detail.onu_type = extract_name(
            _normalize_snmp_value(await self.snmp_client.get(query.olt_ip, f"{BASE_OID_2}{board_oids.onu_type_oid}.{query.onu_id}"))
        )
        detail.serial_number = extract_serial_number(
            _normalize_snmp_value(await self.snmp_client.get(query.olt_ip, f"{BASE_OID_1}{board_oids.onu_serial_number_oid}.{query.onu_id}"))
        )
        detail.rx_power = convert_power(
            _normalize_snmp_value(await self.snmp_client.get(query.olt_ip, f"{BASE_OID_1}{board_oids.onu_rx_power_oid}.{query.onu_id}{SNMP_OID_SUFFIX}"))
        )
        detail.olt_rx_power = convert_olt_rx_power(
            _normalize_snmp_value(await self.snmp_client.get(query.olt_ip, f"{BASE_OID_1}{board_oids.olt_rx_power_oid}.{query.onu_id}"))
        )
        detail.tx_power = convert_power(
            _normalize_snmp_value(await self.snmp_client.get(query.olt_ip, f"{BASE_OID_2}{board_oids.onu_tx_power_oid}.{query.onu_id}{SNMP_OID_SUFFIX}"))
        )
        detail.status = extract_status(
            _normalize_snmp_value(await self.snmp_client.get(query.olt_ip, f"{BASE_OID_1}{board_oids.onu_status_oid}.{query.onu_id}"))
        )
        detail.description = extract_name(
            _normalize_snmp_value(await self.snmp_client.get(query.olt_ip, f"{BASE_OID_1}{board_oids.onu_description_oid}.{query.onu_id}"))
        )
        detail.last_online = convert_byte_array_to_datetime(
            _normalize_snmp_value(await self.snmp_client.get(query.olt_ip, f"{BASE_OID_1}{board_oids.onu_last_online_oid}.{query.onu_id}"))
        )
        detail.last_offline = convert_byte_array_to_datetime(
            _normalize_snmp_value(await self.snmp_client.get(query.olt_ip, f"{BASE_OID_1}{board_oids.onu_last_offline_oid}.{query.onu_id}"))
        )
        detail.uptime = get_uptime_duration(detail.last_online, self.olt_timezone)
        detail.last_down_time_duration = get_last_down_duration(detail.last_offline, detail.last_online)
        detail.offline_reason = extract_last_offline_reason(
            _normalize_snmp_value(await self.snmp_client.get(query.olt_ip, f"{BASE_OID_1}{board_oids.onu_last_offline_reason_oid}.{query.onu_id}"))
        )
        detail.gpon_optical_distance = extract_gpon_optical_distance(
            _normalize_snmp_value(await self.snmp_client.get(query.olt_ip, f"{BASE_OID_1}{board_oids.onu_gpon_optical_distance_oid}.{query.onu_id}"))
        )
        return detail

    async def get_onup(self, query: ONUPortQuery) -> ONUCustomerInfo:
        detail, _ = await self._get_onup_detail(query)
        return detail

    async def get_onu_debug(self, query: ONUPortQuery) -> ONUDebugInfo:
        if self.cli_transport is None:
            raise RuntimeError("CLI client is not configured")
        detail, snmp_oids = await self._get_onup_detail(query, debug=True)
        port_spec = parse_onup_port(query.port)
        onu_interface = f"gpon-onu_{port_spec.shelf_id}/{port_spec.slot_id}/{port_spec.port_id}:{query.onu_id}"
        commands = [
            f"sh gpon onu detail-info {onu_interface}",
            f"sh pon power attenuation {onu_interface}",
        ]
        outputs = await self.cli_transport.run_commands(query.olt_ip, commands, self.default_cli_fallback_access)
        return ONUDebugInfo(
            onu=detail,
            snmp_oids=[ONUDebugOIDOutput(field=field, oid=oid) for field, oid in snmp_oids],
            cli_outputs=[ONUDebugCLIOutput(command=command, output=outputs.get(command, "")) for command in commands],
        )

    async def get_onus(self, olt_ip: str, port: str) -> list[ONUInfoPerBoard]:
        port_spec = parse_onup_port(port)
        board_oids = generate_onup_oids(
            port_spec.port_type, port_spec.shelf_id, port_spec.slot_id, port_spec.port_id
        )
        walked = await self.snmp_client.walk(olt_ip, f"{BASE_OID_1}{board_oids.onu_id_name_oid}")
        items: list[ONUInfoPerBoard] = []

        for oid_name, raw_name in walked:
            onu_id_str = extract_onu_id(oid_name)
            if not onu_id_str:
                continue
            onu_id = int(onu_id_str)
            batch_oids = [
                f"{BASE_OID_2}{board_oids.onu_type_oid}.{onu_id}",
                f"{BASE_OID_1}{board_oids.onu_serial_number_oid}.{onu_id}",
                f"{BASE_OID_1}{board_oids.onu_rx_power_oid}.{onu_id}{SNMP_OID_SUFFIX}",
                f"{BASE_OID_1}{board_oids.onu_status_oid}.{onu_id}",
            ]
            onu_info = ONUInfoPerBoard(
                board=port_spec.slot_id,
                pon=port_spec.port_id,
                onu_id=onu_id,
                name=extract_name(_normalize_snmp_value(raw_name)),
            )
            try:
                batch_values = [_normalize_snmp_value(value) for value in await self.snmp_client.get_many(olt_ip, batch_oids)]
                if len(batch_values) >= 4:
                    onu_info.onu_type = extract_name(batch_values[0])
                    onu_info.serial_number = extract_serial_number(batch_values[1])
                    onu_info.rx_power = convert_power(batch_values[2])
                    onu_info.status = extract_status(batch_values[3])
            except Exception:
                pass
            items.append(onu_info)
        return sorted(items, key=lambda item: item.onu_id)

    async def get_onus_new(self, olt_ip: str, port: str) -> list[ONUInfoPerBoard]:
        port_spec = parse_onup_port(port)
        board_oids = generate_onup_oids(
            port_spec.port_type, port_spec.shelf_id, port_spec.slot_id, port_spec.port_id
        )
        name_rows = await self.snmp_client.walk(olt_ip, f"{BASE_OID_1}{board_oids.onu_id_name_oid}")
        type_rows = await self.snmp_client.walk(olt_ip, f"{BASE_OID_2}{board_oids.onu_type_oid}")
        serial_rows = await self.snmp_client.walk(olt_ip, f"{BASE_OID_1}{board_oids.onu_serial_number_oid}")
        rx_rows = await self.snmp_client.walk(olt_ip, f"{BASE_OID_1}{board_oids.onu_rx_power_oid}")
        status_rows = await self.snmp_client.walk(olt_ip, f"{BASE_OID_1}{board_oids.onu_status_oid}")

        items: dict[int, ONUInfoPerBoard] = {}
        for oid_name, raw_name in name_rows:
            onu_id_str = extract_onu_id(oid_name)
            if not onu_id_str:
                continue
            onu_id = int(onu_id_str)
            items[onu_id] = ONUInfoPerBoard(
                board=port_spec.slot_id,
                pon=port_spec.port_id,
                onu_id=onu_id,
                name=extract_name(_normalize_snmp_value(raw_name)),
            )
        for oid_name, raw_type in type_rows:
            onu_id_str = extract_onu_id(oid_name)
            if onu_id_str and int(onu_id_str) in items:
                items[int(onu_id_str)].onu_type = extract_name(_normalize_snmp_value(raw_type))
        for oid_name, raw_serial in serial_rows:
            onu_id_str = extract_onu_id(oid_name)
            if onu_id_str and int(onu_id_str) in items:
                items[int(onu_id_str)].serial_number = extract_serial_number(_normalize_snmp_value(raw_serial))
        for oid_name, raw_rx in rx_rows:
            parts = oid_name.split(".")
            if len(parts) < 2 or not parts[-2].isdigit():
                continue
            onu_id = int(parts[-2])
            if onu_id in items:
                try:
                    items[onu_id].rx_power = convert_power(_normalize_snmp_value(raw_rx))
                except Exception:
                    pass
        for oid_name, raw_status in status_rows:
            onu_id_str = extract_onu_id(oid_name)
            if onu_id_str and int(onu_id_str) in items:
                items[int(onu_id_str)].status = extract_status(_normalize_snmp_value(raw_status))
        return sorted(items.values(), key=lambda item: item.onu_id)

    async def get_onu_cli(self, query: ONUQuery, access: str) -> ONUCLIInfo:
        if self.cli_transport is None:
            raise RuntimeError("CLI client is not configured")
        onu_interface = f"gpon-onu_1/{query.board_id}/{query.pon_id}:{query.onu_id}"
        olt_interface = f"gpon-olt_1/{query.board_id}/{query.pon_id}"
        commands = [
            f"show pon onu information {onu_interface}",
            f"show pon power olt-rx {onu_interface}",
            f"show pon power onu-rx {onu_interface}",
            f"show gpon onu state {olt_interface} {query.onu_id}",
            f"show gpon remote-onu interface eth {onu_interface}",
            f"show gpon remote-onu model {onu_interface}",
        ]
        outputs = await self.cli_transport.run_commands(query.olt_ip, commands, access)
        return parse_onu_cli_outputs(
            board_id=query.board_id,
            pon_id=query.pon_id,
            onu_id=query.onu_id,
            olt_timezone=self.olt_timezone,
            info_output=outputs[commands[0]],
            olt_rx_output=outputs[commands[1]],
            onu_rx_output=outputs[commands[2]],
            state_output=outputs[commands[3]],
            eth_output=outputs[commands[4]],
            model_output=outputs[commands[5]],
        )

    async def get_onup_cli(self, query: ONUPortQuery, access: str) -> ONUCLIInfo:
        if self.cli_transport is None:
            raise RuntimeError("CLI client is not configured")
        port_spec = parse_onup_port(query.port)
        onu_prefix = port_spec.port_type.removesuffix("-olt") + "-onu"
        pon_family = port_spec.port_type.removesuffix("-olt")
        onu_interface = (
            f"{onu_prefix}_{port_spec.shelf_id}/{port_spec.slot_id}/{port_spec.port_id}:{query.onu_id}"
        )
        olt_interface = f"{port_spec.port_type}_{port_spec.shelf_id}/{port_spec.slot_id}/{port_spec.port_id}"
        commands = [
            f"show pon onu information {onu_interface}",
            f"show pon power olt-rx {onu_interface}",
            f"show pon power onu-rx {onu_interface}",
            f"show {pon_family} onu state {olt_interface} {query.onu_id}",
            f"show {pon_family} remote-onu interface eth {onu_interface}",
            f"show {pon_family} remote-onu model {onu_interface}",
        ]
        outputs = await self.cli_transport.run_commands(query.olt_ip, commands, access)
        return parse_onu_cli_outputs(
            board_id=port_spec.slot_id,
            pon_id=port_spec.port_id,
            onu_id=query.onu_id,
            olt_timezone=self.olt_timezone,
            info_output=outputs[commands[0]],
            olt_rx_output=outputs[commands[1]],
            onu_rx_output=outputs[commands[2]],
            state_output=outputs[commands[3]],
            eth_output=outputs[commands[4]],
            model_output=outputs[commands[5]],
        )

    async def _get_onup_detail(self, query: ONUPortQuery, debug: bool = False) -> tuple[ONUCustomerInfo, list[tuple[str, str]]]:
        port_spec = parse_onup_port(query.port)
        oids = generate_onup_oids(port_spec.port_type, port_spec.shelf_id, port_spec.slot_id, port_spec.port_id)
        name_oid = f"{BASE_OID_1}{oids.onu_id_name_oid}.{query.onu_id}"
        snmp_oids = [
            ("name", name_oid),
            ("onu_type", f"{BASE_OID_2}{oids.onu_type_oid}.{query.onu_id}"),
            ("serial_number", f"{BASE_OID_1}{oids.onu_serial_number_oid}.{query.onu_id}"),
            ("rx_power", f"{BASE_OID_1}{oids.onu_rx_power_oid}.{query.onu_id}{SNMP_OID_SUFFIX}"),
            ("olt_rx_power", f"{BASE_OID_1}{oids.olt_rx_power_oid}.{query.onu_id}"),
            ("tx_power", f"{BASE_OID_2}{oids.onu_tx_power_oid}.{query.onu_id}{SNMP_OID_SUFFIX}"),
            ("status", f"{BASE_OID_1}{oids.onu_status_oid}.{query.onu_id}"),
            ("description", f"{BASE_OID_1}{oids.onu_description_oid}.{query.onu_id}"),
            ("last_online", f"{BASE_OID_1}{oids.onu_last_online_oid}.{query.onu_id}"),
            ("last_offline", f"{BASE_OID_1}{oids.onu_last_offline_oid}.{query.onu_id}"),
            ("offline_reason", f"{BASE_OID_1}{oids.onu_last_offline_reason_oid}.{query.onu_id}"),
            ("gpon_optical_distance", f"{BASE_OID_1}{oids.onu_gpon_optical_distance_oid}.{query.onu_id}"),
        ]

        try:
            raw_name = await self.snmp_client.get(query.olt_ip, name_oid)
        except Exception as exc:
            if is_timeout_error(exc):
                raise RuntimeError(str(exc)) from exc
            raise LookupError(f"ONU not found for port={query.port}, onu_id={query.onu_id}") from exc

        detail = ONUCustomerInfo(
            board=port_spec.slot_id,
            pon=port_spec.port_id,
            onu_id=query.onu_id,
            name=extract_name(_normalize_snmp_value(raw_name)),
        )
        detail.onu_type = await self._onup_fetch_string(query, "onu_type", f"{BASE_OID_2}{oids.onu_type_oid}.{query.onu_id}")
        detail.serial_number = await self._onup_fetch_string(query, "serial_number", f"{BASE_OID_1}{oids.onu_serial_number_oid}.{query.onu_id}", extract_serial_number)
        detail.rx_power = await self._onup_fetch_number(query, "rx_power", f"{BASE_OID_1}{oids.onu_rx_power_oid}.{query.onu_id}{SNMP_OID_SUFFIX}", convert_power)
        detail.olt_rx_power = await self._onup_fetch_number(query, "olt_rx_power", f"{BASE_OID_1}{oids.olt_rx_power_oid}.{query.onu_id}", convert_olt_rx_power)
        detail.tx_power = await self._onup_fetch_optional_number(
            query,
            "tx_power",
            f"{BASE_OID_2}{oids.onu_tx_power_oid}.{query.onu_id}{SNMP_OID_SUFFIX}",
            convert_power,
        )
        detail.status = await self._onup_fetch_number(query, "status", f"{BASE_OID_1}{oids.onu_status_oid}.{query.onu_id}", extract_status)
        detail.description = await self._onup_fetch_string(query, "description", f"{BASE_OID_1}{oids.onu_description_oid}.{query.onu_id}")
        detail.last_online = await self._onup_fetch_optional_datetime(query, "last_online", f"{BASE_OID_1}{oids.onu_last_online_oid}.{query.onu_id}")
        detail.last_offline = await self._onup_fetch_optional_datetime(query, "last_offline", f"{BASE_OID_1}{oids.onu_last_offline_oid}.{query.onu_id}")
        detail.uptime = get_uptime_duration(detail.last_online, self.olt_timezone)
        detail.last_down_time_duration = get_last_down_duration(detail.last_offline, detail.last_online)
        detail.offline_reason = await self._onup_fetch_number(query, "offline_reason", f"{BASE_OID_1}{oids.onu_last_offline_reason_oid}.{query.onu_id}", extract_last_offline_reason)
        detail.gpon_optical_distance = await self._onup_fetch_number(query, "gpon_optical_distance", f"{BASE_OID_1}{oids.onu_gpon_optical_distance_oid}.{query.onu_id}", extract_gpon_optical_distance)
        return detail, snmp_oids

    async def _onup_get_raw(self, query: ONUPortQuery, field: str, oid: str) -> object:
        try:
            return await self.snmp_client.get(query.olt_ip, oid)
        except Exception as exc:
            if is_timeout_error(exc):
                raise RuntimeError(f"onup {field} timeout for port={query.port} oid={oid}: {exc}") from exc
            raise RuntimeError(f"onup {field} fetch failed for port={query.port} oid={oid}: {exc}") from exc

    async def _onup_fetch_string(
        self,
        query: ONUPortQuery,
        field: str,
        oid: str,
        converter: Callable[[object], str] = extract_name,
    ) -> str:
        raw_value = await self._onup_get_raw(query, field, oid)
        try:
            return converter(_normalize_snmp_value(raw_value))
        except Exception as exc:
            raise RuntimeError(
                f"onup {field} conversion failed for port={query.port} oid={oid} raw={raw_value!r}: {exc}"
            ) from exc

    async def _onup_fetch_number(
        self,
        query: ONUPortQuery,
        field: str,
        oid: str,
        converter: Callable[[object], str],
        missing_default: str | None = None,
    ) -> str:
        raw_value = await self._onup_get_raw(query, field, oid)
        try:
            return converter(_normalize_snmp_value(raw_value))
        except Exception as exc:
            raw_text = repr(raw_value)
            if "NoSuchInstance" in raw_text or "NoSuchObject" in raw_text:
                return _onup_missing_default(field) if missing_default is None else missing_default
            raise RuntimeError(
                f"onup {field} conversion failed for port={query.port} oid={oid} raw={raw_value!r}: {exc}"
            ) from exc

    async def _onup_fetch_optional_number(
        self,
        query: ONUPortQuery,
        field: str,
        oid: str,
        converter: Callable[[object], str],
    ) -> str:
        raw_value = await self._onup_get_raw(query, field, oid)
        raw_text = repr(raw_value)
        if "NoSuchInstance" in raw_text or "NoSuchObject" in raw_text:
            return _onup_missing_default(field)
        try:
            return converter(_normalize_snmp_value(raw_value))
        except Exception as exc:
            raise RuntimeError(
                f"onup {field} conversion failed for port={query.port} oid={oid} raw={raw_value!r}: {exc}"
            ) from exc

    async def _onup_fetch_optional_datetime(self, query: ONUPortQuery, field: str, oid: str) -> str:
        raw_value = await self._onup_get_raw(query, field, oid)
        raw_text = repr(raw_value)
        if "NoSuchInstance" in raw_text or "NoSuchObject" in raw_text:
            return ""
        try:
            return convert_byte_array_to_datetime(_normalize_snmp_value(raw_value))
        except Exception:
            return ""
