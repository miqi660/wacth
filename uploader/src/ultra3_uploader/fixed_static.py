from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from .bc_frames import build_c9, parse_c9
from .checksum import c8_checksum
from .errors import (
    FixedStaticControlFrameError,
    FixedStaticOutputError,
    FixedStaticProfileError,
    FixedStaticVerificationError,
    FrameError,
)
from .handoff_models import HandoffExternalUsage


FIXED_STATIC_PLAN_FORMAT = "ultra3-fixed-static-transfer-plan/v1"
FIXED_STATIC_PROFILE_NAME = "njlej-2.1.7-fixed-static"
FIXED_PLAN_FILES = (
    "manifest.json",
    "c8.bin",
    "c9_frames.bin",
    "ca.bin",
    "full_transfer_stream.bin",
)


@dataclass(frozen=True)
class FixedStaticProfile:
    name: str
    firmware: str
    static_container_size: int
    c9_data_size: int
    c9_count: int
    first_sequence: int
    last_sequence: int
    c8_hex: str
    ca_hex: str
    expected_total_write_count: int
    expected_region_stream_size: int
    expected_c9_frame_stream_size: int
    expected_full_transfer_stream_size: int


NJLEJ_217_FIXED_STATIC = FixedStaticProfile(
    name=FIXED_STATIC_PROFILE_NAME,
    firmware="NJ-LEJ-2.1.7",
    static_container_size=351617,
    c9_data_size=230,
    c9_count=1529,
    first_sequence=0,
    last_sequence=1528,
    c8_hex="BCC8020701815D0500F905E2",
    ca_hex="BCCA02010505",
    expected_total_write_count=1531,
    expected_region_stream_size=353146,
    expected_c9_frame_stream_size=362320,
    expected_full_transfer_stream_size=362338,
)


@dataclass(frozen=True)
class FixedStaticC8:
    frame: bytes
    command: str
    direction: int
    declared_length: int
    profile_mode: int
    static_container_size: int
    c9_count: int
    checksum: int


@dataclass(frozen=True)
class FixedStaticCA:
    frame: bytes
    command: str
    direction: int


@dataclass(frozen=True)
class FixedStaticTransferVerification:
    result: str
    profile: str
    c8_exact: bool
    c8_checksum_valid: bool
    ca_exact: bool
    c9_frame_count: int
    sequence_start: int | None
    sequence_end: int | None
    missing_sequences: tuple[int, ...]
    duplicate_sequences: tuple[int, ...]
    out_of_order: bool
    checksum_failures: tuple[int, ...]
    reconstructed_size: int
    reconstructed_sha256: str
    static_container_exact: bool
    region_stream_size: int
    c9_frame_stream_size: int
    full_transfer_stream_size: int
    total_write_count: int
    order_valid: bool
    errors: tuple[str, ...]
    external_usage: HandoffExternalUsage


