from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import LogWriteError
from .notification_parser import NotificationRecord
from .upload_state import UploadState


def redact_device_id(device_id: str | None) -> str:
    if not device_id:
        return "unknown"
    if len(device_id) <= 4:
        return "*" * len(device_id)
    return "*" * (len(device_id) - 4) + device_id[-4:]


class Stage5Logger:
    def __init__(self, log_file: Path | None = None, *, human_output: bool = True) -> None:
        self.log_file = log_file
        self.human_output = human_output
        self.records: list[dict[str, Any]] = []

    def emit(
        self,
        event: str,
        *,
        direction: str = "INFO",
        state: UploadState,
        device_id: str | None = None,
        uuid: str | None = None,
        length: int | None = None,
        hex_data: str | None = None,
        command: str | None = None,
        error: str | None = None,
        **fields: Any,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "direction": direction,
            "state": state.value,
            "device_id": device_id,
            "uuid": uuid,
            "length": length,
            "hex": hex_data,
            "command": command,
            "error": error,
        }
        record.update(fields)
        self.records.append(record)
        if self.log_file is not None:
            try:
                self.log_file.parent.mkdir(parents=True, exist_ok=True)
                with self.log_file.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            except OSError as exc:
                raise LogWriteError(f"无法写入 JSONL 日志 {self.log_file}: {exc}") from exc
        if self.human_output:
            detail = error or command or event
            print(f"[{state.value}] {direction} {detail} device={redact_device_id(device_id)}")
        return record

    def notification(
        self,
        notification: NotificationRecord,
        *,
        state: UploadState,
        device_id: str,
        uuid: str,
    ) -> dict[str, Any]:
        return self.emit(
            "notification",
            direction="RX",
            state=state,
            device_id=device_id,
            uuid=uuid,
            length=notification.length,
            hex_data=notification.hex,
            command=notification.command,
            error=notification.parse_error,
            notification=asdict(notification) | {"raw": notification.hex},
        )
