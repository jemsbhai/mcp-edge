"""Minimal MCP-Lite wire protocol.

MCP-Lite is the simplified MCP dialect Tier-2 devices speak: only three methods --
``tools/list``, ``tools/call``, and ``resources/read`` -- carried as CBOR-encoded,
JSON-RPC-style request/response frames. Prompts, sampling, batching, and notifications
are intentionally omitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import codec

TOOLS_LIST = "tools/list"
TOOLS_CALL = "tools/call"
RESOURCES_READ = "resources/read"
SUPPORTED_METHODS = frozenset({TOOLS_LIST, TOOLS_CALL, RESOURCES_READ})

# JSON-RPC reserves -32700..-32600; the device-specific codes sit just outside that band.
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
TOOL_NOT_FOUND = -32001
RESOURCE_NOT_FOUND = -32002


class ProtocolError(ValueError):
    """Raised when a frame cannot be parsed as an MCP-Lite message."""


@dataclass(frozen=True)
class Request:
    """An MCP-Lite request frame."""

    id: int
    method: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_bytes(self) -> bytes:
        return codec.encode({"id": self.id, "method": self.method, "params": self.params})

    @classmethod
    def from_bytes(cls, frame: bytes) -> Request:
        obj = codec.decode(frame)
        if not isinstance(obj, dict) or "id" not in obj or "method" not in obj:
            raise ProtocolError("not a valid MCP-Lite request frame")
        return cls(id=obj["id"], method=obj["method"], params=obj.get("params") or {})


@dataclass(frozen=True)
class Response:
    """An MCP-Lite response frame: exactly one of ``result`` or ``error`` is set."""

    id: int
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    @property
    def is_error(self) -> bool:
        return self.error is not None

    @classmethod
    def ok(cls, request_id: int, result: dict[str, Any]) -> Response:
        return cls(id=request_id, result=result)

    @classmethod
    def fail(cls, request_id: int, code: int, message: str) -> Response:
        return cls(id=request_id, error={"code": code, "message": message})

    def to_bytes(self) -> bytes:
        body: dict[str, Any] = {"id": self.id}
        if self.error is not None:
            body["error"] = self.error
        else:
            body["result"] = self.result or {}
        return codec.encode(body)

    @classmethod
    def from_bytes(cls, frame: bytes) -> Response:
        obj = codec.decode(frame)
        if not isinstance(obj, dict) or "id" not in obj:
            raise ProtocolError("not a valid MCP-Lite response frame")
        return cls(id=obj["id"], result=obj.get("result"), error=obj.get("error"))


__all__ = [
    "TOOLS_LIST",
    "TOOLS_CALL",
    "RESOURCES_READ",
    "SUPPORTED_METHODS",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "TOOL_NOT_FOUND",
    "RESOURCE_NOT_FOUND",
    "ProtocolError",
    "Request",
    "Response",
]
