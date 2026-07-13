from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .bc_frames import parse_c9
from .bcsdial import BCSDIALPayload
from .constants import BCSDIAL_FOOTER, BCSDIAL_HEADER
from .errors import CaptureParseError, FrameError
from .models import ComparisonResult, ParsedCapture

PREFIX = "[U3BLE] "


def parse_capture(path: Path) -> ParsedCapture:
    capture = ParsedCapture()
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        raise CaptureParseError(f"无法读取抓包 {path}: {exc}") from exc

    for line_number, line in enumerate(lines, 1):
        if not line.startswith(PREFIX):
            continue
        try:
            event = json.loads(line[len(PREFIX):])
        except json.JSONDecodeError as exc:
            raise CaptureParseError(f"第 {line_number} 行 U3BLE JSON 无效: {exc}") from exc
        if event.get("event") not in {"ble_write", "ble_notify_raw"}:
            continue
        try:
            frame = bytes.fromhex(event.get("hex", ""))
        except (TypeError, ValueError) as exc:
            raise CaptureParseError(f"第 {line_number} 行 HEX 无效") from exc
        if event["event"] == "ble_notify_raw":
            capture.notifications.append(frame)
            continue
        capture.writes.append(frame)
        if frame.startswith(b"\xBC\xC8\x02"):
            capture.c8_requests.append(frame)
        elif frame.startswith(b"\xBC\xC9\x02"):
            try:
                capture.c9_packets.append(parse_c9(frame, line_number))
            except FrameError as exc:
                raise CaptureParseError(f"第 {line_number} 行 C9 无效: {exc}") from exc
    return capture


def compare_capture(payload: BCSDIALPayload, capture: ParsedCapture) -> ComparisonResult:
    expected_frames = list(payload.iter_data_frames())
    captured_frames = [packet.frame for packet in capture.c9_packets]
    sequences = [packet.sequence for packet in capture.c9_packets]
    counts = Counter(sequences)
    expected_sequences = list(range(len(expected_frames)))
    duplicate = tuple(sorted(sequence for sequence, count in counts.items() if count > 1))
    missing = tuple(sequence for sequence in expected_sequences if sequence not in counts)
    reconstructed = b"".join(packet.data for packet in capture.c9_packets)

    return ComparisonResult(
        header_ok=payload.data.startswith(BCSDIAL_HEADER),
        footer_ok=payload.data.endswith(BCSDIAL_FOOTER),
        file_size=payload.size,
        c8_exact=len(capture.c8_requests) == 1 and capture.c8_requests[0] == payload.build_prepare_frame(),
        expected_packets=len(expected_frames),
        captured_packets=len(captured_frames),
        sequence_exact=sequences == expected_sequences,
        valid_checksums=sum(packet.checksum_valid for packet in capture.c9_packets),
        duplicate_sequences=duplicate,
        missing_sequences=missing,
        out_of_order=sequences != sorted(sequences),
        full_packet_exact=captured_frames == expected_frames,
        reconstructed_exact=reconstructed == payload.data,
    )

