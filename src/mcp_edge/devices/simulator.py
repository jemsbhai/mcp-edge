"""In-process simulated MCP-Lite device.

A :class:`SimulatedDevice` serves the MCP-Lite method set over a transport, with no
hardware involved. Register tools (callable, typed) and resources (read-only values),
then attach the device to a ``LoopbackTransport`` to exercise the gateway path end to
end -- and, later, to drive the scalability simulations.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .. import mcplite
from ..mcplite import Request, Response

ToolHandler = Callable[[dict[str, Any]], Any]


@dataclass
class Tool:
    """A simulated device tool: a typed, callable capability."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler

    def spec(self) -> dict[str, Any]:
        """The discovery record returned by ``tools/list``."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class SimulatedDevice:
    """An in-process device that answers MCP-Lite request frames."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._tools: dict[str, Tool] = {}
        self._resources: dict[str, Any] = {}

    def add_tool(
        self,
        name: str,
        handler: ToolHandler,
        *,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
    ) -> None:
        """Register a callable tool."""
        self._tools[name] = Tool(name, description, input_schema or {}, handler)

    def add_resource(self, uri: str, value: Any) -> None:
        """Register a read-only resource."""
        self._resources[uri] = value

    def list_tools(self) -> list[dict[str, Any]]:
        return [tool.spec() for tool in self._tools.values()]

    async def handle(self, frame: bytes) -> bytes:
        """Decode one request frame, dispatch it, and encode the response."""
        return self._dispatch(Request.from_bytes(frame)).to_bytes()

    def _dispatch(self, request: Request) -> Response:
        if request.method == mcplite.TOOLS_LIST:
            return Response.ok(request.id, {"tools": self.list_tools()})
        if request.method == mcplite.TOOLS_CALL:
            return self._call_tool(request)
        if request.method == mcplite.RESOURCES_READ:
            return self._read_resource(request)
        return Response.fail(
            request.id, mcplite.METHOD_NOT_FOUND, f"unknown method: {request.method}"
        )

    def _call_tool(self, request: Request) -> Response:
        name = request.params.get("name")
        tool = self._tools.get(name) if isinstance(name, str) else None
        if tool is None:
            return Response.fail(request.id, mcplite.TOOL_NOT_FOUND, f"no such tool: {name}")
        arguments = request.params.get("arguments") or {}
        return Response.ok(request.id, {"content": tool.handler(arguments)})

    def _read_resource(self, request: Request) -> Response:
        uri = request.params.get("uri")
        if not isinstance(uri, str) or uri not in self._resources:
            return Response.fail(
                request.id, mcplite.RESOURCE_NOT_FOUND, f"no such resource: {uri}"
            )
        return Response.ok(request.id, {"contents": self._resources[uri]})


__all__ = ["SimulatedDevice", "Tool", "ToolHandler"]
