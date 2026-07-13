from __future__ import annotations

from .errors import KnownPatchVerificationError
from .models import DiffResult

KNOWN_SIZE = 891180
KNOWN_BEFORE_SHA256 = "C16BAAD36C20FA3473753B12907DF155510C95C4187FE9369C11AF4EFF6F3F8C"
KNOWN_AFTER_SHA256 = "7B25A833D431ED29622EDF4C102F4B555F1E251D1CEC842D848E8E7DCE2C015D"
KNOWN_OFFSET = 0x16F
KNOWN_BEFORE_VALUE = 0x0D
KNOWN_AFTER_VALUE = 0x04


def known_patch_failures(result: DiffResult) -> tuple[str, ...]:
    failures: list[str] = []
    if result.before_info.size != KNOWN_SIZE or result.after_info.size != KNOWN_SIZE:
        failures.append(f"两个文件大小必须均为 {KNOWN_SIZE}")
    if result.before_info.sha256 != KNOWN_BEFORE_SHA256:
        failures.append("before SHA-256 不匹配")
    if result.after_info.sha256 != KNOWN_AFTER_SHA256:
        failures.append("after SHA-256 不匹配")
    if not result.before_info.header_valid or not result.after_info.header_valid:
        failures.append("存在无效 BCSDIAL 文件头")
    if not result.before_info.footer_valid or not result.after_info.footer_valid:
        failures.append("存在无效 BCBC 文件尾")
    if result.changed_byte_count != 1:
        failures.append(f"差异字节必须为 1，实际为 {result.changed_byte_count}")
    if len(result.ranges) != 1:
        failures.append(f"差异区间必须为 1，实际为 {len(result.ranges)}")
    if len(result.ranges) == 1:
        item = result.ranges[0]
        if item.start != KNOWN_OFFSET or item.end != KNOWN_OFFSET:
            failures.append(
                f"差异偏移必须为 0x{KNOWN_OFFSET:08X}，实际为 0x{item.start:08X}"
            )
        if item.before_bytes != bytes([KNOWN_BEFORE_VALUE]):
            failures.append("before 值必须为 0D")
        if item.after_bytes != bytes([KNOWN_AFTER_VALUE]):
            failures.append("after 值必须为 04")
    if result.unchanged_byte_count != KNOWN_SIZE - 1:
        failures.append("未变化字节数不匹配")
    return tuple(failures)


def verify_known_patch(result: DiffResult) -> None:
    failures = known_patch_failures(result)
    if failures:
        raise KnownPatchVerificationError("；".join(failures))
