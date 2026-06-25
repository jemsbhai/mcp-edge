"""Serial (UART) transport for the gateway-to-device link.

This transport carries MCP-Lite frames over a serial port using :mod:`pyserial`
(install the ``serial`` extra: ``pip install mcp-edge[serial]``). pyserial's API is
blocking, so each read and write runs in a worker thread via :func:`asyncio.to_thread`;
the public surface stays the async :class:`Transport`.

Wire format
-----------
A serial line is a raw byte stream and MCP-Lite frames are binary CBOR, so frames are
delimited by a length prefix rather than a sentinel byte. Each frame on the wire is::

    +--------------+--------------------------+
    | length (2 B) | CBOR payload (length B)  |
    +--------------+--------------------------+

The length is an unsigned 16-bit big-endian (network-order) integer, so one frame
carries at most 65535 bytes. Device firmware must frame its replies the same way.
:func:`encode_frame` and :func:`decode_frame` implement this format and are public so
firmware bridges and tests can reuse them.
"""

from __future__ import annotations

import asyncio
import struct
from collections.abc import Callable
from typing import Any

from .base import Transport, TransportError

_LENGTH = struct.Struct(">H")

# Largest payload one frame can carry: the 2-byte length prefix caps it at 65535 bytes.
MAX_FRAME_SIZE = 0xFFFF

# A zero-argument callable returning an open pyserial-like port.
SerialFactory = Callable[[], Any]


def encode_frame(payload: bytes) -> bytes:
    """Return ``payload`` prefixed with its 2-byte big-endian length."""
    size = len(payload)
    if size > MAX_FRAME_SIZE:
        raise TransportError(f"frame too large: {size} bytes (max {MAX_FRAME_SIZE})")
    return _LENGTH.pack(size) + payload


def decode_frame(buffer: bytes) -> tuple[bytes, bytes]:
    """Parse one length-prefixed frame from the front of ``buffer``.

    Returns ``(payload, remaining)`` where ``remaining`` is whatever bytes follow the
    frame. Raises :class:`TransportError` if ``buffer`` does not hold a whole frame.
    """
    if len(buffer) < _LENGTH.size:
        raise TransportError("incomplete frame: missing length prefix")
    (size,) = _LENGTH.unpack(buffer[:_LENGTH.size])
    end = _LENGTH.size + size
    if len(buffer) < end:
        raise TransportError("incomplete frame: truncated payload")
    return buffer[_LENGTH.size:end], buffer[end:]


def _import_pyserial() -> Any:
    try:
        import serial
    except ImportError as exc:  # pragma: no cover
        raise TransportError(
            "pyserial is required for SerialTransport; install mcp-edge[serial]"
        ) from exc
    return serial


class SerialTransport(Transport):
    """Frame-oriented transport over a serial port.

    Construct it with a port name for real hardware (``SerialTransport("COM3")`` on
    Windows, ``SerialTransport("/dev/ttyUSB0")`` on Linux). For tests or custom links,
    pass ``serial_factory``: a zero-argument callable returning any object exposing
    ``read(size)``, ``write(data)``, ``close()`` and an ``is_open`` flag (``flush()`` is
    called when present). When a factory is supplied, pyserial is never imported.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        *,
        timeout: float = 1.0,
        serial_factory: SerialFactory | None = None,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._serial_factory = serial_factory
        self._serial: Any = None

    @property
    def is_open(self) -> bool:
        port = self._serial
        return bool(port is not None and getattr(port, "is_open", False))

    async def open(self) -> None:
        if self.is_open:
            return
        self._serial = await asyncio.to_thread(self._open_port)

    async def close(self) -> None:
        port = self._serial
        if port is None:
            return
        self._serial = None
        await asyncio.to_thread(port.close)

    async def send(self, frame: bytes) -> None:
        self._require_open()
        await asyncio.to_thread(self._write_frame, encode_frame(frame))

    async def receive(self) -> bytes:
        self._require_open()
        return await asyncio.to_thread(self._read_frame)

    def _open_port(self) -> Any:
        if self._serial_factory is not None:
            return self._serial_factory()
        serial = _import_pyserial()
        return serial.Serial(self._port, self._baudrate, timeout=self._timeout)

    def _write_frame(self, data: bytes) -> None:
        port = self._serial
        port.write(data)
        flush = getattr(port, "flush", None)
        if flush is not None:
            flush()

    def _read_frame(self) -> bytes:
        header = self._read_exactly(_LENGTH.size)
        (size,) = _LENGTH.unpack(header)
        return self._read_exactly(size)

    def _read_exactly(self, count: int) -> bytes:
        port = self._serial
        chunks: list[bytes] = []
        remaining = count
        while remaining > 0:
            chunk = port.read(remaining)
            if not chunk:
                raise TransportError("serial read timed out or port closed")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _require_open(self) -> None:
        if not self.is_open:
            raise TransportError("serial transport is not open")


__all__ = [
    "SerialTransport",
    "SerialFactory",
    "encode_frame",
    "decode_frame",
    "MAX_FRAME_SIZE",
]
