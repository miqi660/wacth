from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def valid_data() -> bytes:
    return b"BCSDIAL" + bytes(range(64)) + b"BCBC"


@pytest.fixture
def valid_file(tmp_path: Path, valid_data: bytes) -> Path:
    path = tmp_path / "sample.bin"
    path.write_bytes(valid_data)
    return path
