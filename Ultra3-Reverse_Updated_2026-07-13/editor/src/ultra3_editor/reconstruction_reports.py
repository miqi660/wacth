from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import EditorError, ReportExistsError
from .models import ReconstructionResult, UploadSession


def reconstruction_dict(
    result: ReconstructionResult,
    *,
    output_path: Path | None,
) -> dict[str, Any]:
    session = result.selected_session
    c8 = session.c8_packet
    sequences = [packet.sequence for packet in session.c9_packets]
    checksum_passed = sum(packet.checksum_valid for packet in session.c9_packets)
    return {
        "status": result.status,
        "source_capture": str(result.capture.info.path),
        "source_capture_sha256": result.capture.info.sha256,
        "format": result.capture.detected_format,
        "requested_format": result.capture.requested_format,
        "session_count": len(result.sessions),
        "session_index": session.index,
        "c8_hex": session.c8_record.payload.hex().upper(),
        "mode": c8.mode if c8 else None,
        "declared_size": c8.declared_size if c8 else None,
        "declared_packet_count": c8.declared_packet_count if c8 else None,
        "actual_packet_count": len(session.c9_records),
        "first_sequence": sequences[0] if sequences else None,
        "last_sequence": sequences[-1] if sequences else None,
        "checksum_passed": checksum_passed,
        "checksum_failed": len(session.checksum_failed_sequences),
        "checksum_failed_sequences": list(session.checksum_failed_sequences),
        "missing_sequences": list(session.missing_sequences),
        "duplicate_sequences": list(session.duplicate_sequences),
        "out_of_order": session.out_of_order,
        "reconstructed_size": result.reconstructed_size,
        "reconstructed_sha256": result.reconstructed_sha256,
        "output_path": str(output_path.resolve()) if output_path else None,
        "header_valid": result.header_valid,
        "footer_valid": result.footer_valid,
        "errors": list(result.errors),
        "capture_statistics": _statistics_dict(result),
        "sessions": [_session_dict(item) for item in result.sessions],
        "real_ble_usage": {
            "bleak_initializations": 0,
            "scan": 0,
            "connect": 0,
            "ff02_writes": 0,
        },
    }


def _statistics_dict(result: ReconstructionResult) -> dict[str, int]:
    stats = result.capture.statistics
    return {
        "total_lines": stats.total_lines,
        "recognized_records": stats.recognized_records,
        "ff02_writes": stats.ff02_writes,
        "ff03_notifications": stats.ff03_notifications,
        "unrecognized_lines": stats.unrecognized_lines,
        "non_target_frames": stats.non_target_frames,
        "c8_count": stats.c8_count,
        "c9_count": stats.c9_count,
        "ca_apply_count": stats.ca_apply_count,
    }


def _session_dict(session: UploadSession) -> dict[str, Any]:
    c8 = session.c8_packet
    sequences = [packet.sequence for packet in session.c9_packets]
    return {
        "session_index": session.index,
        "c8_hex": session.c8_record.payload.hex().upper(),
        "mode": c8.mode if c8 else None,
        "declared_file_size": c8.declared_size if c8 else None,
        "declared_packet_count": c8.declared_packet_count if c8 else None,
        "first_sequence": sequences[0] if sequences else None,
        "last_sequence": sequences[-1] if sequences else None,
        "c9_count": len(session.c9_records),
        "start_line": session.start_line,
        "end_line": session.end_line,
        "complete": session.complete,
        "errors": list(session.errors),
    }


def write_reconstructed_binary(data: bytes, path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    except FileExistsError as exc:
        raise ReportExistsError(f"输出文件已存在，拒绝覆盖: {path}") from exc
    except OSError as exc:
        raise EditorError(f"无法写入重组 BIN {path}: {exc}") from exc


def write_reconstruction_json(
    result: ReconstructionResult,
    path: Path,
    *,
    output_path: Path | None,
) -> None:
    _write_text_exclusive(
        path,
        json.dumps(
            reconstruction_dict(result, output_path=output_path),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )


def write_reconstruction_markdown(
    result: ReconstructionResult,
    path: Path,
    *,
    output_path: Path | None,
) -> None:
    data = reconstruction_dict(result, output_path=output_path)
    stats = data["capture_statistics"]
    lines = [
        "# Ultra3 C9 Reconstruction Report",
        "",
        f"- Status: `{data['status']}`",
        f"- Source capture: `{data['source_capture']}`",
        f"- Source SHA-256: `{data['source_capture_sha256']}`",
        f"- Parsing format: `{data['format']}`",
        f"- Upload sessions: `{data['session_count']}`",
        f"- Selected session: `{data['session_index']}`",
        "",
        "## C8 / C9 validation",
        "",
        f"- C8: `{data['c8_hex']}`",
        f"- Mode: `{data['mode']}`",
        f"- Declared file size: `{data['declared_size']}`",
        f"- Declared packet count: `{data['declared_packet_count']}`",
        f"- Actual packet count: `{data['actual_packet_count']}`",
        f"- Sequence: `{data['first_sequence']}..{data['last_sequence']}`",
        f"- Checksum passed: `{data['checksum_passed']}`",
        f"- Checksum failed: `{data['checksum_failed']}`",
        f"- Missing sequences: `{data['missing_sequences']}`",
        f"- Duplicate sequences: `{data['duplicate_sequences']}`",
        f"- Out of order: `{data['out_of_order']}`",
        "",
        "## Reconstructed BCSDIAL",
        "",
        f"- Output: `{data['output_path']}`",
        f"- Size: `{data['reconstructed_size']}`",
        f"- SHA-256: `{data['reconstructed_sha256']}`",
        f"- BCSDIAL header: `{data['header_valid']}`",
        f"- BCBC footer: `{data['footer_valid']}`",
        "",
        "## Capture parsing statistics",
        "",
        f"- Total lines: `{stats['total_lines']}`",
        f"- Recognized records: `{stats['recognized_records']}`",
        f"- FF02 writes: `{stats['ff02_writes']}`",
        f"- FF03 notifications: `{stats['ff03_notifications']}`",
        f"- Unrecognized lines: `{stats['unrecognized_lines']}`",
        f"- Non-target frames: `{stats['non_target_frames']}`",
        f"- C8/C9/CA: `{stats['c8_count']}/{stats['c9_count']}/{stats['ca_apply_count']}`",
        "",
        "## Errors",
        "",
        *(f"- {error}" for error in data["errors"]),
        *( ["- None"] if not data["errors"] else [] ),
        "",
        "## Safety and unknown behavior",
        "",
        "- Real BLE usage: `0`（Bleak/scan/connect/FF02 write 均为 0）。",
        "- 输入抓包和重组 BIN 未被修改；工具只按原始 C9 DATA 顺序输出。",
        "- 未实现自动排序、去重、补零、丢包修复、BIN patch 或 GUI。",
        "- 尚未执行 A0_repeat_1/A0_repeat_2 真实 DIY 重复样本采集。",
        "- 尚未确认 DIY 时间位置、颜色字段或生成结果的确定性。",
    ]
    _write_text_exclusive(path, "\n".join(lines) + "\n")


def _write_text_exclusive(path: Path, content: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except FileExistsError as exc:
        raise ReportExistsError(f"输出文件已存在，拒绝覆盖: {path}") from exc
    except OSError as exc:
        raise EditorError(f"无法写入重组报告 {path}: {exc}") from exc
