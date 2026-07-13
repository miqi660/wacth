from __future__ import annotations

import pytest

from reconstruction_helpers import build_c8, build_c9, payload
from ultra3_editor.c9_protocol import parse_c8, parse_c9
from ultra3_editor.errors import FrameValidationError


def test_c8_fields_and_checksum_are_parsed() -> None:
    frame = build_c8(payload(500))
    parsed = parse_c8(frame)
    assert parsed.mode == 1
    assert parsed.declared_size == 500
    assert parsed.declared_packet_count == 3
    assert parsed.checksum_valid


def test_c8_checksum_failure_is_reported_without_guessing() -> None:
    assert not parse_c8(build_c8(payload(20), checksum_delta=1)).checksum_valid


def test_c9_sequence_data_and_checksum_are_parsed() -> None:
    data = bytes(range(20))
    parsed = parse_c9(build_c9(513, data), line_number=9)
    assert parsed.sequence == 513
    assert parsed.data == data
    assert parsed.checksum_valid
    assert parsed.line_number == 9


def test_full_c9_data_length_is_230() -> None:
    parsed = parse_c9(build_c9(0, bytes(230)), line_number=1)
    assert len(parsed.data) == 230
    assert len(parsed.frame) == 237


def test_short_final_c9_is_supported() -> None:
    parsed = parse_c9(build_c9(2, bytes(40)), line_number=1)
    assert len(parsed.data) == 40
    assert len(parsed.frame) == 47


def test_c9_checksum_failure_is_reported() -> None:
    parsed = parse_c9(build_c9(0, b"data", checksum_delta=1), line_number=1)
    assert not parsed.checksum_valid


def test_c9_len_mismatch_is_rejected() -> None:
    frame = bytearray(build_c9(0, b"data"))
    frame[3] += 1
    with pytest.raises(FrameValidationError, match="LEN"):
        parse_c9(bytes(frame), line_number=1)


def test_non_c9_frame_is_rejected() -> None:
    with pytest.raises(FrameValidationError):
        parse_c9(build_c8(payload(20)), line_number=1)