@dataclass(frozen=True)
class FixedStaticTransferPlan:
    profile: FixedStaticProfile
    static_container: bytes
    static_container_sha256: str
    c8_frame: bytes
    c9_frames: tuple[bytes, ...]
    ca_frame: bytes
    verification: FixedStaticTransferVerification

    @property
    def firmware(self) -> str:
        return self.profile.firmware

    @property
    def static_container_size(self) -> int:
        return len(self.static_container)

    @property
    def region_stream_size(self) -> int:
        return len(self.region_stream)

    @property
    def c9_count(self) -> int:
        return len(self.c9_frames)

    @property
    def sequence_range(self) -> tuple[int, int]:
        return (self.profile.first_sequence, self.profile.last_sequence)

    @property
    def total_write_count(self) -> int:
        return len(self.frames)

    @property
    def c9_frame_stream_size(self) -> int:
        return len(self.c9_frame_stream)

    @property
    def full_transfer_stream_size(self) -> int:
        return len(self.full_transfer_stream)

    @property
    def region_stream(self) -> bytes:
        return b"".join(frame[6:] for frame in self.c9_frames)

    @property
    def c9_frame_stream(self) -> bytes:
        return b"".join(self.c9_frames)

    @property
    def full_transfer_stream(self) -> bytes:
        return self.c8_frame + self.c9_frame_stream + self.ca_frame

    @property
    def frames(self) -> tuple[bytes, ...]:
        return (self.c8_frame, *self.c9_frames, self.ca_frame)

    def to_manifest_dict(self) -> dict[str, Any]:
        c9_stream = self.c9_frame_stream
        full_stream = self.full_transfer_stream
        return {
            "schema": FIXED_STATIC_PLAN_FORMAT,
            "profile": self.profile.name,
            "firmware": self.profile.firmware,
            "static_container_size": len(self.static_container),
            "static_container_sha256": self.static_container_sha256,
            "c9_count": len(self.c9_frames),
            "sequence_range": "0..1528",
            "total_write_count": len(self.frames),
            "c8": {
                "length": len(self.c8_frame),
                "hex": self.c8_frame.hex().upper(),
                "evidence": "stage8c3b-two-successful-binder-captures",
            },
            "ca": {
                "length": len(self.ca_frame),
                "hex": self.ca_frame.hex().upper(),
                "evidence": "stage8c3b-two-successful-binder-captures",
                "generation_scope": "fixed-profile-only",
            },
            "region_stream_size": len(self.region_stream),
            "c9_frame_stream_size": len(c9_stream),
            "full_transfer_stream_size": len(full_stream),
            "offline_only": True,
            "ble_supported": False,
            "files": {
                "c8": "c8.bin",
                "c9_frame_stream": "c9_frames.bin",
                "ca": "ca.bin",
                "full_transfer_stream": "full_transfer_stream.bin",
            },
            "c9_frame_stream_sha256": _sha256(c9_stream),
            "full_transfer_stream_sha256": _sha256(full_stream),
            "write_order": "C8 -> C9[0..1528] -> CA",
            "status": "offline_plan_only",
            "verification": fixed_verification_to_dict(self.verification),
        }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _require_profile(profile: FixedStaticProfile) -> None:
    if profile != NJLEJ_217_FIXED_STATIC:
        raise FixedStaticProfileError(
            f"不支持固定静态 Profile: {getattr(profile, 'name', profile)!r}"
        )


def build_njlej_217_static_c8(*, static_container_size: int, c9_count: int) -> bytes:
    """仅为已冻结的 NJ-LEJ-2.1.7 / 351617-byte Profile 构建 C8。"""
    profile = NJLEJ_217_FIXED_STATIC
    if static_container_size != profile.static_container_size:
        raise FixedStaticProfileError(
            f"static_container 大小必须为 {profile.static_container_size}"
        )
    if c9_count != profile.c9_count:
        raise FixedStaticProfileError(f"C9 数量必须为 {profile.c9_count}")
    size_le = static_container_size.to_bytes(4, "little")
    count_le = c9_count.to_bytes(2, "little")
    frame = (
        b"\xBC\xC8\x02\x07\x01"
        + size_le
        + count_le
        + bytes((c8_checksum(1, size_le, count_le),))
    )
    if frame.hex().upper() != profile.c8_hex:
        raise FixedStaticControlFrameError("固定 Profile C8 与冻结证据不一致")
    return frame


def parse_njlej_217_static_c8(frame: bytes) -> FixedStaticC8:
    profile = NJLEJ_217_FIXED_STATIC
    if len(frame) != 12:
        raise FixedStaticControlFrameError("固定 Profile C8 长度必须为 12")
    if frame[:3] != b"\xBC\xC8\x02" or frame[3] != 0x07:
        raise FixedStaticControlFrameError("固定 Profile C8 头或 LEN 无效")
    size = int.from_bytes(frame[5:9], "little")
    count = int.from_bytes(frame[9:11], "little")
    expected_checksum = c8_checksum(frame[4], frame[5:9], frame[9:11])
    if frame[-1] != expected_checksum:
        raise FixedStaticControlFrameError("固定 Profile C8 checksum 无效")
    if frame[4] != 1 or size != profile.static_container_size or count != profile.c9_count:
        raise FixedStaticControlFrameError("固定 Profile C8 声明字段不匹配")
    if frame.hex().upper() != profile.c8_hex:
        raise FixedStaticControlFrameError("固定 Profile C8 与冻结证据不完全一致")
    return FixedStaticC8(
        frame, "C8", frame[2], frame[3], frame[4], size, count, frame[-1]
    )


def build_njlej_217_static_ca() -> bytes:
    return bytes.fromhex(NJLEJ_217_FIXED_STATIC.ca_hex)


