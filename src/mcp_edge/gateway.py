"""The MCP-Edge gateway.

The gateway is itself an MCP server. It aggregates the tools of every attached device
into a single composite namespace -- each tool exposed under a device-prefixed name such
as ``sensor-01/read_temp`` -- and routes calls back to the owning device. This is the
surface a cloud MCP client ultimately talks to.
"""

from __future__ import annotations

from typing import Any

from .registry import DeviceRegistry, RegisteredDevice, RegistryError

SEPARATOR = "/"


class GatewayError(RuntimeError):
    """Raised for an unknown or disconnected device, or a malformed qualified name."""


def qualify(device_name: str, tool_name: str) -> str:
    """Compose a device-prefixed (qualified) tool name."""
    return f"{device_name}{SEPARATOR}{tool_name}"


def split_qualified(qualified_name: str) -> tuple[str, str]:
    """Split a qualified name into ``(device_name, tool_name)`` on the first separator."""
    device_name, separator, tool_name = qualified_name.partition(SEPARATOR)
    if not separator or not device_name or not tool_name:
        raise GatewayError(f"malformed qualified name: {qualified_name!r}")
    return device_name, tool_name


class Gateway:
    """Aggregates attached devices behind one composite MCP tool namespace."""

    def __init__(self, registry: DeviceRegistry | None = None) -> None:
        self.registry = registry if registry is not None else DeviceRegistry()

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return every connected device's tools under device-prefixed names."""
        tools: list[dict[str, Any]] = []
        for device in self.registry:
            if not device.connected:
                continue
            for tool in await device.client.list_tools():
                tools.append({**tool, "name": qualify(device.name, tool["name"])})
        return tools

    async def call_tool(self, qualified_name: str, arguments: dict[str, Any]) -> Any:
        """Route a qualified tool call to the owning device."""
        device_name, tool_name = split_qualified(qualified_name)
        device = self._device(device_name)
        return await device.client.call_tool(tool_name, arguments)

    async def read_resource(self, device_name: str, uri: str) -> Any:
        """Route a resource read to a named device."""
        return await self._device(device_name).client.read_resource(uri)

    def _device(self, device_name: str) -> RegisteredDevice:
        try:
            device = self.registry.get(device_name)
        except RegistryError as exc:
            raise GatewayError(str(exc)) from exc
        if not device.connected:
            raise GatewayError(f"device is disconnected: {device_name}")
        return device


__all__ = ["Gateway", "GatewayError", "qualify", "split_qualified"]
