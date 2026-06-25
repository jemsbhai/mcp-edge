"""Tests for exposing the gateway as an MCP server."""

from __future__ import annotations

import mcp.types as types
from mcp.server.lowlevel import Server

from mcp_edge.client import MCPLiteClient
from mcp_edge.devices import SimulatedDevice
from mcp_edge.gateway import Gateway
from mcp_edge.registry import DeviceRegistry
from mcp_edge.server import build_server, call_tool_payload, list_tools_payload
from mcp_edge.tiers import Tier
from mcp_edge.transports import LoopbackTransport


async def _gateway() -> Gateway:
    registry = DeviceRegistry()
    device = SimulatedDevice("sensor-01")
    device.add_tool(
        "read_temp",
        lambda args: {"celsius": 21.5},
        description="Read the temperature.",
        input_schema={"type": "object", "properties": {}},
    )
    transport = LoopbackTransport(device.handle)
    await transport.open()
    registry.register("sensor-01", MCPLiteClient(transport), Tier.SMART_NODE)
    return Gateway(registry)


async def test_list_tools_payload_returns_mcp_tools() -> None:
    tools = await list_tools_payload(await _gateway())
    assert all(isinstance(tool, types.Tool) for tool in tools)
    assert [tool.name for tool in tools] == ["sensor-01/read_temp"]
    assert tools[0].inputSchema["type"] == "object"


async def test_call_tool_payload_wraps_result_as_text() -> None:
    content = await call_tool_payload(await _gateway(), "sensor-01/read_temp", {})
    assert len(content) == 1
    block = content[0]
    assert isinstance(block, types.TextContent)
    assert block.text == '{"celsius": 21.5}'


def test_build_server_returns_a_server() -> None:
    server = build_server(Gateway(), name="edge-test")
    assert isinstance(server, Server)
