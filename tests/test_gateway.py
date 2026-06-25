"""Tests for the gateway: composite tool namespace and call routing."""

from __future__ import annotations

import pytest

from mcp_edge.client import MCPLiteClient
from mcp_edge.devices import SimulatedDevice
from mcp_edge.gateway import Gateway, GatewayError, split_qualified
from mcp_edge.registry import DeviceRegistry
from mcp_edge.tiers import Tier
from mcp_edge.transports import LoopbackTransport


async def _registry_with_two_devices() -> DeviceRegistry:
    registry = DeviceRegistry()

    sensor = SimulatedDevice("sensor-01")
    sensor.add_tool("read_temp", lambda args: 21.5, description="temp in C")
    sensor_transport = LoopbackTransport(sensor.handle)
    await sensor_transport.open()
    registry.register("sensor-01", MCPLiteClient(sensor_transport), Tier.SMART_NODE)

    ring = SimulatedDevice("ring")
    ring.add_tool("heart_rate", lambda args: 72)
    ring.add_resource("ring://steps", {"steps": 4096})
    ring_transport = LoopbackTransport(ring.handle)
    await ring_transport.open()
    registry.register("ring", MCPLiteClient(ring_transport), Tier.BLE_WEARABLE)

    return registry


async def test_list_tools_prefixes_and_aggregates() -> None:
    gateway = Gateway(await _registry_with_two_devices())
    names = [tool["name"] for tool in await gateway.list_tools()]
    assert names == ["sensor-01/read_temp", "ring/heart_rate"]


async def test_call_tool_routes_to_owning_device() -> None:
    gateway = Gateway(await _registry_with_two_devices())
    assert await gateway.call_tool("sensor-01/read_temp", {}) == 21.5
    assert await gateway.call_tool("ring/heart_rate", {}) == 72


async def test_read_resource_routes() -> None:
    gateway = Gateway(await _registry_with_two_devices())
    assert await gateway.read_resource("ring", "ring://steps") == {"steps": 4096}


async def test_unknown_device_raises_gateway_error() -> None:
    gateway = Gateway(await _registry_with_two_devices())
    with pytest.raises(GatewayError):
        await gateway.call_tool("ghost/whatever", {})


async def test_disconnected_device_is_skipped_and_unroutable() -> None:
    registry = await _registry_with_two_devices()
    registry.get("ring").connected = False
    gateway = Gateway(registry)
    names = [tool["name"] for tool in await gateway.list_tools()]
    assert names == ["sensor-01/read_temp"]
    with pytest.raises(GatewayError):
        await gateway.call_tool("ring/heart_rate", {})


def test_split_qualified_rejects_malformed() -> None:
    with pytest.raises(GatewayError):
        split_qualified("noslash")
