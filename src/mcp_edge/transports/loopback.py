"""In-process loopback transport.

Connects the gateway side directly to a device's frame handler in the same process,
with no real I/O. Used by the device simulator and by tests to exercise the full
request/response path without hardware.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from .base import Transport, TransportError

FrameHandler = Callable[[bytes], Awaitable[bytes]]


class LoopbackTransport(Transport):
    """A transport whose peer is an in-process async frame handler."""

    def __init__(self, handler: FrameHandler) -> None:
        self._handler = handler
        self._responses: asyncio.Queue[bytes] = asyncio.Queue()
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open

    async def open(self) -> None:
        self._open = True

    async def close(self) -> None:
        self._open = False

    async def send(self, frame: bytes) -> None:
        if not self._open:
            raise TransportError("transport is not open")
        self._responses.put_nowait(await self._handler(frame))

    async def receive(self) -> bytes:
        if not self._open:
            raise TransportError("transport is not open")
        return await self._responses.get()


__all__ = ["LoopbackTransport", "FrameHandler"]
