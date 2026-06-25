"""Tests for the simulated MCP-Lite device, including end-to-end over loopback."""

from __future__ import annotations

from mcp_edge import mcplite
from mcp_edge.devices import SimulatedDevice
from mcp_edge.mcplite import Request, Response
from mcp_edge.transports import LoopbackTransport


def _make_device() -> SimulatedDevice:
    device = SimulatedDevice("sensor-01")
    device.add_tool(
        "read_temp",
        lambda args: 21.5,
        description="Read the temperature in Celsius.",
        input_schema={"type": "object", "properties": {}},
    )
    device.add_resource("sensor://battery", {"percent": 87})
    return device


async def _call(device: SimulatedDevice, request: Request) -> Response:
    async with LoopbackTransport(device.handle) as transport:
        return Response.from_bytes(await transport.request(request.to_bytes()))


async def test_tools_list_over_loopback() -> None:
    response = await _call(_make_device(), Request(1, mcplite.TOOLS_LIST))
    result = response.result
    assert result is not None
    tools = result["tools"]
    assert [tool["name"] for tool in tools] == ["read_temp"]
    assert tools[0]["inputSchema"]["type"] == "object"


async def test_tools_call_invokes_handler() -> None:
    request = Request(2, mcplite.TOOLS_CALL, {"name": "read_temp", "arguments": {}})
    response = await _call(_make_device(), request)
    assert response.result == {"content": 21.5}


async def test_tools_call_unknown_tool_errors() -> None:
    response = await _call(_make_device(), Request(3, mcplite.TOOLS_CALL, {"name": "nope"}))
    error = response.error
    assert error is not None
    assert error["code"] == mcplite.TOOL_NOT_FOUND


async def test_resources_read_over_loopback() -> None:
    request = Request(4, mcplite.RESOURCES_READ, {"uri": "sensor://battery"})
    response = await _call(_make_device(), request)
    assert response.result == {"contents": {"percent": 87}}


async def test_unknown_method_errors() -> None:
    response = await _call(_make_device(), Request(5, "prompts/list"))
    error = response.error
    assert error is not None
    assert error["code"] == mcplite.METHOD_NOT_FOUND
