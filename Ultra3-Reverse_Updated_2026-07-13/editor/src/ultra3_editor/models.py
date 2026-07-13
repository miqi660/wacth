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


@dataclass(frozen=True)
class CaptureFileInfo:
    path: Path
    size: int
    sha256: str


@dataclass(frozen=True)
class CaptureRecord:
    line_number: int
    timestamp: str | None
    direction: str
    characteristic_uuid: str | None
    payload: bytes
    source_text: str
    kind: str


@dataclass(frozen=True)
class CaptureStatistics:
    total_lines: int
    recognized_records: int
    ff02_writes: int
    ff03_notifications: int
    unrecognized_lines: int
    non_target_frames: int
    c8_count: int
    c9_count: int
    ca_apply_count: int


@dataclass(frozen=True)
class ParsedCapture:
    info: CaptureFileInfo
    requested_format: str
    detected_format: str
    records: tuple[CaptureRecord, ...]
    statistics: CaptureStatistics


@dataclass(frozen=True)
class C8Packet:
    frame: bytes
    mode: int
    declared_size: int
    declared_packet_count: int
    checksum_valid: bool


@dataclass(frozen=True)
class C9Packet:
    frame: bytes
    sequence: int
    data: bytes
    checksum_valid: bool
    line_number: int


@dataclass(frozen=True)
class UploadSession:
    index: int
    c8_record: CaptureRecord
    c8_packet: C8Packet | None
    c9_records: tuple[CaptureRecord, ...]
    c9_packets: tuple[C9Packet, ...]
    ca_records: tuple[CaptureRecord, ...]
    start_line: int
    end_line: int
    complete: bool
    errors: tuple[str, ...]
    reconstructed_data: bytes
    missing_sequences: tuple[int, ...]
    duplicate_sequences: tuple[int, ...]
    out_of_order: bool
    checksum_failed_sequences: tuple[int, ...]


@dataclass(frozen=True)
class ReconstructionResult:
    capture: ParsedCapture
    sessions: tuple[UploadSession, ...]
    selected_session: UploadSession
    status: str
    reconstructed_size: int
    reconstructed_sha256: str | None
    header_valid: bool
    footer_valid: bool
    errors: tuple[str, ...]
