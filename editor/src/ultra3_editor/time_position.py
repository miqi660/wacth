from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .errors import (
    EditOutputExistsError,
    EditVerificationError,
    FileReadError,
    InputOutputSamePathError,
    NoChangeRequestedError,
    TimePositionEditError,
    UnexpectedChangedBytesError,
)
from .static_diy import (
    STATIC_DIY_SIZE,
    TIME_POSITION_OFFSET,
    TimePosition,
    inspect_static_diy,
)

TOP_GOLDEN_SHA256 = "9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635"
BOTTOM_GOLDEN_SHA256 = "3B8302F6746AB2B78FA48599328DB7907788FA322D18ADF297280C8A5D3370C0"
EDIT_SCOPE = "GreenLion Static DIY / NJ-LEJ-2.1.7 / 351617-byte reconstructed BIN"


@dataclass(frozen=True)
class TimePositionEditResult:
    status: str
    feature: str
    container: str
    scope: str
    input_path: Path
    input_size: int
    input_sha256_before: str
    input_sha256_after: str
    input_unchanged: bool
    detected_input_position: TimePosition
    requested_position: TimePosition
    output_position: TimePosition
    output_path: Path
    output_size: int
    output_sha256: str
    field_offset: int
    field_offset_hex: str
    field_width: int
    before_hex: str
    after_hex: str
    changed_byte_count: int
    changed_offsets: tuple[int, ...]
    unchanged_byte_count: int
    output_revalidated: bool
    validation_passed: bool
    exact_golden_match: bool | str
    golden_target_sha256: str | None
    real_ble_usage: int
    errors: tuple[str, ...]


def set_time_position(
    input_path: str | Path,
    output_path: str | Path,
    position: TimePosition,
    json_path: str | Path | None = None,
    report_path: str | Path | None = None,
) -> TimePositionEditResult:
    if not isinstance(position, TimePosition):
        raise TimePositionEditError("position 必须是 TimePosition.TOP 或 TimePosition.BOTTOM")

    source_info = inspect_static_diy(input_path)
    source = source_info.path
    output = Path(output_path).resolve()
    json_output = Path(json_path).resolve() if json_path is not None else None
    report_output = Path(report_path).resolve() if report_path is not None else None
    targets = [path for path in (output, json_output, report_output) if path is not None]
    _validate_output_targets(source, targets)

    if source_info.time_position is position:
        raise NoChangeRequestedError(
            f"输入文件当前已是 {position.value}，无需修改"
        )

    try:
        source_data = source.read_bytes()
    except OSError as exc:
        raise FileReadError(f"无法再次读取输入文件: {source}") from exc
    source_data_sha256 = _sha256(source_data)
    if source_data_sha256 != source_info.sha256:
        raise EditVerificationError("输入文件在验证后发生变化，拒绝生成输出")

    output_data = bytearray(source_data)
    output_data[TIME_POSITION_OFFSET] = position.byte_value
    changed_offsets = tuple(
        index
        for index, (before, after) in enumerate(zip(source_data, output_data))
        if before != after
    )
    if changed_offsets != (TIME_POSITION_OFFSET,):
        raise UnexpectedChangedBytesError(
            f"预期仅改变 offset 0x{TIME_POSITION_OFFSET:08X}，实际为 {changed_offsets}"
        )
    if output_data[1:] != source_data[1:]:
        raise UnexpectedChangedBytesError("offset 1..EOF 未保持逐字节一致")

    output_bytes = bytes(output_data)
    calculated_output_sha256 = _sha256(output_bytes)
    golden_target_sha256 = _golden_target(source_info.sha256, position)
    exact_golden_match: bool | str = (
        calculated_output_sha256 == golden_target_sha256
        if golden_target_sha256 is not None
        else "not_applicable"
    )

    created: list[Path] = []
    try:
        _prepare_parents(targets)
        _write_binary_exclusive(output, output_bytes)
        created.append(output)

        output_info = inspect_static_diy(output)
        if output_info.time_position is not position:
            raise EditVerificationError("输出位置复验失败")
        if output_info.size != STATIC_DIY_SIZE:
            raise EditVerificationError("输出大小复验失败")
        if output_info.sha256 != calculated_output_sha256:
            raise EditVerificationError("输出 SHA-256 复验失败")
        try:
            written_data = output.read_bytes()
        except OSError as exc:
            raise EditVerificationError("无法回读输出文件") from exc
        written_changed_offsets = tuple(
            index
            for index, (before, after) in enumerate(zip(source_data, written_data))
            if before != after
        )
        if written_changed_offsets != (TIME_POSITION_OFFSET,) or written_data[1:] != source_data[1:]:
            raise UnexpectedChangedBytesError("写入后的输出不再是严格单字节变更")

        input_after = inspect_static_diy(source)
        if input_after.sha256 != source_info.sha256:
            raise EditVerificationError("输入文件在输出生成过程中发生变化")

        result = TimePositionEditResult(
            status="COMPLETE",
            feature="set-time-position",
            container="greenlion-static",
            scope=EDIT_SCOPE,
            input_path=source,
            input_size=source_info.size,
            input_sha256_before=source_info.sha256,
            input_sha256_after=input_after.sha256,
            input_unchanged=True,
            detected_input_position=source_info.time_position,
            requested_position=position,
            output_position=output_info.time_position,
            output_path=output,
            output_size=output_info.size,
            output_sha256=output_info.sha256,
            field_offset=TIME_POSITION_OFFSET,
            field_offset_hex=f"0x{TIME_POSITION_OFFSET:08X}",
            field_width=1,
            before_hex=f"{source_info.first_byte:02X}",
            after_hex=f"{output_info.first_byte:02X}",
            changed_byte_count=1,
            changed_offsets=changed_offsets,
            unchanged_byte_count=STATIC_DIY_SIZE - 1,
            output_revalidated=True,
            validation_passed=True,
            exact_golden_match=exact_golden_match,
            golden_target_sha256=golden_target_sha256,
            real_ble_usage=0,
            errors=(),
        )

        if json_output is not None:
            _write_text_exclusive(
                json_output,
                json.dumps(time_position_edit_dict(result), ensure_ascii=False, indent=2) + "\n",
            )
            created.append(json_output)
        if report_output is not None:
            _write_text_exclusive(report_output, render_time_position_markdown(result))
            created.append(report_output)
        return result
    except Exception:
        for path in reversed(created):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        raise


