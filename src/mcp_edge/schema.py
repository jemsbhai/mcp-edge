"""Schema caching for the gateway.

Fetching a device's tool list over a constrained link is comparatively expensive, and
the list rarely changes, so the gateway caches each device's ``tools/list`` result and
reuses it until explicitly invalidated (for example, when a device reconnects).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

ToolList = list[dict[str, Any]]
ToolFetcher = Callable[[], Awaitable[ToolList]]


class SchemaCache:
    """Caches device tool specifications keyed by device name."""

    def __init__(self) -> None:
        self._cache: dict[str, ToolList] = {}

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, device_name: object) -> bool:
        return device_name in self._cache

    async def get(self, device_name: str, fetch: ToolFetcher) -> ToolList:
        """Return cached tools for ``device_name``, fetching and caching on a miss."""
        cached = self._cache.get(device_name)
        if cached is None:
            cached = await fetch()
            self._cache[device_name] = cached
        return cached

    def invalidate(self, device_name: str) -> None:
        """Drop the cached tools for ``device_name`` (a no-op if absent)."""
        self._cache.pop(device_name, None)

    def clear(self) -> None:
        """Drop all cached tools."""
        self._cache.clear()


__all__ = ["SchemaCache", "ToolList", "ToolFetcher"]
