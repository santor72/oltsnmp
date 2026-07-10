from __future__ import annotations

import json
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import TypeAdapter

from app.cache import CacheClient
from app.config import get_settings
from app.core.registry import VendorRegistry
from app.core.vendor_resolver import VendorResolver
from app.inventory.chain import InventoryChain
from app.inventory.snmp_platform import SNMPPlatformInventory
from app.inventory.zabbix import ZabbixInventory
from app.models import CacheInvalidateResult, ONUCLIInfo, ONUCustomerInfo, ONUInfoPerBoard, ONUQuery, ONUPortQuery
from app.services.onu_service import OnuService
from app.snmp_client import SNMPClient
from app.vendors.zte.adapter import ZTEAdapter
from app.vendors.zte.cli_transport import ZTECLITransport


app = FastAPI(title="ZTE OLT ONU Detail API", version="0.1.0")
ONU_INFO_LIST_ADAPTER = TypeAdapter(list[ONUInfoPerBoard])


def _build_dependencies() -> tuple[object, object, object, object]:
    settings = get_settings()
    snmp_client = SNMPClient(
        community=settings.snmp_community,
        port=settings.snmp_port,
        timeout=settings.snmp_timeout,
        retries=settings.snmp_retries,
    )
    zte_cli_transport = ZTECLITransport(
        username=settings.cli_username,
        password=settings.cli_password,
        secret=settings.cli_secret,
        ssh_port=settings.cli_ssh_port,
        telnet_port=settings.cli_telnet_port,
        timeout=settings.cli_timeout,
    )
    cache_client = CacheClient(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        db=settings.redis_db,
        prefix=settings.redis_prefix,
    )
    zte_adapter = ZTEAdapter(snmp_client, settings.olt_timezone, cli_transport=zte_cli_transport)
    registry = VendorRegistry([zte_adapter], default_vendor=settings.default_vendor)
    inventory_providers = []
    if settings.zabbix_url and settings.zabbix_token:
        inventory_providers.append(
            ZabbixInventory(
                registry=registry,
                zabbix_url=settings.zabbix_url,
                zabbix_token=settings.zabbix_token,
                timeout=settings.zabbix_timeout,
                debug=settings.debug,
            )
        )
    inventory_providers.append(
        SNMPPlatformInventory(
            registry=registry,
            snmp_client=snmp_client,
            debug=settings.debug,
        )
    )
    resolver = VendorResolver(
        registry=registry,
        default_vendor=settings.default_vendor,
        inventory=InventoryChain(inventory_providers),
    )
    service = OnuService(registry)
    return settings, service, cache_client, resolver


def _apply_vendor_debug_headers(response: Response, debug_enabled: bool, details: object) -> None:
    if not debug_enabled:
        return
    payload = getattr(details, "as_dict", lambda: details)()
    response.headers["X-Vendor-Debug"] = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    if isinstance(payload, dict):
        response.headers["X-Resolved-Vendor"] = str(payload.get("resolved_vendor", ""))
        response.headers["X-Vendor-Source"] = str(payload.get("source", ""))


async def _cache_get(cache: CacheClient, key: str) -> object | None:
    try:
        return await cache.get_json(key)
    except Exception:
        return None


