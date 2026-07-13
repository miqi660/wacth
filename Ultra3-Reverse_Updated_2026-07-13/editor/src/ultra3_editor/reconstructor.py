from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

from .bcsdial import BCSDIAL_FOOTER, BCSDIAL_HEADER
from .c9_protocol import C9_DATA_SIZE, packet_count_for_size, parse_c8, parse_c9
from .capture_reader import read_capture
from .errors import FrameValidationError, SessionSelectionError
from .models import (
    CaptureRecord,
    ParsedCapture,
    ReconstructionResult,
    UploadSession,
)

CA_APPLY_FRAME = bytes.fromhex("BCCA02010505")


def reconstruct_capture(
    path: str | Path,
    *,
    capture_format: str = "auto",
    session_index: int | None = None,
) -> ReconstructionResult:
    capture = read_capture(path, capture_format=capture_format)
    sessions = locate_upload_sessions(capture)
    selected = select_session(sessions, session_index=session_index)
    data = selected.reconstructed_data
    return ReconstructionResult(
        capture=capture,
        sessions=sessions,
        selected_session=selected,
        status="COMPLETE" if selected.complete else "FAILED",
        reconstructed_size=len(data),
        reconstructed_sha256=(
            hashlib.sha256(data).hexdigest().upper() if data else None
        ),
        header_valid=data.startswith(BCSDIAL_HEADER),
        footer_valid=data.endswith(BCSDIAL_FOOTER),
        errors=selected.errors,
    )


def locate_upload_sessions(capture: ParsedCapture) -> tuple[UploadSession, ...]:
    sessions: list[UploadSession] = []
    current_c8: CaptureRecord | None = None
    current_c9: list[CaptureRecord] = []
    current_ca: list[CaptureRecord] = []
    declared_count: int | None = None
    last_relevant_line: int | None = None

    def finish(end_line: int) -> None:
        nonlocal current_c8, current_c9, current_ca, declared_count
        if current_c8 is None:
            return
        sessions.append(_validate_session(
            len(sessions),
            current_c8,
            tuple(current_c9),
            tuple(current_ca),
            end_line,
        ))
        current_c8 = None
        current_c9 = []
        current_ca = []
        declared_count = None

    for record in capture.records:
        if record.kind != "ff02_write":
            continue
        payload = record.payload
        if payload.startswith(b"\xBC\xC8\x02"):
            if current_c8 is not None:
                finish(record.line_number - 1)
            current_c8 = record
            last_relevant_line = record.line_number
            try:
                declared_count = parse_c8(payload).declared_packet_count
            except FrameValidationError:
                declared_count = None
            continue
        if current_c8 is None:
            continue
        last_relevant_line = record.line_number
        if payload.startswith(b"\xBC\xC9\x02"):
            current_c9.append(record)
            if declared_count is not None and len(current_c9) == declared_count:
                finish(record.line_number)
            continue
        if payload == CA_APPLY_FRAME:
            current_ca.append(record)
            finish(record.line_number)

    if current_c8 is not None:
        finish(last_relevant_line or current_c8.line_number)
    return tuple(sessions)


def select_session(
    sessions: tuple[UploadSession, ...],
    *,
    session_index: int | None,
) -> UploadSession:
    if not sessions:
        raise SessionSelectionError("抓包中没有 C8 上传会话")
    if session_index is not None:
        if session_index < 0 or session_index >= len(sessions):
            raise SessionSelectionError(
                f"session-index {session_index} 超出范围 0..{len(sessions) - 1}"
            )
        return sessions[session_index]
    complete = [session for session in sessions if session.complete]
    if len(complete) == 1:
        return complete[0]
    candidates = ", ".join(
        f"{session.index}(lines {session.start_line}-{session.end_line}, complete={session.complete})"
        for session in sessions
    )
    if len(complete) > 1:
        raise SessionSelectionError(
            f"存在多个完整上传会话，请提供 --session-index；候选: {candidates}"
        )
    if len(sessions) == 1:
        return sessions[0]
    raise SessionSelectionError(f"没有完整上传会话；候选: {candidates}")


