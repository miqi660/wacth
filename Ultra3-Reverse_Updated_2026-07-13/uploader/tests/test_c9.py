import pytest

from ultra3_uploader.bc_frames import build_c9, iter_c9, parse_c9
from ultra3_uploader.errors import FrameError


def test_build_and_parse_c9() -> None:
    data = bytes(range(230))
    frame = build_c9(0x1234, data)
    packet = parse_c9(frame)
    assert len(frame) == 237
    assert frame[:6] == bytes.fromhex("BCC902E83412")
    assert packet.sequence == 0x1234
    assert packet.data == data
    assert packet.checksum_valid


def test_iter_c9_uses_230_byte_chunks() -> None:
    frames = list(iter_c9(b"A" * 231))
    assert len(frames) == 2
    assert parse_c9(frames[0]).data == b"A" * 230
    assert parse_c9(frames[1]).data == b"A"
    assert parse_c9(frames[1]).sequence == 1


def test_parse_c9_reports_bad_checksum_without_hiding_packet() -> None:
    frame = bytearray(build_c9(0, b"data"))
    frame[-1] ^= 0xFF
    assert not parse_c9(bytes(frame)).checksum_valid


def test_parse_c9_rejects_bad_length() -> None:
    frame = bytearray(build_c9(0, b"data"))
    frame[3] += 1
    with pytest.raises(FrameError, match="LEN"):
        parse_c9(bytes(frame))

