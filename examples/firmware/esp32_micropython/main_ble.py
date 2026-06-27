"""MicroPython entry point: run the MCP-Lite device on an ESP32 over BLE (aioble).

Flash this file together with ``mcplite_device.py`` onto an ESP32 running MicroPython,
after installing aioble (``mip.install("aioble")`` or via Thonny's package manager). It
exposes the same two demo tools as the serial ``main.py`` -- ``read_temp`` and
``set_led`` -- but over a Bluetooth Low Energy GATT link instead of a UART, speaking the
Nordic UART Service so the gateway's ``BLETransport`` can drive it.

The peripheral advertises the Nordic UART Service, accepts one central at a time, and
exchanges MCP-Lite frames: inbound writes on the RX characteristic are reassembled with
``FrameReader`` and dispatched, and each reply frame is split into notification-sized
chunks sent on the TX characteristic. The framing is identical to the serial transport.

This is example code: it is NOT exercised in CI (Wokwi has no BLE radio) and has not been
validated on physical hardware. Treat it as a reference to adapt and test on your board.
"""

import asyncio

import aioble
import bluetooth
from machine import Pin
from mcplite_device import FrameReader, MCPLiteDevice, frame

# --- Nordic UART Service ------------------------------------------------------------
_NUS_SERVICE = bluetooth.UUID("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
_NUS_RX = bluetooth.UUID("6e400002-b5a3-f393-e0a9-e50e24dcca9e")  # central writes here
_NUS_TX = bluetooth.UUID("6e400003-b5a3-f393-e0a9-e50e24dcca9e")  # notify to the central

_DEVICE_NAME = "mcp-edge"
_ADV_INTERVAL_US = 250000
# Conservative notification payload size (BLE default ATT MTU is 23, minus 3 ATT header
# bytes). Raise it if the central negotiates a larger MTU; the gateway reassembles by the
# length prefix regardless, so any value the link accepts works.
_NOTIFY_CHUNK = 20
# A short pause between notification chunks: MicroPython's BLE stack can only queue a few
# notifications, so back-to-back sends risk dropping packets.
_NOTIFY_GAP_MS = 20

# --- Board wiring -------------------------------------------------------------------
LED_PIN = 2  # onboard LED on most ESP32 DevKit boards
_led = Pin(LED_PIN, Pin.OUT)

# --- GATT server --------------------------------------------------------------------
_service = aioble.Service(_NUS_SERVICE)
_rx_char = aioble.Characteristic(_service, _NUS_RX, write=True, capture=True)
_tx_char = aioble.Characteristic(_service, _NUS_TX, notify=True)
aioble.register_services(_service)


def _read_temp(args):
    # Placeholder reading. Swap in a real sensor once one is wired up.
    return {"celsius": 21.5}


def _set_led(args):
    on = bool(args.get("on"))
    _led.value(1 if on else 0)
    return {"on": on}


def _build_device():
    device = MCPLiteDevice()
    device.add_tool("read_temp", _read_temp, "Read the current temperature in Celsius")
    device.add_tool("set_led", _set_led, "Turn the onboard LED on or off")
    return device


async def _notify_frame(connection, payload):
    # Split the length-prefixed reply into notification-sized chunks.
    for start in range(0, len(payload), _NOTIFY_CHUNK):
        end = start + _NOTIFY_CHUNK
        _tx_char.notify(connection, payload[start:end])
        await asyncio.sleep_ms(_NOTIFY_GAP_MS)


async def _serve(connection, device):
    reader = FrameReader()
    while True:
        _, data = await _rx_char.written()
        reader.feed(data)
        request = reader.next_frame()
        while request is not None:
            await _notify_frame(connection, frame(device.handle(request)))
            request = reader.next_frame()


async def _run():
    device = _build_device()
    print("mcp-edge BLE device ready")
    while True:
        async with await aioble.advertise(
            _ADV_INTERVAL_US, name=_DEVICE_NAME, services=[_NUS_SERVICE]
        ) as connection:
            print("mcp-edge: central connected", connection.device)
            server = asyncio.create_task(_serve(connection, device))
            await connection.disconnected()
            server.cancel()
        print("mcp-edge: central disconnected")


asyncio.run(_run())
