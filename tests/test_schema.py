"""Tests for schema caching."""

from __future__ import annotations

from typing import Any

from mcp_edge.client import DeviceClient
from mcp_edge.gateway import Gateway
from mcp_edge.registry import DeviceRegistry
from mcp_edge.schema import SchemaCache
from mcp_edge.tiers import Tier


async def test_cache_fetches_once_then_serves_cached() -> None:
    calls = 0

    async def fetch() -> list[dict[str, Any]]:
        nonlocal calls
        calls += 1
        return [{"name": "t"}]

    cache = SchemaCache()
    assert await cache.get("dev", fetch) == [{"name": "t"}]
    assert await cache.get("dev", fetch) == [{"name": "t"}]
    assert calls == 1


async def test_invalidate_forces_refetch() -> None:
    calls = 0

    async def fetch() -> list[dict[str, Any]]:
        nonlocal calls
        calls += 1
        return [{"name": "t"}]

    cache = SchemaCache()
    await cache.get("dev", fetch)
    cache.invalidate("dev")
    await cache.get("dev", fetch)
    assert calls == 2


def test_invalidate_unknown_is_noop() -> None:
    cache = SchemaCache()
    cache.invalidate("ghost")
    assert "ghost" not in cache


class _CountingClient(DeviceClient):
    def __init__(self) -> None:
        self.calls = 0

    async def list_tools(self) -> list[dict[str, Any]]:
        self.calls += 1
        return [{"name": "ping", "description": "", "inputSchema": {}}]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return None

    async def read_resource(self, uri: str) -> Any:
        return None


async def test_gateway_caches_until_refreshed() -> None:
    registry = DeviceRegistry()
    client = _CountingClient()
    registry.register("dev", client, Tier.SMART_NODE)
    gateway = Gateway(registry)

    assert [tool["name"] for tool in await gateway.list_tools()] == ["dev/ping"]
    await gateway.list_tools()
    assert client.calls == 1

    gateway.refresh("dev")
    await gateway.list_tools()
    assert client.calls == 2
