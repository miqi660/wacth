from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from reconstruction_helpers import (
    build_c8,
    build_c9,
    frames_for,
    payload,
    write_hex_lines,
)
from ultra3_editor.errors import CaptureReadError, SessionSelectionError
from ultra3_editor.reconstructor import reconstruct_capture


def reconstruct_frames(tmp_path: Path, frames: list[bytes]):
    path = write_hex_lines(tmp_path / "capture.log", frames)
    return reconstruct_capture(path, capture_format="hex-lines")


def test_reconstructs_single_packet_file(tmp_path: Path) -> None:
    data = payload(20)
    result = reconstruct_frames(tmp_path, frames_for(data))
    assert result.status == "COMPLETE"
    assert result.selected_session.reconstructed_data == data
    assert len(result.selected_session.c9_packets) == 1


def test_reconstructs_multiple_packets_in_original_order(tmp_path: Path) -> None:
    data = payload(500)
    result = reconstruct_frames(tmp_path, frames_for(data))
    assert result.status == "COMPLETE"
    assert result.selected_session.reconstructed_data == data
    assert [packet.sequence for packet in result.selected_session.c9_packets] == [0, 1, 2]
    assert [len(packet.data) for packet in result.selected_session.c9_packets] == [230, 230, 40]


def test_missing_sequence_is_rejected(tmp_path: Path) -> None:
    data = payload(500)
    frames = [
        build_c8(data),
        build_c9(0, data[:230]),
        build_c9(2, data[460:]),
    ]
    result = reconstruct_frames(tmp_path, frames)
    assert result.status == "FAILED"
    assert result.selected_session.missing_sequences == (1,)
    assert any("缺失 sequence" in error for error in result.errors)


def test_duplicate_sequence_is_rejected(tmp_path: Path) -> None:
    data = payload(500)
    frames = [
        build_c8(data),
        build_c9(0, data[:230]),
        build_c9(1, data[230:460]),
        build_c9(1, data[460:]),
    ]
    result = reconstruct_frames(tmp_path, frames)
    assert result.status == "FAILED"
    assert result.selected_session.duplicate_sequences == (1,)


def test_out_of_order_sequence_is_rejected(tmp_path: Path) -> None:
    data = payload(500)
    frames = [
        build_c8(data),
        build_c9(0, data[:230]),
        build_c9(2, data[460:]),
        build_c9(1, data[230:460]),
    ]
    result = reconstruct_frames(tmp_path, frames)
    assert result.status == "FAILED"
    assert result.selected_session.out_of_order


def test_c9_checksum_failure_is_rejected(tmp_path: Path) -> None:
    data = payload(20)
    result = reconstruct_frames(
        tmp_path,
        [build_c8(data), build_c9(0, data, checksum_delta=1)],
    )
    assert result.status == "FAILED"
    assert result.selected_session.checksum_failed_sequences == (0,)


def test_c8_checksum_failure_is_rejected(tmp_path: Path) -> None:
    data = payload(20)
    result = reconstruct_frames(
        tmp_path,
        [build_c8(data, checksum_delta=1), build_c9(0, data)],
    )
    assert result.status == "FAILED"
    assert "C8 checksum 错误" in result.errors


def test_declared_packet_count_mismatch_is_rejected(tmp_path: Path) -> None:
    data = payload(500)
    result = reconstruct_frames(tmp_path, [
        build_c8(data, declared_count=2),
        build_c9(0, data[:230]),
        build_c9(1, data[230:460]),
    ])
    assert result.status == "FAILED"
    assert any("packet count 与声明文件大小不一致" in error for error in result.errors)


def test_reconstructed_size_mismatch_is_rejected(tmp_path: Path) -> None:
    data = payload(500)
    result = reconstruct_frames(tmp_path, [
        build_c8(data),
        build_c9(0, data[:230]),
        build_c9(1, data[230:460]),
        build_c9(2, data[460:-1]),
    ])
    assert result.status == "FAILED"
    assert any("重组大小与声明不符" in error for error in result.errors)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"XCSDIAL" + bytes(9) + b"BCBC", "BCSDIAL 头"),
        (b"BCSDIAL" + bytes(9) + b"BCBX", "BCBC 尾"),
    ],
)
def test_invalid_reconstructed_boundaries_are_rejected(
    data: bytes,
    message: str,
    tmp_path: Path,
) -> None:
    result = reconstruct_frames(tmp_path, frames_for(data))
    assert result.status == "FAILED"
    assert any(message in error for error in result.errors)


