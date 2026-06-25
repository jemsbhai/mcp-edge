"""Tests for the CLI parser and run wiring."""

from __future__ import annotations

from mcp_edge.cli import build_parser, demo_gateway


def test_run_subcommand_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(["run", "--demo"])
    assert args.command == "run"
    assert args.demo is True
    assert args.config is None


async def test_demo_gateway_lists_simulated_tools() -> None:
    gateway = await demo_gateway()
    names = [tool["name"] for tool in await gateway.list_tools()]
    assert "sensor-01/read_temp" in names
    assert "sensor-01/read_humidity" in names
    assert "ring/heart_rate" in names
    assert len(gateway.registry) == 2
