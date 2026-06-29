"""UDP transport for the gateway-to-device link over Wi-Fi or any IP network.

Like the TCP transport, this carries MCP-Lite frames over IP using stdlib asyncio -- no
third-party dependency -- and is the client side of the link (the device runs a UDP
server). Unlike TCP, UDP is connectionless and datagram-oriented: each datagram preserves
its own message boundary, so one frame travels in exactly one datagram. The frame still
uses the shared length-prefix wire format (:func:`mcp_edge.transports.serial.encode_frame`,
a 2-byte big-endian length followed by the CBOR payload) so the format is identical across
links and device firmware can reuse the same framing.

UDP is unreliable and unordered: datagrams may be dropped, duplicated, or reordered, and a
request gets no acknowledgement beyond its reply. :meth:`UdpTransport.receive` therefore
waits at most ``timeout`` seconds for a datagram and raises :class:`TransportError` if none
arrives; a reported socket error (such as an ICMP port-unreachable) surfaces the same way.
Keep frames small enough to fit a single datagram, well under the network MTU, to avoid IP
fragmentation.

Connect with a host and port (``UdpTransport("192.168.1.50", 8765)``); the mDNS discovery
helper can find those. For tests or custom links, pass ``endpoint_factory``: a
zero-argument callable returning a ``(transport, protocol)`` pair as
``loop.create_datagram_endpoint`` produces, where ``protocol`` exposes a ``queue`` of
inbound datagrams.

Validated in software against an in-memory fake endpoint; not yet exercised over a real
network link to a device.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from .base import Transport, TransportError
from .serial import decode_frame, encode_frame

# A zero-argument callable returning an open (transport, protocol) datagram-endpoint pair.
EndpointFactory = Callable[[], tuple[Any, Any]]


class _UdpClientProtocol(asyncio.DatagramProtocol):
    """Collects inbound datagrams (and socket errors) onto a queue for the transport."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[bytes | Exception] = asyncio.Queue()

    def datagram_received(self, data: bytes, addr: object) -> None:
        self.queue.put_nowait(data)

    def error_received(self, exc: Exception) -> None:
        self.queue.put_nowait(exc)


class UdpTransport(Transport):
    """Frame-oriented transport over UDP (client side, via asyncio datagram endpoints).

    Each frame is sent as one length-prefixed datagram, matching the serial and TCP wire
    format. Because UDP is best-effort, a lost reply surfaces as a ``TransportError`` from
    ``receive`` once ``timeout`` elapses.
    """

    def __init__(
        self,
        host: str,
        port: int,
        *,
        timeout: float = 10.0,
        endpoint_factory: EndpointFactory | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._endpoint_factory = endpoint_factory
        self._transport: Any = None
        self._protocol: Any = None

    @property
    def is_open(self) -> bool:
        transport = self._transport
        return bool(transport is not None and not transport.is_closing())

    async def open(self) -> None:
        if self.is_open:
            return
        self._transport, self._protocol = await self._connect()

    async def close(self) -> None:
        transport = self._transport
        if transport is None:
            return
        self._transport = None
        self._protocol = None
        transport.close()

    async def send(self, frame: bytes) -> None:
        self._require_open()
        self._transport.sendto(encode_frame(frame))

    async def receive(self) -> bytes:
        self._require_open()
        try:
            item = await asyncio.wait_for(self._protocol.queue.get(), self._timeout)
        except asyncio.TimeoutError as exc:
            raise TransportError(
                f"no UDP datagram from {self._host}:{self._port} within {self._timeout}s"
            ) from exc
        if isinstance(item, Exception):
            raise TransportError(
                f"UDP socket error from {self._host}:{self._port}: {item}"
            ) from item
        payload, _ = decode_frame(item)
        return payload

    async def _connect(self) -> tuple[Any, Any]:
        if self._endpoint_factory is not None:
            return self._endpoint_factory()
        loop = asyncio.get_running_loop()
        return await loop.create_datagram_endpoint(
            _UdpClientProtocol, remote_addr=(self._host, self._port)
        )

    def _require_open(self) -> None:
        if not self.is_open:
            raise TransportError("UDP transport is not open")


__all__ = ["EndpointFactory", "UdpTransport"]