def parse_njlej_217_static_ca(frame: bytes) -> FixedStaticCA:
    expected = build_njlej_217_static_ca()
    if frame != expected:
        raise FixedStaticControlFrameError("固定 Profile CA 必须与冻结证据完全一致")
    return FixedStaticCA(frame, "CA", frame[2])


def build_fixed_static_transfer_plan(
    static_container: bytes,
    *,
    profile: FixedStaticProfile = NJLEJ_217_FIXED_STATIC,
) -> FixedStaticTransferPlan:
    """从固定大小 static_container 构建纯离线 C8/C9/CA 计划。"""
    _require_profile(profile)
    if len(static_container) != profile.static_container_size:
        raise FixedStaticProfileError(
            f"static_container 大小错误: {len(static_container)} != {profile.static_container_size}"
        )
    c9_frames = tuple(
        build_c9(sequence, static_container[offset:offset + profile.c9_data_size])
        for sequence, offset in enumerate(
            range(0, len(static_container), profile.c9_data_size)
        )
    )
    plan = FixedStaticTransferPlan(
        profile=profile,
        static_container=bytes(static_container),
        static_container_sha256=_sha256(static_container),
        c8_frame=build_njlej_217_static_c8(
            static_container_size=len(static_container), c9_count=len(c9_frames)
        ),
        c9_frames=c9_frames,
        ca_frame=build_njlej_217_static_ca(),
        verification=_empty_verification(profile),
    )
    verification = verify_fixed_static_transfer_plan(plan)
    if verification.result != "PASS":
        raise FixedStaticVerificationError("; ".join(verification.errors))
    return replace(plan, verification=verification)


def _empty_verification(profile: FixedStaticProfile) -> FixedStaticTransferVerification:
    return FixedStaticTransferVerification(
        "PENDING", profile.name, False, False, False, 0, None, None, (), (),
        False, (), 0, "", False, 0, 0, 0, 0, False, (), HandoffExternalUsage()
    )