def test_empty_log_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "empty.log"
    path.write_bytes(b"")
    with pytest.raises(CaptureReadError, match="为空"):
        reconstruct_capture(path)


def test_log_without_c8_is_rejected(tmp_path: Path) -> None:
    data = payload(20)
    path = write_hex_lines(tmp_path / "no-c8.log", [build_c9(0, data)])
    with pytest.raises(SessionSelectionError, match="没有 C8"):
        reconstruct_capture(path)


def test_only_c8_is_failed_session(tmp_path: Path) -> None:
    data = payload(20)
    result = reconstruct_frames(tmp_path, [build_c8(data)])
    assert result.status == "FAILED"
    assert any("没有可重组" in error for error in result.errors)


def test_multiple_complete_sessions_require_index(tmp_path: Path) -> None:
    first = payload(20)
    second = payload(21)
    path = write_hex_lines(
        tmp_path / "multiple.log",
        frames_for(first) + frames_for(second),
    )
    with pytest.raises(SessionSelectionError, match="多个完整"):
        reconstruct_capture(path)


def test_session_index_selects_requested_session(tmp_path: Path) -> None:
    first = payload(20)
    second = payload(21)
    path = write_hex_lines(
        tmp_path / "multiple.log",
        frames_for(first) + frames_for(second),
    )
    result = reconstruct_capture(path, session_index=1)
    assert result.selected_session.index == 1
    assert result.selected_session.reconstructed_data == second


def test_new_c8_prevents_session_data_mixing(tmp_path: Path) -> None:
    first = payload(500)
    second = payload(20)
    path = write_hex_lines(tmp_path / "separate.log", [
        build_c8(first),
        build_c9(0, first[:230]),
        *frames_for(second),
    ])
    result = reconstruct_capture(path)
    assert len(result.sessions) == 2
    assert not result.sessions[0].complete
    assert result.selected_session.index == 1
    assert result.selected_session.reconstructed_data == second


def test_ca_apply_ends_incomplete_session_without_becoming_data(tmp_path: Path) -> None:
    data = payload(500)
    result = reconstruct_frames(tmp_path, [
        build_c8(data),
        build_c9(0, data[:230]),
        bytes.fromhex("BCCA02010505"),
    ])
    assert result.status == "FAILED"
    assert len(result.selected_session.ca_records) == 1
    assert result.reconstructed_size == 230


def archive_root() -> Path:
    candidates = [
        Path(os.environ["ULTRA3_ARCHIVE_ROOT"])
        if "ULTRA3_ARCHIVE_ROOT" in os.environ
        else None,
        Path.home() / "Desktop" / "Ultra3-Reverse_Updated_2026-07-13",
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "captures").is_dir():
            return candidate
    raise AssertionError("找不到 Ultra3 Frozen 归档；请设置 ULTRA3_ARCHIVE_ROOT")


def test_golden_frida_capture_reconstructs_exact_bin() -> None:
    root = archive_root()
    capture = root / "captures" / "2026-07-13_bcsdial_ble_direct" / "raw" / "capture_light_v2.log"
    golden = (
        root
        / "dynamic_watchface"
        / "baseline"
        / "2026-07-13_bcsdial_ff02_upload_success"
        / "evidence"
        / "samples"
        / "168844266159401_jump13_to_4_reconstructed_from_ble.bin"
    )
    capture_before = hashlib.sha256(capture.read_bytes()).hexdigest()
    result = reconstruct_capture(capture, capture_format="auto")
    assert result.status == "COMPLETE"
    assert result.capture.detected_format == "frida"
    assert result.reconstructed_size == 891180
    assert result.reconstructed_sha256 == "7B25A833D431ED29622EDF4C102F4B555F1E251D1CEC842D848E8E7DCE2C015D"
    assert len(result.selected_session.c9_packets) == 3875
    assert result.selected_session.c9_packets[0].sequence == 0
    assert result.selected_session.c9_packets[-1].sequence == 3874
    assert result.selected_session.reconstructed_data == golden.read_bytes()
    assert hashlib.sha256(capture.read_bytes()).hexdigest() == capture_before
