from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from .bc_frames import build_c9, parse_c9
from .errors import FrameError, StaticTransferPlanError
from .handoff import validate_handoff
from .handoff_models import HandoffExternalUsage


STATIC_PLAN_FORMAT = "ultra3-static-transfer-plan/v1"
STATIC_FIRMWARE = "NJ-LEJ-2.1.7"
STATIC_PAYLOAD_SIZE = 353146
STATIC_FRAME_COUNT = 1529
STATIC_NORMAL_REGION_SIZE = 231
STATIC_FINAL_REGION_SIZE = 178
STATIC_NORMAL_FRAME_SIZE = 237
STATIC_FINAL_FRAME_SIZE = 184
PLAN_MANIFEST_NAME = "manifest.json"
PLAN_FRAMES_NAME = "c9_frames.bin"


@dataclass(frozen=True)
class StaticC9Frame:
    """一个已校验的静态 C9 帧及其 payload region。"""

    sequence: int
    data: bytes
    checksum: int
    region: bytes
    frame: bytes


@dataclass(frozen=True)
class StaticTransferVerification:
    """静态 C9 帧流的确定性离线复核结果。"""

    result: str
    payload_size: int
    payload_sha256: str
    c9_frame_count: int
    sequence_start: int | None
    sequence_end: int | None
    missing_sequences: tuple[int, ...]
    duplicate_sequences: tuple[int, ...]
    out_of_order: bool
    out_of_range_sequences: tuple[int, ...]
    checksum_failures: tuple[int, ...]
    normal_region_size: int | None
    final_region_size: int | None
    normal_frame_size: int | None
    final_frame_size: int | None
    reconstructed_size: int
    reconstructed_sha256: str
    exact_match: bool
    errors: tuple[str, ...]
    external_usage: HandoffExternalUsage


@dataclass(frozen=True)
class StaticTransferPlan:
    """由有效 Handoff 和显式静态 payload 构建的离线 C9 计划。"""

    handoff_schema: str
    handoff_manifest_sha256: str
    firmware: str
    source_artifact_path: str
    source_size: int
    source_sha256: str
    payload_identifier: str
    payload_size: int
    payload_sha256: str
    c9_frames: tuple[StaticC9Frame, ...]
    verification: StaticTransferVerification
    c8_frame: bytes | None = None
    ca_frame: bytes | None = None

    def to_manifest_dict(self) -> dict[str, Any]:
        """返回不含本机路径和当前时间的确定性计划 manifest。"""
        frame_stream = b"".join(item.frame for item in self.c9_frames)
        return {
            "format": STATIC_PLAN_FORMAT,
            "firmware": self.firmware,
            "handoff": {
                "schema": self.handoff_schema,
                "manifest_sha256": self.handoff_manifest_sha256,
            },
            "source": {
                "artifact_path": self.source_artifact_path,
                "size": self.source_size,
                "sha256": self.source_sha256,
            },
            "payload": {
                "identifier": self.payload_identifier,
                "size": self.payload_size,
                "sha256": self.payload_sha256,
                "transformation": "builder-data-plus-c9-checksum",
            },
            "c9": {
                "frame_count": len(self.c9_frames),
                "sequence_start": 0,
                "sequence_end": len(self.c9_frames) - 1,
                "normal_region_size": STATIC_NORMAL_REGION_SIZE,
                "final_region_size": STATIC_FINAL_REGION_SIZE,
                "normal_frame_size": STATIC_NORMAL_FRAME_SIZE,
                "final_frame_size": STATIC_FINAL_FRAME_SIZE,
                "checksum_algorithm": "sum8(sequence_le16+data)",
                "frames_file": PLAN_FRAMES_NAME,
                "frames_size": len(frame_stream),
                "frames_sha256": _sha256(frame_stream),
            },
            "c8": {"status": "not_implemented", "frame_hex": None},
            "ca": {"status": "not_implemented", "frame_hex": None},
            "verification": verification_to_dict(self.verification),
        }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(info.st_mode) or bool(attributes & reparse_flag)


def _inside(child: Path, root: Path) -> bool:
    try:
        return os.path.commonpath((os.path.normcase(str(child)), os.path.normcase(str(root)))) == os.path.normcase(str(root))
    except ValueError:
        return False


