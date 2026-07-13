from __future__ import annotations

import hashlib
from pathlib import Path

from .errors import BCSDIALValidationError, FileReadError
from .models import BCSDIALFileInfo, LoadedBCSDIAL

BCSDIAL_HEADER = b"BCSDIAL"
BCSDIAL_FOOTER = b"BCBC"


def read_bcsdial(path: str | Path, *, require_valid: bool = True) -> LoadedBCSDIAL:
    candidate = Path(path).expanduser()
    if not candidate.exists():
        raise FileReadError(f"文件不存在: {candidate}")
    if not candidate.is_file():
        raise FileReadError(f"路径不是普通文件: {candidate}")
    try:
        data = candidate.read_bytes()
    except OSError as exc:
        raise FileReadError(f"无法读取文件 {candidate}: {exc}") from exc
    if not data:
        raise BCSDIALValidationError(f"文件为空: {candidate}")

    resolved = candidate.resolve()
    info = BCSDIALFileInfo(
        path=resolved,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest().upper(),
        header=data[: len(BCSDIAL_HEADER)],
        footer=data[-len(BCSDIAL_FOOTER) :],
        header_valid=data.startswith(BCSDIAL_HEADER),
        footer_valid=data.endswith(BCSDIAL_FOOTER),
    )
    if require_valid:
        require_valid_bcsdial(info)
    return LoadedBCSDIAL(info=info, data=data)


def require_valid_bcsdial(info: BCSDIALFileInfo) -> None:
    if not info.header_valid:
        raise BCSDIALValidationError("BCSDIAL 文件头错误")
    if not info.footer_valid:
        raise BCSDIALValidationError("BCBC 文件尾错误")
