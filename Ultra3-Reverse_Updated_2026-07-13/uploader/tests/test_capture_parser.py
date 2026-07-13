import json
from pathlib import Path

import pytest

from ultra3_uploader.bcsdial import BCSDIALPayload
from ultra3_uploader.capture_parser import PREFIX, compare_capture, parse_capture
from ultra3_uploader.errors import CaptureParseError


def line(event: str, frame: bytes) -> str:
    return PREFIX + json.dumps({"event": event, "hex": frame.hex().upper()})


def test_parse_and_compare_synthetic_capture(tmp_path: Path) -> None:
    payload = BCSDIALPayload(b"BCSDIALBCBC")
    c9 = list(payload.iter_data_frames())
    log = tmp_path / "capture.log"
    log.write_text("\n".join((
        "unrelated output",
        line("ble_write", payload.build_prepare_frame()),
        line("ble_notify_raw", bytes.fromhex("BCD103010202")),
        line("ble_write", c9[0]),
    )), encoding="utf-8")

    capture = parse_capture(log)
    result = compare_capture(payload, capture)
    assert capture.notifications == [bytes.fromhex("BCD103010202")]
    assert result.ok


def test_compare_detects_duplicate_and_out_of_order(tmp_path: Path) -> None:
    payload = BCSDIALPayload(b"BCSDIAL" + b"X" * 450 + b"BCBC")
    frames = list(payload.iter_data_frames())
    log = tmp_path / "capture.log"
    log.write_text("\n".join((
        line("ble_write", payload.build_prepare_frame()),
        line("ble_write", frames[1]),
        line("ble_write", frames[0]),
        line("ble_write", frames[1]),
    )), encoding="utf-8")

    result = compare_capture(payload, parse_capture(log))
    assert result.duplicate_sequences == (1,)
    assert result.missing_sequences == (2,)
    assert result.out_of_order
    assert not result.full_packet_exact
    assert not result.reconstructed_exact


def test_invalid_u3ble_json_has_line_number(tmp_path: Path) -> None:
    log = tmp_path / "capture.log"
    log.write_text("ignored\n[U3BLE] {bad", encoding="utf-8")
    with pytest.raises(CaptureParseError, match="第 2 行"):
        parse_capture(log)

