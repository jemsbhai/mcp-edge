"""Tests that the portable firmware core speaks the gateway's wire protocol.

The core under test lives in examples/firmware/esp32_micropython/mcplite_device.py and is
loaded by path (it is example code, not part of the installed package). Everything here
runs under CPython with no hardware, so it stays in the hermetic core CI.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import cbor2

from mcp_edge import mcplite
from mcp_edge.codec import decode as edge_decode
from mcp_edge.codec import encode as edge_encode
from mcp_edge.mcplite import Request, Response
from mcp_edge.transports.serial import decode_frame, encode_frame

_CORE_PATH = (
    Path(__file__).resolve().parent.parent
    / "examples"
    / "firmware"
    / "esp32_micropython"
    / "mcplite_device.py"
)
_spec = importlib.util.spec_from_file_location("mcplite_device", _CORE_PATH)
device_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(device_core)


# Representative MCP-Lite values; the floats are exact in IEEE-754 so equality holds.
_VALUES = [
    0,
    1,
    23,
    24,
    255,
    256,
    65535,
    70000,
    -1,
    -24,
    -300,
    True,
    False,
    None,
    21.5,
    -2.25,
    0.0,
    "celsius",
    "",
    "température",
    [1, 2, 3],
    {"name": "read_temp", "arguments": {}},
    {"tools": [{"name": "t", "description": "d", "inputSchema": {"type": "object"}}]},
    {"nested": {"list": [1, {"x": True}], "value": -3.5}},
]


class _Stream:
    """Minimal read-only stream over a byte buffer, mimicking MicroPython UART.read."""

    def __init__(self, data: bytes, *, chunk: int | None = None) -> None:
        self._data = bytearray(data)
        self._chunk = chunk

    def read(self, size: int) -> bytes:
        if self._chunk is not None:
            size = min(size, self._chunk)
        taken = bytes(self._data[:size])
        del self._data[:len(taken)]
        return taken


def _build_device() -> object:
    device = device_core.MCPLiteDevice()
    device.add_tool("read_temp", lambda args: {"celsius": 21.5})
    device.add_tool("set_led", lambda args: {"on": bool(args.get("on"))})
    return device


def _exchange(device: object, request: Request) -> Response:
    # The full path: gateway encodes + frames -> device reads + dispatches + frames ->
    # gateway decodes, exactly as MCPLiteClient over SerialTransport would.
    inbound = _Stream(encode_frame(request.to_bytes()))
    request_payload = device_core.read_frame(inbound)
    reply = device_core.frame(device.handle(request_payload))
    response_payload, tail = decode_frame(reply)
    assert tail == b""
    return Response.from_bytes(response_payload)


def test_constants_match_mcplite() -> None:
    assert device_core.TOOLS_LIST == mcplite.TOOLS_LIST
    assert device_core.TOOLS_CALL == mcplite.TOOLS_CALL
    assert device_core.RESOURCES_READ == mcplite.RESOURCES_READ
    assert device_core.METHOD_NOT_FOUND == mcplite.METHOD_NOT_FOUND
    assert device_core.TOOL_NOT_FOUND == mcplite.TOOL_NOT_FOUND
    assert device_core.RESOURCE_NOT_FOUND == mcplite.RESOURCE_NOT_FOUND


def test_gateway_decodes_device_cbor() -> None:
    for value in _VALUES:
        assert edge_decode(device_core.dumps(value)) == value


def test_device_decodes_gateway_cbor() -> None:
    for value in _VALUES:
        assert device_core.loads(edge_encode(value)) == value


def test_device_decodes_canonical_floats() -> None:
    # cbor2 canonical picks float16 / float32 / float64; the device reads all three.
    assert device_core.loads(cbor2.dumps(21.5, canonical=True)) == 21.5
    assert device_core.loads(cbor2.dumps(100000.0, canonical=True)) == 100000.0
    assert device_core.loads(cbor2.dumps(1.5, canonical=True)) == 1.5


def test_device_frame_matches_serial_framing() -> None:
    payload = b"\x01\x02\x03\x04"
    assert decode_frame(device_core.frame(payload)) == (payload, b"")


def test_device_reads_serial_framing() -> None:
    stream = _Stream(encode_frame(b"hello frame"))
    assert device_core.read_frame(stream) == b"hello frame"


def test_read_frame_returns_none_when_idle() -> None:
    assert device_core.read_frame(_Stream(b"")) is None


def test_read_frame_reassembles_partial_reads() -> None:
    stream = _Stream(encode_frame(b"reassemble me"), chunk=1)
    assert device_core.read_frame(stream) == b"reassemble me"


def test_tools_list_round_trip() -> None:
    response = _exchange(_build_device(), Request(1, mcplite.TOOLS_LIST, {}))
    assert not response.is_error
    names = [tool["name"] for tool in response.result["tools"]]
    assert names == ["read_temp", "set_led"]


def test_tools_call_round_trip() -> None:
    request = Request(7, mcplite.TOOLS_CALL, {"name": "read_temp", "arguments": {}})
    response = _exchange(_build_device(), request)
    assert not response.is_error
    assert response.id == 7
    assert response.result == {"content": {"celsius": 21.5}}


def test_tools_call_passes_arguments() -> None:
    request = Request(8, mcplite.TOOLS_CALL, {"name": "set_led", "arguments": {"on": True}})
    response = _exchange(_build_device(), request)
    assert response.result == {"content": {"on": True}}


def test_unknown_tool_returns_error() -> None:
    request = Request(9, mcplite.TOOLS_CALL, {"name": "missing", "arguments": {}})
    response = _exchange(_build_device(), request)
    assert response.is_error
    assert response.error["code"] == mcplite.TOOL_NOT_FOUND


def test_unknown_method_returns_error() -> None:
    response = _exchange(_build_device(), Request(3, "prompts/list", {}))
    assert response.is_error
    assert response.error["code"] == mcplite.METHOD_NOT_FOUND


# --- FrameReader: push-based frame reassembly for packet links (e.g. BLE) ------------

def test_frame_reader_reassembles_single_frame() -> None:
    reader = device_core.FrameReader()
    reader.feed(encode_frame(b"hello frame"))
    assert reader.next_frame() == b"hello frame"
    assert reader.next_frame() is None


def test_frame_reader_reassembles_byte_at_a_time() -> None:
    reader = device_core.FrameReader()
    for byte in encode_frame(b"reassemble me"):
        reader.feed(bytes([byte]))
    assert reader.next_frame() == b"reassemble me"


def test_frame_reader_yields_multiple_frames_in_order() -> None:
    reader = device_core.FrameReader()
    reader.feed(encode_frame(b"one") + encode_frame(b"two"))
    assert reader.next_frame() == b"one"
    assert reader.next_frame() == b"two"
    assert reader.next_frame() is None


def test_frame_reader_returns_none_until_frame_complete() -> None:
    reader = device_core.FrameReader()
    framed = encode_frame(b"partial")
    reader.feed(framed[:3])
    assert reader.next_frame() is None
    reader.feed(framed[3:])
    assert reader.next_frame() == b"partial"


def test_frame_reader_handles_empty_payload() -> None:
    reader = device_core.FrameReader()
    reader.feed(encode_frame(b""))
    assert reader.next_frame() == b""
