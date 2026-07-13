from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .errors import (
    FileReadError,
    InvalidExistingTimePositionError,
    UnsupportedStaticDiySizeError,
)

STATIC_DIY_SIZE = 351_617
TIME_POSITION_OFFSET = 0


class TimePosition(str, Enum):
    TOP = "top"
    BOTTOM = "bottom"

    @property
    def byte_value(self) -> int:
        return 0 if self is TimePosition.TOP else 1

    @property
    def label(self) -> str:
        return "上方" if self is TimePosition.TOP else "下方"


@dataclass(frozen=True)
class StaticDiyInspection:
    path: Path
    size: int
    sha256: str
    first_byte: int
    time_position: TimePosition


def inspect_static_diy(path: str | Path) -> StaticDiyInspection:
    source = Path(path)
    if not source.is_file():
        raise FileReadError(f"输入文件不存在或不是普通文件: {source}")
    try:
        data = source.read_bytes()
    except OSError as exc:
        raise FileReadError(f"无法读取输入文件: {source}") from exc
    if len(data) != STATIC_DIY_SIZE:
        raise UnsupportedStaticDiySizeError(
            f"文件大小 {len(data)} 不受支持，当前只验证 {STATIC_DIY_SIZE} 字节"
        )
    try:
        position = TimePosition.TOP if data[0] == 0 else TimePosition.BOTTOM
        if data[0] not in (0, 1):
            raise ValueError
    except (IndexError, ValueError) as exc:
        raise InvalidExistingTimePositionError(
            f"offset 0x{TIME_POSITION_OFFSET:08X} 的值不是 00 或 01"
        ) from exc
    return StaticDiyInspection(
        path=source.resolve(),
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest().upper(),
        first_byte=data[0],
        time_position=position,
    )
