# ESP32 (MicroPython) MCP-Lite device

A worked example of an **MCP-Edge Tier-2 device**: an ESP32 running MicroPython that
exposes tools over a serial link, which an MCP-Edge gateway on a host drives with
`SerialTransport`.

> **Status:** the protocol core is validated in software against the gateway's codec and
> framing (`tests/test_firmware_core.py` in the repo root), and `main.py` is booted on a
> *simulated* ESP32 in CI (see [Simulated boot test](#simulated-boot-test)). It has **not**
> been run on physical hardware by the maintainers — treat the flashing and wiring notes
> below as a starting point and verify against your own board.

## Files

| File | Runtime | Role |
| --- | --- | --- |
| `mcplite_device.py` | CPython **and** MicroPython | Portable protocol core: a small CBOR codec, the 2-byte length framing, and the request dispatcher. No hardware imports. |
| `main.py` | MicroPython | Device entry point: wires `read_temp` and `set_led` into the core and serves them over UART1. |
| `host_demo.py` | CPython (host) | Drives a connected board: lists tools, reads the temperature, toggles the LED. Requires hardware; not part of CI. |

## Flash the board

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

## Run the host demo

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

## Note on floats

Frames are CBOR, and floats are encoded as 64-bit doubles to match the gateway's codec.
A MicroPython build without double-precision support will lose precision on float-heavy
payloads; the demo tools use values that round-trip cleanly. The `read_temp` value is a
fixed placeholder -- swap in a real sensor in `main.py`.
