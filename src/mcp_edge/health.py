"""Health monitoring for attached devices.

The monitor periodically probes each registered device with a lightweight request and
flips ``RegisteredDevice.connected`` accordingly. The gateway already honors that flag --
unreachable devices drop out of the tool namespace and become unroutable -- so health
state and routing stay consistent with no extra wiring.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from .registry import DeviceRegistry, RegisteredDevice

Probe = Callable[[RegisteredDevice], Awaitable[bool]]


async def default_probe(device: RegisteredDevice) -> bool:
    """Return whether a device answers a lightweight ``tools/list`` request."""
    try:
        await device.client.list_tools()
    except Exception:
        return False
    return True


class HealthMonitor:
    """Periodically probes registered devices and updates their connection state."""

    def __init__(
        self,
        registry: DeviceRegistry,
        *,
        interval: float = 30.0,
        probe: Probe | None = None,
    ) -> None:
        self.registry = registry
        self.interval = interval
        self._probe = probe if probe is not None else default_probe

    async def check(self, device: RegisteredDevice) -> bool:
        """Probe one device, update its ``connected`` flag, and return reachability."""
        reachable = await self._probe(device)
        device.connected = reachable
        return reachable

    async def check_all(self) -> None:
        """Probe every registered device once."""
        for device in list(self.registry):
            await self.check(device)

    async def run(self, *, iterations: int | None = None) -> None:
        """Probe all devices every ``interval`` seconds.

        Runs forever by default; pass ``iterations`` to bound the loop (used in tests).
        """
        count = 0
        while True:
            await self.check_all()
            count += 1
            if iterations is not None and count >= iterations:
                return
            await asyncio.sleep(self.interval)


__all__ = ["HealthMonitor", "default_probe", "Probe"]
