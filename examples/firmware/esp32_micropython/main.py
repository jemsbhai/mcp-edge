"""MicroPython entry point: run the MCP-Lite device on an ESP32 over UART.

Flash this file together with ``mcplite_device.py`` onto an ESP32 running MicroPython
(see ``README.md`` in this directory). It wires two demo tools -- ``read_temp`` and
``set_led`` -- into the portable device core and serves them over a dedicated UART, so
an MCP-Edge gateway on a host can drive the board with ``SerialTransport``.

UART0 is left alone for the REPL and boot logs; data frames travel on UART1. Edit the
pin and baud constants below to match your board's wiring.
"""

from machine import UART, Pin
from mcplite_device import MCPLiteDevice, serve_forever

# --- Board wiring (edit to match your hardware) -------------------------------------
LED_PIN = 2     # onboard LED on most ESP32 DevKit boards
UART_ID = 1     # UART1; UART0 stays free for the REPL and logs
UART_TX = 17
UART_RX = 16
UART_BAUD = 115200

_led = Pin(LED_PIN, Pin.OUT)


def _read_temp(args):
    # Placeholder reading. Swap in a real sensor (an attached DS18B20, or the ESP32's
    # internal temperature sensor) once one is wired up.
    return {"celsius": 21.5}


def _set_led(args):
    on = bool(args.get("on"))
    _led.value(1 if on else 0)
    return {"on": on}


def main():
    uart = UART(UART_ID, baudrate=UART_BAUD, tx=UART_TX, rx=UART_RX, timeout=200)
    device = MCPLiteDevice()
    device.add_tool("read_temp", _read_temp, "Read the current temperature in Celsius")
    device.add_tool("set_led", _set_led, "Turn the onboard LED on or off")
    # Startup marker on UART0 (the REPL/log channel). The Wokwi CI boot smoke test
    # waits for this line to confirm the firmware booted under real MicroPython.
    print("mcp-edge device ready")
    serve_forever(device, uart)


main()
