"""Tests for the CBOR codec."""

from __future__ import annotations

import pytest

from mcp_edge import codec

SAMPLES: list[object] = [
    {"name": "arduino_uno/read_analog", "pin": 3, "value": 512},
    {"tools": [{"name": "read_temp", "unit": "C"}, {"name": "set_led", "state": True}]},
    [1, 2, 3, "four", {"five": 5}],
    {"nested": {"a": [1, 2, {"b": None}]}, "flag": False},
]


@pytest.mark.parametrize("obj", SAMPLES)
def test_round_trip(obj: object) -> None:
    assert codec.decode(codec.encode(obj)) == obj


@pytest.mark.parametrize("obj", SAMPLES)
def test_cbor_not_larger_than_json(obj: object) -> None:
    assert len(codec.encode(obj)) <= len(codec.json_bytes(obj))


def test_size_reduction_within_unit_range() -> None:
    for obj in SAMPLES:
        reduction = codec.size_reduction(obj)
        assert 0.0 <= reduction < 1.0


def test_size_reduction_of_empty_mapping_is_defined() -> None:
    assert codec.size_reduction({}) >= 0.0
