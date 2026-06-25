"""Tests for the offline request buffer."""

from __future__ import annotations

import pytest

from mcp_edge.buffer import BufferFull, OfflineBuffer


def test_enqueue_increases_length() -> None:
    buffer: OfflineBuffer[str] = OfflineBuffer(max_size=3)
    buffer.enqueue("a")
    buffer.enqueue("b")
    assert len(buffer) == 2
    assert not buffer.is_full


def test_enqueue_on_full_raises() -> None:
    buffer: OfflineBuffer[int] = OfflineBuffer(max_size=2)
    buffer.enqueue(1)
    buffer.enqueue(2)
    assert buffer.is_full
    with pytest.raises(BufferFull):
        buffer.enqueue(3)


async def test_flush_applies_handler_in_fifo_order() -> None:
    buffer: OfflineBuffer[str] = OfflineBuffer()
    for item in ["a", "b", "c"]:
        buffer.enqueue(item)

    seen: list[str] = []

    async def handler(item: str) -> None:
        seen.append(item)

    flushed = await buffer.flush(handler)
    assert flushed == 3
    assert seen == ["a", "b", "c"]
    assert len(buffer) == 0


async def test_flush_retains_items_when_handler_fails() -> None:
    buffer: OfflineBuffer[str] = OfflineBuffer()
    for item in ["a", "b", "c"]:
        buffer.enqueue(item)

    seen: list[str] = []

    async def failing(item: str) -> None:
        if item == "b":
            raise RuntimeError("still offline")
        seen.append(item)

    with pytest.raises(RuntimeError):
        await buffer.flush(failing)

    assert seen == ["a"]
    assert len(buffer) == 2

    async def ok(item: str) -> None:
        seen.append(item)

    flushed = await buffer.flush(ok)
    assert flushed == 2
    assert seen == ["a", "b", "c"]


async def test_flush_empty_returns_zero() -> None:
    buffer: OfflineBuffer[str] = OfflineBuffer()

    async def handler(item: str) -> None:
        raise AssertionError("handler should not be called on an empty buffer")

    assert await buffer.flush(handler) == 0


def test_clear_discards_items() -> None:
    buffer: OfflineBuffer[int] = OfflineBuffer()
    buffer.enqueue(1)
    buffer.enqueue(2)
    buffer.clear()
    assert len(buffer) == 0
