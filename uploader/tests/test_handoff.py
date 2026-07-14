from __future__ import annotations

import ast
import hashlib
import json
import os
import stat
from dataclasses import FrozenInstanceError, fields
from importlib.resources import files
from pathlib import Path

import pytest
from jsonschema.exceptions import SchemaError

from ultra3_uploader import (
    HandoffExternalUsage,
    HandoffValidationIssue,
    HandoffValidationStatus,
    UploaderHandoffValidationResult,
    validate_handoff,
)
from ultra3_uploader import handoff


REPO = Path(__file__).resolve().parents[2]
HEADER = bytes.fromhex("02 00 00 FF FF FF 00 00 80 01 40 01 FC 00 D2 00 00")
SIZE = 351617
FIRMWARE = "NJ-LEJ-2.1.7"
SCHEMA_SHA = "FB4E5BBFEC42D0E75F251B5512A374CB3E222625711B79653C3C07638B331DA5"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def artifact_bytes(header: bytes = HEADER) -> bytes:
    return header + b"\0" * (SIZE - len(header))


def document_for(
    artifact: Path,
    relative: str = "watchface.bin",
    *,
    golden_status: str = "not_applicable",
) -> dict:
    return {
        "schema": "ultra3-handoff/v1",
        "artifact_type": "greenlion_static_diy_complete_bin",
        "artifact_path": relative,
        "artifact_size": SIZE,
        "artifact_sha256": sha256(artifact),
        "container": "greenlion-static",
        "firmware_scope": [FIRMWARE],
        "builder_version": "0.2.4-greenlion-exact",
        "pillow_version": "10.4.0",
        "template_sha256": "5D04DE76C94DA9D7F7069AF3E6038E1575D3B42E5E009EAD590CE4DD33F5E1CC",
        "template_header_hex": "02 00 00 FF FF FF 00 00 80 01 40 01 FC 00 D2 00 00",
        "template_offset_zero": 2,
        "layout": {
            "header": {"start": 0, "end": 17, "length": 17},
            "main": {"start": 17, "end": 245777, "length": 245760},
            "thumbnail": {"start": 245777, "end": 351617, "length": 105840},
        },
        "main_resource": {
            "width": 320,
            "height": 384,
            "encoding": "greenlion-next-high-rgb565",
        },
        "thumbnail_resource": {
            "width": 210,
            "height": 252,
            "encoding": "greenlion-next-high-rgb565",
            "source": "auto-from-main-image",
        },
        "build_validation": {
            "output_revalidated": True,
            "input_unchanged": True,
            "template_unchanged": True,
            "golden_status": golden_status,
            "exact_golden_match": True if golden_status == "match" else None,
            "determinism_status": "not_evaluated",
        },
        "device_evidence": {"level": "C", "note": "离线测试证据"},
        "transfer": {
            "status": "not_prepared",
            "payload_size": None,
            "chunk_count": None,
            "ble_frames_present": False,
        },
    }


def write_manifest(path: Path, document: object) -> Path:
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def bundle(tmp_path: Path) -> tuple[Path, Path, dict]:
    artifact = tmp_path / "watchface.bin"
    artifact.write_bytes(artifact_bytes())
    document = document_for(artifact)
    manifest = write_manifest(tmp_path / "watchface.handoff.json", document)
    return manifest, artifact, document


def codes(result: UploaderHandoffValidationResult) -> set[str]:
    return {issue.error_code for issue in result.errors}


def warning_codes(result: UploaderHandoffValidationResult) -> set[str]:
    return {issue.error_code for issue in result.warnings}


def test_public_api_and_models_are_frozen(bundle: tuple[Path, Path, dict]) -> None:
    manifest, _artifact, _document = bundle
    result = validate_handoff(manifest)
    assert isinstance(result, UploaderHandoffValidationResult)
    with pytest.raises(FrozenInstanceError):
        result.size_valid = False  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.external_usage.ble_scans = 1  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.warnings[0].message = "changed"  # type: ignore[misc]


def test_packaged_schema_matches_frozen_docs_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    packaged = files("ultra3_uploader.schemas").joinpath("ultra3_handoff_v1.schema.json").read_bytes()
    docs = (REPO / "docs/handoff/ultra3_handoff_v1.schema.json").read_bytes()
    assert packaged == docs
    assert hashlib.sha256(packaged).hexdigest().upper() == SCHEMA_SHA


