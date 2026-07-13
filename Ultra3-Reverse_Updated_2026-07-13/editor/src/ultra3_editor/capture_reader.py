from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .errors import CaptureFormatError, CaptureReadError
from .models import (
    CaptureFileInfo,
    CaptureRecord,
    CaptureStatistics,
    ParsedCapture,
)

TARGET_WRITE_CHARACTERISTIC = "0000ff02-0000-1000-8000-00805f9b34fb"
TARGET_NOTIFY_CHARACTERISTIC = "0000ff03-0000-1000-8000-00805f9b34fb"
CAPTURE_FORMATS = ("auto", "frida", "hex-lines", "jsonl")
FRIDA_PREFIX = "[U3BLE] "
UUID_PATTERN = re.compile(
    r"(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
HEX_FROM_BC_PATTERN = re.compile(
    r"(?i)(?:0x)?BC(?:(?:0x)?[0-9a-f]{2}|[\s,:;|_\-])+"
)


def read_capture(path: str | Path, *, capture_format: str = "auto") -> ParsedCapture:
    if capture_format not in CAPTURE_FORMATS:
        raise CaptureFormatError(f"不支持的抓包格式: {capture_format}")
    candidate = Path(path).expanduser()
    if not candidate.exists():
        raise CaptureReadError(f"抓包文件不存在: {candidate}")
    if not candidate.is_file():
        raise CaptureReadError(f"抓包路径不是普通文件: {candidate}")
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise CaptureReadError(f"无法读取抓包 {candidate}: {exc}") from exc
    if not raw:
        raise CaptureReadError("抓包文件为空")
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if not any(line.strip() for line in lines):
        raise CaptureReadError("抓包文件不包含有效文本行")

    records: list[CaptureRecord] = []
    format_hints: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        record, hint = _parse_line(line_number, line, capture_format)
        if hint is not None:
            format_hints.add(hint)
        if record is not None:
            records.append(record)

    detected_format = _detected_format(capture_format, format_hints)
    statistics = _statistics(len(lines), records)
    return ParsedCapture(
        info=CaptureFileInfo(
            path=candidate.resolve(),
            size=len(raw),
            sha256=hashlib.sha256(raw).hexdigest().upper(),
        ),
        requested_format=capture_format,
        detected_format=detected_format,
        records=tuple(records),
        statistics=statistics,
    )


def _parse_line(
    line_number: int,
    line: str,
    capture_format: str,
) -> tuple[CaptureRecord | None, str | None]:
    stripped = line.strip()
    if not stripped:
        return None, None
    if capture_format in {"auto", "frida"} and stripped.startswith(FRIDA_PREFIX):
        event_text = stripped[len(FRIDA_PREFIX) :]
        try:
            event = json.loads(event_text)
        except json.JSONDecodeError:
            return None, "frida"
        return _record_from_json(line_number, line, event), "frida"
    if capture_format == "frida":
        return None, None
    if capture_format in {"auto", "jsonl"} and stripped.startswith("{"):
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            return None, "jsonl"
        return _record_from_json(line_number, line, event), "jsonl"
    if capture_format == "jsonl":
        return None, None
    if capture_format in {"auto", "hex-lines"}:
        record = _record_from_text(line_number, line)
        return record, "hex-lines" if record is not None else None
    return None, None


def _record_from_json(
    line_number: int,
    source_text: str,
    event: Any,
) -> CaptureRecord | None:
    if not isinstance(event, dict):
        return None
    event_name = str(event.get("event", "")).lower()
    direction = str(event.get("direction", "")).upper()
    uuid = _event_uuid(event)
    payload_text = _event_payload(event)
    if payload_text is None:
        return None
    payload = _decode_hex(payload_text)
    if payload is None:
        return None

    notify = (
        "notify" in event_name
        or direction == "RX"
        or uuid == TARGET_NOTIFY_CHARACTERISTIC
    )
    write = (
        "write" in event_name
        or direction == "TX"
        or any(key in event for key in ("tx", "write"))
    )
    if notify:
        kind = (
            "ff03_notification"
            if uuid in {None, TARGET_NOTIFY_CHARACTERISTIC}
            else "other"
        )
        direction = "RX"
    elif write:
        kind = (
            "ff02_write"
            if uuid in {None, TARGET_WRITE_CHARACTERISTIC}
            else "other"
        )
        direction = "TX"
    elif uuid == TARGET_WRITE_CHARACTERISTIC:
        kind = "ff02_write"
        direction = "TX"
    else:
        kind = "other"
        direction = direction or "UNKNOWN"
    return CaptureRecord(
        line_number=line_number,
        timestamp=_optional_text(event.get("ts", event.get("timestamp"))),
        direction=direction,
        characteristic_uuid=uuid,
        payload=payload,
        source_text=source_text,
        kind=kind,
    )


def _event_uuid(event: dict[str, Any]) -> str | None:
    for key in ("characteristic_uuid", "uuid", "characteristic"):
        value = event.get(key)
        if isinstance(value, str):
            match = UUID_PATTERN.search(value)
            if match:
                return match.group(0).lower()
            lowered = value.lower()
            if lowered == "ff02":
                return TARGET_WRITE_CHARACTERISTIC
            if lowered == "ff03":
                return TARGET_NOTIFY_CHARACTERISTIC
    return None


def _event_payload(event: dict[str, Any]) -> str | None:
    for key in ("frame_hex", "hex", "payload", "tx", "write"):
        value = event.get(key)
        if isinstance(value, str):
            return value
    return None


def _record_from_text(line_number: int, source_text: str) -> CaptureRecord | None:
    stripped = source_text.strip()
    payload = _decode_hex(stripped)
    if payload is not None:
        return CaptureRecord(
            line_number=line_number,
            timestamp=None,
            direction="TX",
            characteristic_uuid=TARGET_WRITE_CHARACTERISTIC,
            payload=payload,
            source_text=source_text,
            kind="ff02_write",
        )

    lowered = f" {stripped.lower()} "
    has_write_marker = "ff02" in lowered or " tx " in lowered or "write" in lowered
    has_notify_marker = "ff03" in lowered or " rx " in lowered or "notify" in lowered
    if not has_write_marker and not has_notify_marker:
        return None
    payload = _extract_marked_hex(stripped)
    if payload is None:
        return None
    uuid_match = UUID_PATTERN.search(stripped)
    uuid = uuid_match.group(0).lower() if uuid_match else None
    if has_notify_marker:
        kind = (
            "ff03_notification"
            if uuid in {None, TARGET_NOTIFY_CHARACTERISTIC}
            else "other"
        )
        direction = "RX"
    else:
        kind = (
            "ff02_write"
            if uuid in {None, TARGET_WRITE_CHARACTERISTIC}
            else "other"
        )
        direction = "TX"
    return CaptureRecord(
        line_number=line_number,
        timestamp=None,
        direction=direction,
        characteristic_uuid=uuid,
        payload=payload,
        source_text=source_text,
        kind=kind,
    )


def _extract_marked_hex(text: str) -> bytes | None:
    candidates = list(HEX_FROM_BC_PATTERN.finditer(text))
    if not candidates:
        return None
    return _decode_hex(max((match.group(0) for match in candidates), key=len))


def _decode_hex(value: str) -> bytes | None:
    normalized = re.sub(r"(?i)0x", "", value)
    normalized = re.sub(r"[\s,:;|_\-]", "", normalized)
    if not normalized or len(normalized) % 2 or re.fullmatch(r"[0-9a-fA-F]+", normalized) is None:
        return None
    try:
        return bytes.fromhex(normalized)
    except ValueError:
        return None


def _optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _detected_format(requested: str, hints: set[str]) -> str:
    if requested != "auto":
        return requested
    if len(hints) == 1:
        return next(iter(hints))
    return "auto"


def _statistics(total_lines: int, records: list[CaptureRecord]) -> CaptureStatistics:
    ff02 = [record for record in records if record.kind == "ff02_write"]
    recognized_commands = sum(
        record.payload.startswith((b"\xBC\xC8\x02", b"\xBC\xC9\x02"))
        or record.payload == bytes.fromhex("BCCA02010505")
        for record in ff02
    )
    other_records = sum(record.kind == "other" for record in records)
    return CaptureStatistics(
        total_lines=total_lines,
        recognized_records=len(records),
        ff02_writes=len(ff02),
        ff03_notifications=sum(
            record.kind == "ff03_notification" for record in records
        ),
        unrecognized_lines=total_lines - len(records),
        non_target_frames=other_records + len(ff02) - recognized_commands,
        c8_count=sum(record.payload.startswith(b"\xBC\xC8\x02") for record in ff02),
        c9_count=sum(record.payload.startswith(b"\xBC\xC9\x02") for record in ff02),
        ca_apply_count=sum(
            record.payload == bytes.fromhex("BCCA02010505") for record in ff02
        ),
    )
