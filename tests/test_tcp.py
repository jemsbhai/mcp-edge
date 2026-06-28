"""Tests for the TCP transport over fake in-memory asyncio streams.

A ``connection_factory`` injects a fake ``(reader, writer)`` pair, so these tests exercise
the framing and lifecycle with no real sockets and stay in the hermetic core CI. The fake
reader is fed bytes the way a peer would send them; the fake writer records what the
transport sent.
"""

from __future__ import annotations

import asyncio

import pytest

from mcp_edge.transports import TcpTransport, TransportError
from mcp_edge.transports.serial import MAX_FRAME_SIZE, encode_frame


class _FakeReader:
    """Minimal asyncio.StreamReader stand-in backed by an in-memory buffer."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._eof = False
        self._available = asyncio.Event()

    def feed(self, data: bytes) -> None:
        self._buffer.extend(data)
        self._available.set()

    def feed_eof(self) -> None:
        self._eof = True
        self._available.set()

    async def readexactly(self, n: int) -> bytes:
        while len(self._buffer) < n:
            if self._eof:
                raise asyncio.IncompleteReadError(bytes(self._buffer), n)
            self._available.clear()
            await self._available.wait()
        chunk = bytes(self._buffer[:n])
        del self._buffer[:n]
        return chunk


class _FakeWriter:
    """Minimal asyncio.StreamWriter stand-in that records what was written."""

    def __init__(self) -> None:
        self.written = bytearray()
        self.drain_calls = 0
        self.close_calls = 0
        self._closing = False

    def write(self, data: bytes) -> None:
        self.written.extend(data)

    async def drain(self) -> None:
        self.drain_calls += 1

    def close(self) -> None:
        self.close_calls += 1
        self._closing = True

    async def wait_closed(self) -> None:
        pass

    def is_closing(self) -> bool:
        return self._closing


def _transport(reader: _FakeReader, writer: _FakeWriter) -> TcpTransport:
    return TcpTransport("device.local", 8765, connection_factory=lambda: (reader, writer))


def _frame_into(reader: _FakeReader, payload: bytes) -> None:
    reader.feed(encode_frame(payload))


async def test_open_uses_connection_factory() -> None:
    transport = _transport(_FakeReader(), _FakeWriter())
    await transport.open()
    assert transport.is_open
    await transport.close()


async def test_is_open_tracks_lifecycle() -> None:
    transport = _transport(_FakeReader(), _FakeWriter())
    assert not transport.is_open
    await transport.open()
    assert transport.is_open
    await transport.close()
    assert not transport.is_open


async def test_close_closes_writer() -> None:
    writer = _FakeWriter()
    transport = _transport(_FakeReader(), writer)
    await transport.open()
    await transport.close()
    assert writer.close_calls == 1
    assert not transport.is_open


async def test_open_and_close_are_idempotent() -> None:
    reader, writer = _FakeReader(), _FakeWriter()
    connects = []

    def factory() -> tuple[_FakeReader, _FakeWriter]:
        connects.append(1)
        return reader, writer

    transport = TcpTransport("device.local", 8765, connection_factory=factory)
    await transport.open()
    await transport.open()
    assert transport.is_open
    assert len(connects) == 1
    await transport.close()
    await transport.close()
    assert not transport.is_open
    assert writer.close_calls == 1


async def test_send_writes_framed_and_drains() -> None:
    writer = _FakeWriter()
    transport = _transport(_FakeReader(), writer)
    async with transport:
        await transport.send(b"hello tcp")
    assert writer.written == encode_frame(b"hello tcp")
    assert writer.drain_calls >= 1


async def test_receive_reads_framed() -> None:
    reader = _FakeReader()
    transport = _transport(reader, _FakeWriter())
    async with transport:
        _frame_into(reader, b"hello back")
        assert await transport.receive() == b"hello back"


async def test_receive_reads_multiple_frames_in_order() -> None:
    reader = _FakeReader()
    transport = _transport(reader, _FakeWriter())
    async with transport:
        _frame_into(reader, b"one")
        _frame_into(reader, b"two")
        assert await transport.receive() == b"one"
        assert await transport.receive() == b"two"


async def test_receive_handles_empty_payload() -> None:
    reader = _FakeReader()
    transport = _transport(reader, _FakeWriter())
    async with transport:
        _frame_into(reader, b"")
        assert await transport.receive() == b""


async def test_request_returns_reply() -> None:
    reader, writer = _FakeReader(), _FakeWriter()
    transport = _transport(reader, writer)
    async with transport:
        _frame_into(reader, b"pong")
        assert await transport.request(b"ping") == b"pong"
    assert writer.written == encode_frame(b"ping")


async def test_receive_awaits_data() -> None:
    reader = _FakeReader()
    transport = _transport(reader, _FakeWriter())
    async with transport:
        pending = asyncio.create_task(transport.receive())
        await asyncio.sleep(0)  # let receive() start and block on the reader
        assert not pending.done()
        _frame_into(reader, b"later")
        assert await pending == b"later"


async def test_receive_raises_when_connection_closes() -> None:
    reader = _FakeReader()
    transport = _transport(reader, _FakeWriter())
    async with transport:
        reader.feed_eof()
        with pytest.raises(TransportError):
            await transport.receive()


async def test_send_while_closed_raises() -> None:
    transport = _transport(_FakeReader(), _FakeWriter())
    with pytest.raises(TransportError):
        await transport.send(b"x")


async def test_receive_while_closed_raises() -> None:
    transport = _transport(_FakeReader(), _FakeWriter())
    with pytest.raises(TransportError):
        await transport.receive()


async def test_send_rejects_oversized_frame() -> None:
    transport = _transport(_FakeReader(), _FakeWriter())
    async with transport:
        with pytest.raises(TransportError):
            await transport.send(b"\x00" * (MAX_FRAME_SIZE + 1))
