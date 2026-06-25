"""Tests for the gateway-facing device clients."""

from __future__ import annotations

import pytest

from mcp_edge.client import DeviceError, MCPLiteClient
from mcp_edge.devices import SimulatedDevice
from mcp_edge.transports import LoopbackTransport


def _device() -> SimulatedDevice:
    device = SimulatedDevice("sensor-01")
    device.add_tool("read_temp", lambda args: 21.5, description="temp in C")
    device.add_resource("sensor://battery", {"percent": 87})
    return device


async def test_list_tools() -> None:
    async with LoopbackTransport(_device().handle) as transport:
        tools = await MCPLiteClient(transport).list_tools()
    assert [tool["name"] for tool in tools] == ["read_temp"]


async def test_call_tool() -> None:
    async with LoopbackTransport(_device().handle) as transport:
        content = await MCPLiteClient(transport).call_tool("read_temp", {})
    assert content == 21.5


async def test_read_resource() -> None:
    async with LoopbackTransport(_device().handle) as transport:
        contents = await MCPLiteClient(transport).read_resource("sensor://battery")
    assert contents == {"percent": 87}


async def test_error_response_raises_device_error() -> None:
    async with LoopbackTransport(_device().handle) as transport:
        client = MCPLiteClient(transport)
        with pytest.raises(DeviceError) as excinfo:
            await client.call_tool("missing", {})
    assert excinfo.value.code is not None
