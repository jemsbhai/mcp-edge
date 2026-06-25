"""Tests for the device registry."""

from __future__ import annotations

from typing import Any

import pytest

from mcp_edge.client import DeviceClient
from mcp_edge.registry import DeviceRegistry, RegistryError
from mcp_edge.tiers import Tier


class _StubClient(DeviceClient):
    async def list_tools(self) -> list[dict[str, Any]]:
        return []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return None

    async def read_resource(self, uri: str) -> Any:
        return None


def test_register_and_get() -> None:
    registry = DeviceRegistry()
    client = _StubClient()
    registry.register("dev-a", client, Tier.SMART_NODE)
    assert "dev-a" in registry
    assert len(registry) == 1
    entry = registry.get("dev-a")
    assert entry.tier is Tier.SMART_NODE
    assert entry.client is client
    assert entry.connected


def test_duplicate_registration_raises() -> None:
    registry = DeviceRegistry()
    registry.register("dev-a", _StubClient(), Tier.SMART_NODE)
    with pytest.raises(RegistryError):
        registry.register("dev-a", _StubClient(), Tier.SMART_NODE)


def test_get_unknown_raises() -> None:
    with pytest.raises(RegistryError):
        DeviceRegistry().get("ghost")


def test_unregister() -> None:
    registry = DeviceRegistry()
    registry.register("dev-a", _StubClient(), Tier.EDGE_COMPUTER)
    registry.unregister("dev-a")
    assert "dev-a" not in registry
    assert registry.names() == []


def test_iter_yields_registered_devices() -> None:
    registry = DeviceRegistry()
    registry.register("a", _StubClient(), Tier.SMART_NODE)
    registry.register("b", _StubClient(), Tier.EDGE_COMPUTER)
    assert sorted(device.name for device in registry) == ["a", "b"]
