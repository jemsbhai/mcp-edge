"""Command-line interface for MCP-Edge."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from . import __version__

if TYPE_CHECKING:
    from .gateway import Gateway


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser for the ``mcp-edge`` command."""
    parser = argparse.ArgumentParser(
        prog="mcp-edge",
        description="MCP-Edge: extend the Model Context Protocol to edge and IoT devices.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"mcp-edge {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="Run an MCP-Edge gateway over stdio.")
    run.add_argument("--config", help="Path to a gateway configuration file.")
    run.add_argument(
        "--demo",
        action="store_true",
        help="Serve a gateway preloaded with simulated devices.",
    )
    return parser


async def demo_gateway() -> Gateway:
    """Build a gateway preloaded with simulated devices, for demos and local testing."""
    from .client import MCPLiteClient
    from .devices import SimulatedDevice
    from .gateway import Gateway
    from .registry import DeviceRegistry
    from .tiers import Tier
    from .transports import LoopbackTransport

    registry = DeviceRegistry()

    sensor = SimulatedDevice("sensor-01")
    sensor.add_tool(
        "read_temp",
        lambda args: {"celsius": 21.5},
        description="Read the temperature in Celsius.",
    )
    sensor.add_tool(
        "read_humidity",
        lambda args: {"percent": 48},
        description="Read the relative humidity in percent.",
    )
    sensor_transport = LoopbackTransport(sensor.handle)
    await sensor_transport.open()
    registry.register("sensor-01", MCPLiteClient(sensor_transport), Tier.SMART_NODE)

    ring = SimulatedDevice("ring")
    ring.add_tool(
        "heart_rate",
        lambda args: {"bpm": 72},
        description="Read the current heart rate in beats per minute.",
    )
    ring_transport = LoopbackTransport(ring.handle)
    await ring_transport.open()
    registry.register("ring", MCPLiteClient(ring_transport), Tier.BLE_WEARABLE)

    return Gateway(registry)


async def _serve(*, config: str | None, demo: bool) -> None:
    import sys

    from .gateway import Gateway
    from .registry import DeviceRegistry
    from .server import build_server, run_stdio

    if config is not None:
        print("mcp-edge: --config is not supported yet; ignoring it", file=sys.stderr)

    gateway = await demo_gateway() if demo else Gateway(DeviceRegistry())
    count = len(gateway.registry)
    print(f"mcp-edge: serving {count} device(s) over stdio", file=sys.stderr)
    await run_stdio(build_server(gateway))


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``mcp-edge`` console script."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        import asyncio

        asyncio.run(_serve(config=args.config, demo=args.demo))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
