from __future__ import annotations

import asyncio
import time
from typing import Protocol


class Sleeper(Protocol):
    async def sleep(self, seconds: float) -> None: ...


class Clock(Protocol):
    def monotonic(self) -> float: ...


class RealSleeper:
    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class RealClock:
    def monotonic(self) -> float:
        return time.monotonic()


class FakeClock:
    def __init__(self) -> None:
        self.current = 0.0

    def monotonic(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


class FakeSleeper:
    def __init__(self, clock: FakeClock | None = None) -> None:
        self.clock = clock
        self.calls: list[float] = []

    @property
    def total_seconds(self) -> float:
        return sum(self.calls)

    async def sleep(self, seconds: float) -> None:
        self.calls.append(seconds)
        if self.clock is not None:
            self.clock.advance(seconds)
        await asyncio.sleep(0)

