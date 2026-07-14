from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from enum import Enum
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .handoff_models import HandoffExternalUsage


SCHEMA_RESOURCE = "ultra3_handoff_v1.schema.json"
MANIFEST_MAX_BYTES = 64 * 1024
EXPECTED_SIZE = 351617
EXPECTED_HEADER = bytes.fromhex("02 00 00 FF FF FF 00 00 80 01 40 01 FC 00 D2 00 00")
EXPECTED_LAYOUT = {
    "header": {"start": 0, "end": 17, "length": 17},
    "main": {"start": 17, "end": 245777, "length": 245760},
    "thumbnail": {"start": 245777, "end": 351617, "length": 105840},
}


class HandoffValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True)
class HandoffValidationIssue:
    error_code: str
    message: str
    path: str | None = None
    expected: object | None = None
    actual: object | None = None


@dataclass(frozen=True)
class UploaderHandoffValidationResult:
    status: HandoffValidationStatus
    manifest_path: Path
    manifest_sha256: str | None
    schema_version: str | None
    artifact_type: str | None
    bundle_root: Path
    artifact_relative_path: str | None
    artifact_path: Path | None
    expected_artifact_size: int | None
    actual_artifact_size: int | None
    size_valid: bool
    expected_artifact_sha256: str | None
    actual_artifact_sha256: str | None
    sha_valid: bool
    header_valid: bool
    offset_zero_valid: bool
    layout_valid: bool
    artifact_unchanged: bool
    firmware_scope: tuple[str, ...]
    target_firmware: str | None
    firmware_compatible: bool | None
    transfer_unprepared: bool
    device_evidence_level: str | None
    golden_status: str | None
    warnings: tuple[HandoffValidationIssue, ...]
    errors: tuple[HandoffValidationIssue, ...]
    safe_to_prepare_transfer: bool
    external_usage: HandoffExternalUsage


class _DuplicateKeyError(ValueError):
    pass


def _issue(
    code: str,
    message: str,
    *,
    path: str | None = None,
    expected: object | None = None,
    actual: object | None = None,
) -> HandoffValidationIssue:
    return HandoffValidationIssue(code, message, path, expected, actual)


def _pairs_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateKeyError(key)
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"不允许的 JSON 数值: {value}")


def _read_packaged_schema() -> tuple[dict[str, Any], Draft202012Validator]:
    raw = files("ultra3_uploader.schemas").joinpath(SCHEMA_RESOURCE).read_bytes()
    schema = json.loads(raw.decode("utf-8"))
    for node in _walk_json(schema):
        reference = node.get("$ref") if isinstance(node, dict) else None
        if isinstance(reference, str) and not reference.startswith("#"):
            raise SchemaError(f"不允许远程 Schema 引用: {reference}")
    Draft202012Validator.check_schema(schema)
    return schema, Draft202012Validator(schema)


