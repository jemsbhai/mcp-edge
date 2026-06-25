"""Tests for the transport connection pool."""

from __future__ import annotations

import pytest

from mcp_edge.pool import ConnectionPool, PoolError
from mcp_edge.transports import LoopbackTransport, Transport


async def _echo(frame: bytes) -> bytes:
    return frame


def _factory(key: str) -> Transport:
    return LoopbackTransport(_echo)


async def test_acquire_opens_and_reuses() -> None:
    pool = ConnectionPool(_factory, max_size=2)
    first = await pool.acquire("dev-a")
    assert first.is_open
    again = await pool.acquire("dev-a")
    assert again is first
    assert len(pool) == 1


async def test_acquire_distinct_keys() -> None:
    pool = ConnectionPool(_factory, max_size=2)
    a = await pool.acquire("dev-a")
    b = await pool.acquire("dev-b")
    assert a is not b
    assert len(pool) == 2


async def test_exceeding_max_size_raises() -> None:
    pool = ConnectionPool(_factory, max_size=1)
    await pool.acquire("dev-a")
    with pytest.raises(PoolError):
        await pool.acquire("dev-b")


async def test_release_frees_a_slot() -> None:
    pool = ConnectionPool(_factory, max_size=1)
    first = await pool.acquire("dev-a")
    await pool.release("dev-a")
    assert not first.is_open
    assert "dev-a" not in pool
    await pool.acquire("dev-b")
    assert len(pool) == 1


async def test_aclose_closes_all() -> None:
    pool = ConnectionPool(_factory, max_size=4)
    a = await pool.acquire("dev-a")
    b = await pool.acquire("dev-b")
    await pool.aclose()
    assert not a.is_open
    assert not b.is_open
    assert len(pool) == 0
