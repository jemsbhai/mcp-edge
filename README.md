# MCP-Edge

[![CI](https://github.com/jemsbhai/mcp-edge/actions/workflows/ci.yml/badge.svg)](https://github.com/jemsbhai/mcp-edge/actions/workflows/ci.yml)

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
> are projected estimates, not measurements taken from this codebase. The full gateway
> path is exercised against *simulated* devices. Serial/UART, BLE, and Wi-Fi (TCP)
> transports have landed in the codebase — each validated in software against an in-memory
> fake and paired with ESP32 MicroPython example firmware, but not yet exercised on
> physical hardware.

## Installation

Requires Python 3.10+.

```bash
pip install mcp-edge
```

For development, install from source:

```bash
git clone https://github.com/jemsbhai/mcp-edge
cd mcp-edge
pip install -e ".[dev]"
```

## Quickstart

**Run a demo gateway** — an MCP server exposing two simulated devices over stdio:

```bash
mcp-edge run --demo
```

This serves a simulated sensor (`read_temp`, `read_humidity`) and a simulated ring
(`heart_rate`), each tool namespaced by device (`sensor-01/read_temp`, ...). To drive it
from an MCP client such as the MCP Inspector or Claude Desktop, configure a stdio server
with command `mcp-edge` and arguments `["run", "--demo"]`. The process logs to stderr and
waits for a client on stdin.

**Use the gateway as a library:**

```python
import asyncio

from mcp_edge.client import MCPLiteClient
from mcp_edge.devices import SimulatedDevice
from mcp_edge.gateway import Gateway
from mcp_edge.registry import DeviceRegistry
from mcp_edge.tiers import Tier
from mcp_edge.transports import LoopbackTransport


async def main() -> None:
    device = SimulatedDevice("sensor-01")
    device.add_tool("read_temp", lambda args: {"celsius": 21.5})

    transport = LoopbackTransport(device.handle)
    await transport.open()

    registry = DeviceRegistry()
    registry.register("sensor-01", MCPLiteClient(transport), Tier.SMART_NODE)

    gateway = Gateway(registry)
    print([tool["name"] for tool in await gateway.list_tools()])  # ['sensor-01/read_temp']
    print(await gateway.call_tool("sensor-01/read_temp", {}))     # {'celsius': 21.5}


asyncio.run(main())
```

**Connect your own device over serial** *(experimental)* — install the `serial` extra
(`pip install "mcp-edge[serial]"`) and point `SerialTransport` at the port your device is
on. It exposes the same `Transport` interface, so it drops into the example above in place
of `LoopbackTransport`:

```python
from mcp_edge.transports import SerialTransport

# "COM3" on Windows, "/dev/ttyUSB0" on Linux/macOS
transport = SerialTransport("COM3", baudrate=115200)
```

Frames use a length-prefixed wire format — a 2-byte big-endian length followed by the CBOR
payload — documented in `transports/serial.py`. Device firmware must frame its replies the
same way; the exported `encode_frame` / `decode_frame` helpers make that straightforward.
This path is **not yet validated on physical hardware**. Worked ESP32 MicroPython firmware
for the serial, BLE, and Wi-Fi transports lives in
[`examples/firmware/esp32_micropython/`](examples/firmware/esp32_micropython/).

## Roadmap

- [x] **v0.1** — gateway core, in-process (loopback) transport, protocol adaptations
      (CBOR, schema caching, connection pooling, offline buffering), device simulator,
      health monitor, CLI, hermetic CI
- [ ] **v0.2** — real transports and [Wokwi](https://wokwi.com) firmware-in-the-loop
      tests (Arduino / ESP32 / RP2040). The serial/UART (`pyserial`), BLE (`bleak`), and
      Wi-Fi (TCP, with mDNS discovery via `zeroconf`) transports have landed
      (software-tested), each with ESP32 MicroPython example firmware
- [ ] **v0.2+** — Edge Impulse (inference as an MCP tool) and Arduino IoT Cloud
      (properties as MCP) integration examples; Renode / QEMU backends

## Development

```powershell
pip install -e ".[dev]"
pytest -q
ruff check .
```

## License

MIT — see [LICENSE](LICENSE).