def _walk_json(value: object):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_json(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(info.st_mode) or bool(attributes & reparse_flag)


def _canonical_path_errors(value: object) -> list[str]:
    if not isinstance(value, str) or not value:
        return ["artifact_path 必须是非空字符串"]
    errors: list[str] = []
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        errors.append("artifact_path 不得为绝对路径")
    if "\\" in value:
        errors.append("artifact_path 必须使用 POSIX 分隔符")
    if ":" in value:
        errors.append("artifact_path 不得包含冒号")
    if "\0" in value:
        errors.append("artifact_path 不得包含 NUL")
    parts = value.split("/")
    if "" in parts:
        errors.append("artifact_path 不得包含空路径段")
    if "." in parts:
        errors.append("artifact_path 不得包含 .")
    if ".." in parts:
        errors.append("artifact_path 不得包含 ..")
    return errors


def _inside(child: Path, root: Path) -> bool:
    child_text = os.path.normcase(str(child))
    root_text = os.path.normcase(str(root))
    try:
        return os.path.commonpath((child_text, root_text)) == root_text
    except ValueError:
        return False


def _identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return (info.st_size, info.st_mtime_ns, info.st_dev, info.st_ino)


def _read_artifact(path: Path) -> tuple[str, bytes, tuple[int, int, int, int], tuple[int, int, int, int]]:
    digest = hashlib.sha256()
    header = bytearray()
    with path.open("rb") as stream:
        before = _identity(os.fstat(stream.fileno()))
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            if len(header) < len(EXPECTED_HEADER):
                header.extend(chunk[: len(EXPECTED_HEADER) - len(header)])
            digest.update(chunk)
        after = _identity(os.fstat(stream.fileno()))
    return digest.hexdigest().upper(), bytes(header), before, after


def _schema_issue(error: Any) -> HandoffValidationIssue:
    path = ".".join(str(part) for part in error.absolute_path) or None
    first = next(iter(error.absolute_path), None)
    if first == "schema":
        code = "unsupported_schema"
    elif first == "artifact_type":
        code = "unsupported_artifact_type"
    elif first == "layout":
        code = "artifact_layout_mismatch"
    elif first == "transfer":
        code = "handoff_already_prepared"
    else:
        code = "schema_validation_failed"
    return _issue(
        code,
        error.message,
        path=path,
        expected=error.validator_value,
        actual=error.instance,
    )


def validate_handoff(
    manifest_path: Path,
    *,
    bundle_root: Path | None = None,
    target_firmware: str | None = None,
) -> UploaderHandoffValidationResult:
    manifest_input = Path(manifest_path)
    bundle_input = Path(bundle_root) if bundle_root is not None else manifest_input.parent
    warnings: list[HandoffValidationIssue] = []
    errors: list[HandoffValidationIssue] = []
    values: dict[str, Any] = {
        "manifest_sha256": None,
        "schema_version": None,
        "artifact_type": None,
        "artifact_relative_path": None,
        "artifact_path": None,
        "expected_artifact_size": None,
        "actual_artifact_size": None,
        "size_valid": False,
        "expected_artifact_sha256": None,
        "actual_artifact_sha256": None,
        "sha_valid": False,
        "header_valid": False,
        "offset_zero_valid": False,
        "layout_valid": False,
        "artifact_unchanged": False,
        "firmware_scope": (),
        "firmware_compatible": None,
        "transfer_unprepared": False,
        "device_evidence_level": None,
        "golden_status": None,
    }

    def finish() -> UploaderHandoffValidationResult:
        status = HandoffValidationStatus.INVALID if errors else HandoffValidationStatus.VALID
        safe = (
            status is HandoffValidationStatus.VALID
            and values["size_valid"]
            and values["sha_valid"]
            and values["header_valid"]
            and values["offset_zero_valid"]
            and values["layout_valid"]
            and values["artifact_unchanged"]
            and values["firmware_compatible"] is True
            and values["transfer_unprepared"]
        )
        return UploaderHandoffValidationResult(
            status=status,
            manifest_path=manifest_input,
            bundle_root=bundle_input,
            target_firmware=target_firmware,
            warnings=tuple(warnings),
            errors=tuple(errors),
            safe_to_prepare_transfer=safe,
            external_usage=HandoffExternalUsage(),
            **values,
        )

    try:
        _schema, validator = _read_packaged_schema()
    except (OSError, UnicodeError, ValueError, SchemaError) as exc:
        errors.append(_issue("schema_invalid", f"Uploader 内置 Schema 无效: {exc}"))
        return finish()

    try:
        manifest_info = manifest_input.lstat()
    except FileNotFoundError:
        errors.append(_issue("manifest_missing", "Manifest 不存在", path=str(manifest_input)))
        return finish()
    except OSError as exc:
        errors.append(_issue("manifest_not_regular", f"无法访问 Manifest: {exc}", path=str(manifest_input)))
        return finish()
    if _is_link_or_reparse(manifest_input):
        errors.append(_issue("manifest_symlink", "Manifest 不得为符号链接或 reparse point", path=str(manifest_input)))
        return finish()
    if not stat.S_ISREG(manifest_info.st_mode):
        errors.append(_issue("manifest_not_regular", "Manifest 必须是普通文件", path=str(manifest_input)))
        return finish()
    if manifest_info.st_size > MANIFEST_MAX_BYTES:
        errors.append(_issue(
            "manifest_too_large",
            "Manifest 超过 64 KiB 上限",
            path=str(manifest_input),
            expected=MANIFEST_MAX_BYTES,
            actual=manifest_info.st_size,
        ))
        return finish()
    try:
        raw_manifest = manifest_input.read_bytes()
    except OSError as exc:
        errors.append(_issue("manifest_not_regular", f"无法读取 Manifest: {exc}", path=str(manifest_input)))
        return finish()
    values["manifest_sha256"] = hashlib.sha256(raw_manifest).hexdigest().upper()
    if raw_manifest.startswith(b"\xef\xbb\xbf"):
        errors.append(_issue("manifest_bom_not_allowed", "Manifest 不得包含 UTF-8 BOM", path=str(manifest_input)))
        return finish()
    try:
        manifest_text = raw_manifest.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        errors.append(_issue("manifest_not_utf8", f"Manifest 不是严格 UTF-8: {exc}", path=str(manifest_input)))
        return finish()
    try:
        document = json.loads(
            manifest_text,
            object_pairs_hook=_pairs_object,
            parse_constant=_reject_constant,
        )
    except _DuplicateKeyError as exc:
        errors.append(_issue("manifest_duplicate_key", "Manifest 包含重复 JSON key", actual=str(exc)))
        return finish()
    except (json.JSONDecodeError, ValueError) as exc:
        errors.append(_issue("manifest_invalid_json", f"Manifest JSON 无效: {exc}"))
        return finish()
    if not isinstance(document, dict):
        errors.append(_issue("manifest_root_not_object", "Manifest 根值必须是 JSON object", actual=type(document).__name__))
        return finish()

    values["schema_version"] = document.get("schema") if isinstance(document.get("schema"), str) else None
    values["artifact_type"] = document.get("artifact_type") if isinstance(document.get("artifact_type"), str) else None
    values["artifact_relative_path"] = document.get("artifact_path") if isinstance(document.get("artifact_path"), str) else None
    values["expected_artifact_size"] = document.get("artifact_size") if isinstance(document.get("artifact_size"), int) else None
    values["expected_artifact_sha256"] = document.get("artifact_sha256") if isinstance(document.get("artifact_sha256"), str) else None
    scope = document.get("firmware_scope")
    if isinstance(scope, list) and all(isinstance(item, str) for item in scope):
        values["firmware_scope"] = tuple(scope)
    evidence = document.get("device_evidence")
    if isinstance(evidence, dict) and isinstance(evidence.get("level"), str):
        values["device_evidence_level"] = evidence["level"]
    validation = document.get("build_validation")
    if isinstance(validation, dict) and isinstance(validation.get("golden_status"), str):
        values["golden_status"] = validation["golden_status"]
    values["layout_valid"] = document.get("layout") == EXPECTED_LAYOUT
    transfer = document.get("transfer")
    values["transfer_unprepared"] = transfer == {
        "status": "not_prepared",
        "payload_size": None,
        "chunk_count": None,
        "ble_frames_present": False,
    }

    path_errors = _canonical_path_errors(values["artifact_relative_path"])
    errors.extend(
        _issue("invalid_artifact_path", message, path=values["artifact_relative_path"])
        for message in path_errors
    )

    schema_errors = sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path))
    if schema_errors:
        errors.extend(_schema_issue(error) for error in schema_errors)
    if schema_errors or path_errors:
        return finish()

    if values["device_evidence_level"] == "C":
        warnings.append(_issue(
            "device_evidence_level_c",
            "设备证据为 Level C；离线验证不代表静态传输或真机上传已验证",
            actual="C",
        ))
    if target_firmware is None:
        warnings.append(_issue(
            "target_firmware_not_provided",
            "未提供目标固件；Bundle 有效，但不能进入传输准备",
            expected=list(values["firmware_scope"]),
        ))
    elif target_firmware in values["firmware_scope"]:
        values["firmware_compatible"] = True
    else:
        values["firmware_compatible"] = False
        errors.append(_issue(
            "firmware_scope_mismatch",
            "目标固件不在 Manifest firmware scope 中",
            expected=list(values["firmware_scope"]),
            actual=target_firmware,
        ))

    try:
        root_info = bundle_input.lstat()
    except FileNotFoundError:
        errors.append(_issue("bundle_root_missing", "bundle_root 不存在", path=str(bundle_input)))
        return finish()
    except OSError as exc:
        errors.append(_issue("bundle_root_not_directory", f"无法访问 bundle_root: {exc}", path=str(bundle_input)))
        return finish()
    if _is_link_or_reparse(bundle_input):
        errors.append(_issue("bundle_root_symlink", "bundle_root 不得为符号链接或 reparse point", path=str(bundle_input)))
        return finish()
    if not stat.S_ISDIR(root_info.st_mode):
        errors.append(_issue("bundle_root_not_directory", "bundle_root 必须是目录", path=str(bundle_input)))
        return finish()

    root_resolved = bundle_input.resolve(strict=True)
    relative_parts = values["artifact_relative_path"].split("/")
    candidate = root_resolved.joinpath(*relative_parts)
    resolved_candidate = candidate.resolve(strict=False)
    if not _inside(resolved_candidate, root_resolved):
        errors.append(_issue("artifact_outside_bundle", "artifact 解析后越过 bundle_root", path=values["artifact_relative_path"]))
        return finish()
    current = root_resolved
    for part in relative_parts:
        current = current / part
        try:
            current.lstat()
        except FileNotFoundError:
            errors.append(_issue("artifact_missing", "artifact 或其路径组件不存在", path=values["artifact_relative_path"]))
            return finish()
        except OSError as exc:
            errors.append(_issue("artifact_not_regular", f"无法访问 artifact: {exc}", path=values["artifact_relative_path"]))
            return finish()
        if _is_link_or_reparse(current):
            code = "artifact_symlink" if current == candidate else "artifact_path_component_symlink"
            errors.append(_issue(code, "artifact 路径不得包含符号链接或 reparse point", path=values["artifact_relative_path"]))
            return finish()

    values["artifact_path"] = resolved_candidate
    if resolved_candidate == manifest_input.resolve(strict=True):
        errors.append(_issue("artifact_same_as_manifest", "artifact 不得回指 Manifest", path=values["artifact_relative_path"]))
        return finish()
    artifact_info = resolved_candidate.lstat()
    if not stat.S_ISREG(artifact_info.st_mode):
        errors.append(_issue("artifact_not_regular", "artifact 必须是普通文件", path=values["artifact_relative_path"]))
        return finish()

    before_path = _identity(artifact_info)
    values["actual_artifact_size"] = artifact_info.st_size
    values["size_valid"] = artifact_info.st_size == EXPECTED_SIZE
    if not values["size_valid"]:
        errors.append(_issue(
            "artifact_size_mismatch",
            "artifact 大小不匹配",
            path=values["artifact_relative_path"],
            expected=EXPECTED_SIZE,
            actual=artifact_info.st_size,
        ))
        values["artifact_unchanged"] = before_path == _identity(resolved_candidate.stat())
        return finish()

    try:
        actual_sha, header, before_handle, after_handle = _read_artifact(resolved_candidate)
        after_path = _identity(resolved_candidate.stat())
    except OSError as exc:
        errors.append(_issue("artifact_not_regular", f"无法只读验证 artifact: {exc}", path=values["artifact_relative_path"]))
        return finish()
    values["actual_artifact_sha256"] = actual_sha
    values["sha_valid"] = actual_sha == values["expected_artifact_sha256"]
    values["header_valid"] = header == EXPECTED_HEADER
    values["offset_zero_valid"] = bool(header) and header[0] == 2
    values["artifact_unchanged"] = before_path == before_handle == after_handle == after_path
    if not values["sha_valid"]:
        errors.append(_issue(
            "artifact_hash_mismatch",
            "artifact SHA-256 与 Manifest 不匹配",
            path=values["artifact_relative_path"],
            expected=values["expected_artifact_sha256"],
            actual=actual_sha,
        ))
    if not values["header_valid"]:
        errors.append(_issue(
            "artifact_header_mismatch",
            "artifact 17 字节 header 不匹配",
            path=values["artifact_relative_path"],
            expected=EXPECTED_HEADER.hex(" ").upper(),
            actual=header.hex(" ").upper(),
        ))
    if not values["offset_zero_valid"]:
        errors.append(_issue(
            "artifact_offset_zero_mismatch",
            "artifact offset 0 必须为 02",
            path=values["artifact_relative_path"],
            expected=2,
            actual=header[0] if header else None,
        ))
    if not values["layout_valid"]:
        errors.append(_issue(
            "artifact_layout_mismatch",
            "Manifest layout 与冻结契约不匹配",
            expected=EXPECTED_LAYOUT,
            actual=document.get("layout"),
        ))
    if not values["artifact_unchanged"]:
        errors.append(_issue(
            "artifact_changed_during_validation",
            "artifact 在验证期间发生变化",
            path=values["artifact_relative_path"],
        ))
    return finish()


