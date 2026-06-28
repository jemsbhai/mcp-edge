"""TCP transport for the gateway-to-device link over Wi-Fi or any IP network.

This transport carries MCP-Lite frames over a TCP connection using stdlib asyncio streams
-- no third-party dependency. It is the client side of the link; the device runs a TCP
server. The wire format matches the serial transport: each frame is length-prefixed by
:func:`mcp_edge.transports.serial.encode_frame` (a 2-byte big-endian length followed by the
CBOR payload), which TCP's reliable, ordered byte stream carries directly.

Connect with a host and port (``TcpTransport("192.168.1.50", 8765)``); the optional mDNS
discovery helper can find those for you. For tests or custom links, pass
``connection_factory``: a zero-argument callable returning an ``(asyncio.StreamReader,
asyncio.StreamWriter)`` pair.

Validated in software against in-memory fake streams; not yet exercised over a real network
link to a device.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from .base import Transport, TransportError
from .serial import encode_frame

_LENGTH_PREFIX = 2

# A zero-argument callable returning an open (reader, writer) stream pair.
ConnectionFactory = Callable[[], tuple[Any, Any]]


class TcpTransport(Transport):
    """Frame-oriented transport over a TCP connection (client side, via asyncio).

    Wire format matches the serial transport, so the length-prefix framing is identical
    across links. A dropped connection surfaces as ``TransportError`` from ``receive``.
    """

    def __init__(
        self,
        host: str,
        port: int,
        *,
        timeout: float = 10.0,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._connection_factory = connection_factory
        self._reader: Any = None
        self._writer: Any = None

    @property
    def is_open(self) -> bool:
        writer = self._writer
        return bool(writer is not None and not writer.is_closing())

    async def open(self) -> None:
        if self.is_open:
            return
        self._reader, self._writer = await self._connect()

    async def close(self) -> None:
        writer = self._writer
        if writer is None:
            return
        self._reader = None
        self._writer = None
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # best-effort on teardown: the peer may already be gone
            pass

    async def send(self, frame: bytes) -> None:
        self._require_open()
        self._writer.write(encode_frame(frame))
        await self._writer.drain()

    async def receive(self) -> bytes:
        self._require_open()
        try:
            header = await self._reader.readexactly(_LENGTH_PREFIX)
            size = (header[0] << 8) | header[1]
            if size == 0:
                return b""
            return await self._reader.readexactly(size)
        except asyncio.IncompleteReadError as exc:
            raise TransportError("connection closed while reading a frame") from exc

    async def _connect(self) -> tuple[Any, Any]:
        if self._connection_factory is not None:
            return self._connection_factory()
        return await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port), self._timeout
        )

    def _require_open(self) -> None:
        if not self.is_open:
            raise TransportError("TCP transport is not open")


__all__ = ["ConnectionFactory", "TcpTransport"]
