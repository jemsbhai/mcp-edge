"""Expose an MCP-Edge :class:`~mcp_edge.gateway.Gateway` as an MCP server.

The gateway's tools are dynamic -- discovered from attached devices at runtime -- so we
build on the SDK's low-level ``Server`` and register ``list_tools`` / ``call_tool``
handlers that delegate to the gateway, rather than declaring tools with decorators.
"""

from __future__ import annotations

import json
from typing import Any

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .gateway import Gateway

DEFAULT_SERVER_NAME = "mcp-edge"


def tool_to_mcp(spec: dict[str, Any]) -> types.Tool:
    """Convert a gateway tool specification into an MCP :class:`~mcp.types.Tool`."""
    return types.Tool(
        name=spec["name"],
        description=spec.get("description") or "",
        inputSchema=spec.get("inputSchema") or {"type": "object"},
    )


async def list_tools_payload(gateway: Gateway) -> list[types.Tool]:
    """Return the gateway's composite tool list as MCP tool descriptors."""
    return [tool_to_mcp(spec) for spec in await gateway.list_tools()]


async def call_tool_payload(
    gateway: Gateway, name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    """Route a tool call through the gateway and wrap the result as text content."""
    result = await gateway.call_tool(name, arguments)
    text = result if isinstance(result, str) else json.dumps(result, default=str)
    return [types.TextContent(type="text", text=text)]


def build_server(gateway: Gateway, *, name: str = DEFAULT_SERVER_NAME) -> Server:
    """Build a low-level MCP ``Server`` backed by ``gateway``."""
    server: Server = Server(name)

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return await list_tools_payload(gateway)

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        return await call_tool_payload(gateway, name, arguments)

    return server


async def run_stdio(server: Server) -> None:
    """Serve ``server`` over stdio until the client disconnects.

    Note: stdio is the JSON-RPC channel, so callers must log only to stderr.
    """
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


__all__ = [
    "DEFAULT_SERVER_NAME",
    "tool_to_mcp",
    "list_tools_payload",
    "call_tool_payload",
    "build_server",
    "run_stdio",
]