async def _cache_set(cache: CacheClient, key: str, value: object, ttl_seconds: int) -> None:
    try:
        await cache.set_json(key, value, ttl_seconds)
    except Exception:
        return


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.delete("/cache/invalidate", response_model=CacheInvalidateResult)
async def invalidate_cache(
    response: Response,
    olt_ip: str = Query(..., description="OLT IP address"),
    board_id: int | None = Query(None, ge=1, le=30),
    pon_id: int | None = Query(None, ge=1, le=16),
    port: str | None = Query(None, description="OLT port identifier"),
    onu_id: int | None = Query(None, ge=1),
    debug: bool = Query(False, description="Include vendor resolution debug headers"),
    vendor: str | None = Query(None, description="Equipment vendor override"),
) -> CacheInvalidateResult:
    try:
        _, _, cache, resolver = _build_dependencies()
        if not cache.enabled():
            raise HTTPException(status_code=503, detail="Redis cache is not configured")
        if board_id is None or pon_id is None:
            if port is None:
                raise HTTPException(status_code=400, detail="board_id and pon_id or port must be provided")
        resolution = await resolver.resolve_details(olt_ip, vendor)
        resolved_vendor = resolution.resolved_vendor
        _apply_vendor_debug_headers(response, debug, resolution)

        keys: list[str] = []
        if board_id is not None and pon_id is not None:
            keys.extend(
                [
                    cache.key("onus", resolved_vendor, olt_ip, board_id, pon_id),
                    cache.key("onus-new", resolved_vendor, olt_ip, board_id, pon_id),
                ]
            )
            if onu_id is not None:
                keys.append(cache.key("onu", resolved_vendor, olt_ip, board_id, pon_id, onu_id))
                keys.append(cache.key("onucli", resolved_vendor, "ssh", olt_ip, board_id, pon_id, onu_id))
                keys.append(cache.key("onucli", resolved_vendor, "telnet", olt_ip, board_id, pon_id, onu_id))
        if port is not None and onu_id is not None:
            keys.append(cache.key("onup", resolved_vendor, olt_ip, port, onu_id))

        deleted = 0
        for key in keys:
            deleted += await cache.delete(key)

        return CacheInvalidateResult(deleted=deleted, keys=keys)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/cache/clear", response_model=CacheInvalidateResult)
async def clear_cache() -> CacheInvalidateResult:
    try:
        _, _, cache, _ = _build_dependencies()
        if not cache.enabled():
            raise HTTPException(status_code=503, detail="Redis cache is not configured")

        deleted, keys = await cache.clear_prefix()
        return CacheInvalidateResult(deleted=deleted, keys=keys)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/onu", response_model=ONUCustomerInfo)
async def get_onu(
    response: Response,
    olt_ip: str = Query(..., description="OLT IP address"),
    board_id: int = Query(..., ge=1, le=30),
    pon_id: int = Query(..., ge=1, le=16),
    onu_id: int = Query(..., ge=1),
    nocache: bool = Query(False, description="Bypass cache read and refresh cached value"),
    debug: bool = Query(False, description="Include vendor resolution debug headers"),
    vendor: str | None = Query(None, description="Equipment vendor override"),
) -> ONUCustomerInfo:
    try:
        settings, service, cache, resolver = _build_dependencies()
        resolution = await resolver.resolve_details(olt_ip, vendor)
        resolved_vendor = resolution.resolved_vendor
        _apply_vendor_debug_headers(response, debug, resolution)
        cache_key = cache.key("onu", resolved_vendor, olt_ip, board_id, pon_id, onu_id)
        if not nocache:
            cached = await _cache_get(cache, cache_key)
            if cached is not None:
                return ONUCustomerInfo.model_validate(cached)
        query = ONUQuery(olt_ip=olt_ip, board_id=board_id, pon_id=pon_id, onu_id=onu_id)
        result = await service.get_onu(query, vendor=resolved_vendor)
        await _cache_set(cache, cache_key, result.model_dump(), settings.cache_ttl_onu)
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/onup", response_model=ONUCustomerInfo)
async def get_onup(
    response: Response,
    olt_ip: str = Query(..., description="OLT IP address"),
    port: str = Query(..., description="OLT port identifier, e.g. gpon-olt_1/1/1 or 1/1/1"),
    onu_id: int = Query(..., ge=1),
    nocache: bool = Query(False, description="Bypass cache read and refresh cached value"),
    debug: bool = Query(False, description="Include vendor resolution debug headers"),
    vendor: str | None = Query(None, description="Equipment vendor override"),
) -> ONUCustomerInfo:
    try:
        settings, service, cache, resolver = _build_dependencies()
        resolution = await resolver.resolve_details(olt_ip, vendor)
        resolved_vendor = resolution.resolved_vendor
        _apply_vendor_debug_headers(response, debug, resolution)
        cache_key = cache.key("onup", resolved_vendor, olt_ip, port, onu_id)
        if not nocache:
            cached = await _cache_get(cache, cache_key)
            if cached is not None:
                return ONUCustomerInfo.model_validate(cached)
        query = ONUPortQuery(olt_ip=olt_ip, port=port, onu_id=onu_id)
        result = await service.get_onup(query, vendor=resolved_vendor)
        await _cache_set(cache, cache_key, result.model_dump(), settings.cache_ttl_onu)
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/onus", response_model=list[ONUInfoPerBoard])
async def get_onus(
    response: Response,
    olt_ip: str = Query(..., description="OLT IP address"),
    board_id: int = Query(..., ge=1, le=30),
    pon_id: int = Query(..., ge=1, le=16),
    nocache: bool = Query(False, description="Bypass cache read and refresh cached value"),
    debug: bool = Query(False, description="Include vendor resolution debug headers"),
    vendor: str | None = Query(None, description="Equipment vendor override"),
) -> list[ONUInfoPerBoard]:
    try:
        settings, service, cache, resolver = _build_dependencies()
        resolution = await resolver.resolve_details(olt_ip, vendor)
        resolved_vendor = resolution.resolved_vendor
        _apply_vendor_debug_headers(response, debug, resolution)
        cache_key = cache.key("onus", resolved_vendor, olt_ip, board_id, pon_id)
        if not nocache:
            cached = await _cache_get(cache, cache_key)
            if cached is not None:
                return ONU_INFO_LIST_ADAPTER.validate_python(cached)
        result = await service.get_onus(olt_ip=olt_ip, board_id=board_id, pon_id=pon_id, vendor=resolved_vendor)
        await _cache_set(cache, cache_key, [item.model_dump() for item in result], settings.cache_ttl_onus)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/onus-new", response_model=list[ONUInfoPerBoard])