def test_expected_external_usage_fields_are_all_zero() -> None:
    usage = HandoffExternalUsage()
    assert {field.name: getattr(usage, field.name) for field in fields(usage)} == {
        "bleak_initializations": 0,
        "ble_scans": 0,
        "ble_connections": 0,
        "ff02_writes": 0,
        "ff03_notifications": 0,
        "adb": 0,
        "frida": 0,
        "network_requests": 0,
        "payloads_generated": 0,
        "c9_frames_generated": 0,
        "real_uploads": 0,
    }


def test_invalid_packaged_schema_returns_structured_result(
    bundle: tuple[Path, Path, dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, _artifact, _document = bundle

    def invalid_schema():
        raise SchemaError("模拟无效 Schema")

    monkeypatch.setattr(handoff, "_read_packaged_schema", invalid_schema)
    result = validate_handoff(manifest)
    assert result.status is HandoffValidationStatus.INVALID
    assert codes(result) == {"schema_invalid"}


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("golden_match.handoff.json", "match"),
        ("custom_not_applicable.handoff.json", "not_applicable"),
    ],
)
def test_real_stage8c0_samples(name: str, expected: str) -> None:
    manifest = REPO / "editor/artifacts/stage8c0_handoff_design" / name
    without_firmware = validate_handoff(manifest, bundle_root=REPO)
    assert without_firmware.status is HandoffValidationStatus.VALID
    assert without_firmware.firmware_compatible is None
    assert not without_firmware.safe_to_prepare_transfer
    assert "target_firmware_not_provided" in warning_codes(without_firmware)
    matched = validate_handoff(manifest, bundle_root=REPO, target_firmware=FIRMWARE)
    assert matched.status is HandoffValidationStatus.VALID
    assert matched.firmware_compatible is True
    assert matched.safe_to_prepare_transfer
    assert matched.golden_status == expected
    assert matched.device_evidence_level == "C"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "manifest_missing"),
        ("directory", "manifest_not_regular"),
        (b" " * (64 * 1024 + 1), "manifest_too_large"),
        (b"\xff", "manifest_not_utf8"),
        (b"\xef\xbb\xbf{}", "manifest_bom_not_allowed"),
        (b'{"x":1,"x":2}', "manifest_duplicate_key"),
        (b'{"x":{"y":1,"y":2}}', "manifest_duplicate_key"),
        (b"{", "manifest_invalid_json"),
        (b"[]", "manifest_root_not_object"),
        (b'{"x":NaN}', "manifest_invalid_json"),
        (b'{"x":Infinity}', "manifest_invalid_json"),
        (b'{"x":-Infinity}', "manifest_invalid_json"),
        (b'{/* comment */"x":1}', "manifest_invalid_json"),
        (b'{} trailing', "manifest_invalid_json"),
    ],
    ids=[
        "missing",
        "directory",
        "too-large",
        "non-utf8",
        "bom",
        "duplicate-root",
        "duplicate-nested",
        "invalid-json",
        "root-array",
        "nan",
        "infinity",
        "negative-infinity",
        "comment",
        "trailing-content",
    ],
)
def test_manifest_read_failures(tmp_path: Path, raw: bytes | str | None, expected: str) -> None:
    path = tmp_path / "manifest.json"
    if raw == "directory":
        path.mkdir()
    elif isinstance(raw, bytes):
        path.write_bytes(raw)
    result = validate_handoff(path)
    assert result.status is HandoffValidationStatus.INVALID
    assert expected in codes(result)


def test_manifest_symlink_rejected_by_guard(
    bundle: tuple[Path, Path, dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, _artifact, _document = bundle
    original = handoff._is_link_or_reparse
    monkeypatch.setattr(handoff, "_is_link_or_reparse", lambda path: path == manifest or original(path))
    assert "manifest_symlink" in codes(validate_handoff(manifest))


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("unknown_root", "schema_validation_failed"),
        ("unknown_nested", "schema_validation_failed"),
        ("schema", "unsupported_schema"),
        ("artifact_type", "unsupported_artifact_type"),
        ("lower_sha", "schema_validation_failed"),
        ("layout", "artifact_layout_mismatch"),
        ("prepared", "handoff_already_prepared"),
    ],
)
def test_schema_rejections(
    bundle: tuple[Path, Path, dict], mutation: str, expected: str
) -> None:
    manifest, _artifact, document = bundle
    if mutation == "unknown_root":
        document["unknown"] = True
    elif mutation == "unknown_nested":
        document["main_resource"]["unknown"] = True
    elif mutation == "schema":
        document["schema"] = "ultra3-handoff/v2"
    elif mutation == "artifact_type":
        document["artifact_type"] = "other"
    elif mutation == "lower_sha":
        document["artifact_sha256"] = document["artifact_sha256"].lower()
    elif mutation == "layout":
        document["layout"]["main"]["end"] = 1
    else:
        document["transfer"]["status"] = "prepared"
    write_manifest(manifest, document)
    result = validate_handoff(manifest)
    assert result.status is HandoffValidationStatus.INVALID
    assert expected in codes(result)


