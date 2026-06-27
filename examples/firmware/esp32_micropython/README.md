# ESP32 (MicroPython) MCP-Lite device

A worked example of an **MCP-Edge Tier-2 device**: an ESP32 running MicroPython that
exposes tools over a serial link or Bluetooth Low Energy, which an MCP-Edge gateway on a
host drives with `SerialTransport` or `BLETransport`.

> **Status:** the protocol core is validated in software against the gateway's codec and
> framing (`tests/test_firmware_core.py` in the repo root), and the serial `main.py` is
> booted on a *simulated* ESP32 in CI (see [Simulated boot test](#simulated-boot-test)).
> The BLE entry points share that tested core but are **not** booted in CI — Wokwi has no
> BLE radio. Nothing here has been run on physical hardware by the maintainers — treat the
> flashing and wiring notes below as a starting point and verify against your own board.

## Files

| File | Runtime | Role |
| --- | --- | --- |
| `mcplite_device.py` | CPython **and** MicroPython | Portable protocol core: a small CBOR codec, the 2-byte length framing (pull-based `read_frame` for streams and push-based `FrameReader` for packet links), and the request dispatcher. No hardware imports. |
| `main.py` | MicroPython | Serial device entry point: wires `read_temp` and `set_led` into the core and serves them over UART1. |
| `main_ble.py` | MicroPython | BLE device entry point (aioble): the same tools over the Nordic UART Service. Needs aioble installed. Not booted in CI. |
| `main_ble_lowlevel.py` | MicroPython | BLE device entry point using the built-in `bluetooth` module — nothing extra to install. Not booted in CI. |
| `host_demo.py` | CPython (host) | Drives a connected board over serial: lists tools, reads the temperature, toggles the LED. Requires hardware; not part of CI. |
| `host_demo_ble.py` | CPython (host) | The same demo over BLE, via `BLETransport`. Requires hardware; not part of CI. |

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

CI runs a boot smoke test on a [Wokwi](https://wokwi.com)-simulated ESP32
(`.github/workflows/wokwi.yml`, driven by `wokwi.toml` and `diagram.json` in this
directory). It boots `main.py` under real MicroPython and waits for the
`mcp-edge device ready` marker, confirming the firmware imports `mcplite_device.py` and
initializes without error on-device — which catches MicroPython-incompatible code that the
CPython tests would miss. It does **not** exercise the serial protocol: Wokwi checks text
on UART0, while data frames travel on UART1.

The Wokwi CLI boots a bare firmware image (unlike the web IDE, it does not auto-load
project files), so the workflow bakes `main.py` and `mcplite_device.py` into the image
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

> Unlike the serial path, the BLE entry points are **not** booted in CI: Wokwi has no BLE
> radio, so there is no simulated boot test for them. The portable reassembly they rely on
> (`FrameReader`) is covered by `tests/test_firmware_core.py`, but the BLE link glue itself
> has not been exercised in CI or on hardware.

## Note on floats

Frames are CBOR, and floats are encoded as 64-bit doubles to match the gateway's codec.
A MicroPython build without double-precision support will lose precision on float-heavy
payloads; the demo tools use values that round-trip cleanly. The `read_temp` value is a
fixed placeholder -- swap in a real sensor in `main.py`.
