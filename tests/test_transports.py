"""Tests for the transport channel and the in-process loopback transport."""

from __future__ import annotations

import pytest

from mcp_edge.transports import LoopbackTransport, TransportError


async def _echo(frame: bytes) -> bytes:
    return frame


async def test_request_returns_handler_response() -> None:
    async def handler(frame: bytes) -> bytes:
        return frame.upper()

    transport = LoopbackTransport(handler)
    async with transport:
        reply = await transport.request(b"ping")
    assert reply == b"PING"


async def test_send_then_receive() -> None:
    transport = LoopbackTransport(_echo)
    await transport.open()
    await transport.send(b"hello")
    assert await transport.receive() == b"hello"
    await transport.close()


async def test_context_manager_opens_and_closes() -> None:
    transport = LoopbackTransport(_echo)
    assert not transport.is_open
    async with transport as open_transport:
        assert open_transport.is_open
    assert not transport.is_open


async def test_send_while_closed_raises() -> None:
    transport = LoopbackTransport(_echo)
    with pytest.raises(TransportError):
        await transport.send(b"x")


async def test_receive_while_closed_raises() -> None:
    transport = LoopbackTransport(_echo)
    with pytest.raises(TransportError):
        await transport.receive()
