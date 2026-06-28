"""Tests for the device health monitor."""

from __future__ import annotations

from typing import Any

from mcp_edge.client import DeviceClient, DeviceError
from mcp_edge.health import HealthMonitor, default_probe
from mcp_edge.registry import DeviceRegistry, RegisteredDevice
from mcp_edge.tiers import Tier


class _HealthyClient(DeviceClient):
    async def list_tools(self) -> list[dict[str, Any]]:
        return []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return None

    async def read_resource(self, uri: str) -> Any:
        return None


class _FailingClient(_HealthyClient):
    async def list_tools(self) -> list[dict[str, Any]]:
        raise DeviceError("unreachable", code=-1)


class _FlushRecordingClient(_HealthyClient):
    """A reachable client that counts flush() calls, to check the reconnect hook."""

    def __init__(self) -> None:
        self.flushes = 0

    async def flush(self) -> int:
        self.flushes += 1
        return 0


async def test_default_probe_true_when_reachable() -> None:
    device = RegisteredDevice("d", Tier.SMART_NODE, _HealthyClient())
    assert await default_probe(device) is True


async def test_default_probe_false_when_unreachable() -> None:
    device = RegisteredDevice("d", Tier.SMART_NODE, _FailingClient())
    assert await default_probe(device) is False


async def test_check_all_updates_connected_flags() -> None:
    registry = DeviceRegistry()
    registry.register("good", _HealthyClient(), Tier.SMART_NODE)
    registry.register("bad", _FailingClient(), Tier.SMART_NODE)
    monitor = HealthMonitor(registry, interval=0)

    await monitor.check_all()

    assert registry.get("good").connected is True
    assert registry.get("bad").connected is False


async def test_run_bounded_iterations() -> None:
    registry = DeviceRegistry()
    registry.register("bad", _FailingClient(), Tier.SMART_NODE)
    monitor = HealthMonitor(registry, interval=0)
    await monitor.run(iterations=2)
    assert registry.get("bad").connected is False


async def test_recovery_flips_back_to_connected() -> None:
    registry = DeviceRegistry()
    registry.register("good", _HealthyClient(), Tier.SMART_NODE)
    device = registry.get("good")
    device.connected = False
    monitor = HealthMonitor(registry, interval=0)
    await monitor.check(device)
    assert device.connected is True


async def test_on_reconnect_fires_on_recovery_edge() -> None:
    registry = DeviceRegistry()
    registry.register("d", _HealthyClient(), Tier.SMART_NODE)
    device = registry.get("d")
    device.connected = False

    reconnected: list[str] = []

    async def on_reconnect(dev: RegisteredDevice) -> None:
        reconnected.append(dev.name)

    monitor = HealthMonitor(registry, interval=0, on_reconnect=on_reconnect)
    await monitor.check(device)
    assert device.connected is True
    assert reconnected == ["d"]


async def test_on_reconnect_silent_when_already_connected() -> None:
    registry = DeviceRegistry()
    registry.register("d", _HealthyClient(), Tier.SMART_NODE)
    device = registry.get("d")

    reconnected: list[str] = []

    async def on_reconnect(dev: RegisteredDevice) -> None:
        reconnected.append(dev.name)

    monitor = HealthMonitor(registry, interval=0, on_reconnect=on_reconnect)
    await monitor.check(device)
    assert reconnected == []


async def test_on_reconnect_silent_on_disconnect() -> None:
    registry = DeviceRegistry()
    registry.register("d", _FailingClient(), Tier.SMART_NODE)
    device = registry.get("d")

    reconnected: list[str] = []

    async def on_reconnect(dev: RegisteredDevice) -> None:
        reconnected.append(dev.name)

    monitor = HealthMonitor(registry, interval=0, on_reconnect=on_reconnect)
    await monitor.check(device)
    assert device.connected is False
    assert reconnected == []


async def test_on_reconnect_failure_does_not_break_check() -> None:
    registry = DeviceRegistry()
    registry.register("d", _HealthyClient(), Tier.SMART_NODE)
    device = registry.get("d")
    device.connected = False

    async def on_reconnect(dev: RegisteredDevice) -> None:
        raise RuntimeError("flush failed")

    monitor = HealthMonitor(registry, interval=0, on_reconnect=on_reconnect)
    assert await monitor.check(device) is True
    assert device.connected is True


async def test_reconnect_hook_flushes_the_client() -> None:
    client = _FlushRecordingClient()
    registry = DeviceRegistry()
    registry.register("d", client, Tier.SMART_NODE)
    device = registry.get("d")
    device.connected = False

    async def on_reconnect(dev: RegisteredDevice) -> None:
        flush = getattr(dev.client, "flush", None)
        if flush is not None:
            await flush()

    monitor = HealthMonitor(registry, interval=0, on_reconnect=on_reconnect)
    await monitor.check(device)
    assert client.flushes == 1