def _read_payload(payload_path: Path, bundle_root: Path) -> bytes:
    try:
        root = bundle_root.resolve(strict=True)
    except OSError as exc:
        raise StaticTransferPlanError(f"无法解析 bundle_root: {exc}") from exc
    if not root.is_dir() or _is_link_or_reparse(root):
        raise StaticTransferPlanError("bundle_root 必须是非链接目录")
    candidate = payload_path if payload_path.is_absolute() else root / payload_path
    resolved = candidate.resolve(strict=False)
    if not _inside(resolved, root):
        raise StaticTransferPlanError("payload 必须位于 bundle_root 内")
    if resolved == root:
        raise StaticTransferPlanError("payload 必须是普通文件")
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise StaticTransferPlanError("payload 必须位于 bundle_root 内") from exc
    current = root
    for part in relative.parts:
        current = current / part
        try:
            info = current.lstat()
        except OSError as exc:
            raise StaticTransferPlanError(f"无法访问 payload: {exc}") from exc
        if _is_link_or_reparse(current):
            raise StaticTransferPlanError("payload 路径不得包含符号链接或 reparse point")
    if not stat.S_ISREG(info.st_mode):
        raise StaticTransferPlanError("payload 必须是普通文件")
    before = (info.st_size, info.st_mtime_ns, info.st_dev, info.st_ino)
    try:
        data = resolved.read_bytes()
        after_info = resolved.stat()
    except OSError as exc:
        raise StaticTransferPlanError(f"无法读取 payload: {exc}") from exc
    after = (after_info.st_size, after_info.st_mtime_ns, after_info.st_dev, after_info.st_ino)
    if before != after:
        raise StaticTransferPlanError("payload 在读取期间发生变化")
    return data


def _build_static_frames(payload: bytes) -> tuple[StaticC9Frame, ...]:
    regions = tuple(
        payload[offset:offset + STATIC_NORMAL_REGION_SIZE]
        for offset in range(0, len(payload), STATIC_NORMAL_REGION_SIZE)
    )
    if len(regions) != STATIC_FRAME_COUNT:
        raise StaticTransferPlanError(
            f"静态 payload region 数量错误: {len(regions)} != {STATIC_FRAME_COUNT}"
        )
    frames: list[StaticC9Frame] = []
    for sequence, region in enumerate(regions):
        expected_size = (
            STATIC_FINAL_REGION_SIZE
            if sequence == STATIC_FRAME_COUNT - 1
            else STATIC_NORMAL_REGION_SIZE
        )
        if len(region) != expected_size:
            raise StaticTransferPlanError(
                f"C9 sequence {sequence} region 大小错误: {len(region)} != {expected_size}"
            )
        data, checksum = region[:-1], region[-1]
        frame = build_c9(sequence, data)
        if frame[-1] != checksum:
            raise StaticTransferPlanError(f"C9 sequence {sequence} checksum 无效")
        frames.append(StaticC9Frame(sequence, data, checksum, region, frame))
    return tuple(frames)


def build_static_transfer_plan(
    manifest_path: Path,
    *,
    payload_path: Path,
    expected_payload_sha256: str,
    bundle_root: Path | None = None,
    target_firmware: str = STATIC_FIRMWARE,
) -> StaticTransferPlan:
    """验证 Handoff 与显式 payload，并构建不执行 BLE 的静态 C9 计划。"""
    if not re.fullmatch(r"[A-Fa-f0-9]{64}", expected_payload_sha256):
        raise StaticTransferPlanError("expected payload SHA-256 必须是 64 位十六进制")
    handoff = validate_handoff(
        Path(manifest_path),
        bundle_root=Path(bundle_root) if bundle_root is not None else None,
        target_firmware=target_firmware,
    )
    if not handoff.safe_to_prepare_transfer:
        codes = ", ".join(issue.error_code for issue in handoff.errors) or "not_safe"
        raise StaticTransferPlanError(f"Handoff 未通过传输准备验证: {codes}")
    if handoff.artifact_path is None or handoff.actual_artifact_size is None:
        raise StaticTransferPlanError("Handoff 未解析出 source artifact")
    root = Path(bundle_root) if bundle_root is not None else Path(manifest_path).parent
    payload = _read_payload(Path(payload_path), root)
    if len(payload) != STATIC_PAYLOAD_SIZE:
        raise StaticTransferPlanError(
            f"静态 payload 大小错误: {len(payload)} != {STATIC_PAYLOAD_SIZE}"
        )
    payload_sha256 = _sha256(payload)
    if payload_sha256.lower() != expected_payload_sha256.lower():
        raise StaticTransferPlanError(
            f"静态 payload SHA-256 不匹配: {payload_sha256} != {expected_payload_sha256.lower()}"
        )
    frames = _build_static_frames(payload)
    verification = verify_static_transfer_frames(
        [item.frame for item in frames], payload_sha256
    )
    if not verification.exact_match:
        raise StaticTransferPlanError("静态 C9 计划复核失败: " + "; ".join(verification.errors))
    return StaticTransferPlan(
        handoff_schema=handoff.schema_version or "unknown",
        handoff_manifest_sha256=(handoff.manifest_sha256 or "").lower(),
        firmware=target_firmware,
        source_artifact_path=handoff.artifact_relative_path or "unknown",
        source_size=handoff.actual_artifact_size,
        source_sha256=(handoff.actual_artifact_sha256 or "").lower(),
        payload_identifier=f"sha256:{payload_sha256}",
        payload_size=len(payload),
        payload_sha256=payload_sha256,
        c9_frames=frames,
        verification=verification,
    )


