from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .bc_frames import build_c8, iter_c9, packet_count_for_size
from .constants import BCSDIAL_FOOTER, BCSDIAL_HEADER, C9_CHUNK_SIZE
from .errors import BCSDIALValidationError, FrameError


@dataclass(frozen=True)
class BCSDIALPayload:
    data: bytes
    source: Path | None = None

    @classmethod
    def from_path(cls, path: Path) -> "BCSDIALPayload":
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise BCSDIALValidationError(f"无法读取文件 {path}: {exc}") from exc
        payload = cls(data=data, source=path)
        payload.validate()
        return payload

    def validate(self) -> None:
        if not self.data:
            raise BCSDIALValidationError("BCSDIAL 文件为空")
        if not self.data.startswith(BCSDIAL_HEADER):
            raise BCSDIALValidationError("BCSDIAL 文件头错误")
        if not self.data.endswith(BCSDIAL_FOOTER):
            raise BCSDIALValidationError("BCBC 文件尾错误")
        try:
            packet_count_for_size(len(self.data))
        except FrameError as exc:
            raise BCSDIALValidationError(str(exc)) from exc

    @property
    def size(self) -> int:
        return len(self.data)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest().upper()

    @property
    def packet_count(self) -> int:
        return packet_count_for_size(self.size)

    @property
    def final_chunk_size(self) -> int:
        return self.size - (self.packet_count - 1) * C9_CHUNK_SIZE

    def build_prepare_frame(self) -> bytes:
        return build_c8(self.size, self.packet_count)

    def iter_data_frames(self) -> Iterator[bytes]:
        return iter_c9(self.data)
