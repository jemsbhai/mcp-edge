# MCP-Edge

**Extend the [Model Context Protocol (MCP)](https://modelcontextprotocol.io) to edge and IoT devices.**

MCP-Edge lets cloud LLM agents discover and invoke physical hardware through the same
tool interface they already use for software APIs. It provides:

- a **gateway** that bridges cloud-native MCP transports (SSE / HTTP) to constrained
  device channels (UART, BLE, local Wi-Fi), presenting every downstream device as a
  standard MCP tool provider;
- **MCP-Lite**, a lightweight MCP server for devices with as little as ~512 KB of RAM;
- a **four-tier device taxonomy** (constrained MCUs, smart IoT nodes, BLE-only
  wearables, Linux-class edge computers) that maps an MCP strategy to each tier;
- protocol adaptations for constrained links: CBOR encoding, schema caching,
  connection pooling, and offline request buffering.

> **Status: alpha, under active development.** The public API is unstable and will
> change. This repository is a *reference implementation* of the framework described in
> the MCP-Edge paper (IEEE Cloud Summit 2026). Performance figures reported in the paper
> are projected estimates, not measurements taken from this codebase.

## Installation

Requires Python 3.10+. Not yet published to PyPI — install from source:

```bash
pip install -e ".[dev]"
```

Optional transport backends:

```bash
pip install "mcp-edge[serial]"   # UART / USB serial devices
pip install "mcp-edge[ble]"      # BLE devices
pip install "mcp-edge[wifi]"     # local Wi-Fi / mDNS discovery
```

## Quickstart

_Coming soon — the gateway and device simulator land in upcoming releases._

## Roadmap

- [ ] **v0.1** — gateway core, serial + simulated transports, protocol adaptations,
      device simulator, CLI, hermetic CI
- [ ] **v0.1–0.2** — [Wokwi](https://wokwi.com) firmware-in-the-loop tests
      (Arduino / ESP32 / RP2040)
- [ ] **v0.2+** — Edge Impulse (inference as an MCP tool) and Arduino IoT Cloud
      (properties as MCP) integration examples; Renode / QEMU backends

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1     # PowerShell (Windows); use `source .venv/bin/activate` on Unix
pip install -e ".[dev]"
pytest -q
ruff check .
```

## License

MIT — see [LICENSE](LICENSE).
