from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ultra3_editor.bcsdial import read_bcsdial
from ultra3_editor.errors import BCSDIALValidationError, FileReadError


def test_recognizes_bcsdial_header(valid_file: Path) -> None:
    assert read_bcsdial(valid_file).info.header_valid
    assert read_bcsdial(valid_file).info.header_ascii == "BCSDIAL"


def test_recognizes_bcbc_footer(valid_file: Path) -> None:
    assert read_bcsdial(valid_file).info.footer_valid
    assert read_bcsdial(valid_file).info.footer == b"BCBC"


def test_wrong_header_is_rejected(tmp_path: Path, valid_data: bytes) -> None:
    path = tmp_path / "bad-header.bin"
    path.write_bytes(b"X" + valid_data[1:])
    with pytest.raises(BCSDIALValidationError, match="文件头"):
        read_bcsdial(path)


def test_wrong_footer_is_rejected(tmp_path: Path, valid_data: bytes) -> None:
    path = tmp_path / "bad-footer.bin"
    path.write_bytes(valid_data[:-1] + b"X")
    with pytest.raises(BCSDIALValidationError, match="文件尾"):
        read_bcsdial(path)


def test_empty_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")
    with pytest.raises(BCSDIALValidationError, match="为空"):
        read_bcsdial(path)


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(FileReadError, match="不存在"):
        read_bcsdial(tmp_path / "missing.bin")


def test_directory_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(FileReadError, match="普通文件"):
        read_bcsdial(tmp_path)


def test_sha256_is_calculated_from_exact_bytes(
    valid_file: Path,
    valid_data: bytes,
) -> None:
    expected = hashlib.sha256(valid_data).hexdigest().upper()
    assert read_bcsdial(valid_file).info.sha256 == expected
    assert read_bcsdial(valid_file).info.path.is_absolute()
