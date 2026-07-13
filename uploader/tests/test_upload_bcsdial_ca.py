from __future__ import annotations

import asyncio

from ultra3_uploader.bcsdial import BCSDIALPayload
from ultra3_uploader.constants import CA_APPLY_FRAME
from ultra3_uploader.fake_transport import FakeBleTransport
from ultra3_uploader.logging_utils import Stage5Logger
from ultra3_uploader.timing import FakeClock, FakeSleeper
from ultra3_uploader.upload_bcsdial import upload_bcsdial
from ultra3_uploader.upload_state import UploadState


def payload() -> BCSDIALPayload:
    return BCSDIALPayload(b"BCSDIAL" + b"\x00" * 489 + b"BCBC")


def run_case(
    transport: FakeBleTransport,
    logger: Stage5Logger | None = None,
    *,
    ca_timeout: float = 0.02,
):
    clock = FakeClock()
    return asyncio.run(upload_bcsdial(
        transport,
        payload(),
        ca_timeout=ca_timeout,
        logger=logger or Stage5Logger(human_output=False),
        sleeper=FakeSleeper(clock),
        clock=clock,
    ))


def test_ca_timeout_never_sends_apply() -> None:
    transport = FakeBleTransport(
        auto_prepare=True, last_c9_sequence=2, ca_mode="missing"
    )
    result = run_case(transport)
    assert not result.success
    assert result.c9_writes == 3
    assert result.ca_writes == 0
    assert not result.ca_apply_sent
    assert transport.disconnect_calls == 1


def test_early_ca_aborts_and_is_not_cached() -> None:
    transport = FakeBleTransport(
        auto_prepare=True,
        last_c9_sequence=2,
        ca_mode="early",
        early_ca_sequence=0,
    )
    result = run_case(transport)
    assert not result.success
    assert result.c9_writes == 1
    assert result.ca_writes == 0
    assert "最后一个 C9 之前" in (result.error_message or "")


def test_duplicate_ca_is_logged_but_apply_is_sent_once() -> None:
    logger = Stage5Logger(human_output=False)
    transport = FakeBleTransport(
        auto_prepare=True, last_c9_sequence=2, ca_mode="duplicate"
    )
    result = run_case(transport, logger)
    assert result.success
    assert result.ca_writes == 1
    assert sum(data == CA_APPLY_FRAME for _uuid, data in transport.writes) == 1
    assert any(record["event"] == "duplicate_ca" for record in logger.records)


def test_delayed_ca_can_arrive_before_timeout() -> None:
    transport = FakeBleTransport(
        auto_prepare=True,
        last_c9_sequence=2,
        ca_mode="delayed",
        ca_delay_seconds=0.001,
    )
    result = run_case(transport, ca_timeout=0.1)
    assert result.success
    assert result.ca_success_received


def test_ca_apply_write_failure_does_not_report_apply_sent() -> None:
    transport = FakeBleTransport(
        auto_prepare=True,
        last_c9_sequence=2,
        ca_mode="normal",
        fail_ca_apply=True,
    )
    result = run_case(transport)
    assert not result.success
    assert result.ca_success_received
    assert not result.ca_apply_sent
    assert result.ca_writes == 0
    assert result.final_state is UploadState.FAILED


def test_periodic_and_unknown_notifications_do_not_change_sequence() -> None:
    logger = Stage5Logger(human_output=False)
    transport = FakeBleTransport(
        auto_prepare=True,
        last_c9_sequence=2,
        ca_mode="normal",
        notifications_at_sequence={
            0: [bytes.fromhex("BC4803054A140F00006D")],
            1: [bytes.fromhex("BC99030100")],
        },
    )
    result = run_case(transport, logger)
    assert result.success
    assert result.c9_writes == 3
    assert result.ca_writes == 1
    unknown = [
        record for record in logger.records
        if record["event"] == "notification" and record["command"] == "UNKNOWN"
    ]
    assert [record["hex"] for record in unknown] == [
        "BC4803054A140F00006D",
        "BC99030100",
    ]
