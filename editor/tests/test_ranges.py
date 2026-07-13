from __future__ import annotations

import pytest

from ultra3_editor.errors import OffsetError
from ultra3_editor.ranges import merge_adjacent_offsets, parse_offset, validate_offset


def test_parse_decimal_offset() -> None:
    assert parse_offset("367") == 0x16F


def test_parse_hexadecimal_offset() -> None:
    assert parse_offset("0x16F") == 0x16F


@pytest.mark.parametrize("value", ["-1", "xyz", "0xGG"])
def test_invalid_offsets_are_rejected(value: str) -> None:
    with pytest.raises(OffsetError):
        parse_offset(value)


def test_validate_offset_rejects_end_boundary() -> None:
    with pytest.raises(OffsetError):
        validate_offset(10, 10)


def test_merge_adjacent_offsets() -> None:
    assert merge_adjacent_offsets([8, 2, 3, 4, 8, 10]) == ((2, 4), (8, 8), (10, 10))
