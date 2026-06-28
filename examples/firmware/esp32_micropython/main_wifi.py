"""MicroPython entry point: run the MCP-Lite device on an ESP32 over Wi-Fi (TCP).

Connects to Wi-Fi, sets the mDNS hostname (so the device is reachable at
``mcp-edge.local``), and serves MCP-Lite frames over a TCP server on ``PORT``, reusing the
portable core. The gateway connects with ``TcpTransport("mcp-edge.local", PORT)``.

mDNS note: stock MicroPython advertises only the hostname (an A record), not the
``_mcp-edge._tcp.local.`` service record, so
``mcp_edge.transports.discovery.discover()`` will not list this device. Full service
discovery needs the third-party micropython-mdns library (a custom firmware build); see
the README.

Flash this together with ``mcplite_device.py``, and set ``WIFI_SSID`` / ``WIFI_PASSWORD``
below (the defaults connect to Wokwi's simulated network).

This is example code: the boot + Wi-Fi-connect path is smoke-tested on a simulated ESP32
in CI (the wifi-boot job), but the TCP protocol round-trip is not, and it has not been
validated on physical hardware.
"""

import asyncio

import network
from machine import Pin
from mcplite_device import FrameReader, MCPLiteDevice, frame

WIFI_SSID = "Wokwi-GUEST"
WIFI_PASSWORD = ""
HOSTNAME = "mcp-edge"
PORT = 8765
LED_PIN = 2
_READ_CHUNK = 256

_led = Pin(LED_PIN, Pin.OUT)


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


async def _connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    try:
        wlan.config(hostname=HOSTNAME)
    except Exception:  # older firmware may not accept the hostname option
        pass
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            await asyncio.sleep_ms(100)
    return wlan.ifconfig()[0]


async def _serve_client(reader, writer, device):
    frames = FrameReader()
    try:
        while True:
            data = await reader.read(_READ_CHUNK)
            if not data:
                break  # client disconnected
            frames.feed(data)
            request = frames.next_frame()
            while request is not None:
                writer.write(frame(device.handle(request)))
                await writer.drain()
                request = frames.next_frame()
    finally:
        writer.close()
        await writer.wait_closed()


async def _run():
    ip = await _connect_wifi()
    device = _build_device()

    async def handle(reader, writer):
        await _serve_client(reader, writer, device)

    await asyncio.start_server(handle, "0.0.0.0", PORT)
    print("mcp-edge device ready")
    print("mcp-edge:", HOSTNAME + ".local", "->", ip, "port", PORT)
    while True:
        await asyncio.sleep_ms(1000)


asyncio.run(_run())
