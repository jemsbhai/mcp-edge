"""Transport adapters for the MCP-Edge gateway-to-device link."""

from __future__ import annotations

from .base import Transport, TransportError
from .loopback import FrameHandler, LoopbackTransport

__all__ = ["Transport", "TransportError", "LoopbackTransport", "FrameHandler"]
