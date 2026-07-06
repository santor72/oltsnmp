from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    snmp_community: str
    snmp_port: int = 161
    snmp_timeout: float = 2.0
    snmp_retries: int = 1
    olt_timezone: str = "Asia/Jakarta"
    cli_username: str = ""
    cli_password: str = ""
    cli_secret: str = ""
    cli_ssh_port: int = 22
    cli_telnet_port: int = 23
    cli_timeout: float = 10.0
    redis_host: str = ""
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    redis_prefix: str = "zte-olt-fastapi"
    cache_ttl_onu: int = 60
    cache_ttl_onus: int = 300
    cache_ttl_onus_new: int = 300
    cache_ttl_onucli: int = 60
    default_vendor: str = "zte"
    zabbix_url: str = ""
    zabbix_token: str = ""
    zabbix_timeout: float = 5.0
    debug: bool = False


def get_settings() -> Settings:
    community = os.getenv("SNMP_COMMUNITY", "").strip()
    if not community:
        raise RuntimeError("SNMP_COMMUNITY environment variable is required")

    return Settings(
        snmp_community=community,
        snmp_port=int(os.getenv("SNMP_PORT", "161")),
        snmp_timeout=float(os.getenv("SNMP_TIMEOUT", "2")),
        snmp_retries=int(os.getenv("SNMP_RETRIES", "1")),
        olt_timezone=os.getenv("OLT_TIMEZONE", "Asia/Jakarta").strip() or "Asia/Jakarta",
        cli_username=os.getenv("CLI_USERNAME", "").strip(),
        cli_password=os.getenv("CLI_PASSWORD", "").strip(),
        cli_secret=os.getenv("CLI_SECRET", "").strip(),
        cli_ssh_port=int(os.getenv("CLI_SSH_PORT", "22")),
        cli_telnet_port=int(os.getenv("CLI_TELNET_PORT", "23")),
        cli_timeout=float(os.getenv("CLI_TIMEOUT", "10")),
        redis_host=os.getenv("REDIS_HOST", "").strip(),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        redis_password=os.getenv("REDIS_PASSWORD", "").strip(),
        redis_db=int(os.getenv("REDIS_DB", "0")),
        redis_prefix=os.getenv("REDIS_PREFIX", "zte-olt-fastapi").strip() or "zte-olt-fastapi",
        cache_ttl_onu=int(os.getenv("CACHE_TTL_ONU", "60")),
        cache_ttl_onus=int(os.getenv("CACHE_TTL_ONUS", "300")),
        cache_ttl_onus_new=int(os.getenv("CACHE_TTL_ONUS_NEW", "300")),
        cache_ttl_onucli=int(os.getenv("CACHE_TTL_ONUCLI", "60")),
        default_vendor=os.getenv("DEFAULT_VENDOR", "zte").strip() or "zte",
        zabbix_url=os.getenv("ZABBIX_URL", "").strip(),
        zabbix_token=os.getenv("ZABBIX_TOKEN", "").strip(),
        zabbix_timeout=float(os.getenv("ZABBIX_TIMEOUT", "5")),
        debug=os.getenv("DEBUG", "").strip().lower() in {"1", "true", "yes", "on"},
    )
