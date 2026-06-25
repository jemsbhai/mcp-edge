"""Gateway-facing device clients.

The gateway reaches every device through a uniform :class:`DeviceClient` interface --
list its tools, call a tool, read a resource -- regardless of how the device is wired.
:class:`MCPLiteClient` implements that interface for Tier-2 devices by speaking the
MCP-Lite protocol over a transport.
"""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from typing import Any

from . import mcplite
from .mcplite import Request, Response
from .transports import Transport


class DeviceError(RuntimeError):
    """Raised when a device returns an error response."""

    def __init__(self, message: str, *, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class DeviceClient(ABC):
    """Uniform interface the gateway uses to reach a single device."""

    @abstractmethod
    async def list_tools(self) -> list[dict[str, Any]]:
        """Return the device's tool specifications."""

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Invoke a tool by name and return its content."""

    @abstractmethod
    async def read_resource(self, uri: str) -> Any:
        """Read a resource by URI and return its contents."""


class MCPLiteClient(DeviceClient):
    """A :class:`DeviceClient` that speaks MCP-Lite over a transport."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport
        self._ids = itertools.count(1)

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request = Request(next(self._ids), method, params)
        response = Response.from_bytes(await self._transport.request(request.to_bytes()))
        if response.is_error:
            error = response.error or {}
            raise DeviceError(error.get("message", "device error"), code=error.get("code"))
        return response.result or {}

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._call(mcplite.TOOLS_LIST, {})
        return list(result.get("tools", []))

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = await self._call(mcplite.TOOLS_CALL, {"name": name, "arguments": arguments})
        return result.get("content")

    async def read_resource(self, uri: str) -> Any:
        result = await self._call(mcplite.RESOURCES_READ, {"uri": uri})
        return result.get("contents")


__all__ = ["DeviceClient", "MCPLiteClient", "DeviceError"]
