from __future__ import annotations

from dataclasses import dataclass

from .upload_state import UploadState


@dataclass(frozen=True)
class UploadProgress:
    current_packet: int
    total_packets: int
    packets_sent: int
    bytes_sent: int
    total_bytes: int
    percent: float
    elapsed_seconds: float
    effective_bytes_per_second: float
    estimated_remaining_seconds: float | None
    current_sequence: int
    state: UploadState


def make_progress(
    *,
    packets_sent: int,
    total_packets: int,
    bytes_sent: int,
    total_bytes: int,
    elapsed_seconds: float,
    current_sequence: int,
    state: UploadState,
) -> UploadProgress:
    rate = bytes_sent / elapsed_seconds if elapsed_seconds > 0 else 0.0
    remaining = (
        (total_bytes - bytes_sent) / rate
        if rate > 0 and bytes_sent < total_bytes
        else 0.0 if bytes_sent == total_bytes else None
    )
    return UploadProgress(
        current_packet=packets_sent,
        total_packets=total_packets,
        packets_sent=packets_sent,
        bytes_sent=bytes_sent,
        total_bytes=total_bytes,
        percent=(bytes_sent / total_bytes * 100.0) if total_bytes else 0.0,
        elapsed_seconds=elapsed_seconds,
        effective_bytes_per_second=rate,
        estimated_remaining_seconds=remaining,
        current_sequence=current_sequence,
        state=state,
    )

