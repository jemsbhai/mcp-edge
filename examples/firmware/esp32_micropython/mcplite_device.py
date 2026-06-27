"""Portable MCP-Lite device core (CPython + MicroPython).

This module is the protocol brain of an MCP-Edge device. It runs unchanged on a host
under CPython (so it can be tested) and on a microcontroller under MicroPython (see
``main.py`` in this directory), so it deliberately avoids type annotations, f-strings,
and any hardware or third-party imports -- only ``struct`` from the standard library.

It re-implements, in a constrained-device-friendly form, the three things a device needs
to talk to the MCP-Edge gateway:

* a CBOR encoder/decoder for the JSON-like value subset MCP-Lite uses, wire compatible
  with the gateway's ``cbor2``-based codec;
* the length-prefixed framing the serial transport uses: a 2-byte big-endian length
  followed by the CBOR payload, with both a pull-based reader (``read_frame``) for stream
  links and a push-based reader (``FrameReader``) for packet links such as BLE;
* an MCP-Lite request dispatcher for ``tools/list``, ``tools/call`` and
  ``resources/read`` that mirrors the in-process simulator's behaviour.

The constants below mirror ``mcp_edge.mcplite``; the host test cross-checks them. Floats
are sent as CBOR float64 to match the gateway's codec; inbound floats are decoded with
``struct``, which assumes a MicroPython build with double-precision support.
"""

import struct

TOOLS_LIST = "tools/list"
TOOLS_CALL = "tools/call"
RESOURCES_READ = "resources/read"

METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
TOOL_NOT_FOUND = -32001
RESOURCE_NOT_FOUND = -32002


# --- CBOR (JSON-subset) codec -------------------------------------------------------

def _write_head(out, major, length):
    prefix = major << 5
    if length < 24:
        out.append(prefix | length)
    elif length < 0x100:
        out.append(prefix | 24)
        out.append(length)
    elif length < 0x10000:
        out.append(prefix | 25)
        out.append((length >> 8) & 0xFF)
        out.append(length & 0xFF)
    elif length < 0x100000000:
        out.append(prefix | 26)
        out.append((length >> 24) & 0xFF)
        out.append((length >> 16) & 0xFF)
        out.append((length >> 8) & 0xFF)
        out.append(length & 0xFF)
    else:
        out.append(prefix | 27)
        for shift in (56, 48, 40, 32, 24, 16, 8, 0):
            out.append((length >> shift) & 0xFF)


def _encode(out, obj):
    if obj is True:
        out.append(0xF5)
    elif obj is False:
        out.append(0xF4)
    elif obj is None:
        out.append(0xF6)
    elif isinstance(obj, int):
        if obj >= 0:
            _write_head(out, 0, obj)
        else:
            _write_head(out, 1, -1 - obj)
    elif isinstance(obj, float):
        out.append(0xFB)
        out.extend(struct.pack(">d", obj))
    elif isinstance(obj, str):
        data = obj.encode("utf-8")
        _write_head(out, 3, len(data))
        out.extend(data)
    elif isinstance(obj, (bytes, bytearray)):
        _write_head(out, 2, len(obj))
        out.extend(obj)
    elif isinstance(obj, dict):
        _write_head(out, 5, len(obj))
        for key in obj:
            _encode(out, key)
            _encode(out, obj[key])
    elif isinstance(obj, (list, tuple)):
        _write_head(out, 4, len(obj))
        for item in obj:
            _encode(out, item)
    else:
        raise ValueError("cannot CBOR-encode type: " + str(type(obj)))


def dumps(obj):
    """Encode a JSON-like object to CBOR bytes."""
    out = bytearray()
    _encode(out, obj)
    return bytes(out)


def _read_uint(data, index, info):
    if info < 24:
        return info, index
    if info == 24:
        return data[index], index + 1
    if info == 25:
        return (data[index] << 8) | data[index + 1], index + 2
    if info == 26:
        value = (
            (data[index] << 24)
            | (data[index + 1] << 16)
            | (data[index + 2] << 8)
            | data[index + 3]
        )
        return value, index + 4
    if info == 27:
        value = 0
        for offset in range(8):
            value = (value << 8) | data[index + offset]
        return value, index + 8
    raise ValueError("indefinite-length CBOR items are not supported")


def _read_float16(high, low):
    bits = (high << 8) | low
    exponent = (bits >> 10) & 0x1F
    mantissa = bits & 0x3FF
    sign = -1.0 if (bits & 0x8000) else 1.0
    if exponent == 0:
        magnitude = mantissa / 1024.0 * (2.0 ** -14)
    elif exponent == 0x1F:
        magnitude = float("inf") if mantissa == 0 else float("nan")
    else:
        magnitude = (1.0 + mantissa / 1024.0) * (2.0 ** (exponent - 15))
    return sign * magnitude


