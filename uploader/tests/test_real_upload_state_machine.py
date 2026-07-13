from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from tests.real_transport_stub import RealTransportStub
from ultra3_uploader.bc_frames import parse_c9
from ultra3_uploader.bcsdial import BCSDIALPayload
from ultra3_uploader.constants import CA_APPLY_FRAME, FF02_UUID
from ultra3_uploader.logging_utils import Stage5Logger
from ultra3_uploader.real_upload import RealUploadAuthorization, reserve_log_file
from ultra3_uploader.timing import FakeClock, FakeSleeper
from ultra3_uploader.upload_bcsdial import upload_bcsdial
from ultra3_uploader.upload_state import UploadState


def small_payload() -> BCSDIALPayload:
    return BCSDIALPayload(b"BCSDIAL" + b"\x00" * 489 + b"BCBC")


def golden_payload() -> BCSDIALPayload:
    candidates = [
        Path(os.environ["ULTRA3_ARCHIVE_ROOT"])
        if "ULTRA3_ARCHIVE_ROOT" in os.environ
        else None,
        Path(__file__).resolve().parents[2],
        Path.home() / "Desktop" / "Ultra3-Reverse_Updated_2026-07-13",
    ]
    root = next(
        candidate
        for candidate in candidates
        if candidate is not None and (candidate / "dynamic_watchface").is_dir()
    )
    return BCSDIALPayload.from_path(
        root
        / "dynamic_watchface"
        / "baseline"
        / "2026-07-13_bcsdial_ff02_upload_success"
        / "evidence"
        / "samples"
        / "168844266159401_jump13_to_4_reconstructed_from_ble.bin"
    )


def run_real(
    transport: RealTransportStub,
    value: BCSDIALPayload,
    log: Path,
    *,
    cancellation_event: asyncio.Event | None = None,
    ca_timeout: float = 0.02,
):
    reserve_log_file(log)
    clock = FakeClock()
    sleeper = FakeSleeper(clock)
    logger = Stage5Logger(log, human_output=False)
    result = asyncio.run(upload_bcsdial(
        transport,
        value,
        packet_delay_ms=45,
        ready_timeout=0.02,
        ca_timeout=ca_timeout,
        cancellation_event=cancellation_event,
        logger=logger,
        sleeper=sleeper,
        clock=clock,
        authorization=RealUploadAuthorization(
            confirmed=True,
            expected_sha256=value.sha256,
            log_file=log,
        ),
    ))
    return result, sleeper, logger


def test_real_stub_golden_full_upload_uses_existing_state_machine(
    tmp_path: Path,
) -> None:
    value = golden_payload()
    transport = RealTransportStub(
        auto_prepare=True,
        last_c9_sequence=value.packet_count - 1,
        ca_mode="normal",
        max_write_size=244,
    )
    result, sleeper, logger = run_real(transport, value, tmp_path / "golden.jsonl")

    assert result.success
    assert result.final_state is UploadState.COMPLETE
    assert (result.c8_writes, result.c9_writes, result.ca_writes) == (1, 3875, 1)
    assert result.total_writes == 3877
    assert result.packets_sent == 3875
    assert result.bytes_sent == 891180
    assert result.last_sequence == 3874
    writes = [data for uuid, data in transport.writes if uuid == FF02_UUID]
    assert writes[0].hex().upper() == "BCC80207012C990D00230F05"
    assert [parse_c9(frame).sequence for frame in writes[1:-1]] == list(range(3875))
    assert writes[-1] == CA_APPLY_FRAME
    assert len(sleeper.calls) == 3874
    assert set(sleeper.calls) == {0.045}
    ca_success = next(i for i, row in enumerate(logger.records) if row["event"] == "ca_success")
    ca_apply = next(
        i
        for i, row in enumerate(logger.records)
        if row["event"] == "write" and row["command"] == "CA"
    )
    assert ca_success < ca_apply
    assert transport.notify_unsubscriptions == [
        "0000ff03-0000-1000-8000-00805f9b34fb"
    ]
    assert transport.disconnect_calls == 1


@pytest.mark.parametrize(
    ("transport_options", "expected_c9", "cancelled"),
    [
        ({"ca_mode": "missing"}, 3, False),
        ({"ca_mode": "normal", "fail_at_sequence": 1}, 1, False),
        ({"ca_mode": "normal", "disconnect_at_sequence": 1}, 2, False),
        ({"ca_mode": "normal", "cancel_at_sequence": 1}, 2, True),
        ({"ca_mode": "normal", "fail_ca_apply": True}, 3, False),
    ],
    ids=["ca_timeout", "c9_failure", "disconnect", "cancel", "ca_apply_failure"],
)
def test_real_stub_failure_stops_without_retry_or_apply(
    transport_options: dict[str, object],
    expected_c9: int,
    cancelled: bool,
    tmp_path: Path,
) -> None:
    value = small_payload()
    event = asyncio.Event() if cancelled else None
    transport = RealTransportStub(
        auto_prepare=True,
        last_c9_sequence=value.packet_count - 1,
        cancellation_event=event,
        **transport_options,
    )
    result, _sleeper, _logger = run_real(
        transport,
        value,
        tmp_path / "failure.jsonl",
        cancellation_event=event,
    )
    assert not result.success
    assert result.final_state is (
        UploadState.CANCELLED if cancelled else UploadState.FAILED
    )
    assert result.c9_writes == expected_c9
    assert result.ca_writes == 0
    ca_attempts = sum(data == CA_APPLY_FRAME for _uuid, data in transport.write_attempts)
    assert ca_attempts == (1 if transport_options.get("fail_ca_apply") else 0)
    assert transport.disconnect_calls <= 1
    assert len(transport.notify_unsubscriptions) <= 1


def test_periodic_48_notification_is_recorded_without_changing_sequence(
    tmp_path: Path,
) -> None:
    value = small_payload()
    notification = bytes.fromhex("BC48030100")
    transport = RealTransportStub(
        auto_prepare=True,
        last_c9_sequence=value.packet_count - 1,
        ca_mode="normal",
        notifications_at_sequence={0: [notification]},
    )
    result, _sleeper, logger = run_real(transport, value, tmp_path / "48.jsonl")
    assert result.success
    assert result.c9_writes == 3
    assert [
        parse_c9(data).sequence
        for _uuid, data in transport.writes
        if data.startswith(b"\xBC\xC9")
    ] == [0, 1, 2]
    assert any(row["hex"] == notification.hex().upper() for row in logger.records)
