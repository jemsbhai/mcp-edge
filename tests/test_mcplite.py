"""Tests for the MCP-Lite wire protocol."""

from __future__ import annotations

import pytest

from mcp_edge import codec, mcplite
from mcp_edge.mcplite import ProtocolError, Request, Response


def test_request_round_trip() -> None:
    request = Request(id=1, method=mcplite.TOOLS_CALL, params={"name": "read_temp"})
    assert Request.from_bytes(request.to_bytes()) == request


def test_request_defaults_to_empty_params() -> None:
    request = Request(id=7, method=mcplite.TOOLS_LIST)
    assert request.params == {}
    assert Request.from_bytes(request.to_bytes()).params == {}


def test_response_ok_round_trip() -> None:
    response = Response.ok(1, {"tools": []})
    restored = Response.from_bytes(response.to_bytes())
    assert restored == response
    assert not restored.is_error


def test_response_error_round_trip() -> None:
    response = Response.fail(2, mcplite.TOOL_NOT_FOUND, "no such tool: x")
    restored = Response.from_bytes(response.to_bytes())
    assert restored == response
    assert restored.is_error


def test_from_bytes_rejects_non_object_frame() -> None:
    with pytest.raises(ProtocolError):
        Request.from_bytes(codec.encode([1, 2, 3]))
