from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BCSDIALFileInfo:
    path: Path
    size: int
    sha256: str
    header: bytes
    footer: bytes
    header_valid: bool
    footer_valid: bool

    @property
    def valid(self) -> bool:
        return self.header_valid and self.footer_valid and self.size > 0

    @property
    def header_ascii(self) -> str:
        return self.header.decode("ascii", errors="replace")


@dataclass(frozen=True)
class LoadedBCSDIAL:
    info: BCSDIALFileInfo
    data: bytes


@dataclass(frozen=True)
class ByteStatistics:
    zero_count: int
    nonzero_count: int
    unique_byte_count: int
    most_common_byte: int
    most_common_count: int


@dataclass(frozen=True)
class InspectionResult:
    info: BCSDIALFileInfo
    first_64: bytes
    last_64: bytes
    statistics: ByteStatistics
    selected_offset: int | None
    context_start: int | None
    context_end: int | None
    context_bytes: bytes


@dataclass(frozen=True)
class DiffByte:
    offset: int
    before: int | None
    after: int | None


@dataclass(frozen=True)
class DiffRange:
    start: int
    end: int
    length: int
    before_bytes: bytes
    after_bytes: bytes
    context_start: int
    context_end: int
    before_context: bytes
    after_context: bytes


@dataclass(frozen=True)
class DiffResult:
    before_info: BCSDIALFileInfo
    after_info: BCSDIALFileInfo
    same_size: bool
    changed_byte_count: int
    unchanged_byte_count: int
    ranges: tuple[DiffRange, ...]
    first_difference: int | None
    last_difference: int | None

    @property
    def changed_percentage(self) -> float:
        total = max(self.before_info.size, self.after_info.size)
        return 0.0 if total == 0 else self.changed_byte_count / total * 100.0
