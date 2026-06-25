"""Offline request buffering.

When a device is briefly unreachable, the gateway can buffer operations destined for it
and replay them in order once it returns, rather than dropping them. The buffer is a
bounded FIFO; on overflow it raises rather than silently discarding, and a flush that
fails part-way leaves the failed item (and the rest) queued for the next attempt.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class BufferFull(RuntimeError):
    """Raised when enqueuing onto a full buffer."""


class OfflineBuffer(Generic[T]):
    """A bounded FIFO buffer of operations for a temporarily unreachable device."""

    def __init__(self, *, max_size: int = 128) -> None:
        self.max_size = max_size
        self._items: deque[T] = deque()

    def __len__(self) -> int:
        return len(self._items)

    @property
    def is_full(self) -> bool:
        return len(self._items) >= self.max_size

    def enqueue(self, item: T) -> None:
        """Append ``item``; raises :class:`BufferFull` if the buffer is full."""
        if self.is_full:
            raise BufferFull(f"buffer is full (max_size={self.max_size})")
        self._items.append(item)

    async def flush(self, handler: Callable[[T], Awaitable[None]]) -> int:
        """Apply ``handler`` to each item in FIFO order, removing it on success.

        Returns the number flushed. If ``handler`` raises, the failed item stays at the
        front (and the remaining items stay queued) so the operation can be retried.
        """
        count = 0
        while self._items:
            await handler(self._items[0])
            self._items.popleft()
            count += 1
        return count

    def clear(self) -> None:
        """Discard all buffered items."""
        self._items.clear()


__all__ = ["OfflineBuffer", "BufferFull"]
