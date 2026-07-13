from ultra3_uploader.checksum import c8_checksum, c9_checksum, sum8


def test_sum8_wraps() -> None:
    assert sum8(bytes((0xFF, 0x02))) == 0x01


def test_golden_c8_checksum() -> None:
    assert c8_checksum(1, bytes.fromhex("2C990D00"), bytes.fromhex("230F")) == 0x05


def test_c9_checksum_includes_little_endian_sequence() -> None:
    assert c9_checksum(0x0102, bytes((0x03, 0x04))) == 0x0A