def verify_fixed_static_transfer_plan(
    plan: FixedStaticTransferPlan,
) -> FixedStaticTransferVerification:
    """严格复核固定控制帧、C9 原序和四层字节流大小。"""
    errors: list[str] = []
    profile = NJLEJ_217_FIXED_STATIC
    try:
        _require_profile(plan.profile)
    except FixedStaticProfileError as exc:
        errors.append(str(exc))
    c8_exact = plan.c8_frame.hex().upper() == NJLEJ_217_FIXED_STATIC.c8_hex
    c8_checksum_valid = False
    try:
        parse_njlej_217_static_c8(plan.c8_frame)
        c8_checksum_valid = True
    except FixedStaticControlFrameError as exc:
        errors.append(str(exc))
    ca_exact = plan.ca_frame.hex().upper() == NJLEJ_217_FIXED_STATIC.ca_hex
    try:
        parse_njlej_217_static_ca(plan.ca_frame)
    except FixedStaticControlFrameError as exc:
        errors.append(str(exc))

    sequences: list[int] = []
    checksum_failures: list[int] = []
    data_parts: list[bytes] = []
    region_parts: list[bytes] = []
    for index, frame in enumerate(plan.c9_frames):
        try:
            packet = parse_c9(frame)
        except FrameError as exc:
            errors.append(f"C9 frame {index} 无效: {exc}")
            continue
        sequences.append(packet.sequence)
        data_parts.append(packet.data)
        region_parts.append(packet.data + frame[-1:])
        if not packet.checksum_valid:
            checksum_failures.append(packet.sequence)
        expected_data_size = (
            177 if packet.sequence == profile.last_sequence else profile.c9_data_size
        )
        if len(packet.data) != expected_data_size:
            errors.append(
                f"C9 sequence {packet.sequence} DATA 大小错误: {len(packet.data)} != {expected_data_size}"
            )

    counts = Counter(sequences)
    missing = tuple(
        sequence
        for sequence in range(profile.first_sequence, profile.last_sequence + 1)
        if counts[sequence] == 0
    )
    duplicates = tuple(sorted(sequence for sequence, count in counts.items() if count > 1))
    expected_sequences = list(
        range(profile.first_sequence, profile.last_sequence + 1)
    )
    out_of_order = sequences != expected_sequences
    if len(plan.c9_frames) != profile.c9_count:
        errors.append(f"C9 frame 数量错误: {len(plan.c9_frames)} != {profile.c9_count}")
    if missing:
        errors.append(f"缺少 sequence: {list(missing)}")
    if duplicates:
        errors.append(f"重复 sequence: {list(duplicates)}")
    if out_of_order:
        errors.append("C9 sequence 输入顺序不是 0..1528")
    if checksum_failures:
        errors.append(f"C9 checksum 失败: {checksum_failures}")

    reconstructed = b"".join(data_parts)
    region_stream = b"".join(region_parts)
    c9_stream = b"".join(plan.c9_frames)
    full_stream = plan.c8_frame + c9_stream + plan.ca_frame
    static_container_exact = reconstructed == plan.static_container
    checks = (
        (len(reconstructed) == profile.static_container_size, "重组 static_container 大小错误"),
        (static_container_exact, "重组 DATA 与 static_container 不一致"),
        (_sha256(plan.static_container) == plan.static_container_sha256, "static_container SHA-256 元数据错误"),
        (len(region_stream) == profile.expected_region_stream_size, "region_stream 大小错误"),
        (len(c9_stream) == profile.expected_c9_frame_stream_size, "c9_frame_stream 大小错误"),
        (len(full_stream) == profile.expected_full_transfer_stream_size, "full_transfer_stream 大小错误"),
        (len(plan.frames) == profile.expected_total_write_count, "总写入数量错误"),
    )
    errors.extend(message for passed, message in checks if not passed)
    order_valid = c8_exact and ca_exact and not out_of_order and not missing and not duplicates
    if not order_valid:
        errors.append("写入顺序必须为 C8 -> C9[0..1528] -> CA")
    exact = not errors
    return FixedStaticTransferVerification(
        result="PASS" if exact else "FAIL",
        profile=profile.name,
        c8_exact=c8_exact,
        c8_checksum_valid=c8_checksum_valid,
        ca_exact=ca_exact,
        c9_frame_count=len(plan.c9_frames),
        sequence_start=min(sequences) if sequences else None,
        sequence_end=max(sequences) if sequences else None,
        missing_sequences=missing,
        duplicate_sequences=duplicates,
        out_of_order=out_of_order,
        checksum_failures=tuple(checksum_failures),
        reconstructed_size=len(reconstructed),
        reconstructed_sha256=_sha256(reconstructed),
        static_container_exact=static_container_exact,
        region_stream_size=len(region_stream),
        c9_frame_stream_size=len(c9_stream),
        full_transfer_stream_size=len(full_stream),
        total_write_count=len(plan.frames),
        order_valid=order_valid,
        errors=tuple(errors),
        external_usage=HandoffExternalUsage(c9_frames_generated=len(plan.c9_frames)),
    )


def fixed_verification_to_dict(
    result: FixedStaticTransferVerification,
) -> dict[str, Any]:
    document = asdict(result)
    document["sequence_range"] = (
        f"{result.sequence_start}..{result.sequence_end}"
        if result.sequence_start is not None and result.sequence_end is not None
        else None
    )
    del document["sequence_start"]
    del document["sequence_end"]
    return document


def write_fixed_static_transfer_plan(
    plan: FixedStaticTransferPlan, output_dir: Path
) -> None:
    """独占创建固定 Profile 的五个离线计划文件。"""
    if plan.verification.result != "PASS":
        raise FixedStaticVerificationError("拒绝写入未通过复核的固定静态计划")
    output = Path(output_dir)
    created = False
    try:
        output.mkdir()
        created = True
        payloads = {
            "c8.bin": plan.c8_frame,
            "c9_frames.bin": plan.c9_frame_stream,
            "ca.bin": plan.ca_frame,
            "full_transfer_stream.bin": plan.full_transfer_stream,
        }
        for name, data in payloads.items():
            with (output / name).open("xb") as stream:
                stream.write(data)
        text = json.dumps(plan.to_manifest_dict(), ensure_ascii=False, indent=2) + "\n"
        with (output / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    except FileExistsError as exc:
        if created:
            _remove_fixed_output(output)
        raise FixedStaticOutputError(f"输出计划路径已存在: {output}") from exc
    except OSError as exc:
        if created:
            _remove_fixed_output(output)
        raise FixedStaticOutputError(f"无法写入固定静态计划: {exc}") from exc


def _remove_fixed_output(output: Path) -> None:
    for name in FIXED_PLAN_FILES:
        path = output / name
        if path.exists():
            path.unlink()
    if output.exists():
        output.rmdir()
