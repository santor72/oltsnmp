from __future__ import annotations

from typing import Any


class SNMPClient:
    def __init__(self, community: str, port: int, timeout: float, retries: int) -> None:
        self.community = community
        self.port = port
        self.timeout = timeout
        self.retries = retries

    def _hlapi(self) -> Any:
        try:
            from pysnmp.hlapi.asyncio import (  # type: ignore
                CommunityData,
                ContextData,
                ObjectIdentity,
                ObjectType,
                SnmpEngine,
                UdpTransportTarget,
                bulk_cmd,
                get_cmd,
            )
        except ImportError as exc:
            raise RuntimeError("pysnmp is required. Install dependencies from python_fastapi/requirements.txt") from exc

        return {
            "CommunityData": CommunityData,
            "ContextData": ContextData,
            "ObjectIdentity": ObjectIdentity,
            "ObjectType": ObjectType,
            "SnmpEngine": SnmpEngine,
            "UdpTransportTarget": UdpTransportTarget,
            "bulk_cmd": bulk_cmd,
            "get_cmd": get_cmd,
        }

    async def get(self, host: str, oid: str) -> object:
        api = self._hlapi()
        target = await api["UdpTransportTarget"].create(
            (host, self.port),
            timeout=self.timeout,
            retries=self.retries,
        )

        error_indication, error_status, error_index, var_binds = await api["get_cmd"](
            api["SnmpEngine"](),
            api["CommunityData"](self.community, mpModel=1),
            target,
            api["ContextData"](),
            api["ObjectType"](api["ObjectIdentity"](oid.lstrip("."))),
        )
        if error_indication:
            raise RuntimeError(str(error_indication))
        if error_status:
            raise RuntimeError(f"{error_status.prettyPrint()} at index {error_index}")
        if not var_binds:
            raise RuntimeError(f"no variables in response for oid {oid}")

        return var_binds[0][1]

    async def get_many(self, host: str, oids: list[str]) -> list[object]:
        api = self._hlapi()
        target = await api["UdpTransportTarget"].create(
            (host, self.port),
            timeout=self.timeout,
            retries=self.retries,
        )

        object_types = [api["ObjectType"](api["ObjectIdentity"](oid.lstrip("."))) for oid in oids]
        error_indication, error_status, error_index, var_binds = await api["get_cmd"](
            api["SnmpEngine"](),
            api["CommunityData"](self.community, mpModel=1),
            target,
            api["ContextData"](),
            *object_types,
        )
        if error_indication:
            raise RuntimeError(str(error_indication))
        if error_status:
            raise RuntimeError(f"{error_status.prettyPrint()} at index {error_index}")
        if not var_binds:
            raise RuntimeError(f"no variables in response for oids {oids}")

        return [var_bind[1] for var_bind in var_binds]

    async def walk(self, host: str, oid: str) -> list[tuple[str, object]]:
        api = self._hlapi()
        target = await api["UdpTransportTarget"].create(
            (host, self.port),
            timeout=self.timeout,
            retries=self.retries,
        )

        current_oid = oid.lstrip(".")
        results: list[tuple[str, object]] = []

        while True:
            error_indication, error_status, error_index, var_binds = await api["bulk_cmd"](
                api["SnmpEngine"](),
                api["CommunityData"](self.community, mpModel=1),
                target,
                api["ContextData"](),
                0,
                10,
                api["ObjectType"](api["ObjectIdentity"](current_oid)),
                lexicographicMode=False,
            )
            if error_indication:
                raise RuntimeError(str(error_indication))
            if error_status:
                raise RuntimeError(f"{error_status.prettyPrint()} at index {error_index}")
            if not var_binds:
                break

            advanced = False
            for var_bind in var_binds:
                name = "." + str(var_bind[0])
                value = var_bind[1]
                if not name.startswith(oid):
                    return results
                results.append((name, value))
                current_oid = str(var_bind[0])
                advanced = True

            if not advanced:
                break

        return results