def _decode(data, index):
    initial = data[index]
    major = initial >> 5
    info = initial & 0x1F
    index += 1
    if major == 0:
        return _read_uint(data, index, info)
    if major == 1:
        value, index = _read_uint(data, index, info)
        return -1 - value, index
    if major == 2:
        length, index = _read_uint(data, index, info)
        return bytes(data[index:index + length]), index + length
    if major == 3:
        length, index = _read_uint(data, index, info)
        return bytes(data[index:index + length]).decode("utf-8"), index + length
    if major == 4:
        length, index = _read_uint(data, index, info)
        items = []
        for _ in range(length):
            item, index = _decode(data, index)
            items.append(item)
        return items, index
    if major == 5:
        length, index = _read_uint(data, index, info)
        result = {}
        for _ in range(length):
            key, index = _decode(data, index)
            value, index = _decode(data, index)
            result[key] = value
        return result, index
    if major == 7:
        if info == 20:
            return False, index
        if info == 21:
            return True, index
        if info == 22:
            return None, index
        if info == 25:
            return _read_float16(data[index], data[index + 1]), index + 2
        if info == 26:
            return struct.unpack(">f", data[index:index + 4])[0], index + 4
        if info == 27:
            return struct.unpack(">d", data[index:index + 8])[0], index + 8
        raise ValueError("unsupported CBOR simple value: " + str(info))
    raise ValueError("unsupported CBOR major type: " + str(major))


def loads(data):
    """Decode CBOR bytes into a JSON-like object."""
    value, _index = _decode(data, 0)
    return value


# --- Length-prefix framing ----------------------------------------------------------

def frame(payload):
    """Wrap a payload as a 2-byte big-endian length followed by the payload."""
    size = len(payload)
    if size > 0xFFFF:
        raise ValueError("frame too large: " + str(size) + " bytes (max 65535)")
    return bytes([(size >> 8) & 0xFF, size & 0xFF]) + bytes(payload)


def _recv(stream, count):
    buffer = b""
    while len(buffer) < count:
        chunk = stream.read(count - len(buffer))
        if not chunk:
            if not buffer:
                return None
            continue
        buffer += chunk
    return buffer


def read_frame(stream):
    """Read one length-prefixed frame from ``stream``; return ``None`` when idle.

    ``stream.read(n)`` must return up to ``n`` bytes, or an empty value / ``None`` when
    no data is available (as MicroPython's ``UART.read`` does on timeout).
    """
    header = _recv(stream, 2)
    if header is None:
        return None
    size = (header[0] << 8) | header[1]
    if size == 0:
        return b""
    return _recv(stream, size)


class FrameReader:
    """Reassemble length-prefixed frames from pushed byte chunks.

    Unlike ``read_frame``, which pulls from a stream, ``FrameReader`` is fed bytes as they
    arrive and emits complete payloads -- use it on links that deliver discrete packets
    rather than a readable stream, such as BLE notifications. ``feed`` appends received
    bytes; ``next_frame`` returns the next complete payload, or ``None`` while one is still
    incomplete. The framing matches ``frame``: a 2-byte big-endian length then the payload.
    """

    def __init__(self):
        self._buffer = bytearray()

    def feed(self, data):
        """Append received bytes to the reassembly buffer."""
        self._buffer.extend(data)

    def next_frame(self):
        """Return the next complete payload, or ``None`` if a frame is still incomplete."""
        buffer = self._buffer
        if len(buffer) < 2:
            return None
        size = (buffer[0] << 8) | buffer[1]
        end = 2 + size
        if len(buffer) < end:
            return None
        payload = bytes(buffer[2:end])
        del buffer[:end]
        return payload


# --- MCP-Lite device ----------------------------------------------------------------

def _ok(request_id, result):
    return {"id": request_id, "result": result}


def _fail(request_id, code, message):
    return {"id": request_id, "error": {"code": code, "message": message}}


class MCPLiteDevice:
    """An MCP-Lite device: register tools and resources, then dispatch requests."""

    def __init__(self):
        self._tools = {}
        self._resources = {}

    def add_tool(self, name, handler, description="", input_schema=None):
        spec = {
            "name": name,
            "description": description,
            "inputSchema": input_schema or {},
        }
        self._tools[name] = (handler, spec)

    def add_resource(self, uri, value):
        self._resources[uri] = value

    def list_tools(self):
        return [spec for (_handler, spec) in self._tools.values()]

    def dispatch(self, request):
        """Map a decoded request dict to a response dict."""
        request_id = request.get("id", 0)
        method = request.get("method")
        params = request.get("params") or {}
        if method == TOOLS_LIST:
            return _ok(request_id, {"tools": self.list_tools()})
        if method == TOOLS_CALL:
            return self._call_tool(request_id, params)
        if method == RESOURCES_READ:
            return self._read_resource(request_id, params)
        return _fail(request_id, METHOD_NOT_FOUND, "unknown method: " + str(method))

    def _call_tool(self, request_id, params):
        name = params.get("name")
        entry = self._tools.get(name) if isinstance(name, str) else None
        if entry is None:
            return _fail(request_id, TOOL_NOT_FOUND, "no such tool: " + str(name))
        handler, _spec = entry
        arguments = params.get("arguments") or {}
        return _ok(request_id, {"content": handler(arguments)})

    def _read_resource(self, request_id, params):
        uri = params.get("uri")
        if not isinstance(uri, str) or uri not in self._resources:
            return _fail(request_id, RESOURCE_NOT_FOUND, "no such resource: " + str(uri))
        return _ok(request_id, {"contents": self._resources[uri]})

    def handle(self, payload):
        """Decode a CBOR request payload and return the CBOR response payload."""
        return dumps(self.dispatch(loads(payload)))


def serve_forever(device, stream):
    """Serve ``device`` over ``stream`` forever, one length-prefixed frame at a time."""
    while True:
        payload = read_frame(stream)
        if payload is None:
            continue
        try:
            reply = device.handle(payload)
        except Exception:
            continue
        stream.write(frame(reply))