@pytest.mark.parametrize(
    "value",
    [
        ".",
        "./watchface.bin",
        "../watchface.bin",
        "foo/../watchface.bin",
        "foo//watchface.bin",
        "foo/",
        "C:/watchface.bin",
        r"C:\watchface.bin",
        r"\\server\share\watchface.bin",
        r"foo\watchface.bin",
        "https://example/watchface.bin",
        "file://watchface.bin",
        "foo:bar.bin",
        "watchface.bin:stream",
        "watchface\0.bin",
    ],
)
def test_noncanonical_artifact_paths_rejected(
    bundle: tuple[Path, Path, dict], value: str
) -> None:
    manifest, _artifact, document = bundle
    document["artifact_path"] = value
    write_manifest(manifest, document)
    result = validate_handoff(manifest)
    assert "invalid_artifact_path" in codes(result)
    assert result.artifact_path is None


def test_same_directory_and_explicit_bundle_root_succeed(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    root.mkdir()
    artifact = root / "watchface.bin"
    artifact.write_bytes(artifact_bytes())
    manifest = write_manifest(root / "watchface.handoff.json", document_for(artifact))
    assert validate_handoff(manifest, target_firmware=FIRMWARE).safe_to_prepare_transfer
    outside_manifest = write_manifest(tmp_path / "outside.json", document_for(artifact))
    assert validate_handoff(
        outside_manifest,
        bundle_root=root,
        target_firmware=FIRMWARE,
    ).safe_to_prepare_transfer


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("missing", "bundle_root_missing"),
        ("file", "bundle_root_not_directory"),
        ("link", "bundle_root_symlink"),
    ],
)
def test_bundle_root_failures(
    bundle: tuple[Path, Path, dict],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    expected: str,
) -> None:
    manifest, _artifact, _document = bundle
    root = tmp_path / "other"
    if kind == "file":
        root.write_text("not a directory", encoding="utf-8")
    elif kind == "link":
        root.mkdir()
        original = handoff._is_link_or_reparse
        monkeypatch.setattr(handoff, "_is_link_or_reparse", lambda path: path == root or original(path))
    result = validate_handoff(manifest, bundle_root=root)
    assert expected in codes(result)


def test_containment_rejected_before_reading(
    bundle: tuple[Path, Path, dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, _artifact, _document = bundle
    monkeypatch.setattr(handoff, "_inside", lambda child, root: False)
    result = validate_handoff(manifest)
    assert "artifact_outside_bundle" in codes(result)
    assert result.actual_artifact_sha256 is None


def test_artifact_and_component_links_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subdir = tmp_path / "assets"
    subdir.mkdir()
    artifact = subdir / "watchface.bin"
    artifact.write_bytes(artifact_bytes())
    manifest = write_manifest(
        tmp_path / "watchface.handoff.json",
        document_for(artifact, "assets/watchface.bin"),
    )
    original = handoff._is_link_or_reparse
    monkeypatch.setattr(handoff, "_is_link_or_reparse", lambda path: path == artifact or original(path))
    assert "artifact_symlink" in codes(validate_handoff(manifest))
    monkeypatch.setattr(handoff, "_is_link_or_reparse", lambda path: path == subdir or original(path))
    assert "artifact_path_component_symlink" in codes(validate_handoff(manifest))


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("missing", "artifact_missing"),
        ("directory", "artifact_not_regular"),
    ],
)
def test_artifact_missing_or_not_regular(tmp_path: Path, kind: str, expected: str) -> None:
    artifact = tmp_path / "watchface.bin"
    if kind == "directory":
        artifact.mkdir()
    seed = tmp_path / "seed.bin"
    seed.write_bytes(artifact_bytes())
    document = document_for(seed)
    manifest = write_manifest(tmp_path / "watchface.handoff.json", document)
    assert expected in codes(validate_handoff(manifest))


