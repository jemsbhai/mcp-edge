"""Connection pooling for device transports.

Opening a connection to a constrained device is costly, and some links cap concurrent
connections (a BLE adapter, for instance, supports only a handful of simultaneous
pairings). The pool reuses an open transport per device key and refuses to exceed a
configured maximum, so the gateway can share connections and respect those limits.
"""

from __future__ import annotations

from collections.abc import Callable

from .transports import Transport

TransportFactory = Callable[[str], Transport]


class PoolError(RuntimeError):
    """Raised when the pool cannot satisfy a request (for example, it is full)."""


class ConnectionPool:
    """Reuses open transports per device key, capped at ``max_size`` connections."""

    def __init__(self, factory: TransportFactory, *, max_size: int = 8) -> None:
        self._factory = factory
        self.max_size = max_size
        self._open: dict[str, Transport] = {}

    def __len__(self) -> int:
        return len(self._open)

    def __contains__(self, key: object) -> bool:
        return key in self._open

    async def acquire(self, key: str) -> Transport:
        """Return an open transport for ``key``, opening a new one on a miss.

        Raises :class:`PoolError` if a new connection would exceed ``max_size``.
        """
        existing = self._open.get(key)
        if existing is not None:
            return existing
        if len(self._open) >= self.max_size:
            raise PoolError(f"connection pool is full (max_size={self.max_size})")
        transport = self._factory(key)
        await transport.open()
        self._open[key] = transport
        return transport

    async def release(self, key: str) -> None:
        """Close and drop the connection for ``key`` (a no-op if absent)."""
        transport = self._open.pop(key, None)
        if transport is not None:
            await transport.close()

    async def aclose(self) -> None:
        """Close every open connection."""
        for transport in list(self._open.values()):
            await transport.close()
        self._open.clear()


__all__ = ["ConnectionPool", "PoolError", "TransportFactory"]
