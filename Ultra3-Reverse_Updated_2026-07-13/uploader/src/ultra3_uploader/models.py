from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol


class UploadPayload(Protocol):
    def build_prepare_frame(self) -> bytes: ...

    def iter_data_frames(self) -> Iterable[bytes]: ...

    def validate(self) -> None: ...


@dataclass(frozen=True)
class C9Packet:
    sequence: int
    data: bytes
    frame: bytes
    checksum_valid: bool
    line_number: int | None = None


@dataclass
class ParsedCapture:
    c8_requests: list[bytes] = field(default_factory=list)
    c9_packets: list[C9Packet] = field(default_factory=list)
    writes: list[bytes] = field(default_factory=list)
    notifications: list[bytes] = field(default_factory=list)


@dataclass(frozen=True)
class ComparisonResult:
    header_ok: bool
    footer_ok: bool
    file_size: int
    c8_exact: bool
    expected_packets: int
    captured_packets: int
    sequence_exact: bool
    valid_checksums: int
    duplicate_sequences: tuple[int, ...]
    missing_sequences: tuple[int, ...]
    out_of_order: bool
    full_packet_exact: bool
    reconstructed_exact: bool

    @property
    def ok(self) -> bool:
        return all((
            self.header_ok,
            self.footer_ok,
            self.c8_exact,
            self.expected_packets == self.captured_packets,
            self.sequence_exact,
            self.valid_checksums == self.captured_packets,
            not self.duplicate_sequences,
            not self.missing_sequences,
            not self.out_of_order,
            self.full_packet_exact,
            self.reconstructed_exact,
        ))

