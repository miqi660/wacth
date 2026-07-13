from __future__ import annotations

from dataclasses import dataclass

from .upload_state import UploadState


@dataclass(frozen=True)
class UploadResult:
    success: bool
    final_state: UploadState
    c8_writes: int
    c9_writes: int
    ca_writes: int
    total_writes: int
    packets_sent: int
    bytes_sent: int
    last_sequence: int | None
    ca_success_received: bool
    ca_apply_sent: bool
    elapsed_seconds: float
    cancellation_requested: bool
    disconnect_observed: bool
    error_type: str | None
    error_message: str | None