def verify_static_transfer_frames(
    frames: Sequence[bytes],
    expected_payload_sha256: str,
) -> StaticTransferVerification:
    """原序校验 C9 帧并重组 Builder 的 DATA+checksum region 流。"""
    errors: list[str] = []
    sequences: list[int] = []
    packets: list[tuple[int, bytes, int, int, bool]] = []
    for index, frame in enumerate(frames):
        try:
            packet = parse_c9(frame)
        except FrameError as exc:
            errors.append(f"frame {index} 无效: {exc}")
            continue
        sequences.append(packet.sequence)
        packets.append(
            (packet.sequence, packet.data + frame[-1:], len(frame), len(packet.data) + 1, packet.checksum_valid)
        )

    counts = Counter(sequences)
    missing = tuple(sequence for sequence in range(STATIC_FRAME_COUNT) if counts[sequence] == 0)
    duplicates = tuple(sorted(sequence for sequence, count in counts.items() if count > 1))
    out_of_range = tuple(sorted(sequence for sequence in counts if not 0 <= sequence < STATIC_FRAME_COUNT))
    out_of_order = sequences != list(range(STATIC_FRAME_COUNT))
    checksum_failures = tuple(sequence for sequence, _region, _frame_size, _region_size, valid in packets if not valid)

    if len(frames) != STATIC_FRAME_COUNT:
        errors.append(f"C9 frame 数量错误: {len(frames)} != {STATIC_FRAME_COUNT}")
    if missing:
        errors.append(f"缺少 sequence: {list(missing)}")
    if duplicates:
        errors.append(f"重复 sequence: {list(duplicates)}")
    if out_of_range:
        errors.append(f"sequence 越界: {list(out_of_range)}")
    if out_of_order:
        errors.append("C9 sequence 输入顺序不是 0..1528")
    if checksum_failures:
        errors.append(f"checksum 失败: {list(checksum_failures)}")

    by_sequence: dict[int, tuple[bytes, int, int]] = {}
    for sequence, region, frame_size, region_size, _valid in packets:
        by_sequence.setdefault(sequence, (region, frame_size, region_size))
        if 0 <= sequence < STATIC_FRAME_COUNT:
            expected_region = STATIC_FINAL_REGION_SIZE if sequence == STATIC_FRAME_COUNT - 1 else STATIC_NORMAL_REGION_SIZE
            expected_frame = STATIC_FINAL_FRAME_SIZE if sequence == STATIC_FRAME_COUNT - 1 else STATIC_NORMAL_FRAME_SIZE
            if region_size != expected_region:
                errors.append(
                    f"C9 sequence {sequence} region 大小错误: {region_size} != {expected_region}"
                )
            if frame_size != expected_frame:
                errors.append(
                    f"C9 sequence {sequence} frame 大小错误: {frame_size} != {expected_frame}"
                )

    reconstructed = b"".join(region for _sequence, region, _frame_size, _region_size, _valid in packets)
    reconstructed_sha256 = _sha256(reconstructed)
    if len(reconstructed) != STATIC_PAYLOAD_SIZE:
        errors.append(
            f"重组 payload 大小错误: {len(reconstructed)} != {STATIC_PAYLOAD_SIZE}"
        )
    if reconstructed_sha256.lower() != expected_payload_sha256.lower():
        errors.append("重组 payload SHA-256 不匹配")

    normal = by_sequence.get(0)
    final = by_sequence.get(STATIC_FRAME_COUNT - 1)
    exact = not errors
    return StaticTransferVerification(
        result="PASS" if exact else "FAIL",
        payload_size=STATIC_PAYLOAD_SIZE,
        payload_sha256=expected_payload_sha256.lower(),
        c9_frame_count=len(frames),
        sequence_start=min(sequences) if sequences else None,
        sequence_end=max(sequences) if sequences else None,
        missing_sequences=missing,
        duplicate_sequences=duplicates,
        out_of_order=out_of_order,
        out_of_range_sequences=out_of_range,
        checksum_failures=checksum_failures,
        normal_region_size=normal[2] if normal else None,
        final_region_size=final[2] if final else None,
        normal_frame_size=normal[1] if normal else None,
        final_frame_size=final[1] if final else None,
        reconstructed_size=len(reconstructed),
        reconstructed_sha256=reconstructed_sha256,
        exact_match=exact,
        errors=tuple(errors),
        external_usage=HandoffExternalUsage(c9_frames_generated=len(frames)),
    )


