"""Tests for the gateway-facing device clients."""

from __future__ import annotations

import pytest

from mcp_edge.buffer import OfflineBuffer
from mcp_edge.client import DeviceError, MCPLiteClient
from mcp_edge.devices import SimulatedDevice
from mcp_edge.pool import ConnectionPool
from mcp_edge.transports import LoopbackTransport, Transport, TransportError


def _device() -> SimulatedDevice:
    device = SimulatedDevice("sensor-01")
    device.add_tool("read_temp", lambda args: 21.5, description="temp in C")
    device.add_resource("sensor://battery", {"percent": 87})
    return device


class _DownTransport(Transport):
    """An open transport whose every request fails, as if the device dropped off."""

    def __init__(self) -> None:
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open

    async def open(self) -> None:
        self._open = True

    async def close(self) -> None:
        self._open = False

    async def send(self, frame: bytes) -> None:
        raise TransportError("device unreachable")

    async def receive(self) -> bytes:
        raise TransportError("device unreachable")


class _FlakyTransport(Transport):
    """Forwards frames to a device, but fails every request while ``reachable`` is False."""

    def __init__(self, device: SimulatedDevice) -> None:
        self._device = device
        self._open = False
        self._pending = b""
        self.reachable = True

    @property
    def is_open(self) -> bool:
        return self._open

    async def open(self) -> None:
        self._open = True

    async def close(self) -> None:
        self._open = False

    async def send(self, frame: bytes) -> None:
        if not self.reachable:
            raise TransportError("device unreachable")
        self._pending = await self._device.handle(frame)

    async def receive(self) -> bytes:
        return self._pending


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


def test_requires_exactly_one_transport_source() -> None:
    with pytest.raises(ValueError):
        MCPLiteClient()
    pool = ConnectionPool(lambda key: LoopbackTransport(_device().handle))
    with pytest.raises(ValueError):
        MCPLiteClient(LoopbackTransport(_device().handle), pool=pool)


def test_pooled_requires_key() -> None:
    pool = ConnectionPool(lambda key: LoopbackTransport(_device().handle))
    with pytest.raises(ValueError):
        MCPLiteClient(pool=pool)


async def test_pooled_client_lists_tools() -> None:
    device = _device()
    pool = ConnectionPool(lambda key: LoopbackTransport(device.handle))
    tools = await MCPLiteClient.pooled(pool, "sensor-01").list_tools()
    assert [tool["name"] for tool in tools] == ["read_temp"]
    assert "sensor-01" in pool
    await pool.aclose()


async def test_pooled_client_reuses_one_connection() -> None:
    device = _device()
    pool = ConnectionPool(lambda key: LoopbackTransport(device.handle))
    client = MCPLiteClient.pooled(pool, "sensor-01")
    await client.list_tools()
    await client.call_tool("read_temp", {})
    assert len(pool) == 1
    await pool.aclose()


async def test_send_command_delivers_when_reachable() -> None:
    async with LoopbackTransport(_device().handle) as transport:
        delivered = await MCPLiteClient(transport).send_command("read_temp", {})
    assert delivered is True


async def test_send_command_without_buffer_propagates_transport_error() -> None:
    transport = _DownTransport()
    await transport.open()
    with pytest.raises(TransportError):
        await MCPLiteClient(transport).send_command("read_temp", {})


async def test_send_command_buffers_offline_then_flushes_on_recovery() -> None:
    buffer: OfflineBuffer[tuple[str, dict]] = OfflineBuffer()
    transport = _FlakyTransport(_device())
    await transport.open()
    client = MCPLiteClient(transport, buffer=buffer)

    transport.reachable = False
    assert await client.send_command("read_temp", {}) is False
    assert await client.send_command("read_temp", {}) is False
    assert len(buffer) == 2

    transport.reachable = True
    assert await client.flush() == 2
    assert len(buffer) == 0


async def test_flush_drops_rejected_commands() -> None:
    buffer: OfflineBuffer[tuple[str, dict]] = OfflineBuffer()
    transport = _FlakyTransport(_device())
    await transport.open()
    client = MCPLiteClient(transport, buffer=buffer)

    transport.reachable = False
    await client.send_command("does_not_exist", {})
    assert len(buffer) == 1

    transport.reachable = True
    assert await client.flush() == 1
    assert len(buffer) == 0


async def test_flush_without_buffer_returns_zero() -> None:
    async with LoopbackTransport(_device().handle) as transport:
        assert await MCPLiteClient(transport).flush() == 0
