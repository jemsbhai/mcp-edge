"""Tests for the four-tier device taxonomy."""

from __future__ import annotations

import pytest

from mcp_edge import tiers


def test_four_tiers_numbered_1_to_4() -> None:
    assert [t.value for t in tiers.Tier] == [1, 2, 3, 4]


def test_every_tier_has_a_profile() -> None:
    assert set(tiers.TIER_PROFILES) == set(tiers.Tier)


@pytest.mark.parametrize(
    ("tier", "strategy"),
    [
        (tiers.Tier.CONSTRAINED_MCU, tiers.MCPStrategy.GATEWAY_PROXY),
        (tiers.Tier.SMART_NODE, tiers.MCPStrategy.MCP_LITE),
        (tiers.Tier.BLE_WEARABLE, tiers.MCPStrategy.BLE_BRIDGE),
        (tiers.Tier.EDGE_COMPUTER, tiers.MCPStrategy.FULL_MCP),
    ],
)
def test_strategy_mapping(tier: tiers.Tier, strategy: tiers.MCPStrategy) -> None:
    assert tiers.strategy_for(tier) == strategy
    assert tiers.profile_for(tier).strategy == strategy


def test_profile_for_returns_tier_profile() -> None:
    profile = tiers.profile_for(tiers.Tier.SMART_NODE)
    assert isinstance(profile, tiers.TierProfile)
    assert profile.title == "Smart IoT Nodes"


def test_nine_reference_platforms() -> None:
    assert len(tiers.REFERENCE_PLATFORMS) == 9


def test_every_platform_has_a_valid_tier() -> None:
    for platform in tiers.REFERENCE_PLATFORMS:
        assert isinstance(platform, tiers.Platform)
        assert platform.tier in tiers.Tier


def test_every_tier_has_at_least_one_platform() -> None:
    for tier in tiers.Tier:
        assert tiers.platforms_in(tier), f"no reference platform for {tier!r}"


def test_constrained_tier_has_four_platforms() -> None:
    assert len(tiers.platforms_in(tiers.Tier.CONSTRAINED_MCU)) == 4
