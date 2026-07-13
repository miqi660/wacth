from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from tests.real_transport_stub import RealTransportStub
from ultra3_uploader.bcsdial import BCSDIALPayload
from ultra3_uploader.fake_transport import default_snapshot
from ultra3_uploader.errors import MtuTooSmallError, WriteSizeTooSmallError
from ultra3_uploader.logging_utils import Stage5Logger
from ultra3_uploader.real_upload import (
    RealUploadAuthorization,
    reserve_log_file,
    validate_runtime_capabilities,
)
from ultra3_uploader.stage5 import validate_gatt
from ultra3_uploader.timing import FakeClock, FakeSleeper
from ultra3_uploader.upload_bcsdial import upload_bcsdial
from ultra3_uploader.upload_state import UploadState


def payload() -> BCSDIALPayload:
    return BCSDIALPayload(b"BCSDIAL" + b"\x00" * 489 + b"BCBC")


def run_real(
    transport: RealTransportStub,
    value: BCSDIALPayload,
    tmp_path: Path,
):
    log = tmp_path / "real.jsonl"
    reserve_log_file(log)
    clock = FakeClock()
    return asyncio.run(upload_bcsdial(
        transport,
        value,
        ready_timeout=0.02,
        ca_timeout=0.02,
        logger=Stage5Logger(log, human_output=False),
        sleeper=FakeSleeper(clock),
        clock=clock,
        authorization=RealUploadAuthorization(
            confirmed=True,
            expected_sha256=value.sha256,
            log_file=log,
        ),
    ))


@pytest.mark.parametrize(
    "snapshot",
    [
        replace(default_snapshot(), service_found=False),
        replace(default_snapshot(), ff02=None),
        replace(
            default_snapshot(),
            ff02=replace(default_snapshot().ff02, properties=frozenset()),
        ),
        replace(default_snapshot(), ff03=None),
        replace(
            default_snapshot(),
            ff03=replace(default_snapshot().ff03, properties=frozenset()),
        ),
        replace(default_snapshot(), mtu_size=None),
        replace(default_snapshot(), mtu_size=239),
        replace(
            default_snapshot(),
            ff02=replace(
                default_snapshot().ff02,
                max_write_without_response_size=None,
            ),
        ),
        replace(
            default_snapshot(),
            ff02=replace(
                default_snapshot().ff02,
                max_write_without_response_size=236,
            ),
        ),
    ],
    ids=[
        "service_missing",
        "ff02_missing",
        "ff02_no_write_without_response",
        "ff03_missing",
        "ff03_no_notify",
        "mtu_unknown",
        "mtu_239",
        "maximum_unknown",
        "maximum_236",
    ],
)
def test_runtime_preflight_failure_has_zero_writes_and_disconnects(
    snapshot,
    tmp_path: Path,
) -> None:
    value = payload()
    transport = RealTransportStub(snapshot=snapshot, auto_prepare=True)
    result = run_real(transport, value, tmp_path)
    assert not result.success
    assert result.final_state is UploadState.FAILED
    assert transport.connect_calls == [("FAKE-ULTRA3-1", 20.0)]
    assert transport.writes == []
    assert result.c8_writes == result.c9_writes == result.ca_writes == 0
    assert transport.disconnect_calls == 1
    assert not transport.is_connected


@pytest.mark.parametrize(("mtu", "maximum"), [(240, 237), (247, 244)])
def test_runtime_boundary_values_allow_complete_upload(
    mtu: int,
    maximum: int,
    tmp_path: Path,
) -> None:
    value = payload()
    snapshot = replace(
        default_snapshot(),
        mtu_size=mtu,
        ff02=replace(
            default_snapshot().ff02,
            max_write_without_response_size=maximum,
        ),
    )
    transport = RealTransportStub(
        snapshot=snapshot,
        auto_prepare=True,
        last_c9_sequence=value.packet_count - 1,
        ca_mode="normal",
        max_write_size=maximum,
    )
    result = run_real(transport, value, tmp_path)
    assert result.success
    assert (result.c8_writes, result.c9_writes, result.ca_writes) == (1, 3, 1)
    assert result.total_writes == 5


def test_authorization_cannot_weaken_runtime_minimums() -> None:
    authorization = RealUploadAuthorization(
        confirmed=True,
        expected_sha256="0" * 64,
        minimum_mtu=1,
        minimum_write_without_response=1,
    )
    with pytest.raises(MtuTooSmallError):
        validate_runtime_capabilities(
            validate_gatt(replace(default_snapshot(), mtu_size=239)),
            authorization,
        )
    with pytest.raises(WriteSizeTooSmallError):
        validate_runtime_capabilities(
            validate_gatt(replace(
                default_snapshot(),
                ff02=replace(
                    default_snapshot().ff02,
                    max_write_without_response_size=236,
                ),
            )),
            authorization,
        )
