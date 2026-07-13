from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .checksum import c8_checksum, sum8


@dataclass(frozen=True)
class NotificationRecord:
    raw: bytes
    hex: str
    command: str
    direction: str
    length: int
    parsed_fields: dict[str, Any]
    valid: bool
    parse_error: str | None
    timestamp: str


def _record(
    raw: bytes,
    command: str,
    direction: str,
    fields: dict[str, Any],
    valid: bool,
    error: str | None = None,
) -> NotificationRecord:
    return NotificationRecord(
        raw=raw,
        hex=raw.hex().upper(),
        command=command,
        direction=direction,
        length=len(raw),
        parsed_fields=fields,
        valid=valid,
        parse_error=error,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def parse_notification(data: bytes) -> NotificationRecord:
    raw = bytes(data)
    if len(raw) < 3 or raw[0] != 0xBC:
        return _record(raw, "UNKNOWN", "unknown", {}, False, "不是已确认的 BC 通知帧")

    command = f"{raw[1]:02X}"
    direction = f"{raw[2]:02X}"

    if raw[1] == 0x72:
        if len(raw) != 7 or raw[:4] != bytes.fromhex("BC720302"):
            return _record(raw, "72", direction, {}, False, "BC72 长度或固定字段无效")
        countdown = int.from_bytes(raw[4:6], "little")
        valid = raw[-1] == sum8(raw[4:6])
        return _record(
            raw, "72", direction, {"countdown": countdown}, valid,
            None if valid else "BC72 checksum 无效",
        )

    if raw[1] == 0xD1:
        valid = raw == bytes.fromhex("BCD103010202")
        return _record(
            raw, "D1", direction, {"ready_code": raw[4] if len(raw) > 4 else None}, valid,
            None if valid else "不是已确认的 D1 ready 帧",
        )

    if raw[1] == 0xC8:
        if len(raw) != 12 or raw[:4] != bytes.fromhex("BCC80307"):
            return _record(raw, "C8", direction, {}, False, "C8 response 长度或固定字段无效")
        mode = raw[4]
        size_le = raw[5:9]
        count_le = raw[9:11]
        valid = raw[-1] == c8_checksum(mode, size_le, count_le)
        return _record(
            raw,
            "C8",
            direction,
            {
                "mode": mode,
                "file_size": int.from_bytes(size_le, "little"),
                "packet_count": int.from_bytes(count_le, "little"),
            },
            valid,
            None if valid else "C8 response checksum 无效",
        )

    if raw[1] == 0xCA:
        valid = raw == bytes.fromhex("BCCA030300000000")
        return _record(
            raw, "CA", direction, {"status_hex": raw[4:-1].hex().upper()}, valid,
            None if valid else "不是已确认的 CA success 帧",
        )

    return _record(raw, "UNKNOWN", direction, {"observed_command": command}, False, "未确认的通知命令")

