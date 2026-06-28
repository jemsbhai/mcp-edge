"""Gateway-facing device clients.

The gateway reaches every device through a uniform :class:`DeviceClient` interface --
list its tools, call a tool, read a resource -- regardless of how the device is wired.
:class:`MCPLiteClient` implements that interface for Tier-2 devices by speaking the
MCP-Lite protocol over a transport.

A client either holds one transport directly or draws one from a shared
:class:`~mcp_edge.pool.ConnectionPool` per call (see :meth:`MCPLiteClient.pooled`), so the
gateway can reuse and cap device connections. An optional
:class:`~mcp_edge.buffer.OfflineBuffer` lets one-way commands queue while the device is
unreachable and replay once it returns (see :meth:`MCPLiteClient.send_command` and
:meth:`MCPLiteClient.flush`).
"""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from . import mcplite
from .mcplite import Request, Response
from .transports import Transport, TransportError

if TYPE_CHECKING:
    from .buffer import OfflineBuffer
    from .pool import ConnectionPool


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
    """A :class:`DeviceClient` that speaks MCP-Lite over a transport.

    Construct it with a ready transport (``MCPLiteClient(transport)``) or, via
    :meth:`pooled`, with a shared connection pool and a device key. Pass ``buffer`` to
    enable offline queuing of one-way commands.
    """

    def __init__(
        self,
        transport: Transport | None = None,
        *,
        pool: ConnectionPool | None = None,
        key: str | None = None,
        buffer: OfflineBuffer[tuple[str, dict[str, Any]]] | None = None,
    ) -> None:
        if (transport is None) == (pool is None):
            raise ValueError("provide exactly one of transport or pool")
        if pool is not None and key is None:
            raise ValueError("a pooled client requires a device key")
        self._transport = transport
        self._pool = pool
        self._key = key
        self._buffer = buffer
        self._ids = itertools.count(1)

    @classmethod
    def pooled(
        cls,
        pool: ConnectionPool,
        key: str,
        *,
        buffer: OfflineBuffer[tuple[str, dict[str, Any]]] | None = None,
    ) -> MCPLiteClient:
        """Build a client that draws its transport from ``pool`` under ``key`` per call."""
        return cls(pool=pool, key=key, buffer=buffer)

    async def _transport_for_call(self) -> Transport:
        if self._pool is not None:
            assert self._key is not None  # set together with the pool in __init__
            return await self._pool.acquire(self._key)
        assert self._transport is not None  # guaranteed by __init__
        return self._transport

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        transport = await self._transport_for_call()
        request = Request(next(self._ids), method, params)
        response = Response.from_bytes(await transport.request(request.to_bytes()))
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

    async def send_command(self, name: str, arguments: dict[str, Any]) -> bool:
        """Invoke a tool one-way, ignoring its result.

        Returns ``True`` if the call was delivered. If the device is unreachable
        (:class:`~mcp_edge.transports.TransportError`) and a buffer is configured, the
        command is queued for a later :meth:`flush` and ``False`` is returned; without a
        buffer the error propagates. A reachable device that rejects the command still
        raises :class:`DeviceError`.
        """
        try:
            await self._call(mcplite.TOOLS_CALL, {"name": name, "arguments": arguments})
        except TransportError:
            if self._buffer is None:
                raise
            self._buffer.enqueue((name, arguments))
            return False
        return True

    async def flush(self) -> int:
        """Replay queued one-way commands in FIFO order; return the number cleared.

        A command the device now rejects (:class:`DeviceError`) is dropped, since
        retrying will not help. If the device is unreachable again the remaining commands
        stay queued for the next attempt. Returns 0 when no buffer is configured.
        """
        if self._buffer is None:
            return 0

        async def deliver(item: tuple[str, dict[str, Any]]) -> None:
            name, arguments = item
            try:
                await self._call(mcplite.TOOLS_CALL, {"name": name, "arguments": arguments})
            except DeviceError:
                pass  # reachable but rejected -- drop rather than wedge the queue

        return await self._buffer.flush(deliver)


__all__ = ["DeviceClient", "MCPLiteClient", "DeviceError"]
