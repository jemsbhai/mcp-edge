"""Four-tier device taxonomy for MCP-Edge.

Classifies edge and IoT hardware by compute, memory, and connectivity, and maps
each tier to the MCP integration strategy MCP-Edge uses for it. This mirrors the
taxonomy in the MCP-Edge paper (IEEE Cloud Summit 2026) and its RFC 7228 grounding.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum


class MCPStrategy(str, Enum):
    """How a device is exposed to a cloud MCP client."""

    GATEWAY_PROXY = "gateway_proxy"  # Tier 1: gateway holds proxy tools, speaks raw serial/USB/BLE
    MCP_LITE = "mcp_lite"            # Tier 2: device runs a lightweight MCP server
    BLE_BRIDGE = "ble_bridge"        # Tier 3: gateway bridges BLE GATT to MCP
    FULL_MCP = "full_mcp"            # Tier 4: device runs a full MCP server


class Tier(IntEnum):
    """The four MCP-Edge device tiers, numbered 1-4."""

    CONSTRAINED_MCU = 1
    SMART_NODE = 2
    BLE_WEARABLE = 3
    EDGE_COMPUTER = 4


@dataclass(frozen=True)
class TierProfile:
    """The defining characteristics of a tier."""

    tier: Tier
    title: str
    rfc7228_class: str
    memory_connectivity: str
    strategy: MCPStrategy


@dataclass(frozen=True)
class Platform:
    """A reference hardware platform classified into a tier."""

    name: str
    tier: Tier
    ram: str
    connectivity: str
    notes: str = ""


TIER_PROFILES: dict[Tier, TierProfile] = {
    Tier.CONSTRAINED_MCU: TierProfile(
        Tier.CONSTRAINED_MCU,
        "Constrained MCUs",
        "Class 0-1",
        "<=512 KB RAM, no OS, limited or no IP",
        MCPStrategy.GATEWAY_PROXY,
    ),
    Tier.SMART_NODE: TierProfile(
        Tier.SMART_NODE,
        "Smart IoT Nodes",
        "Class 2+",
        "MB-range PSRAM, Wi-Fi",
        MCPStrategy.MCP_LITE,
    ),
    Tier.BLE_WEARABLE: TierProfile(
        Tier.BLE_WEARABLE,
        "BLE Wearables",
        "BLE SoC",
        "No IP stack, short-range radio",
        MCPStrategy.BLE_BRIDGE,
    ),
    Tier.EDGE_COMPUTER: TierProfile(
        Tier.EDGE_COMPUTER,
        "Edge Computers",
        "Linux-class",
        "GBs of RAM, direct network",
        MCPStrategy.FULL_MCP,
    ),
}


REFERENCE_PLATFORMS: tuple[Platform, ...] = (
    Platform("Arduino UNO", Tier.CONSTRAINED_MCU, "2 KB SRAM", "UART", "single-byte command codes"),
    Platform("Xiao RP2040", Tier.CONSTRAINED_MCU, "264 KB SRAM", "USB"),
    Platform("ESP32-C3", Tier.CONSTRAINED_MCU, "400 KB", "Wi-Fi / BLE"),
    Platform("ESP32-C6", Tier.CONSTRAINED_MCU, "512 KB", "Wi-Fi 6 / BLE 5 / Thread"),
    Platform("M5Stack", Tier.SMART_NODE, "520 KB SRAM + 4 MB PSRAM", "Wi-Fi", "MicroPython MCP-Lite"),
    Platform("Waveshare T5", Tier.SMART_NODE, "512 KB + 8 MB PSRAM", "Wi-Fi", "MicroPython MCP-Lite"),
    Platform("Colmi Ring", Tier.BLE_WEARABLE, "n/a", "BLE GATT", "heart rate / SpO2 / steps"),
    Platform(
        "Raspberry Pi 5",
        Tier.EDGE_COMPUTER,
        "4-8 GB",
        "Ethernet / Wi-Fi",
        "full MCP server",
    ),
    Platform(
        "Arduino UNO Q",
        Tier.EDGE_COMPUTER,
        "2-4 GB",
        "Ethernet / Wi-Fi",
        "QRB2210; Linux + STM32 coprocessor",
    ),
)


def profile_for(tier: Tier) -> TierProfile:
    """Return the :class:`TierProfile` for ``tier``."""
    return TIER_PROFILES[tier]


def strategy_for(tier: Tier) -> MCPStrategy:
    """Return the MCP integration strategy for ``tier``."""
    return TIER_PROFILES[tier].strategy


def platforms_in(tier: Tier) -> tuple[Platform, ...]:
    """Return the reference platforms that belong to ``tier``."""
    return tuple(p for p in REFERENCE_PLATFORMS if p.tier == tier)


__all__ = [
    "MCPStrategy",
    "Platform",
    "Tier",
    "TierProfile",
    "TIER_PROFILES",
    "REFERENCE_PLATFORMS",
    "profile_for",
    "strategy_for",
    "platforms_in",
]
