from pathlib import Path

import pytest

from ultra3_uploader.bcsdial import BCSDIALPayload
from ultra3_uploader.errors import BCSDIALValidationError


def write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def test_valid_minimal_bcsdial(tmp_path: Path) -> None:
    payload = BCSDIALPayload.from_path(write(tmp_path / "valid.bin", b"BCSDIALBCBC"))
    assert payload.size == 11
    assert payload.packet_count == 1
    assert payload.final_chunk_size == 11


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "为空"),
        (b"NOTDIALBCBC", "文件头"),
        (b"BCSDIALNOPE", "文件尾"),
    ],
)
def test_rejects_invalid_boundaries(tmp_path: Path, data: bytes, message: str) -> None:
    with pytest.raises(BCSDIALValidationError, match=message):
        BCSDIALPayload.from_path(write(tmp_path / "invalid.bin", data))


def test_missing_file_is_validation_error(tmp_path: Path) -> None:
    with pytest.raises(BCSDIALValidationError, match="无法读取"):
        BCSDIALPayload.from_path(tmp_path / "missing.bin")

