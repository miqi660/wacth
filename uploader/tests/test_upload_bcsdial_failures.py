from __future__ import annotations

import asyncio

import pytest

from ultra3_uploader.bcsdial import BCSDIALPayload
from ultra3_uploader.checksum import c8_checksum
from ultra3_uploader.constants import FF02_UUID
from ultra3_uploader.fake_transport import FakeBleTransport
from ultra3_uploader.logging_utils import Stage5Logger
from ultra3_uploader.timing import FakeClock, FakeSleeper
from ultra3_uploader.upload_bcsdial import upload_bcsdial
from ultra3_uploader.upload_state import UploadState


def payload() -> BCSDIALPayload:
    return BCSDIALPayload(b"BCSDIAL" + b"\x00" * 489 + b"BCBC")


def run_upload(
    transport: FakeBleTransport,
    value: BCSDIALPayload,
    *,
    cancellation_event: asyncio.Event | None = None,
    ready_timeout: float = 0.02,
):
    clock = FakeClock()
    return asyncio.run(upload_bcsdial(
        transport,
        value,
        ready_timeout=ready_timeout,
        ca_timeout=0.02,
        cancellation_event=cancellation_event,
        logger=Stage5Logger(human_output=False),
        sleeper=FakeSleeper(clock),
        clock=clock,
    ))


@pytest.mark.parametrize(("sequence", "successful_c9"), [(0, 0), (1, 1), (2, 2)])
def test_c9_write_failure_stops_immediately(sequence: int, successful_c9: int) -> None:
    value = payload()
    transport = FakeBleTransport(
        auto_prepare=True,
        last_c9_sequence=2,
        ca_mode="normal",
        fail_at_sequence=sequence,
    )
    result = run_upload(transport, value)
    assert not result.success
    assert result.final_state is UploadState.FAILED
    assert result.c9_writes == successful_c9
    assert result.ca_writes == 0
    assert result.packets_sent == successful_c9
    assert transport.notify_unsubscriptions == [
        "0000ff03-0000-1000-8000-00805f9b34fb"
    ]
    assert transport.disconnect_calls == 1


def test_disconnect_after_sequence_stops_following_packets() -> None:
    value = payload()
    transport = FakeBleTransport(
        auto_prepare=True,
        last_c9_sequence=2,
        ca_mode="normal",
        disconnect_at_sequence=1,
    )
    result = run_upload(transport, value)
    assert not result.success
    assert result.c9_writes == 2
    assert result.last_sequence == 1
    assert result.ca_writes == 0
    assert len(transport.write_attempts) == 3  # C8 + seq 0 + seq 1


def test_cancellation_event_after_sequence_returns_cancelled_result() -> None:
    value = payload()
    event = asyncio.Event()
    transport = FakeBleTransport(
        auto_prepare=True,
        last_c9_sequence=2,
        ca_mode="normal",
        cancel_at_sequence=1,
        cancellation_event=event,
    )
    result = run_upload(transport, value, cancellation_event=event)
    assert not result.success
    assert result.final_state is UploadState.CANCELLED
    assert result.cancellation_requested
    assert result.c9_writes == 2
    assert result.ca_writes == 0
    assert transport.disconnect_calls == 1


def test_write_capacity_below_237_refuses_c9() -> None:
    value = payload()
    result = run_upload(FakeBleTransport(auto_prepare=True, max_write_size=236), value)
    assert not result.success
    assert result.c9_writes == 0
    assert result.ca_writes == 0
    assert result.disconnect_observed


def test_unknown_write_capacity_refuses_c9_after_prepare() -> None:
    value = payload()
    result = run_upload(FakeBleTransport(auto_prepare=True, max_write_size=None), value)
    assert not result.success
    assert result.c8_writes == 1
    assert result.c9_writes == 0
    assert "无法确认" in (result.error_message or "")


def test_exact_237_capacity_is_accepted() -> None:
    value = payload()
    transport = FakeBleTransport(
        auto_prepare=True,
        last_c9_sequence=2,
        ca_mode="normal",
        max_write_size=237,
    )
    result = run_upload(transport, value)
    assert result.success
    assert result.c9_writes == 3


def bc72(value: int) -> bytes:
    return bytes.fromhex(f"BC720302{value:02X}00{value:02X}")


def countdown() -> list[bytes]:
    return [bc72(value) for value in range(30, -1, -1)]


def c8_response(
    value: BCSDIALPayload,
    *,
    file_size: int | None = None,
    packet_count: int | None = None,
) -> bytes:
    frame = bytearray(value.build_prepare_frame())
    frame[2] = 0x03
    if file_size is not None:
        frame[5:9] = file_size.to_bytes(4, "little")
    if packet_count is not None:
        frame[9:11] = packet_count.to_bytes(2, "little")
    frame[-1] = c8_checksum(frame[4], bytes(frame[5:9]), bytes(frame[9:11]))
    return bytes(frame)


@pytest.mark.parametrize(
    "notifications",
    [
        [bytes.fromhex("BCD103010202")],
        [bc72(30), bc72(28)],
        countdown(),
    ],
    ids=["missing_bc72", "countdown_out_of_order", "d1_timeout"],
)
def test_prepare_failures_never_send_c9_or_ca(notifications: list[bytes]) -> None:
    value = payload()
    transport = FakeBleTransport(prepare_notifications=notifications)
    result = run_upload(transport, value, ready_timeout=0.01)
    assert not result.success
    assert result.c9_writes == 0
    assert result.ca_writes == 0
    assert result.disconnect_observed


def test_prepare_c8_timeout_never_sends_data() -> None:
    value = payload()
    notifications = countdown() + [bytes.fromhex("BCD103010202")]
    result = run_upload(
        FakeBleTransport(prepare_notifications=notifications),
        value,
        ready_timeout=0.01,
    )
    assert not result.success
    assert result.c9_writes == 0
    assert result.ca_writes == 0


@pytest.mark.parametrize("mismatch", ["size", "count"])
def test_prepare_c8_mismatch_never_sends_data(mismatch: str) -> None:
    value = payload()
    response = (
        c8_response(value, file_size=value.size + 1)
        if mismatch == "size"
        else c8_response(value, packet_count=value.packet_count + 1)
    )
    notifications = countdown() + [bytes.fromhex("BCD103010202"), response]
    result = run_upload(FakeBleTransport(prepare_notifications=notifications), value)
    assert not result.success
    assert result.c9_writes == 0
    assert result.ca_writes == 0


def test_prepare_disconnect_never_sends_data() -> None:
    value = payload()
    result = run_upload(FakeBleTransport(disconnect_on_write=True), value)
    assert not result.success
    assert result.c8_writes == 1
    assert result.c9_writes == 0
    assert result.ca_writes == 0


def test_async_cancel_during_prepare_cleans_up_and_returns_cancelled() -> None:
    value = payload()
    transport = FakeBleTransport()
    clock = FakeClock()

    async def scenario():
        task = asyncio.create_task(upload_bcsdial(
            transport,
            value,
            ready_timeout=60,
            logger=Stage5Logger(human_output=False),
            sleeper=FakeSleeper(clock),
            clock=clock,
        ))
        while not transport.writes:
            await asyncio.sleep(0)
        task.cancel()
        return await task

    result = asyncio.run(scenario())
    assert result.final_state is UploadState.CANCELLED
    assert result.c8_writes == 1
    assert result.c9_writes == 0
    assert result.ca_writes == 0
    assert transport.notify_unsubscriptions
    assert transport.disconnect_calls == 1

