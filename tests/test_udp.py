"""Tests for the UDP transport over a fake in-memory datagram endpoint.

An ``endpoint_factory`` injects a fake ``(transport, protocol)`` pair, so these tests
exercise the framing and lifecycle with no real sockets and stay in the hermetic core CI.
The fake transport records what was sent; inbound datagrams (and socket errors) are pushed
onto the real protocol's queue the way asyncio would deliver them.
"""

from __future__ import annotations

import asyncio

import pytest

from mcp_edge.transports import TransportError, UdpTransport
from mcp_edge.transports.serial import MAX_FRAME_SIZE, encode_frame
from mcp_edge.transports.udp import _UdpClientProtocol


class _FakeDatagramTransport:
    """Minimal asyncio DatagramTransport stand-in that records sent datagrams."""

    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self.close_calls = 0
        self._closing = False

    def sendto(self, data: bytes, addr: object = None) -> None:
        self.sent.append(bytes(data))

    def close(self) -> None:
        self.close_calls += 1
        self._closing = True

    def is_closing(self) -> bool:
        return self._closing


def _udp(transport: _FakeDatagramTransport, protocol: _UdpClientProtocol) -> UdpTransport:
    return UdpTransport(
        "device.local",
        8765,
        timeout=0.1,
        endpoint_factory=lambda: (transport, protocol),
    )


def _datagram_into(protocol: _UdpClientProtocol, payload: bytes) -> None:
    protocol.datagram_received(encode_frame(payload), ("device.local", 8765))


async def test_open_uses_endpoint_factory() -> None:
    transport = _udp(_FakeDatagramTransport(), _UdpClientProtocol())
    await transport.open()
    assert transport.is_open
    await transport.close()


async def test_is_open_tracks_lifecycle() -> None:
    transport = _udp(_FakeDatagramTransport(), _UdpClientProtocol())
    assert not transport.is_open
    await transport.open()
    assert transport.is_open
    await transport.close()
    assert not transport.is_open


async def test_close_closes_transport() -> None:
    datagram_transport = _FakeDatagramTransport()
    transport = _udp(datagram_transport, _UdpClientProtocol())
    await transport.open()
    await transport.close()
    assert datagram_transport.close_calls == 1
    assert not transport.is_open


async def test_open_and_close_are_idempotent() -> None:
    datagram_transport, protocol = _FakeDatagramTransport(), _UdpClientProtocol()
    connects = []

    def factory() -> tuple[_FakeDatagramTransport, _UdpClientProtocol]:
        connects.append(1)
        return datagram_transport, protocol

    transport = UdpTransport("device.local", 8765, endpoint_factory=factory)
    await transport.open()
    await transport.open()
    assert transport.is_open
    assert len(connects) == 1
    await transport.close()
    await transport.close()
    assert not transport.is_open
    assert datagram_transport.close_calls == 1


async def test_send_sends_framed_datagram() -> None:
    datagram_transport = _FakeDatagramTransport()
    transport = _udp(datagram_transport, _UdpClientProtocol())
    async with transport:
        await transport.send(b"hello udp")
    assert datagram_transport.sent == [encode_frame(b"hello udp")]


async def test_receive_decodes_datagram() -> None:
    protocol = _UdpClientProtocol()
    transport = _udp(_FakeDatagramTransport(), protocol)
    async with transport:
        _datagram_into(protocol, b"hello back")
        assert await transport.receive() == b"hello back"


async def test_receive_returns_datagrams_in_order() -> None:
    protocol = _UdpClientProtocol()
    transport = _udp(_FakeDatagramTransport(), protocol)
    async with transport:
        _datagram_into(protocol, b"one")
        _datagram_into(protocol, b"two")
        assert await transport.receive() == b"one"
        assert await transport.receive() == b"two"


async def test_receive_handles_empty_payload() -> None:
    protocol = _UdpClientProtocol()
    transport = _udp(_FakeDatagramTransport(), protocol)
    async with transport:
        _datagram_into(protocol, b"")
        assert await transport.receive() == b""


async def test_request_returns_reply() -> None:
    datagram_transport, protocol = _FakeDatagramTransport(), _UdpClientProtocol()
    transport = _udp(datagram_transport, protocol)
    async with transport:
        _datagram_into(protocol, b"pong")
        assert await transport.request(b"ping") == b"pong"
    assert datagram_transport.sent == [encode_frame(b"ping")]


async def test_receive_awaits_datagram() -> None:
    protocol = _UdpClientProtocol()
    transport = _udp(_FakeDatagramTransport(), protocol)
    async with transport:
        pending = asyncio.create_task(transport.receive())
        await asyncio.sleep(0)  # let receive() start and block on the queue
        assert not pending.done()
        _datagram_into(protocol, b"later")
        assert await pending == b"later"


async def test_receive_times_out_without_a_datagram() -> None:
    transport = _udp(_FakeDatagramTransport(), _UdpClientProtocol())
    async with transport:
        with pytest.raises(TransportError):
            await transport.receive()


async def test_receive_raises_on_socket_error() -> None:
    protocol = _UdpClientProtocol()
    transport = _udp(_FakeDatagramTransport(), protocol)
    async with transport:
        protocol.error_received(OSError("destination unreachable"))
        with pytest.raises(TransportError):
            await transport.receive()


async def test_send_while_closed_raises() -> None:
    transport = _udp(_FakeDatagramTransport(), _UdpClientProtocol())
    with pytest.raises(TransportError):
        await transport.send(b"x")


async def test_receive_while_closed_raises() -> None:
    transport = _udp(_FakeDatagramTransport(), _UdpClientProtocol())
    with pytest.raises(TransportError):
        await transport.receive()


async def test_send_rejects_oversized_frame() -> None:
    transport = _udp(_FakeDatagramTransport(), _UdpClientProtocol())
    async with transport:
        with pytest.raises(TransportError):
            await transport.send(b"\x00" * (MAX_FRAME_SIZE + 1))


async def test_protocol_queues_datagrams_and_errors() -> None:
    protocol = _UdpClientProtocol()
    protocol.datagram_received(b"data", ("device.local", 8765))
    error = OSError("boom")
    protocol.error_received(error)
    assert protocol.queue.get_nowait() == b"data"
    assert protocol.queue.get_nowait() is error
