import asyncio


class ConcurrencyLimiter:
    """Bounds how many requests are processed at once; anything above the limit is rejected
    immediately (503) instead of queueing, so overload turns into a measurable, budgeted loss
    rather than every in-flight request timing out slowly. See ADR 0007."""

    def __init__(self, max_concurrency: int):
        self._max_concurrency = max_concurrency
        self._current = 0
        self._lock = asyncio.Lock()

    async def try_acquire(self) -> bool:
        async with self._lock:
            if self._current >= self._max_concurrency:
                return False
            self._current += 1
            return True

    async def release(self) -> None:
        async with self._lock:
            self._current -= 1
