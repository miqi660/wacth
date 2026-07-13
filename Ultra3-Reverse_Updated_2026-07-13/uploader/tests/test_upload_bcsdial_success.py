from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from ultra3_uploader.bc_frames import parse_c9
from ultra3_uploader.bcsdial import BCSDIALPayload
from ultra3_uploader.constants import CA_APPLY_FRAME, FF02_UUID
from ultra3_uploader.fake_transport import FakeBleTransport
from ultra3_uploader.logging_utils import Stage5Logger
from ultra3_uploader.timing import FakeClock, FakeSleeper
from ultra3_uploader.upload_bcsdial import upload_bcsdial
from ultra3_uploader.upload_state import UploadState


def archive_root() -> Path:
    candidates = [
        Path(os.environ["ULTRA3_ARCHIVE_ROOT"]) if "ULTRA3_ARCHIVE_ROOT" in os.environ else None,
        Path(__file__).resolve().parents[2],
        Path.home() / "Desktop" / "Ultra3-Reverse_Updated_2026-07-13",
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "dynamic_watchface").is_dir():
            return candidate
    raise AssertionError("找不到 Ultra3 Frozen 归档；请设置 ULTRA3_ARCHIVE_ROOT")


def golden_payload() -> BCSDIALPayload:
    path = (
        archive_root()
        / "dynamic_watchface"
        / "baseline"
        / "2026-07-13_bcsdial_ff02_upload_success"
        / "evidence"
        / "samples"
        / "168844266159401_jump13_to_4_reconstructed_from_ble.bin"
    )
    return BCSDIALPayload.from_path(path)


def test_golden_full_upload_exact_success() -> None:
    payload = golden_payload()
    clock = FakeClock()
    sleeper = FakeSleeper(clock)
    progress = []
    logger = Stage5Logger(human_output=False)
    transport = FakeBleTransport(
        auto_prepare=True,
        last_c9_sequence=payload.packet_count - 1,
        ca_mode="normal",
        max_write_size=244,
    )

    result = asyncio.run(upload_bcsdial(
        transport,
        payload,
        packet_delay_ms=45,
        logger=logger,
        sleeper=sleeper,
        clock=clock,
        progress_callback=progress.append,
    ))

    assert result.success
    assert result.final_state is UploadState.COMPLETE
    assert result.c8_writes == 1
    assert result.c9_writes == 3875
    assert result.ca_writes == 1
    assert result.total_writes == 3877
    assert result.packets_sent == 3875
    assert result.bytes_sent == 891180
    assert result.last_sequence == 3874
    assert result.ca_success_received
    assert result.ca_apply_sent
    assert result.disconnect_observed

    writes = [data for uuid, data in transport.writes if uuid == FF02_UUID]
    assert writes[0].hex().upper() == "BCC80207012C990D00230F05"
    assert parse_c9(writes[1]).sequence == 0
    assert parse_c9(writes[3875]).sequence == 3874
    assert writes[3876] == CA_APPLY_FRAME
    c9_frames = writes[1:3876]
    packets = [parse_c9(frame) for frame in c9_frames]
    assert len(c9_frames[0]) == 237
    assert len(c9_frames[-1]) == 167
    assert [packet.sequence for packet in packets] == list(range(3875))
    assert all(packet.checksum_valid for packet in packets)
    assert b"".join(packet.data for packet in packets) == payload.data

    assert len(sleeper.calls) == 3874
    assert set(sleeper.calls) == {0.045}
    assert sleeper.total_seconds == pytest.approx(174.33)
    assert len(progress) == 3875
    assert progress[-1].percent == 100.0
    assert progress[-1].bytes_sent == payload.size
    assert transport.notify_unsubscriptions
    assert transport.disconnect_calls == 1
    assert not transport.is_connected

    ca_success_index = next(
        index for index, record in enumerate(logger.records)
        if record["event"] == "ca_success"
    )
    ca_apply_index = next(
        index for index, record in enumerate(logger.records)
        if record["event"] == "write" and record["command"] == "CA"
    )
    assert ca_success_index < ca_apply_index

