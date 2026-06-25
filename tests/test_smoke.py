"""Smoke tests: the package imports cleanly and exposes its surface."""

from __future__ import annotations

import mcp_edge
from mcp_edge.cli import build_parser


def test_version_is_a_semver_string() -> None:
    assert isinstance(mcp_edge.__version__, str)
    assert mcp_edge.__version__.count(".") >= 2


def test_cli_parser_builds() -> None:
    parser = build_parser()
    assert parser.prog == "mcp-edge"
