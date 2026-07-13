from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tests.real_transport_stub import RealTransportStub
from ultra3_uploader.bcsdial import BCSDIALPayload
from ultra3_uploader.errors import (
    ExpectedSha256RequiredError,
    InvalidSha256Error,
    LogFileExistsError,
    PayloadSha256MismatchError,
    RealUploadError,
    RealUploadNotAuthorizedError,
    RealUploadPacketDelayError,
)
from ultra3_uploader.logging_utils import Stage5Logger
from ultra3_uploader.real_upload import (
    RealUploadAuthorization,
    reserve_log_file,
    validate_local_authorization,
)
from ultra3_uploader.upload_bcsdial import upload_bcsdial


def payload() -> BCSDIALPayload:
    return BCSDIALPayload(b"BCSDIAL" + b"\x00" * 489 + b"BCBC")


def authorization(value: BCSDIALPayload, **changes: object) -> RealUploadAuthorization:
    fields = {
        "confirmed": True,
        "expected_sha256": value.sha256,
    }
    fields.update(changes)
    return RealUploadAuthorization(**fields)


@pytest.mark.parametrize(
    ("changes", "delay", "error_type"),
    [
        ({"confirmed": False}, 45, RealUploadNotAuthorizedError),
        ({"expected_sha256": None}, 45, ExpectedSha256RequiredError),
        ({"expected_sha256": "XYZ"}, 45, InvalidSha256Error),
        ({"expected_sha256": "0" * 64}, 45, PayloadSha256MismatchError),
        ({}, 44.999, RealUploadPacketDelayError),
        ({"required_packet_delay_ms": 44.0}, 44.0, RealUploadPacketDelayError),
    ],
)
def test_local_authorization_rejects_before_connect(
    changes: dict[str, object],
    delay: float,
    error_type: type[Exception],
) -> None:
    value = payload()
    transport = RealTransportStub()
    with pytest.raises(error_type):
        asyncio.run(upload_bcsdial(
            transport,
            value,
            packet_delay_ms=delay,
            authorization=authorization(value, **changes),
        ))
    assert transport.connect_calls == []
    assert transport.writes == []


def test_sha256_comparison_is_case_insensitive() -> None:
    value = payload()
    validate_local_authorization(
        value,
        authorization(value, expected_sha256=value.sha256.lower()),
        packet_delay_ms=45,
    )


def test_real_transport_requires_authorization_before_connect() -> None:
    transport = RealTransportStub()
    with pytest.raises(RealUploadNotAuthorizedError):
        asyncio.run(upload_bcsdial(transport, payload()))
    assert transport.connect_calls == []
    assert transport.writes == []


def test_log_file_is_created_exclusively(tmp_path: Path) -> None:
    log = tmp_path / "real.jsonl"
    reserve_log_file(log)
    assert log.read_bytes() == b""
    with pytest.raises(LogFileExistsError):
        reserve_log_file(log)
    assert log.read_bytes() == b""


def test_logger_must_match_reserved_authorization_log(tmp_path: Path) -> None:
    value = payload()
    log = tmp_path / "real.jsonl"
    reserve_log_file(log)
    transport = RealTransportStub()
    with pytest.raises(RealUploadError, match="日志路径不一致"):
        asyncio.run(upload_bcsdial(
            transport,
            value,
            authorization=authorization(value, log_file=log),
            logger=Stage5Logger(tmp_path / "other.jsonl", human_output=False),
        ))
    assert transport.connect_calls == []
