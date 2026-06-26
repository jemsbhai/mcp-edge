"""BLE (Bluetooth Low Energy) transport for the gateway-to-device link.

This transport carries MCP-Lite frames over a BLE GATT connection using :mod:`bleak`
(install the ``ble`` extra: ``pip install mcp-edge[ble]``). It is the central side of the
link; the device is a GATT peripheral. bleak is imported lazily, so the module loads
without it as long as a ``client_factory`` is supplied.

GATT profile
------------
By default the transport speaks the Nordic UART Service (NUS), the de-facto "BLE serial"
profile: the central writes outbound bytes to the peripheral's RX characteristic and
subscribes to the peripheral's TX characteristic for inbound notifications. Both
characteristic UUIDs are constructor arguments, so firmware that uses its own service can
override them.

Wire format
-----------
The framing matches the serial transport exactly: each MCP-Lite frame is length-prefixed
by :func:`mcp_edge.transports.serial.encode_frame` (a 2-byte big-endian length followed by
the CBOR payload). BLE's ATT MTU is small, so an outbound frame is split into MTU-sized
packets on ``send``; inbound notification bytes are buffered and whole frames are
reassembled from the same length prefix on ``receive``. Because a connected GATT link
already delivers notifications reliably and in order, the length prefix alone is enough to
reassemble frames — no BLE-specific chunk header is needed.

Validated in software against an in-memory fake; not yet exercised on physical hardware.
"""

from __future__ import annotations

import asyncio
import struct
from collections.abc import Callable
from typing import Any

from .base import Transport, TransportError
from .serial import encode_frame

# Nordic UART Service (NUS): the de-facto "BLE serial" GATT profile. The peripheral
# receives on the RX characteristic (the central writes to it) and transmits on the TX
# characteristic (the central subscribes to it for notifications).
NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

# BLE's default ATT MTU is 23 bytes, of which 3 are ATT header overhead, leaving 20 bytes
# of usable payload per write or notification until a larger MTU is negotiated.
_DEFAULT_ATT_MTU = 23
_ATT_HEADER = 3

_LENGTH = struct.Struct(">H")

# A zero-argument callable returning an open bleak-like client.
BleClientFactory = Callable[[], Any]


def _import_bleak() -> Any:
    try:
        import bleak
    except ImportError as exc:  # pragma: no cover
        raise TransportError(
            "bleak is required for BLETransport; install mcp-edge[ble]"
        ) from exc
    return bleak


class BLETransport(Transport):
    """Frame-oriented transport over a BLE GATT link (central side, via bleak).

    Construct it with a peripheral address for real hardware
    (``BLETransport("AA:BB:CC:DD:EE:FF")``; on macOS, a device UUID). The characteristic
    UUIDs default to the Nordic UART Service and can be overridden for firmware that uses
    its own. For tests or custom links, pass ``client_factory``: a zero-argument callable
    returning any object exposing the bleak ``BleakClient`` surface this transport uses
    (``connect``/``disconnect``, ``start_notify``/``stop_notify``, ``write_gatt_char``,
    ``is_connected`` and ``mtu_size``). When a factory is supplied, bleak is never
    imported.

    By default writes use write-with-response (acknowledged, with backpressure); pass
    ``write_with_response=False`` for peripherals whose RX characteristic only supports
    write-without-response.
    """

    def __init__(
        self,
        address: str,
        *,
        write_char_uuid: str = NUS_RX_CHAR_UUID,
        notify_char_uuid: str = NUS_TX_CHAR_UUID,
        timeout: float = 10.0,
        write_with_response: bool = True,
        client_factory: BleClientFactory | None = None,
    ) -> None:
        self._address = address
        self._write_uuid = write_char_uuid
        self._notify_uuid = notify_char_uuid
        self._timeout = timeout
        self._write_with_response = write_with_response
        self._client_factory = client_factory
        self._client: Any = None
        self._rx_buffer = bytearray()
        self._frames: asyncio.Queue[bytes] = asyncio.Queue()

    @property
    def is_open(self) -> bool:
        client = self._client
        return bool(client is not None and getattr(client, "is_connected", False))

    async def open(self) -> None:
        if self.is_open:
            return
        client = self._make_client()
        await client.connect()
        await client.start_notify(self._notify_uuid, self._on_notify)
        self._client = client

    async def close(self) -> None:
        client = self._client
        if client is None:
            return
        self._client = None
        try:
            await client.stop_notify(self._notify_uuid)
        except Exception:  # best-effort on teardown: the peripheral may already be gone
            pass
        await client.disconnect()

    async def send(self, frame: bytes) -> None:
        self._require_open()
        data = encode_frame(frame)
        size = self._chunk_size()
        for start in range(0, len(data), size):
            end = start + size
            await self._client.write_gatt_char(
                self._write_uuid, data[start:end], response=self._write_with_response
            )

    async def receive(self) -> bytes:
        self._require_open()
        return await self._frames.get()

    def _make_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        bleak = _import_bleak()
        return bleak.BleakClient(self._address, timeout=self._timeout)

    def _on_notify(self, _sender: object, data: bytearray) -> None:
        self._rx_buffer.extend(data)
        while True:
            frame = self._pop_frame()
            if frame is None:
                break
            self._frames.put_nowait(frame)

    def _pop_frame(self) -> bytes | None:
        buffer = self._rx_buffer
        if len(buffer) < _LENGTH.size:
            return None
        (size,) = _LENGTH.unpack_from(buffer)
        end = _LENGTH.size + size
        if len(buffer) < end:
            return None
        payload = bytes(buffer[_LENGTH.size:end])
        del buffer[:end]
        return payload

    def _chunk_size(self) -> int:
        mtu = getattr(self._client, "mtu_size", _DEFAULT_ATT_MTU)
        return max(1, mtu - _ATT_HEADER)

    def _require_open(self) -> None:
        if not self.is_open:
            raise TransportError("BLE transport is not open")


__all__ = [
    "BLETransport",
    "BleClientFactory",
    "NUS_SERVICE_UUID",
    "NUS_RX_CHAR_UUID",
    "NUS_TX_CHAR_UUID",
]
