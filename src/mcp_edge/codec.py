"""CBOR codec for the MCP-Edge device link.

Device-to-gateway messages are encoded as CBOR, which is typically 30-50% smaller
than the equivalent JSON; the gateway transcodes to standard JSON for the cloud MCP
client. This module wraps ``cbor2`` with a small, typed surface plus helpers for
quantifying the size saving.
"""

from __future__ import annotations

import json
from typing import Any

import cbor2


def encode(obj: Any) -> bytes:
    """Encode a Python object to CBOR bytes."""
    return cbor2.dumps(obj)


def decode(data: bytes) -> Any:
    """Decode CBOR bytes back into a Python object."""
    return cbor2.loads(data)


def json_bytes(obj: Any) -> bytes:
    """Encode ``obj`` as compact UTF-8 JSON (used as the size-comparison baseline)."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def size_reduction(obj: Any) -> float:
    """Fraction by which CBOR shrinks ``obj`` versus compact JSON, in the range [0, 1).

    A value of ``0.4`` means the CBOR encoding is 40% smaller than the JSON one.
    Returns ``0.0`` when the JSON baseline is empty.
    """
    json_len = len(json_bytes(obj))
    if json_len == 0:
        return 0.0
    return 1.0 - len(encode(obj)) / json_len


__all__ = ["encode", "decode", "json_bytes", "size_reduction"]