def test_artifact_cannot_be_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "watchface.handoff.json"
    seed = tmp_path / "seed.bin"
    seed.write_bytes(artifact_bytes())
    document = document_for(seed, manifest.name)
    write_manifest(manifest, document)
    assert "artifact_same_as_manifest" in codes(validate_handoff(manifest))


def test_artifact_size_hash_header_and_offset_failures(tmp_path: Path) -> None:
    artifact = tmp_path / "watchface.bin"
    artifact.write_bytes(b"small")
    document = document_for(artifact)
    manifest = write_manifest(tmp_path / "watchface.handoff.json", document)
    assert "artifact_size_mismatch" in codes(validate_handoff(manifest))

    artifact.write_bytes(artifact_bytes())
    document = document_for(artifact)
    document["artifact_sha256"] = "A" * 64
    write_manifest(manifest, document)
    assert "artifact_hash_mismatch" in codes(validate_handoff(manifest))

    changed_header = b"\x01" + HEADER[1:]
    artifact.write_bytes(artifact_bytes(changed_header))
    write_manifest(manifest, document_for(artifact))
    result = validate_handoff(manifest)
    assert {"artifact_header_mismatch", "artifact_offset_zero_mismatch"} <= codes(result)


def test_artifact_change_during_validation_detected(
    bundle: tuple[Path, Path, dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, artifact, _document = bundle
    original = handoff._read_artifact

    def changing(path: Path):
        value = original(path)
        info = path.stat()
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000_000))
        return value

    monkeypatch.setattr(handoff, "_read_artifact", changing)
    result = validate_handoff(manifest)
    assert "artifact_changed_during_validation" in codes(result)
    assert not result.artifact_unchanged


def test_validation_is_read_only_and_creates_no_files(bundle: tuple[Path, Path, dict]) -> None:
    manifest, artifact, _document = bundle
    before_files = {path.name for path in manifest.parent.iterdir()}
    before_manifest = sha256(manifest)
    before_artifact = sha256(artifact)
    artifact.chmod(stat.S_IREAD)
    try:
        result = validate_handoff(manifest, target_firmware=FIRMWARE)
    finally:
        artifact.chmod(stat.S_IREAD | stat.S_IWRITE)
    assert result.safe_to_prepare_transfer
    assert sha256(manifest) == before_manifest
    assert sha256(artifact) == before_artifact
    assert {path.name for path in manifest.parent.iterdir()} == before_files


def test_firmware_semantics(bundle: tuple[Path, Path, dict]) -> None:
    manifest, _artifact, _document = bundle
    missing = validate_handoff(manifest)
    assert missing.status is HandoffValidationStatus.VALID
    assert missing.firmware_compatible is None
    assert not missing.safe_to_prepare_transfer
    assert "target_firmware_not_provided" in warning_codes(missing)
    matched = validate_handoff(manifest, target_firmware=FIRMWARE)
    assert matched.status is HandoffValidationStatus.VALID
    assert matched.firmware_compatible is True
    assert matched.safe_to_prepare_transfer
    mismatch = validate_handoff(manifest, target_firmware="OTHER")
    assert mismatch.status is HandoffValidationStatus.INVALID
    assert mismatch.firmware_compatible is False
    assert not mismatch.safe_to_prepare_transfer
    assert "firmware_scope_mismatch" in codes(mismatch)


def test_match_does_not_skip_hash_and_not_applicable_is_not_an_issue(
    bundle: tuple[Path, Path, dict]
) -> None:
    manifest, artifact, document = bundle
    document["build_validation"]["golden_status"] = "match"
    document["build_validation"]["exact_golden_match"] = True
    document["artifact_sha256"] = "A" * 64
    write_manifest(manifest, document)
    assert "artifact_hash_mismatch" in codes(validate_handoff(manifest))
    write_manifest(manifest, document_for(artifact, golden_status="not_applicable"))
    result = validate_handoff(manifest, target_firmware=FIRMWARE)
    assert result.safe_to_prepare_transfer
    assert not any("not_applicable" in issue.error_code for issue in result.errors + result.warnings)


def test_handoff_module_has_no_operational_dependencies() -> None:
    source = Path(handoff.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not imports & {
        "bleak",
        "ultra3_editor",
        "PIL",
        "subprocess",
        "requests",
        "urllib",
        "socket",
    }
    for forbidden in (
        "build_c8",
        "iter_c9",
        "payload_353146",
        "1529",
        "upload_session",
        "upload-handoff",
    ):
        assert forbidden not in source
