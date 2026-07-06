from __future__ import annotations

import asyncio
from typing import Any


class ZTECLITransport:
    default_fallback_access = "telnet"
    ssh_device_type = "zte_zxros"
    telnet_device_type = "zte_zxros_telnet"

    def __init__(
        self,
        username: str,
        password: str,
        secret: str,
        ssh_port: int,
        telnet_port: int,
        timeout: float,
    ) -> None:
        self.username = username
        self.password = password
        self.secret = secret
        self.ssh_port = ssh_port
        self.telnet_port = telnet_port
        self.timeout = timeout

    def _validate(self) -> None:
        if not self.username:
            raise RuntimeError("CLI_USERNAME environment variable is required for CLI endpoint")
        if not self.password:
            raise RuntimeError("CLI_PASSWORD environment variable is required for CLI endpoint")

    def _connect_handler(self) -> Any:
        try:
            from netmiko import ConnectHandler  # type: ignore
        except ImportError as exc:
            raise RuntimeError("netmiko is required. Install dependencies from python_fastapi/requirements.txt") from exc
        return ConnectHandler

    async def run_commands(self, host: str, commands: list[str], access: str) -> dict[str, str]:
        self._validate()
        return await asyncio.to_thread(self._run_commands_sync, host, commands, access)

    def _run_commands_sync(self, host: str, commands: list[str], access: str) -> dict[str, str]:
        connect_handler = self._connect_handler()
        if access == "telnet":
            device_type = self.telnet_device_type
            port = self.telnet_port
        else:
            device_type = self.ssh_device_type
            port = self.ssh_port
        connection = connect_handler(
            device_type=device_type,
            host=host,
            username=self.username,
            password=self.password,
            secret=self.secret or None,
            port=port,
            timeout=self.timeout,
            conn_timeout=self.timeout,
            banner_timeout=self.timeout,
            auth_timeout=self.timeout,
            fast_cli=False,
        )
        try:
            if self.secret:
                connection.enable()
            return {
                command: connection.send_command(command, expect_string=r"#", read_timeout=self.timeout * 4)
                for command in commands
            }
        finally:
            connection.disconnect()
