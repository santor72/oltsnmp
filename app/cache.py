from __future__ import annotations

import json
from typing import Any


class CacheClient:
    def __init__(self, host: str, port: int, password: str, db: int, prefix: str) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.prefix = prefix
        self._client: Any | None = None

    def enabled(self) -> bool:
        return bool(self.host)

    def key(self, *parts: object) -> str:
        normalized = ":".join(str(part).replace(" ", "_") for part in parts)
        return f"{self.prefix}:{normalized}"

    def _get_client(self) -> Any:
        if self._client is None:
            from redis.asyncio import Redis  # type: ignore

            self._client = Redis(
                host=self.host,
                port=self.port,
                password=self.password or None,
                db=self.db,
                decode_responses=True,
            )
        return self._client

    async def get_json(self, key: str) -> Any | None:
        if not self.enabled():
            return None
        data = await self._get_client().get(key)
        return json.loads(data) if data else None

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        if not self.enabled():
            return
        await self._get_client().set(key, json.dumps(value), ex=ttl_seconds)

    async def delete(self, key: str) -> int:
        if not self.enabled():
            return 0
        return int(await self._get_client().delete(key))

    async def clear_prefix(self) -> tuple[int, list[str]]:
        if not self.enabled():
            return 0, []

        client = self._get_client()
        pattern = f"{self.prefix}:*"
        cursor = 0
        keys: list[str] = []

        while True:
            cursor, batch = await client.scan(cursor=cursor, match=pattern, count=200)
            keys.extend(batch)
            if cursor == 0:
                break

        if not keys:
            return 0, []

        deleted = int(await client.delete(*keys))
        return deleted, keys
