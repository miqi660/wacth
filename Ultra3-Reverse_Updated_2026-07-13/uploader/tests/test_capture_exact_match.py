from __future__ import annotations

import os
from pathlib import Path

from ultra3_uploader.bc_frames import parse_c9
from ultra3_uploader.bcsdial import BCSDIALPayload
from ultra3_uploader.capture_parser import compare_capture, parse_capture


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


def test_frozen_capture_exact_match() -> None:
    root = archive_root()
    baseline = root / "dynamic_watchface" / "baseline" / "2026-07-13_bcsdial_ff02_upload_success"
    sample = baseline / "evidence" / "samples" / "168844266159401_jump13_to_4_reconstructed_from_ble.bin"
    capture_path = baseline / "evidence" / "capture_light_v2.log"

    payload = BCSDIALPayload.from_path(sample)
    capture = parse_capture(capture_path)
    result = compare_capture(payload, capture)

    assert payload.size == 891180
    assert payload.sha256 == "7B25A833D431ED29622EDF4C102F4B555F1E251D1CEC842D848E8E7DCE2C015D"
    assert payload.packet_count == 3875
    assert payload.final_chunk_size == 160
    assert payload.build_prepare_frame().hex().upper() == "BCC80207012C990D00230F05"
    assert capture.c9_packets[0].sequence == 0
    assert capture.c9_packets[-1].sequence == 3874
    assert len(parse_c9(capture.c9_packets[-1].frame).data) == 160
    assert result.ok

