"""Command-line interface for MCP-Edge."""

from __future__ import annotations

import argparse

from . import __version__


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

    run = subparsers.add_parser("run", help="Run an MCP-Edge gateway.")
    run.add_argument("--config", help="Path to a gateway configuration file.")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``mcp-edge`` console script."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        parser.error("`run` is not implemented yet — the gateway lands in an upcoming release.")

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
