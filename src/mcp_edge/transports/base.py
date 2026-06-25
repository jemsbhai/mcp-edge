"""Transport abstraction for the gateway-to-device link.

A :class:`Transport` is an async, frame-oriented byte channel: each ``send`` and
``receive`` moves one whole message frame. Concrete transports (in-process loopback,
serial/UART, BLE, local Wi-Fi) implement the channel; higher layers build the MCP-Lite
request/response protocol on top.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class TransportError(RuntimeError):
    """Raised when a transport operation fails (for example, used while closed)."""


class Transport(ABC):
    """An async, frame-oriented byte channel between the gateway and a device."""

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """Whether the transport is currently open."""

    @abstractmethod
    async def open(self) -> None:
        """Open the channel. Implementations should be idempotent."""

    @abstractmethod
    async def close(self) -> None:
        """Close the channel. Implementations should be idempotent."""

    @abstractmethod
    async def send(self, frame: bytes) -> None:
        """Send one frame to the device."""

    @abstractmethod
    async def receive(self) -> bytes:
        """Receive the next frame from the device."""

    async def request(self, frame: bytes) -> bytes:
        """Send a frame and await the next frame in reply (request/response)."""
        await self.send(frame)
        return await self.receive()

    async def __aenter__(self) -> Transport:
        await self.open()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()


__all__ = ["Transport", "TransportError"]