def handoff_result_to_dict(result: UploaderHandoffValidationResult) -> dict[str, Any]:
    return {
        "status": result.status.value,
        "manifest_path": str(result.manifest_path),
        "manifest_sha256": result.manifest_sha256,
        "schema_version": result.schema_version,
        "artifact_type": result.artifact_type,
        "bundle_root": str(result.bundle_root),
        "artifact_relative_path": result.artifact_relative_path,
        "artifact_path": result.artifact_relative_path if result.artifact_path is not None else None,
        "expected_artifact_size": result.expected_artifact_size,
        "actual_artifact_size": result.actual_artifact_size,
        "size_valid": result.size_valid,
        "expected_artifact_sha256": result.expected_artifact_sha256,
        "actual_artifact_sha256": result.actual_artifact_sha256,
        "sha_valid": result.sha_valid,
        "header_valid": result.header_valid,
        "offset_zero_valid": result.offset_zero_valid,
        "layout_valid": result.layout_valid,
        "artifact_unchanged": result.artifact_unchanged,
        "firmware_scope": list(result.firmware_scope),
        "target_firmware": result.target_firmware,
        "firmware_compatible": result.firmware_compatible,
        "transfer_unprepared": result.transfer_unprepared,
        "device_evidence_level": result.device_evidence_level,
        "golden_status": result.golden_status,
        "warnings": [asdict(issue) for issue in result.warnings],
        "errors": [asdict(issue) for issue in result.errors],
        "safe_to_prepare_transfer": result.safe_to_prepare_transfer,
        "external_usage": asdict(result.external_usage),
        "boundary": "离线预检通过不表示静态传输协议、真机连接或真实上传可用",
    }
