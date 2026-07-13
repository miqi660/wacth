from __future__ import annotations

from pathlib import Path

from ultra3_editor.differ import diff_bcsdial


def write_pair(
    tmp_path: Path,
    before: bytes,
    after: bytes,
) -> tuple[Path, Path]:
    before_path = tmp_path / "before.bin"
    after_path = tmp_path / "after.bin"
    before_path.write_bytes(before)
    after_path.write_bytes(after)
    return before_path, after_path


def test_identical_files_have_zero_differences(
    tmp_path: Path,
    valid_data: bytes,
) -> None:
    before, after = write_pair(tmp_path, valid_data, valid_data)
    result = diff_bcsdial(before, after)
    assert result.changed_byte_count == 0
    assert result.unchanged_byte_count == len(valid_data)
    assert result.ranges == ()
    assert result.first_difference is None
    assert result.last_difference is None


def test_single_byte_difference_is_identified(
    tmp_path: Path,
    valid_data: bytes,
) -> None:
    changed = bytearray(valid_data)
    changed[12] ^= 0xFF
    before, after = write_pair(tmp_path, valid_data, bytes(changed))
    result = diff_bcsdial(before, after, context=2)
    assert result.changed_byte_count == 1
    assert result.first_difference == result.last_difference == 12
    assert result.ranges[0].before_bytes == valid_data[12:13]
    assert result.ranges[0].after_bytes == bytes(changed[12:13])


def test_adjacent_differences_are_merged(
    tmp_path: Path,
    valid_data: bytes,
) -> None:
    changed = bytearray(valid_data)
    changed[20:23] = b"XYZ"
    before, after = write_pair(tmp_path, valid_data, bytes(changed))
    result = diff_bcsdial(before, after)
    assert len(result.ranges) == 1
    assert (result.ranges[0].start, result.ranges[0].end, result.ranges[0].length) == (20, 22, 3)


def test_non_adjacent_differences_remain_separate(
    tmp_path: Path,
    valid_data: bytes,
) -> None:
    changed = bytearray(valid_data)
    changed[20] ^= 1
    changed[22] ^= 1
    before, after = write_pair(tmp_path, valid_data, bytes(changed))
    result = diff_bcsdial(before, after)
    assert [(item.start, item.end) for item in result.ranges] == [(20, 20), (22, 22)]


def test_different_size_files_compare_safely(
    tmp_path: Path,
    valid_data: bytes,
) -> None:
    before, after = write_pair(tmp_path, valid_data, valid_data + b"\xAA\xBB")
    result = diff_bcsdial(before, after)
    assert not result.same_size
    assert result.changed_byte_count == 2
    assert result.unchanged_byte_count == len(valid_data)
    assert result.ranges[-1].after_bytes == b"\xAA\xBB"
    assert result.ranges[-1].before_bytes == b""


def test_diff_never_changes_inputs(tmp_path: Path, valid_data: bytes) -> None:
    changed = valid_data[:-5] + b"X" + valid_data[-4:]
    before, after = write_pair(tmp_path, valid_data, changed)
    before_hash = before.read_bytes()
    after_hash = after.read_bytes()
    diff_bcsdial(before, after)
    assert before.read_bytes() == before_hash
    assert after.read_bytes() == after_hash
