# Platform support and verification

Where each target board sits in MCP-Edge and how far it has been verified. The project
splits into two install paths:

- **Gateway (host)** — Linux-class boards run the full `mcp-edge` gateway via
  `pip install mcp-edge`. These are ordinary aarch64 Linux machines.
- **Device firmware** — microcontrollers run an MCP-Lite device (the
  [ESP32 MicroPython example](../examples/firmware/esp32_micropython/)), which a gateway
  drives over a serial, BLE, or Wi-Fi transport.

Verification here is **simulation and emulation in CI**, not physical hardware. It proves
the install, deploy, and boot paths on the real OS and CPU architecture, but emulation is
not physical silicon and is not memory-constrained to a real board, so it complements a
hardware pass rather than replacing it.

## Status

| Board | Class | Install path | How it's verified | Status |
| --- | --- | --- | --- | --- |
| Raspberry Pi 4 Model B | Linux | Gateway (`pip install`) | Native `ubuntu-24.04-arm` runner + Raspberry Pi OS under QEMU | Verified in CI |
| Raspberry Pi 5 Model B | Linux | Gateway (`pip install`) | Native `ubuntu-24.04-arm` runner + Raspberry Pi OS under QEMU | Verified in CI |
| Arduino UNO Q | Linux + MCU | Gateway (`pip install`) on the Linux side | Native `ubuntu-24.04-arm` runner + Raspberry Pi OS under QEMU | Verified in CI (gateway) |
| ESP32-S3 | MCU | Device firmware | Wokwi boot smoke test (`board-esp32-s3-devkitc-1`) | Verified in CI |
| ESP32-C3 | MCU | Device firmware | Wokwi boot smoke test (`board-esp32-c3-devkitm-1`) | Verified in CI |
| ESP32-C6 | MCU | Device firmware | Wokwi boot smoke test (`board-esp32-c6-devkitc-1`) | Verified in CI |
| ESP32-C5 | MCU | Device firmware | Wokwi C5 support is still alpha | Sim planned |
| RP2040 | MCU | Device firmware | Wokwi (rp2 port uses different image tooling) | Stretch |
| nRF52840 | MCU | Device firmware | Renode (also on the Renode/QEMU roadmap) | Stretch |
| Arduino UNO R4 | MCU | Device firmware | Needs an Arduino/C MCP-Lite firmware port first | Needs firmware port |
| Arduino Giga | MCU | Device firmware | Needs a firmware port; no MicroPython example yet | Needs firmware port |
| Arduino UNO R3 | MCU (AVR) | None | ATmega328P, 2 KB RAM — cannot host an MCP-Lite device | Cannot host |
| Arduino Mega 2560 | MCU (AVR) | None | ATmega2560, 8 KB RAM — cannot host an MCP-Lite device | Cannot host |

## Notes

- **Linux boards** are verified two ways: the native `ubuntu-24.04-arm` job installs the
  full extras (so the compiled wheels `cbor2`, `bleak`, and `zeroconf` are proven to build
  on aarch64), runs the test suite, and boots the demo gateway; the QEMU job repeats those
  checks inside the actual Raspberry Pi OS image. The Arduino UNO Q is a Linux SBC paired
  with an MCU, so its gateway (Linux) side is covered here; its MCU side would follow the
  device-firmware path.
- **ESP32 family** reuses the existing Wokwi boot harness, booting the same MicroPython
  firmware on each chip variant (ESP32, S3, C3, C6) to confirm it imports and initializes
  under real MicroPython on that target. The variants run the Wi-Fi entry point, which has
  no board-specific GPIO; the serial entry point pins UART1 to GPIO16/17, which are flash
  pins on the C3, so it stays ESP32-only. C5 is left for later since Wokwi's C5 support is
  still alpha.
- **RP2040 and nRF52840** are reachable in simulation (Wokwi and Renode respectively) but
  need their own tooling, so they are staged as stretch work.
- **AVR boards (UNO R3, Mega 2560)** have single-digit kilobytes of RAM and cannot host an
  MCP-Lite device. They are listed for completeness, not as a target to flash.
- **UNO R4 and Giga** are capable enough but have no MCP-Lite firmware yet (the only worked
  example is ESP32 MicroPython), so they need a firmware port before they can be verified.
