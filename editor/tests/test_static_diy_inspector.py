from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ultra3_editor.errors import (
    FileReadError,
    InvalidExistingTimePositionError,
    UnsupportedStaticDiySizeError,
)
from ultra3_editor.static_diy import STATIC_DIY_SIZE, TimePosition, inspect_static_diy


def write_static(path: Path, first_byte: int) -> Path:
    path.write_bytes(bytes([first_byte]) + bytes(STATIC_DIY_SIZE - 1))
    return path


@pytest.mark.parametrize(
    ("first_byte", "position"),
    ((0, TimePosition.TOP), (1, TimePosition.BOTTOM)),
)
def test_inspects_verified_time_positions(
    tmp_path: Path,
    first_byte: int,
    position: TimePosition,
) -> None:
    path = write_static(tmp_path / "watchface.bin", first_byte)
    result = inspect_static_diy(path)
    assert result.size == STATIC_DIY_SIZE
    assert result.first_byte == first_byte
    assert result.time_position is position
    assert result.sha256 == hashlib.sha256(path.read_bytes()).hexdigest().upper()


@pytest.mark.parametrize("size", (0, STATIC_DIY_SIZE - 1, STATIC_DIY_SIZE + 1))
def test_rejects_unverified_sizes(tmp_path: Path, size: int) -> None:
    path = tmp_path / "wrong-size.bin"
    path.write_bytes(bytes(size))
    with pytest.raises(UnsupportedStaticDiySizeError):
        inspect_static_diy(path)


def test_rejects_unknown_time_position(tmp_path: Path) -> None:
    path = write_static(tmp_path / "unknown.bin", 2)
    with pytest.raises(InvalidExistingTimePositionError, match="00 或 01"):
        inspect_static_diy(path)


def test_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileReadError, match="不存在"):
        inspect_static_diy(tmp_path / "missing.bin")


def test_inspection_does_not_modify_input(tmp_path: Path) -> None:
    path = write_static(tmp_path / "top.bin", 0)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    inspect_static_diy(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
