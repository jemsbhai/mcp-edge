"""Tests for the serial transport and its length-prefix frame format.

These tests inject an in-memory ``FakePort`` via ``serial_factory``, so they run with
no hardware and without pyserial installed, and stay in the hermetic core CI.
"""

from __future__ import annotations

import pytest

from mcp_edge.transports import SerialTransport, TransportError
from mcp_edge.transports.serial import (
    MAX_FRAME_SIZE,
    decode_frame,
    encode_frame,
)


class FakePort:
    """In-memory stand-in for a pyserial port.

    ``read`` pulls from ``rx`` and ``write`` appends to ``tx``; both are shared
    bytearrays, so a pair of ports wired rx<->tx forms a bidirectional link. ``chunk``
    caps the bytes returned per ``read`` to mimic partial UART reads.
    """

    def __init__(self, rx: bytearray, tx: bytearray, *, chunk: int | None = None) -> None:
        self._rx = rx
        self._tx = tx
        self._chunk = chunk
        self.is_open = True

    def read(self, size: int) -> bytes:
        if self._chunk is not None:
            size = min(size, self._chunk)
        data = bytes(self._rx[:size])
        del self._rx[:len(data)]
        return data

    def write(self, data: bytes) -> int:
        self._tx.extend(data)
        return len(data)

    def close(self) -> None:
        self.is_open = False


def _pair(*, chunk: int | None = None) -> tuple[FakePort, FakePort]:
    a_to_b = bytearray()
    b_to_a = bytearray()
    a = FakePort(rx=b_to_a, tx=a_to_b, chunk=chunk)
    b = FakePort(rx=a_to_b, tx=b_to_a, chunk=chunk)
    return a, b


def _transport(port: FakePort) -> SerialTransport:
    return SerialTransport("fake", serial_factory=lambda: port)


async def test_encode_decode_round_trip() -> None:
    payload, rest = decode_frame(encode_frame(b"hello"))
    assert payload == b"hello"
    assert rest == b""


async def test_decode_splits_multiple_frames() -> None:
    buffer = encode_frame(b"one") + encode_frame(b"two")
    first, rest = decode_frame(buffer)
    second, tail = decode_frame(rest)
    assert (first, second) == (b"one", b"two")
    assert tail == b""


async def test_encode_rejects_oversized_frame() -> None:
    with pytest.raises(TransportError):
        encode_frame(b"\x00" * (MAX_FRAME_SIZE + 1))


async def test_decode_rejects_incomplete_buffer() -> None:
    with pytest.raises(TransportError):
        decode_frame(b"\x00")  # only part of the length prefix
    with pytest.raises(TransportError):
        decode_frame(encode_frame(b"payload")[:-1])  # truncated payload


async def test_send_then_receive_between_paired_ports() -> None:
    sender_port, receiver_port = _pair()
    sender = _transport(sender_port)
    receiver = _transport(receiver_port)
    async with sender, receiver:
        await sender.send(b"\x01\x02\x03")
        assert await receiver.receive() == b"\x01\x02\x03"


async def test_frames_preserve_order_and_boundaries() -> None:
    sender_port, receiver_port = _pair()
    sender = _transport(sender_port)
    receiver = _transport(receiver_port)
    async with sender, receiver:
        for frame in (b"a", b"bb", b"ccc"):
            await sender.send(frame)
        assert await receiver.receive() == b"a"
        assert await receiver.receive() == b"bb"
        assert await receiver.receive() == b"ccc"


async def test_partial_reads_are_reassembled() -> None:
    sender_port, receiver_port = _pair(chunk=1)
    sender = _transport(sender_port)
    receiver = _transport(receiver_port)
    async with sender, receiver:
        await sender.send(b"reassemble me")
        assert await receiver.receive() == b"reassemble me"


async def test_request_returns_peer_reply() -> None:
    client_port, device_port = _pair()
    client = _transport(client_port)
    device = _transport(device_port)
    async with client, device:
        await device.send(b"pong")  # stage the reply on the return path
        assert await client.request(b"ping") == b"pong"


async def test_receive_without_data_raises() -> None:
    port_a, _port_b = _pair()
    transport = _transport(port_a)
    await transport.open()
    with pytest.raises(TransportError):
        await transport.receive()
    await transport.close()


async def test_is_open_tracks_lifecycle() -> None:
    port_a, _port_b = _pair()
    transport = _transport(port_a)
    assert not transport.is_open
    await transport.open()
    assert transport.is_open
    await transport.close()
    assert not transport.is_open


async def test_send_while_closed_raises() -> None:
    port_a, _port_b = _pair()
    transport = _transport(port_a)
    with pytest.raises(TransportError):
        await transport.send(b"x")


async def test_open_and_close_are_idempotent() -> None:
    port_a, _port_b = _pair()
    transport = _transport(port_a)
    await transport.open()
    await transport.open()
    assert transport.is_open
    await transport.close()
    await transport.close()
    assert not transport.is_open
