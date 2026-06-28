# ESP32 (MicroPython) MCP-Lite device

A worked example of an **MCP-Edge Tier-2 device**: an ESP32 running MicroPython that
exposes tools over a serial link, Bluetooth Low Energy, or Wi-Fi, which an MCP-Edge
gateway on a host drives with `SerialTransport`, `BLETransport`, or `TcpTransport`.

> **Status:** the protocol core is validated in software against the gateway's codec and
> framing (`tests/test_firmware_core.py` in the repo root). The serial `main.py` and the
> Wi-Fi `main_wifi.py` are booted on a *simulated* ESP32 in CI (see
> [Simulated boot test](#simulated-boot-test)); the BLE entry points share that tested
> core but are **not** booted — Wokwi has no BLE radio. Nothing here has been run on
> physical hardware by the maintainers — treat the flashing and wiring notes below as a
> starting point and verify against your own board.

## Files

| File | Runtime | Role |
| --- | --- | --- |
| `mcplite_device.py` | CPython **and** MicroPython | Portable protocol core: a small CBOR codec, the 2-byte length framing (pull-based `read_frame` for streams and push-based `FrameReader` for packet links), and the request dispatcher. No hardware imports. |
| `main.py` | MicroPython | Serial device entry point: wires `read_temp` and `set_led` into the core and serves them over UART1. |
| `main_ble.py` | MicroPython | BLE device entry point (aioble): the same tools over the Nordic UART Service. Needs aioble installed. Not booted in CI. |
| `main_ble_lowlevel.py` | MicroPython | BLE device entry point using the built-in `bluetooth` module — nothing extra to install. Not booted in CI. |
| `main_wifi.py` | MicroPython | Wi-Fi device entry point: the same tools over a TCP server, reachable at `mcp-edge.local`. Booted in CI against Wokwi's simulated network. |
| `host_demo.py` | CPython (host) | Drives a connected board over serial: lists tools, reads the temperature, toggles the LED. Requires hardware; not part of CI. |
| `host_demo_ble.py` | CPython (host) | The same demo over BLE, via `BLETransport`. Requires hardware; not part of CI. |
| `host_demo_wifi.py` | CPython (host) | The same demo over Wi-Fi, via `TcpTransport`, with an optional `--discover` flag. Requires a device on the network; not part of CI. |

## Flash the board (serial)

1. Install [MicroPython](https://micropython.org/download/esp32/) on your ESP32 with
   `esptool`, then confirm the REPL responds over USB (UART0).
2. Copy both `mcplite_device.py` and `main.py` to the board's filesystem. With
   [`mpremote`](https://docs.micropython.org/en/latest/reference/mpremote.html):

   ```bash
   mpremote connect <port> cp mcplite_device.py :
   mpremote connect <port> cp main.py :
   ```

   `main.py` runs automatically on boot and starts serving.

## Wire the data UART

`main.py` puts data frames on **UART1** (TX `GPIO17`, RX `GPIO16`), leaving UART0 free
for the REPL and boot logs. Connect a USB-to-UART adapter to the host and cross the
lines:

| Board pin | Adapter pin |
| --- | --- |
| `GPIO17` (TX) | RX |
| `GPIO16` (RX) | TX |
| `GND` | `GND` |

Edit the pin constants at the top of `main.py` if your board differs.

## Run the host demo (serial)

```bash
pip install "mcp-edge[serial]"
python host_demo.py --port COM5            # Windows
python host_demo.py --port /dev/ttyUSB0    # Linux
```

You should see the tool list, a temperature reading, and the LED toggling on then off.

## Simulated boot test

CI runs boot smoke tests on a [Wokwi](https://wokwi.com)-simulated ESP32
(`.github/workflows/wokwi.yml`, driven by `wokwi.toml` and `diagram.json` in this
directory) as a two-leg matrix. Each leg boots an entry point under real MicroPython and
waits for the `mcp-edge device ready` marker, confirming the firmware imports
`mcplite_device.py` and initializes without error on-device — which catches
MicroPython-incompatible code that the CPython tests would miss.

- **serial** boots `main.py`. It does **not** exercise the protocol round-trip: Wokwi
  checks text on UART0, while data frames travel on UART1.
- **wifi** boots `main_wifi.py`, which joins Wokwi's simulated `Wokwi-GUEST` network and
  starts its TCP server (the marker prints only after Wi-Fi connects). It covers the
  boot + connect path but not the TCP round-trip — Wokwi's default Public Gateway is
  outbound-only.

The Wokwi CLI boots a bare firmware image (unlike the web IDE, it does not auto-load
project files), so each leg bakes its `main.py` and `mcplite_device.py` into the image
first: it downloads the stock MicroPython build, pads it to 4 MB, adds a `vfs` partition,
and writes the files into a littlefs image with
[`mp-image-tool-esp32`](https://github.com/glenn20/mp-image-tool-esp32). The job needs a
`WOKWI_CLI_TOKEN` repository secret and skips cleanly without it, so forks and PRs are
unaffected.

## Bluetooth Low Energy (BLE)

The device can speak over BLE instead of a UART, using the **Nordic UART Service** (NUS):
the central writes request frames to the RX characteristic, and the device sends reply
frames back as notifications on the TX characteristic. The framing is identical to the
serial link, so the same `mcplite_device.py` core is reused — inbound packets are
reassembled with `FrameReader` — and only the link glue differs.

Two device entry points are provided; flash **one** of them as `main.py`:

- **`main_ble.py`** uses [aioble](https://github.com/micropython/micropython-lib/tree/master/micropython/bluetooth/aioble),
  the recommended async BLE library. It is the more readable option but must be installed
  on the board (`mpremote ... mip install aioble`, or via Thonny's package manager).
- **`main_ble_lowlevel.py`** uses MicroPython's built-in `bluetooth` module directly, so
  it runs on a stock build with nothing to install, at the cost of more boilerplate.

```bash
# aioble version
mpremote connect <port> mip install aioble
mpremote connect <port> cp mcplite_device.py :
mpremote connect <port> cp main_ble.py :main.py

# or the built-in bluetooth version (no mip install)
mpremote connect <port> cp mcplite_device.py :
mpremote connect <port> cp main_ble_lowlevel.py :main.py
```

No wiring is needed — BLE is wireless; just power the board. Drive it from the host with:

```bash
pip install "mcp-edge[ble]"
python host_demo_ble.py --address AA:BB:CC:DD:EE:FF
```

Find the device's address (a MAC on Linux/Windows, a UUID on macOS) with a BLE scanner —
for example `bleak`'s `BleakScanner`, or a phone app such as nRF Connect. The device
advertises as `mcp-edge`.

> Unlike the serial and Wi-Fi paths, the BLE entry points are **not** booted in CI: Wokwi
> has no BLE radio, so there is no simulated boot test for them. The portable reassembly
> they rely on (`FrameReader`) is covered by `tests/test_firmware_core.py`, but the BLE
> link glue itself has not been exercised in CI or on hardware.

## Wi-Fi (TCP)

The device can also speak over Wi-Fi: `main_wifi.py` connects to a network and serves the
same MCP-Lite frames over a **TCP server** (port 8765 by default), reusing the identical
length-prefix framing — inbound bytes are reassembled with `FrameReader`. A gateway on the
same network drives it with `TcpTransport`.

Flash it as `main.py`, and set your network credentials at the top of `main_wifi.py`
(`WIFI_SSID` / `WIFI_PASSWORD`; the defaults connect to Wokwi's simulated `Wokwi-GUEST`
network):

```bash
mpremote connect <port> cp mcplite_device.py :
mpremote connect <port> cp main_wifi.py :main.py
```

No data wiring is needed — power the board and let it join Wi-Fi. Drive it from the host:

```bash
pip install "mcp-edge[wifi]"
python host_demo_wifi.py --host mcp-edge.local    # connect by hostname
python host_demo_wifi.py --host 192.168.1.50      # or by IP
```

### Finding the device (mDNS)

`main_wifi.py` sets its hostname to `mcp-edge`, so on a network with mDNS it answers at
`mcp-edge.local`. That is all the **stock** MicroPython firmware advertises — a plain
hostname (an A record), not a service record. The library's
`mcp_edge.transports.discovery.discover()` browses for the `_mcp-edge._tcp.local.`
*service*, which the stock firmware does **not** announce, so it will not list this
device — reach it by hostname or IP instead. To make the device discoverable through
`discover()`, add a full mDNS responder such as
[micropython-mdns](https://github.com/cbrand/micropython-mdns), which needs a custom
firmware build (stock builds disable the native C mDNS responder). `discover()` itself is
a general browser and will find any host advertising the service (for example a Linux box
running Avahi):

```bash
python host_demo_wifi.py --discover    # browse mDNS, then connect to the first match
```

> The Wokwi `wifi` boot leg connects to `Wokwi-GUEST` through Wokwi's default Public
> Gateway, which is outbound-only — so CI confirms the device boots, joins Wi-Fi, and
> starts its server, but does not reach the TCP server for a round-trip (that needs
> Wokwi's paid Private Gateway). The example has not been run on physical hardware.

## Note on floats

Frames are CBOR, and floats are encoded as 64-bit doubles to match the gateway's codec.
A MicroPython build without double-precision support will lose precision on float-heavy
payloads; the demo tools use values that round-trip cleanly. The `read_temp` value is a
fixed placeholder -- swap in a real sensor in `main.py`.
