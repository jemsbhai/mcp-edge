# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project scaffold: packaging metadata (`pyproject.toml`), MIT license,
  `.gitignore`, `.env.example`, README, package skeleton, test harness, and CI workflow.
- `mcp-edge` CLI entry point (argparse) with `--version` and a placeholder `run` command.

## [0.1.0] - Unreleased

First release (in progress). Planned scope:

- Gateway core: device registry, schema aggregator, composite MCP server, health monitor.
- Transports: simulated loopback adapter and a `pyserial` UART/USB adapter.
- Protocol adaptations: CBOR codec, schema caching, connection pooling, offline buffering.
- Device simulator: simulated MCP-Lite and gateway-proxy devices for tests and scalability.