def _validate_session(
    index: int,
    c8_record: CaptureRecord,
    c9_records: tuple[CaptureRecord, ...],
    ca_records: tuple[CaptureRecord, ...],
    end_line: int,
) -> UploadSession:
    errors: list[str] = []
    c8_packet = None
    try:
        c8_packet = parse_c8(c8_record.payload)
    except FrameValidationError as exc:
        errors.append(f"C8 结构错误: {exc}")
    if c8_packet is not None:
        if not c8_packet.checksum_valid:
            errors.append("C8 checksum 错误")
        if not 1 <= c8_packet.declared_packet_count <= 0xFFFF:
            errors.append("C8 packet count 不合法")
        try:
            expected_count = packet_count_for_size(c8_packet.declared_size)
            if c8_packet.declared_packet_count != expected_count:
                errors.append(
                    "C8 packet count 与声明文件大小不一致: "
                    f"{c8_packet.declared_packet_count} != {expected_count}"
                )
        except FrameValidationError as exc:
            errors.append(str(exc))

    packets = []
    malformed_line: int | None = None
    for record in c9_records:
        try:
            packets.append(parse_c9(record.payload, line_number=record.line_number))
        except FrameValidationError as exc:
            if malformed_line is None:
                malformed_line = record.line_number
            errors.append(f"第 {record.line_number} 行 C9 结构错误: {exc}")

    sequences = [packet.sequence for packet in packets]
    counts = Counter(sequences)
    duplicates = tuple(sorted(sequence for sequence, count in counts.items() if count > 1))
    declared_count = c8_packet.declared_packet_count if c8_packet is not None else 0
    missing = tuple(
        sequence for sequence in range(declared_count) if sequence not in counts
    )
    out_of_order = sequences != sorted(sequences)
    checksum_failed = tuple(
        packet.sequence for packet in packets if not packet.checksum_valid
    )
    if checksum_failed:
        errors.append(
            "C9 checksum 错误 sequence: "
            + ",".join(str(sequence) for sequence in checksum_failed)
        )
    if sequences and sequences[0] != 0:
        errors.append(f"C9 sequence 未从 0 开始: {sequences[0]}")
    if duplicates:
        errors.append("重复 sequence: " + ",".join(map(str, duplicates)))
    if missing:
        errors.append("缺失 sequence: " + ",".join(map(str, missing)))
    if out_of_order:
        errors.append("C9 sequence 乱序")
    if c8_packet is not None:
        expected_sequences = list(range(c8_packet.declared_packet_count))
        if sequences != expected_sequences:
            errors.append("C9 sequence 不严格连续")
        if len(c9_records) != c8_packet.declared_packet_count:
            errors.append(
                "C9 数量与声明不符: "
                f"{len(c9_records)} != {c8_packet.declared_packet_count}"
            )
        _validate_data_lengths(packets, c8_packet.declared_size, errors)

    reconstructed = b"".join(packet.data for packet in packets)
    if c8_packet is not None and len(reconstructed) != c8_packet.declared_size:
        errors.append(
            "重组大小与声明不符: "
            f"{len(reconstructed)} != {c8_packet.declared_size}"
        )
    if reconstructed and not reconstructed.startswith(BCSDIAL_HEADER):
        errors.append("重组文件缺失 BCSDIAL 头")
    if reconstructed and not reconstructed.endswith(BCSDIAL_FOOTER):
        errors.append("重组文件缺失 BCBC 尾")
    if not reconstructed:
        errors.append("会话没有可重组的 C9 DATA")
    if malformed_line is not None:
        errors.append(f"first malformed frame line: {malformed_line}")

    return UploadSession(
        index=index,
        c8_record=c8_record,
        c8_packet=c8_packet,
        c9_records=c9_records,
        c9_packets=tuple(packets),
        ca_records=ca_records,
        start_line=c8_record.line_number,
        end_line=end_line,
        complete=not errors,
        errors=tuple(errors),
        reconstructed_data=reconstructed,
        missing_sequences=missing,
        duplicate_sequences=duplicates,
        out_of_order=out_of_order,
        checksum_failed_sequences=checksum_failed,
    )


def _validate_data_lengths(packets, declared_size: int, errors: list[str]) -> None:
    try:
        count = packet_count_for_size(declared_size)
    except FrameValidationError:
        return
    final_size = declared_size - C9_DATA_SIZE * (count - 1)
    for packet in packets:
        if packet.sequence >= count:
            errors.append(f"sequence {packet.sequence} 超过声明包数")
            continue
        expected = final_size if packet.sequence == count - 1 else C9_DATA_SIZE
        if len(packet.data) != expected:
            errors.append(
                f"sequence {packet.sequence} DATA 长度 {len(packet.data)} != {expected}"
            )
