from __future__ import annotations

from pathlib import Path

import pytest

from ultra3_editor.errors import OffsetError
from ultra3_editor.inspector import inspect_bcsdial


def test_inspection_contains_edges_and_statistics(
    valid_file: Path,
    valid_data: bytes,
) -> None:
    result = inspect_bcsdial(valid_file)
    assert result.first_64 == valid_data[:64]
    assert result.last_64 == valid_data[-64:]
    assert result.statistics.zero_count == valid_data.count(0)
    assert result.statistics.nonzero_count + result.statistics.zero_count == len(valid_data)
    assert result.info.valid


def test_inspection_returns_requested_context(valid_file: Path) -> None:
    result = inspect_bcsdial(valid_file, offset=10, context=3)
    assert result.selected_offset == 10
    assert (result.context_start, result.context_end) == (7, 13)
    assert len(result.context_bytes) == 7


def test_context_is_clamped_at_file_start(valid_file: Path) -> None:
    result = inspect_bcsdial(valid_file, offset=0, context=32)
    assert result.context_start == 0
    assert result.context_end == 32


def test_out_of_range_offset_is_rejected(valid_file: Path, valid_data: bytes) -> None:
    with pytest.raises(OffsetError, match="超出"):
        inspect_bcsdial(valid_file, offset=len(valid_data), context=1)


def test_negative_context_is_rejected(valid_file: Path) -> None:
    with pytest.raises(OffsetError, match="context"):
        inspect_bcsdial(valid_file, context=-1)


def test_inspection_never_changes_input(valid_file: Path) -> None:
    before = valid_file.read_bytes()
    inspect_bcsdial(valid_file, offset=3, context=2)
    assert valid_file.read_bytes() == before
