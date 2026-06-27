"""MicroPython entry point: MCP-Lite device on an ESP32 over BLE (built-in bluetooth).

This is the low-level alternative to ``main_ble.py``: it uses MicroPython's built-in
``bluetooth`` module directly instead of aioble, so it runs on a stock MicroPython build
with nothing to ``mip install``. Flash it together with ``mcplite_device.py``. It exposes
the same ``read_temp`` and ``set_led`` tools over the Nordic UART Service, so the
gateway's ``BLETransport`` can drive it -- identical framing to the serial transport.

The GATT write IRQ stays light: it only appends inbound bytes to a ``FrameReader``. The
main loop drains complete frames, dispatches them, and sends each reply as chunked
notifications (notifying from the IRQ is avoided, since it re-enters the BLE stack).

This is example code: it is NOT exercised in CI (Wokwi has no BLE radio) and has not been
validated on physical hardware. Treat it as a reference to adapt and test on your board.
"""

import time

import bluetooth
from machine import Pin
from mcplite_device import FrameReader, MCPLiteDevice, frame
from micropython import const

# IRQ event codes and characteristic flags from the MicroPython bluetooth API.
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_FLAG_WRITE = const(0x0008)
_FLAG_NOTIFY = const(0x0010)

# Nordic UART Service: central writes frames to RX, device notifies replies on TX.
_NUS_UUID = bluetooth.UUID("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
_NUS_TX = (bluetooth.UUID("6e400003-b5a3-f393-e0a9-e50e24dcca9e"), _FLAG_NOTIFY)
_NUS_RX = (bluetooth.UUID("6e400002-b5a3-f393-e0a9-e50e24dcca9e"), _FLAG_WRITE)
_NUS_SERVICE = (_NUS_UUID, (_NUS_TX, _NUS_RX))

_DEVICE_NAME = "mcp-edge"
_ADV_INTERVAL_US = const(250000)
# Conservative notification payload size (default ATT MTU 23, minus 3 ATT header bytes);
# the gateway reassembles by the length prefix, so any value the link accepts works.
_NOTIFY_CHUNK = const(20)
# Main-loop poll interval, also used as a pause between notification chunks: MicroPython's
# BLE stack can only queue a few notifications, so back-to-back sends risk dropping them.
_GAP_MS = const(20)

LED_PIN = const(2)
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


def _advertising_payload(name):
    # Minimal advertising payload: Flags (LE general discoverable, BR/EDR not supported)
    # followed by the Complete Local Name. The 128-bit service UUID is left out to fit.
    name_bytes = name.encode()
    flags = bytes((2, 0x01, 0x06))
    local_name = bytes((len(name_bytes) + 1, 0x09)) + name_bytes
    return flags + local_name


class _BLEDevice:
    def __init__(self, ble, device):
        self._ble = ble
        self._device = device
        self._reader = FrameReader()
        self._connections = set()
        self._ble.active(True)
        self._ble.irq(self._irq)
        ((self._tx_handle, self._rx_handle),) = self._ble.gatts_register_services(
            (_NUS_SERVICE,)
        )
        self._ble.gatts_set_buffer(self._rx_handle, 256, True)
        self._payload = _advertising_payload(_DEVICE_NAME)
        self._advertise()

    def _advertise(self):
        self._ble.gap_advertise(_ADV_INTERVAL_US, adv_data=self._payload)

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
            self._reader = FrameReader()  # fresh reassembly buffer per connection
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self._connections.discard(conn_handle)
            self._advertise()
        elif event == _IRQ_GATTS_WRITE:
            _, value_handle = data
            if value_handle == self._rx_handle:
                self._reader.feed(self._ble.gatts_read(self._rx_handle))

    def poll(self):
        request = self._reader.next_frame()
        while request is not None:
            self._notify(frame(self._device.handle(request)))
            request = self._reader.next_frame()

    def _notify(self, reply):
        for start in range(0, len(reply), _NOTIFY_CHUNK):
            end = start + _NOTIFY_CHUNK
            chunk = reply[start:end]
            for conn_handle in self._connections:
                self._ble.gatts_notify(conn_handle, self._tx_handle, chunk)
            time.sleep_ms(_GAP_MS)


def main():
    server = _BLEDevice(bluetooth.BLE(), _build_device())
    print("mcp-edge BLE device ready")
    while True:
        server.poll()
        time.sleep_ms(_GAP_MS)


main()
