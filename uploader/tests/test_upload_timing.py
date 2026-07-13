import asyncio

import pytest

from ultra3_uploader.timing import FakeClock, FakeSleeper


def test_fake_sleeper_records_and_advances_without_real_wait() -> None:
    clock = FakeClock()
    sleeper = FakeSleeper(clock)

    async def scenario() -> None:
        await sleeper.sleep(0.045)
        await sleeper.sleep(0.045)

    asyncio.run(scenario())
    assert sleeper.calls == [0.045, 0.045]
    assert sleeper.total_seconds == pytest.approx(0.09)
    assert clock.monotonic() == pytest.approx(0.09)

