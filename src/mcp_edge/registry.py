"""Device registry for the MCP-Edge gateway.

Tracks the devices currently attached to a gateway: their name, tier, reachability
client, and connection state. The gateway queries the registry to build its composite
tool namespace and to route calls.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from .client import DeviceClient
from .tiers import Tier


class RegistryError(LookupError):
    """Raised for duplicate registration or lookup of an unknown device."""


@dataclass
class RegisteredDevice:
    """A device known to the gateway."""

    name: str
    tier: Tier
    client: DeviceClient
    connected: bool = True


class DeviceRegistry:
    """An ordered collection of devices attached to the gateway."""

    def __init__(self) -> None:
        self._devices: dict[str, RegisteredDevice] = {}

    def __len__(self) -> int:
        return len(self._devices)

    def __contains__(self, name: object) -> bool:
        return name in self._devices

    def __iter__(self) -> Iterator[RegisteredDevice]:
        return iter(self._devices.values())

    def register(self, name: str, client: DeviceClient, tier: Tier) -> RegisteredDevice:
        if name in self._devices:
            raise RegistryError(f"device already registered: {name}")
        device = RegisteredDevice(name=name, tier=tier, client=client)
        self._devices[name] = device
        return device

    def unregister(self, name: str) -> None:
        if name not in self._devices:
            raise RegistryError(f"unknown device: {name}")
        del self._devices[name]

    def get(self, name: str) -> RegisteredDevice:
        try:
            return self._devices[name]
        except KeyError:
            raise RegistryError(f"unknown device: {name}") from None

    def names(self) -> list[str]:
        return list(self._devices)


__all__ = ["DeviceRegistry", "RegisteredDevice", "RegistryError"]
