"""mDNS (zeroconf) discovery for MCP-Edge devices on the local network.

This host-side helper browses for devices advertising the MCP-Edge service over mDNS and
resolves each to a host and port you can hand to :class:`mcp_edge.transports.TcpTransport`.
It needs the wifi extra (``pip install mcp-edge[wifi]``); zeroconf is imported lazily, so
this module imports fine without it.

The service type is parameterized, defaulting to the TCP service (``_mcp-edge._tcp.local.``),
so a future UDP transport can reuse this with its own ``_mcp-edge._udp.local.`` type.

This is integration code that talks to a live network: it is not exercised in the hermetic
CI (which never touches the network) and has not been validated against real devices.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from .base import TransportError

MCP_EDGE_TCP_SERVICE = "_mcp-edge._tcp.local."

_DEFAULT_TIMEOUT = 3.0


@dataclass(frozen=True)
class DiscoveredDevice:
    """An MCP-Edge device found via mDNS: its instance name, host, and TCP port."""

    name: str
    host: str
    port: int


def _import_zeroconf() -> Any:
    try:
        import zeroconf.asyncio
    except ImportError as exc:  # pragma: no cover
        raise TransportError(
            "zeroconf is required for mDNS discovery; install mcp-edge[wifi]"
        ) from exc
    return zeroconf


async def discover(
    service_type: str = MCP_EDGE_TCP_SERVICE,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
) -> list[DiscoveredDevice]:
    """Browse for MCP-Edge devices for ``timeout`` seconds and return the ones found.

    Each result's ``host`` and ``port`` can be passed straight to ``TcpTransport``. Requires
    the wifi extra and a working network; raises ``TransportError`` if zeroconf is missing.
    """
    zc = _import_zeroconf()
    ServiceStateChange = zc.ServiceStateChange
    AsyncServiceBrowser = zc.asyncio.AsyncServiceBrowser
    AsyncZeroconf = zc.asyncio.AsyncZeroconf

    names: list[str] = []

    def _on_change(_zeroconf: Any, _service_type: str, name: str, state_change: Any) -> None:
        if state_change is ServiceStateChange.Added and name not in names:
            names.append(name)

    aiozc = AsyncZeroconf()
    try:
        browser = AsyncServiceBrowser(aiozc.zeroconf, service_type, handlers=[_on_change])
        try:
            await asyncio.sleep(timeout)
            devices = []
            for name in names:
                info = await aiozc.async_get_service_info(service_type, name)
                if info is None:
                    continue
                addresses = info.parsed_addresses()
                if not addresses or info.port is None:
                    continue
                devices.append(DiscoveredDevice(name, addresses[0], info.port))
            return devices
        finally:
            await browser.async_cancel()
    finally:
        await aiozc.async_close()


__all__ = ["MCP_EDGE_TCP_SERVICE", "DiscoveredDevice", "discover"]
