"""Drive a real ESP32 MCP-Lite device from a host over Wi-Fi (TCP).

This is a hardware demo, not a test: it needs an ESP32 flashed with ``mcplite_device.py``
and ``main_wifi.py`` from this directory, connected to the same network. It is excluded
from the automated test suite, which stays hermetic.

By default it connects to ``mcp-edge.local`` (the device's mDNS hostname). Pass
``--host``/``--port`` for a different address, or ``--discover`` to browse for devices
advertising the MCP-Edge service over mDNS first -- which requires a device advertising the
full service record (see the README; the stock firmware advertises only its hostname)::

    python host_demo_wifi.py                       # connect to mcp-edge.local:8765
    python host_demo_wifi.py --host 192.168.1.50   # connect by IP
    python host_demo_wifi.py --discover            # find devices via mDNS first

The ``--discover`` path needs the wifi extra: ``pip install "mcp-edge[wifi]"``.
"""

from __future__ import annotations

import argparse
import asyncio

from mcp_edge.client import DeviceError, MCPLiteClient
from mcp_edge.transports import TcpTransport
from mcp_edge.transports.discovery import discover


async def _drive(transport: TcpTransport) -> None:
    async with transport:
        client = MCPLiteClient(transport)

        tools = await client.list_tools()
        print(f"device exposes {len(tools)} tool(s):")
        for tool in tools:
            print(f"  - {tool['name']}: {tool.get('description', '')}")

        reading = await client.call_tool("read_temp", {})
        print(f"read_temp -> {reading}")

        for state in (True, False):
            result = await client.call_tool("set_led", {"on": state})
            print(f"set_led on={state} -> {result}")


async def _run(host: str, port: int, use_discovery: bool) -> None:
    if use_discovery:
        devices = await discover()
        if not devices:
            raise SystemExit("no MCP-Edge devices found via mDNS")
        found = devices[0]
        print(f"discovered {found.name} at {found.host}:{found.port}")
        host, port = found.host, found.port
    await _drive(TcpTransport(host, port))


def main() -> None:
    parser = argparse.ArgumentParser(description="Drive an ESP32 MCP-Lite device over Wi-Fi.")
    parser.add_argument(
        "--host", default="mcp-edge.local", help="device host (default mcp-edge.local)"
    )
    parser.add_argument("--port", type=int, default=8765, help="device TCP port (default 8765)")
    parser.add_argument("--discover", action="store_true", help="find the device via mDNS first")
    args = parser.parse_args()
    try:
        asyncio.run(_run(args.host, args.port, args.discover))
    except DeviceError as exc:
        code = "" if exc.code is None else f" (code {exc.code})"
        raise SystemExit(f"device error{code}: {exc}") from exc


if __name__ == "__main__":
    main()