def verification_to_dict(result: StaticTransferVerification) -> dict[str, Any]:
    """将复核结果转换为字段顺序稳定的 JSON 结构。"""
    sequence_range = (
        f"{result.sequence_start}..{result.sequence_end}"
        if result.sequence_start is not None and result.sequence_end is not None
        else None
    )
    return {
        "result": result.result,
        "payload_size": result.payload_size,
        "payload_sha256": result.payload_sha256,
        "c9_frame_count": result.c9_frame_count,
        "sequence_range": sequence_range,
        "missing": len(result.missing_sequences),
        "duplicates": len(result.duplicate_sequences),
        "out_of_order": result.out_of_order,
        "out_of_range_sequences": list(result.out_of_range_sequences),
        "checksum_failures": len(result.checksum_failures),
        "normal_region_size": result.normal_region_size,
        "final_region_size": result.final_region_size,
        "normal_frame_size": result.normal_frame_size,
        "final_frame_size": result.final_frame_size,
        "reconstructed_size": result.reconstructed_size,
        "reconstructed_sha256": result.reconstructed_sha256,
        "exact_match": result.exact_match,
        "errors": list(result.errors),
        "external_usage": asdict(result.external_usage),
    }


def write_static_transfer_plan(plan: StaticTransferPlan, output_dir: Path) -> None:
    """独占创建确定性计划目录，不覆盖任何已有路径。"""
    output = Path(output_dir)
    created = False
    try:
        output.mkdir()
        created = True
        frame_stream = b"".join(item.frame for item in plan.c9_frames)
        with (output / PLAN_FRAMES_NAME).open("xb") as stream:
            stream.write(frame_stream)
        text = json.dumps(plan.to_manifest_dict(), ensure_ascii=False, indent=2) + "\n"
        with (output / PLAN_MANIFEST_NAME).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    except FileExistsError as exc:
        if created:
            _remove_created_plan(output)
        raise StaticTransferPlanError(f"输出计划路径已存在: {output}") from exc
    except OSError as exc:
        if created:
            _remove_created_plan(output)
        raise StaticTransferPlanError(f"无法写入静态计划: {exc}") from exc


def _remove_created_plan(output: Path) -> None:
    for name in (PLAN_MANIFEST_NAME, PLAN_FRAMES_NAME):
        path = output / name
        if path.exists():
            path.unlink()
    if output.exists():
        output.rmdir()


def _load_plan(plan_dir: Path) -> tuple[dict[str, Any], bytes]:
    directory = Path(plan_dir)
    if _is_link_or_reparse(directory) or not directory.is_dir():
        raise StaticTransferPlanError("计划路径必须是非链接目录")
    manifest_path = directory / PLAN_MANIFEST_NAME
    frames_path = directory / PLAN_FRAMES_NAME
    if _is_link_or_reparse(manifest_path) or _is_link_or_reparse(frames_path):
        raise StaticTransferPlanError("计划文件不得为符号链接或 reparse point")
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
        frame_stream = frames_path.read_bytes()
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StaticTransferPlanError(f"无法读取静态计划: {exc}") from exc
    if not isinstance(document, dict) or document.get("format") != STATIC_PLAN_FORMAT:
        raise StaticTransferPlanError("静态计划 format 无效")
    c9 = document.get("c9")
    payload = document.get("payload")
    if not isinstance(c9, dict) or not isinstance(payload, dict):
        raise StaticTransferPlanError("静态计划缺少 c9 或 payload 元数据")
    if c9.get("frames_file") != PLAN_FRAMES_NAME:
        raise StaticTransferPlanError("静态计划 frames_file 无效")
    return document, frame_stream


