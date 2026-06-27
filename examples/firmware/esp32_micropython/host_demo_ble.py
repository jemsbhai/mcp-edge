"""Drive a real ESP32 MCP-Lite device from a host over BLE.

This is a hardware demo, not a test: it needs an ESP32 flashed with ``mcplite_device.py``
and one of the BLE entry points (``main_ble.py`` or ``main_ble_lowlevel.py``) from this
directory, advertising the Nordic UART Service. It is deliberately excluded from the
automated test suite, which stays hermetic.

Install the ble extra first::

    pip install "mcp-edge[ble]"

Find the device's address (a MAC on Linux/Windows, a UUID on macOS) -- for example with
bleak's scanner -- then run, pointing ``--address`` at it::

    python host_demo_ble.py --address AA:BB:CC:DD:EE:FF
"""

from __future__ import annotations

import argparse
import asyncio

from mcp_edge.client import DeviceError, MCPLiteClient
from mcp_edge.transports.ble import BLETransport


async def run(address: str) -> None:
    async with BLETransport(address) as transport:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Drive an ESP32 MCP-Lite device over BLE.")
    parser.add_argument(
        "--address",
        required=True,
        help="BLE device address (MAC on Linux/Windows, UUID on macOS)",
    )
    args = parser.parse_args()
    try:
        asyncio.run(run(args.address))
    except DeviceError as exc:
        code = "" if exc.code is None else f" (code {exc.code})"
        raise SystemExit(f"device error{code}: {exc}") from exc


if __name__ == "__main__":
    main()
