from __future__ import annotations

import os
from pathlib import Path

import pytest

from ultra3_editor.bcsdial import read_bcsdial
from ultra3_editor.differ import diff_bcsdial
from ultra3_editor.errors import KnownPatchVerificationError
from ultra3_editor.known_patch import (
    KNOWN_AFTER_SHA256,
    KNOWN_BEFORE_SHA256,
    verify_known_patch,
)


def archive_root() -> Path:
    candidates = [
        Path(os.environ["ULTRA3_ARCHIVE_ROOT"])
        if "ULTRA3_ARCHIVE_ROOT" in os.environ
        else None,
        Path.home() / "Desktop" / "Ultra3-Reverse_Updated_2026-07-13",
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "dynamic_watchface").is_dir():
            return candidate
    raise AssertionError("找不到 Ultra3 Frozen 归档；请设置 ULTRA3_ARCHIVE_ROOT")


@pytest.fixture(scope="module")
def golden_paths() -> tuple[Path, Path]:
    samples = (
        archive_root()
        / "dynamic_watchface"
        / "baseline"
        / "2026-07-13_bcsdial_ff02_upload_success"
        / "evidence"
        / "samples"
    )
    return (
        samples / "168844266159401_original.bin",
        samples / "168844266159401_jump13_to_4_reconstructed_from_ble.bin",
    )


def test_golden_known_patch_is_verified(golden_paths: tuple[Path, Path]) -> None:
    before, after = golden_paths
    result = diff_bcsdial(before, after, context=32)
    verify_known_patch(result)
    assert result.before_info.sha256 == KNOWN_BEFORE_SHA256
    assert result.after_info.sha256 == KNOWN_AFTER_SHA256
    assert result.changed_byte_count == 1
    assert result.ranges[0].start == 0x16F
    assert result.ranges[0].before_bytes == b"\x0D"
    assert result.ranges[0].after_bytes == b"\x04"


def test_reversed_pair_is_rejected(golden_paths: tuple[Path, Path]) -> None:
    before, after = golden_paths
    with pytest.raises(KnownPatchVerificationError):
        verify_known_patch(diff_bcsdial(after, before))


@pytest.mark.parametrize(
    ("offset", "value"),
    [(0x170, 0x04), (0x16F, 0x05)],
    ids=["wrong_offset", "wrong_value"],
)
def test_wrong_patch_is_rejected(
    offset: int,
    value: int,
    golden_paths: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    before, _after = golden_paths
    data = bytearray(read_bcsdial(before).data)
    data[offset] = value
    candidate = tmp_path / "wrong.bin"
    candidate.write_bytes(data)
    with pytest.raises(KnownPatchVerificationError):
        verify_known_patch(diff_bcsdial(before, candidate))


def test_second_difference_is_rejected(
    golden_paths: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    before, after = golden_paths
    data = bytearray(read_bcsdial(after).data)
    data[0x170] ^= 1
    candidate = tmp_path / "second-difference.bin"
    candidate.write_bytes(data)
    with pytest.raises(KnownPatchVerificationError, match="差异字节"):
        verify_known_patch(diff_bcsdial(before, candidate))