def time_position_edit_dict(result: TimePositionEditResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["input_path"] = str(result.input_path)
    payload["output_path"] = str(result.output_path)
    payload["detected_input_position"] = result.detected_input_position.value
    payload["requested_position"] = result.requested_position.value
    payload["output_position"] = result.output_position.value
    payload["changed_offsets"] = list(result.changed_offsets)
    payload["errors"] = list(result.errors)
    payload["external_usage"] = {"ble": 0, "adb": 0, "frida": 0, "uploader": 0}
    return payload


def render_time_position_markdown(result: TimePositionEditResult) -> str:
    exact = _exact_match_text(result.exact_golden_match)
    golden = result.golden_target_sha256 or "NOT_APPLICABLE"
    return "\n".join(
        (
            "# Stage 7B-1 时间位置编辑记录",
            "",
            f"- status: `{result.status}`",
            f"- feature: `{result.feature}`",
            f"- container: `{result.container}`",
            f"- scope: `{result.scope}`",
            f"- input: `{result.input_path}`",
            f"- input size: `{result.input_size}`",
            f"- input SHA-256 before: `{result.input_sha256_before}`",
            f"- input SHA-256 after: `{result.input_sha256_after}`",
            f"- input unchanged: `{str(result.input_unchanged).lower()}`",
            f"- detected input position: `{result.detected_input_position.value}`",
            f"- requested position: `{result.requested_position.value}`",
            f"- output position: `{result.output_position.value}`",
            f"- output: `{result.output_path}`",
            f"- output size: `{result.output_size}`",
            f"- output SHA-256: `{result.output_sha256}`",
            f"- field: offset `{result.field_offset_hex}`, width `{result.field_width}`",
            f"- before/after: `{result.before_hex}` -> `{result.after_hex}`",
            f"- changed byte count: `{result.changed_byte_count}`",
            f"- changed offsets: `{list(result.changed_offsets)}`",
            f"- unchanged byte count: `{result.unchanged_byte_count}`",
            f"- output revalidated: `{str(result.output_revalidated).lower()}`",
            f"- validation passed: `{str(result.validation_passed).lower()}`",
            f"- exact golden match: `{exact}`",
            f"- golden target SHA-256: `{golden}`",
            "",
            "## 安全边界",
            "",
            "- BLE: `0`",
            "- adb: `0`",
            "- Frida: `0`",
            "- uploader: `0`",
            "- 上传：未执行",
            "- GUI 编辑：未接入",
            "- Builder：未实现、未调用",
            "- 其他组件：未实现",
            "- 输入文件：只读且 SHA-256 复核一致",
            "",
        )
    )


def _validate_output_targets(source: Path, targets: list[Path]) -> None:
    source_key = _path_key(source)
    target_keys = [_path_key(path) for path in targets]
    if source_key in target_keys:
        raise InputOutputSamePathError("输入文件不能同时作为输出目标")
    if len(set(target_keys)) != len(target_keys):
        raise TimePositionEditError("输出 BIN、JSON 和 Markdown 路径不能重复")
    for path in targets:
        if path.exists():
            raise EditOutputExistsError(f"输出目标已存在，拒绝覆盖: {path}")


def _prepare_parents(targets: list[Path]) -> None:
    try:
        for path in targets:
            path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise TimePositionEditError("无法创建输出目录") from exc


def _write_binary_exclusive(path: Path, data: bytes) -> None:
    created = False
    try:
        with path.open("xb") as handle:
            created = True
            handle.write(data)
    except FileExistsError as exc:
        raise EditOutputExistsError(f"输出目标已存在，拒绝覆盖: {path}") from exc
    except OSError as exc:
        if created:
            path.unlink(missing_ok=True)
        raise TimePositionEditError(f"无法写入输出文件: {path}") from exc


def _write_text_exclusive(path: Path, text: str) -> None:
    created = False
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            created = True
            handle.write(text)
    except FileExistsError as exc:
        raise EditOutputExistsError(f"输出目标已存在，拒绝覆盖: {path}") from exc
    except OSError as exc:
        if created:
            path.unlink(missing_ok=True)
        raise TimePositionEditError(f"无法写入报告: {path}") from exc


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _golden_target(input_sha256: str, position: TimePosition) -> str | None:
    if input_sha256 == TOP_GOLDEN_SHA256 and position is TimePosition.BOTTOM:
        return BOTTOM_GOLDEN_SHA256
    if input_sha256 == BOTTOM_GOLDEN_SHA256 and position is TimePosition.TOP:
        return TOP_GOLDEN_SHA256
    return None


def _path_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def _exact_match_text(value: bool | str) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return value.replace("_", "-")
