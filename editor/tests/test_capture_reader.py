from __future__ import annotations

import json
from pathlib import Path

from reconstruction_helpers import build_c8, build_c9, payload, write_frida, write_hex_lines
from ultra3_editor.capture_reader import (
    TARGET_WRITE_CHARACTERISTIC,
    read_capture,
)


def test_pure_hex_lines_are_ff02_writes(tmp_path: Path) -> None:
    data = payload(20)
    path = write_hex_lines(tmp_path / "hex.log", [build_c8(data), build_c9(0, data)])
    capture = read_capture(path, capture_format="hex-lines")
    assert capture.detected_format == "hex-lines"
    assert capture.statistics.ff02_writes == 2
    assert capture.statistics.c8_count == 1
    assert capture.statistics.c9_count == 1


def test_timestamped_frida_log_is_parsed(tmp_path: Path) -> None:
    data = payload(20)
    path = write_frida(tmp_path / "frida.log", [build_c8(data), build_c9(0, data)])
    capture = read_capture(path)
    assert capture.detected_format == "frida"
    assert capture.records[0].timestamp == "2026-07-13T00:00:00.000Z"
    assert capture.records[0].characteristic_uuid == TARGET_WRITE_CHARACTERISTIC


def test_jsonl_frame_hex_is_parsed(tmp_path: Path) -> None:
    frame = build_c8(payload(20))
    path = tmp_path / "capture.jsonl"
    path.write_text(json.dumps({
        "direction": "TX",
        "characteristic_uuid": "FF02",
        "frame_hex": frame.hex(),
    }) + "\n", encoding="utf-8")
    capture = read_capture(path, capture_format="jsonl")
    assert capture.statistics.ff02_writes == 1
    assert capture.records[0].payload == frame


def test_ff03_notification_is_not_counted_as_write(tmp_path: Path) -> None:
    frame = bytes.fromhex("BC4803054B280F000082")
    path = tmp_path / "notify.jsonl"
    path.write_text(json.dumps({
        "event": "ble_notify_raw",
        "uuid": "0000ff03-0000-1000-8000-00805f9b34fb",
        "hex": frame.hex(),
    }) + "\n", encoding="utf-8")
    capture = read_capture(path)
    assert capture.statistics.ff03_notifications == 1
    assert capture.statistics.ff02_writes == 0


def test_other_characteristic_write_is_non_target(tmp_path: Path) -> None:
    frame = build_c8(payload(20))
    path = tmp_path / "other.jsonl"
    path.write_text(json.dumps({
        "event": "ble_write",
        "uuid": "0000aa01-0000-1000-8000-00805f9b34fb",
        "hex": frame.hex(),
    }) + "\n", encoding="utf-8")
    capture = read_capture(path)
    assert capture.statistics.ff02_writes == 0
    assert capture.statistics.non_target_frames == 1


def test_prefixed_text_extracts_complete_hex(tmp_path: Path) -> None:
    frame = build_c8(payload(20))
    spaced = " ".join(f"{value:02X}" for value in frame)
    path = tmp_path / "prefix.log"
    path.write_text(f"2026-07-13 12:00:00 TX FF02 write: {spaced}\n", encoding="utf-8")
    capture = read_capture(path)
    assert capture.records[0].payload == frame


def test_explanatory_text_is_not_mistaken_for_frame(tmp_path: Path) -> None:
    path = tmp_path / "notes.log"
    path.write_text(
        "This document shows C8 example BCC802070114000000010016\n",
        encoding="utf-8",
    )
    capture = read_capture(path)
    assert capture.statistics.recognized_records == 0
    assert capture.statistics.unrecognized_lines == 1


def test_invalid_and_blank_lines_are_counted(tmp_path: Path) -> None:
    frame = build_c8(payload(20))
    path = tmp_path / "mixed.log"
    path.write_text(f"\nnot a record\n{frame.hex()}\n", encoding="utf-8")
    capture = read_capture(path)
    assert capture.statistics.total_lines == 3
    assert capture.statistics.recognized_records == 1
    assert capture.statistics.unrecognized_lines == 2


def test_ca_apply_is_counted_but_not_c9_data(tmp_path: Path) -> None:
    path = write_hex_lines(
        tmp_path / "ca.log",
        [bytes.fromhex("BCCA02010505")],
    )
    capture = read_capture(path)
    assert capture.statistics.ca_apply_count == 1
    assert capture.statistics.c9_count == 0
