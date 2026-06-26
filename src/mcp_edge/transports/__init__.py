"""Transport adapters for the MCP-Edge gateway-to-device link."""

from __future__ import annotations

from .base import Transport, TransportError
from .ble import BLETransport
from .loopback import FrameHandler, LoopbackTransport
from .serial import SerialTransport

__all__ = [
    "Transport",
    "TransportError",
    "LoopbackTransport",
    "FrameHandler",
    "SerialTransport",
    "BLETransport",
]
