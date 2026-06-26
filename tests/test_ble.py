"""Tests for the BLE transport, its MTU chunking, and notification reassembly.

These tests inject an in-memory ``FakeBleClient`` via ``client_factory``, so they run
with no Bluetooth hardware and without bleak installed, and stay in the hermetic core
CI. The fake models the central's view of a connected peripheral: bytes the central
writes are concatenated into an inbound buffer, and the test drives traffic the other
way by replaying notifications through the registered callback the way a peripheral's
notifications would arrive.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from mcp_edge.transports import TransportError
from mcp_edge.transports.ble import (
    NUS_RX_CHAR_UUID,
    NUS_TX_CHAR_UUID,
    BLETransport,
)
from mcp_edge.transports.serial import MAX_FRAME_SIZE, encode_frame


class FakeBleClient:
    """In-memory stand-in for a bleak ``BleakClient``.

    Implements only the surface ``BLETransport`` uses: ``connect``/``disconnect``,
    ``start_notify``/``stop_notify``, ``write_gatt_char``, plus the ``is_connected`` and
    ``mtu_size`` attributes. Bytes written by the central are concatenated into
    ``written`` (and recorded per call in ``write_calls``); ``push_notification`` replays
    bytes to the central's notify callback the way a peripheral's notifications arrive.
    """

    def __init__(self, *, mtu_size: int = 23) -> None:
        self.is_connected = False
        self.mtu_size = mtu_size
        self.written = bytearray()
        self.write_calls: list[tuple[str, bytes, bool]] = []
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.notifying = False
        self.notify_uuid: str | None = None
        self._notify_cb: Callable[[str, bytearray], None] | None = None

    async def connect(self) -> None:
        self.connect_calls += 1
        self.is_connected = True

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.is_connected = False

    async def start_notify(
        self, char_uuid: str, callback: Callable[[str, bytearray], None]
    ) -> None:
        self.notify_uuid = char_uuid
        self._notify_cb = callback
        self.notifying = True

    async def stop_notify(self, char_uuid: str) -> None:
        self.notifying = False
        self._notify_cb = None

    async def write_gatt_char(self, char_uuid: str, data: bytes, response: bool = False) -> None:
        self.write_calls.append((char_uuid, bytes(data), response))
        self.written.extend(data)

    def push_notification(self, data: bytes) -> None:
        if self._notify_cb is None:
            raise RuntimeError("no notify callback registered")
        self._notify_cb(self.notify_uuid, bytearray(data))


def _transport(
    client: FakeBleClient,
    *,
    write_char_uuid: str = NUS_RX_CHAR_UUID,
    notify_char_uuid: str = NUS_TX_CHAR_UUID,
    write_with_response: bool = True,
) -> BLETransport:
    return BLETransport(
        "AA:BB:CC:DD:EE:FF",
        write_char_uuid=write_char_uuid,
        notify_char_uuid=notify_char_uuid,
        write_with_response=write_with_response,
        client_factory=lambda: client,
    )


def _notify_frame(client: FakeBleClient, payload: bytes, *, chunk: int | None = None) -> None:
    """Replay ``payload`` as one length-prefixed frame, split into notification packets."""
    frame = encode_frame(payload)
    size = chunk if chunk is not None else max(1, client.mtu_size - 3)
    for start in range(0, len(frame), size):
        end = start + size
        client.push_notification(frame[start:end])


async def test_open_connects_and_subscribes() -> None:
    client = FakeBleClient()
    transport = _transport(client)
    await transport.open()
    assert client.is_connected
    assert client.connect_calls == 1
    assert client.notifying
    await transport.close()


async def test_open_subscribes_to_notify_characteristic() -> None:
    client = FakeBleClient()
    transport = _transport(client)
    async with transport:
        assert client.notify_uuid == NUS_TX_CHAR_UUID


async def test_close_unsubscribes_and_disconnects() -> None:
    client = FakeBleClient()
    transport = _transport(client)
    await transport.open()
    await transport.close()
    assert not client.notifying
    assert client.disconnect_calls == 1
    assert not transport.is_open


async def test_is_open_tracks_lifecycle() -> None:
    client = FakeBleClient()
    transport = _transport(client)
    assert not transport.is_open
    await transport.open()
    assert transport.is_open
    await transport.close()
    assert not transport.is_open


async def test_open_and_close_are_idempotent() -> None:
    client = FakeBleClient()
    transport = _transport(client)
    await transport.open()
    await transport.open()
    assert transport.is_open
    assert client.connect_calls == 1
    await transport.close()
    await transport.close()
    assert not transport.is_open
    assert client.disconnect_calls == 1


async def test_send_chunks_frame_by_mtu() -> None:
    client = FakeBleClient(mtu_size=23)  # 20 usable payload bytes per packet
    transport = _transport(client)
    payload = b"the quick brown fox jumps over the lazy dog"  # 43 bytes, > one packet
    async with transport:
        await transport.send(payload)
    assert client.written == encode_frame(payload)
    assert len(client.write_calls) > 1
    assert all(len(chunk) <= 20 for _uuid, chunk, _resp in client.write_calls)


async def test_send_targets_write_characteristic() -> None:
    client = FakeBleClient()
    transport = _transport(client)
    async with transport:
        await transport.send(b"hi")
    assert client.write_calls[0][0] == NUS_RX_CHAR_UUID


async def test_send_uses_write_with_response_by_default() -> None:
    client = FakeBleClient()
    transport = _transport(client)
    async with transport:
        await transport.send(b"hi")
    assert all(resp for _uuid, _chunk, resp in client.write_calls)


async def test_write_without_response_is_honored() -> None:
    client = FakeBleClient()
    transport = _transport(client, write_with_response=False)
    async with transport:
        await transport.send(b"hi")
    assert not any(resp for _uuid, _chunk, resp in client.write_calls)


async def test_receive_reassembles_chunked_notifications() -> None:
    client = FakeBleClient()
    transport = _transport(client)
    async with transport:
        _notify_frame(client, b"hello over ble", chunk=1)  # one byte per packet
        assert await transport.receive() == b"hello over ble"


async def test_receive_preserves_frame_order_and_boundaries() -> None:
    client = FakeBleClient()
    transport = _transport(client)
    async with transport:
        _notify_frame(client, b"one")
        _notify_frame(client, b"two")
        assert await transport.receive() == b"one"
        assert await transport.receive() == b"two"


async def test_request_returns_peer_reply() -> None:
    client = FakeBleClient()
    transport = _transport(client)
    async with transport:
        _notify_frame(client, b"pong")  # stage the reply on the notify path
        assert await transport.request(b"ping") == b"pong"
    assert client.written == encode_frame(b"ping")


async def test_receive_awaits_until_notified() -> None:
    client = FakeBleClient()
    transport = _transport(client)
    async with transport:
        pending = asyncio.create_task(transport.receive())
        await asyncio.sleep(0)  # let receive() start and block on the queue
        assert not pending.done()
        _notify_frame(client, b"later")
        assert await pending == b"later"


async def test_send_while_closed_raises() -> None:
    client = FakeBleClient()
    transport = _transport(client)
    with pytest.raises(TransportError):
        await transport.send(b"x")


async def test_receive_while_closed_raises() -> None:
    client = FakeBleClient()
    transport = _transport(client)
    with pytest.raises(TransportError):
        await transport.receive()


async def test_send_rejects_oversized_frame() -> None:
    client = FakeBleClient()
    transport = _transport(client)
    async with transport:
        with pytest.raises(TransportError):
            await transport.send(b"\x00" * (MAX_FRAME_SIZE + 1))


async def test_characteristic_uuids_are_overridable() -> None:
    client = FakeBleClient()
    transport = _transport(
        client, write_char_uuid="custom-rx", notify_char_uuid="custom-tx"
    )
    async with transport:
        assert client.notify_uuid == "custom-tx"
        await transport.send(b"hi")
    assert client.write_calls[0][0] == "custom-rx"
