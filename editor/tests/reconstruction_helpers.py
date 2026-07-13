from __future__ import annotations

import json
from pathlib import Path

from ultra3_editor.c9_protocol import C9_DATA_SIZE, c8_checksum, c9_checksum


def payload(size: int = 500) -> bytes:
    if size < 11:
        raise ValueError("测试 payload 至少需要容纳 BCSDIAL/BCBC")
    return b"BCSDIAL" + bytes((index % 251 for index in range(size - 11))) + b"BCBC"


def build_c8(
    data: bytes,
    *,
    declared_size: int | None = None,
    declared_count: int | None = None,
    checksum_delta: int = 0,
) -> bytes:
    size = len(data) if declared_size is None else declared_size
    count = (
        (size + C9_DATA_SIZE - 1) // C9_DATA_SIZE
        if declared_count is None
        else declared_count
    )
    size_le = size.to_bytes(4, "little")
    count_le = count.to_bytes(2, "little")
    checksum = (c8_checksum(1, size_le, count_le) + checksum_delta) & 0xFF
    return b"\xBC\xC8\x02\x07\x01" + size_le + count_le + bytes([checksum])


def build_c9(
    sequence: int,
    data: bytes,
    *,
    checksum_delta: int = 0,
) -> bytes:
    sequence_le = sequence.to_bytes(2, "little")
    checksum = (c9_checksum(sequence, data) + checksum_delta) & 0xFF
    return (
        b"\xBC\xC9\x02"
        + bytes([2 + len(data)])
        + sequence_le
        + data
        + bytes([checksum])
    )


def frames_for(data: bytes) -> list[bytes]:
    frames = [build_c8(data)]
    frames.extend(
        build_c9(sequence, data[offset : offset + C9_DATA_SIZE])
        for sequence, offset in enumerate(range(0, len(data), C9_DATA_SIZE))
    )
    return frames


def write_hex_lines(path: Path, frames: list[bytes]) -> Path:
    path.write_text(
        "\n".join(frame.hex().upper() for frame in frames) + "\n",
        encoding="utf-8",
    )
    return path


def write_frida(path: Path, frames: list[bytes]) -> Path:
    lines = []
    for index, frame in enumerate(frames):
        event = {
            "event": "ble_write",
            "uuid": "0000ff02-0000-1000-8000-00805f9b34fb",
            "hex": frame.hex().upper(),
            "ts": f"2026-07-13T00:00:{index:02d}.000Z",
        }
        lines.append("[U3BLE] " + json.dumps(event, separators=(",", ":")))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
