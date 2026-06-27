# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- BLE transport (`transports.BLETransport`, `ble` extra) that carries MCP-Lite frames over
  a Bluetooth Low Energy GATT link via bleak. It defaults to the Nordic UART Service —
  writing to the peripheral's RX characteristic and subscribing to its TX characteristic
  for notifications — with both characteristic UUIDs overridable for other firmware. It
  reuses the serial length-prefix framing, splitting each frame into MTU-sized packets on
  send and reassembling inbound notifications from the same prefix; bleak is imported
  lazily. Validated in software against an in-memory fake; not yet exercised on physical
  hardware.
- BLE variant of the ESP32 MicroPython example: two device entry points over the Nordic
  UART Service — `main_ble.py` (aioble) and `main_ble_lowlevel.py` (the built-in
  `bluetooth` module) — plus a `host_demo_ble.py` host demo driven through `BLETransport`.
  The portable core gains a push-based `FrameReader` that reassembles frames from BLE
  packets (covered by `tests/test_firmware_core.py`). The BLE entry points are not booted
  in CI (Wokwi has no BLE radio) and are not validated on hardware.

## [0.1.1] - 2026-06-25

### Added
- Serial (UART) transport (`transports.SerialTransport`, `serial` extra) that carries
  MCP-Lite frames over a length-prefixed wire format: a 2-byte big-endian length followed
  by the CBOR payload. Blocking pyserial I/O runs in a worker thread, and pyserial is
  imported lazily — needed only when opening a real port. The `encode_frame` and
  `decode_frame` helpers are exported so device firmware can match the framing. Validated
  in software against an in-memory fake; not yet exercised on physical hardware.
- Portable firmware device core
  (`examples/firmware/esp32_micropython/mcplite_device.py`) that runs unchanged under
  CPython and MicroPython: a self-contained CBOR-subset codec, the serial length-prefix
  framing, and an MCP-Lite request dispatcher, with no hardware or third-party imports. A
  hermetic test (`tests/test_firmware_core.py`) cross-checks it against the gateway's
  codec, framing, and protocol semantics under CPython.
- ESP32 MicroPython device example (`examples/firmware/esp32_micropython/`): a `main.py`
  entry point exposing `read_temp` and `set_led` over UART, a hardware host demo
  (`host_demo.py`) that drives a real board through `SerialTransport` + `MCPLiteClient`,
  and a README covering flashing and wiring.
- Wokwi-simulated boot smoke test (`.github/workflows/wokwi.yml`) that bakes the device
  files into a MicroPython image and confirms it boots and runs `main.py` on a simulated
  ESP32. Gated on a `WOKWI_CLI_TOKEN` secret and skipped without it. Validates MicroPython
  compatibility only — not the serial protocol round-trip, and not physical hardware.

## [0.1.0] - 2026-06-25

First public release. Alpha: the API is unstable and will change.

### Added
- Four-tier device taxonomy (`tiers`) mapping RFC 7228 device classes to MCP
  strategies, with nine reference platforms.
- CBOR codec (`codec`) for the device link, plus a JSON size-comparison helper.
- Transport abstraction (`transports`) and an in-process loopback transport.
- MCP-Lite protocol (`mcplite`): CBOR-framed `tools/list`, `tools/call`,
  `resources/read`.
- Device simulator (`devices.SimulatedDevice`) for hardware-free development and tests.
- Device client layer (`client`): the `DeviceClient` interface and `MCPLiteClient`.
- Device registry (`registry`) and the aggregating `Gateway`, which exposes every
  device's tools under a device-prefixed composite namespace and routes calls back.
- Gateway exposed as an MCP server (`server.build_server`, `run_stdio`) built on the
  SDK's low-level `Server`.
- `mcp-edge` CLI with `run [--demo]` to serve a gateway (optionally preloaded with
  simulated devices) over stdio.
- Protocol adaptations: schema caching (`schema`), connection pooling (`pool`), and
  offline request buffering (`buffer`).
- Health monitor (`health`) that probes devices and updates their connection state.

### Notes
- Real serial / BLE / Wi-Fi transports (and firmware-in-the-loop testing) arrive in a
  later release; this version exercises the full path against simulated devices.
- Performance figures in the MCP-Edge paper are projected estimates, not measurements
  taken from this code.