async def get_onus_new(
    response: Response,
    olt_ip: str = Query(..., description="OLT IP address"),
    board_id: int = Query(..., ge=1, le=30),
    pon_id: int = Query(..., ge=1, le=16),
    nocache: bool = Query(False, description="Bypass cache read and refresh cached value"),
    debug: bool = Query(False, description="Include vendor resolution debug headers"),
    vendor: str | None = Query(None, description="Equipment vendor override"),
) -> list[ONUInfoPerBoard]:
    try:
        settings, service, cache, resolver = _build_dependencies()
        resolution = await resolver.resolve_details(olt_ip, vendor)
        resolved_vendor = resolution.resolved_vendor
        _apply_vendor_debug_headers(response, debug, resolution)
        cache_key = cache.key("onus-new", resolved_vendor, olt_ip, board_id, pon_id)
        if not nocache:
            cached = await _cache_get(cache, cache_key)
            if cached is not None:
                return ONU_INFO_LIST_ADAPTER.validate_python(cached)
        result = await service.get_onus_new(olt_ip=olt_ip, board_id=board_id, pon_id=pon_id, vendor=resolved_vendor)
        await _cache_set(cache, cache_key, [item.model_dump() for item in result], settings.cache_ttl_onus_new)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/onucli", response_model=ONUCLIInfo)
async def get_onu_cli(
    response: Response,
    olt_ip: str = Query(..., description="OLT IP address"),
    board_id: int = Query(..., ge=1, le=30),
    pon_id: int = Query(..., ge=1, le=16),
    onu_id: int = Query(..., ge=1),
    access: Literal["ssh", "telnet"] = Query("ssh", description="CLI transport"),
    nocache: bool = Query(False, description="Bypass cache read and refresh cached value"),
    debug: bool = Query(False, description="Include vendor resolution debug headers"),
    vendor: str | None = Query(None, description="Equipment vendor override"),
) -> ONUCLIInfo:
    try:
        settings, service, cache, resolver = _build_dependencies()
        resolution = await resolver.resolve_details(olt_ip, vendor)
        resolved_vendor = resolution.resolved_vendor
        _apply_vendor_debug_headers(response, debug, resolution)
        cache_key = cache.key("onucli", resolved_vendor, access, olt_ip, board_id, pon_id, onu_id)
        if not nocache:
            cached = await _cache_get(cache, cache_key)
            if cached is not None:
                return ONUCLIInfo.model_validate(cached)
        result = await service.get_onu_cli(
            ONUQuery(olt_ip=olt_ip, board_id=board_id, pon_id=pon_id, onu_id=onu_id),
            access=access,
            vendor=resolved_vendor,
        )
        await _cache_set(cache, cache_key, result.model_dump(), settings.cache_ttl_onucli)
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
