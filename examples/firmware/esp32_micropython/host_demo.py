"""Drive a real ESP32 MCP-Lite device from a host over USB-serial.

This is a hardware demo, not a test: it needs an ESP32 flashed with ``main.py`` and
``mcplite_device.py`` from this directory, connected to the host through a USB-to-UART
adapter wired to the board's data UART (GPIO17/GPIO16 in the sample ``main.py``). It is
deliberately excluded from the automated test suite, which stays hermetic.

Install the serial extra first::

    pip install "mcp-edge[serial]"

Then run it, pointing ``--port`` at your adapter::

    python host_demo.py --port COM5            # Windows
    python host_demo.py --port /dev/ttyUSB0    # Linux
"""

from __future__ import annotations

import argparse
import asyncio

from mcp_edge.client import DeviceError, MCPLiteClient
from mcp_edge.transports.serial import SerialTransport


async def run(port: str, baudrate: int) -> None:
    async with SerialTransport(port, baudrate=baudrate) as transport:
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
    parser = argparse.ArgumentParser(description="Drive an ESP32 MCP-Lite device.")
    parser.add_argument("--port", required=True, help="serial port, e.g. COM5 or /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200, help="baud rate (default 115200)")
    args = parser.parse_args()
    try:
        asyncio.run(run(args.port, args.baud))
    except DeviceError as exc:
        code = "" if exc.code is None else f" (code {exc.code})"
        raise SystemExit(f"device error{code}: {exc}") from exc


if __name__ == "__main__":
    main()