def _split_frame_stream(stream: bytes) -> tuple[list[bytes], list[str]]:
    frames: list[bytes] = []
    errors: list[str] = []
    offset = 0
    while offset < len(stream):
        if len(stream) - offset < 4:
            errors.append(f"frame stream 尾部不完整: offset {offset}")
            break
        frame_size = stream[offset + 3] + 5
        end = offset + frame_size
        if end > len(stream):
            errors.append(f"frame stream 帧越界: offset {offset}")
            break
        frames.append(stream[offset:end])
        offset = end
    return frames, errors


def inspect_static_plan(plan_dir: Path) -> dict[str, Any]:
    """只读返回计划 manifest。"""
    document, _stream = _load_plan(plan_dir)
    return document


def verify_static_plan(plan_dir: Path) -> StaticTransferVerification:
    """只读验证保存的计划、帧流及重组 payload 身份。"""
    document, frame_stream = _load_plan(plan_dir)
    c9 = document["c9"]
    payload = document["payload"]
    expected_sha = payload.get("sha256")
    if not isinstance(expected_sha, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_sha):
        raise StaticTransferPlanError("计划 payload SHA-256 无效")
    frames, stream_errors = _split_frame_stream(frame_stream)
    result = verify_static_transfer_frames(frames, expected_sha)
    metadata_errors = list(stream_errors)
    handoff = document.get("handoff")
    source = document.get("source")
    c8 = document.get("c8")
    ca = document.get("ca")
    if document.get("firmware") != STATIC_FIRMWARE:
        metadata_errors.append("firmware 不匹配")
    if not isinstance(handoff, dict) or handoff.get("schema") != "ultra3-handoff/v1":
        metadata_errors.append("handoff.schema 不匹配")
    elif not re.fullmatch(r"[a-f0-9]{64}", str(handoff.get("manifest_sha256", ""))):
        metadata_errors.append("handoff.manifest_sha256 无效")
    if not isinstance(source, dict):
        metadata_errors.append("source 元数据无效")
    else:
        if source.get("size") != 351617:
            metadata_errors.append("source.size 不匹配")
        if not re.fullmatch(r"[a-f0-9]{64}", str(source.get("sha256", ""))):
            metadata_errors.append("source.sha256 无效")
        if not isinstance(source.get("artifact_path"), str):
            metadata_errors.append("source.artifact_path 无效")
    if payload.get("identifier") != f"sha256:{expected_sha}":
        metadata_errors.append("payload.identifier 不匹配")
    if payload.get("transformation") != "builder-data-plus-c9-checksum":
        metadata_errors.append("payload.transformation 不匹配")
    if c8 != {"status": "not_implemented", "frame_hex": None}:
        metadata_errors.append("c8 状态必须为 not_implemented")
    if ca != {"status": "not_implemented", "frame_hex": None}:
        metadata_errors.append("ca 状态必须为 not_implemented")
    expected_metadata = {
        "frame_count": STATIC_FRAME_COUNT,
        "sequence_start": 0,
        "sequence_end": STATIC_FRAME_COUNT - 1,
        "normal_region_size": STATIC_NORMAL_REGION_SIZE,
        "final_region_size": STATIC_FINAL_REGION_SIZE,
        "normal_frame_size": STATIC_NORMAL_FRAME_SIZE,
        "final_frame_size": STATIC_FINAL_FRAME_SIZE,
        "checksum_algorithm": "sum8(sequence_le16+data)",
        "frames_file": PLAN_FRAMES_NAME,
        "frames_size": len(frame_stream),
        "frames_sha256": _sha256(frame_stream),
    }
    for key, actual in expected_metadata.items():
        if c9.get(key) != actual:
            metadata_errors.append(f"c9.{key} 不匹配")
    if payload.get("size") != STATIC_PAYLOAD_SIZE:
        metadata_errors.append("payload.size 不匹配")
    if metadata_errors:
        return replace(
            result,
            result="FAIL",
            exact_match=False,
            errors=result.errors + tuple(metadata_errors),
        )
    return result
