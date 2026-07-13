from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

import ultra3_editor.time_position as time_position_module
from ultra3_editor.errors import (
    EditOutputExistsError,
    EditVerificationError,
    FileReadError,
    InputOutputSamePathError,
    InvalidExistingTimePositionError,
    NoChangeRequestedError,
    TimePositionEditError,
    UnsupportedStaticDiySizeError,
)
from ultra3_editor.static_diy import STATIC_DIY_SIZE, TimePosition
from ultra3_editor.time_position import (
    BOTTOM_GOLDEN_SHA256,
    TOP_GOLDEN_SHA256,
    set_time_position,
)


ROOT = Path(__file__).resolve().parents[1]
TOP_GOLDEN = (
    ROOT
    / "samples"
    / "stage7a2_diy_root_capture"
    / "A0_repeat_1"
    / "reconstructed.bin"
)
BOTTOM_GOLDEN = (
    ROOT
    / "samples"
    / "stage7a2_diy_root_capture"
    / "P1_time_bottom"
    / "reconstructed.bin"
)


def _write_static(path: Path, position: TimePosition, fill: int = 0x5A) -> Path:
    path.write_bytes(bytes([position.byte_value]) + bytes([fill]) * (STATIC_DIY_SIZE - 1))
    return path


@pytest.mark.parametrize(
    ("source", "position", "golden_sha256"),
    (
        (TOP_GOLDEN, TimePosition.BOTTOM, BOTTOM_GOLDEN_SHA256),
        (BOTTOM_GOLDEN, TimePosition.TOP, TOP_GOLDEN_SHA256),
    ),
)
def test_golden_bidirectional_edit_is_exact(
    tmp_path: Path,
    source: Path,
    position: TimePosition,
    golden_sha256: str,
) -> None:
    output = tmp_path / "edited.bin"
    result = set_time_position(source, output, position)

    assert output.read_bytes() == (
        BOTTOM_GOLDEN if position is TimePosition.BOTTOM else TOP_GOLDEN
    ).read_bytes()
    assert result.status == "COMPLETE"
    assert result.container == "greenlion-static"
    assert result.feature == "set-time-position"
    assert result.changed_byte_count == 1
    assert result.changed_offsets == (0,)
    assert result.unchanged_byte_count == STATIC_DIY_SIZE - 1
    assert result.output_sha256 == golden_sha256
    assert result.golden_target_sha256 == golden_sha256
    assert result.exact_golden_match is True
    assert result.output_revalidated is True
    assert result.validation_passed is True
    assert result.real_ble_usage == 0
    assert result.errors == ()


def test_non_golden_input_is_supported_without_hash_whitelist(tmp_path: Path) -> None:
    source = _write_static(tmp_path / "input.bin", TimePosition.TOP, fill=0xA5)
    output = tmp_path / "output.bin"

    result = set_time_position(source, output, TimePosition.BOTTOM)

    assert output.read_bytes()[0] == 1
    assert output.read_bytes()[1:] == source.read_bytes()[1:]
    assert result.exact_golden_match == "not_applicable"
    assert result.golden_target_sha256 is None


def test_only_offset_zero_changes_and_input_stays_unchanged(tmp_path: Path) -> None:
    source = _write_static(tmp_path / "input.bin", TimePosition.TOP, fill=0x33)
    input_before = source.read_bytes()
    input_sha256 = hashlib.sha256(input_before).hexdigest().upper()
    output = tmp_path / "output.bin"

    result = set_time_position(source, output, TimePosition.BOTTOM)

    output_data = output.read_bytes()
    assert output_data == b"\x01" + input_before[1:]
    assert source.read_bytes() == input_before
    assert result.input_sha256_before == input_sha256
    assert result.input_sha256_after == input_sha256
    assert result.input_unchanged is True
    assert result.field_offset == 0
    assert result.field_offset_hex == "0x00000000"
    assert result.field_width == 1
    assert result.before_hex == "00"
    assert result.after_hex == "01"


@pytest.mark.parametrize(
    ("position", "expected_before", "expected_after"),
    (
        (TimePosition.BOTTOM, "top", "bottom"),
        (TimePosition.TOP, "bottom", "top"),
    ),
)
def test_result_records_detected_requested_and_output_positions(
    tmp_path: Path,
    position: TimePosition,
    expected_before: str,
    expected_after: str,
) -> None:
    source_position = TimePosition.TOP if position is TimePosition.BOTTOM else TimePosition.BOTTOM
    source = _write_static(tmp_path / "input.bin", source_position)
    result = set_time_position(source, tmp_path / "output.bin", position)

    assert result.detected_input_position is TimePosition(expected_before)
    assert result.requested_position is position
    assert result.output_position is TimePosition(expected_after)


@pytest.mark.parametrize("position", (TimePosition.TOP, TimePosition.BOTTOM))
def test_no_change_is_rejected_without_outputs(
    tmp_path: Path,
    position: TimePosition,
) -> None:
    source = _write_static(tmp_path / "input.bin", position)
    output = tmp_path / "output.bin"
    json_path = tmp_path / "result.json"
    report_path = tmp_path / "result.md"

    with pytest.raises(NoChangeRequestedError):
        set_time_position(source, output, position, json_path, report_path)

    assert not output.exists()
    assert not json_path.exists()
    assert not report_path.exists()


@pytest.mark.parametrize("invalid", ("top", "TOP", 0, 1, None))
def test_api_rejects_non_enum_positions(tmp_path: Path, invalid: object) -> None:
    source = _write_static(tmp_path / "input.bin", TimePosition.TOP)
    with pytest.raises(TimePositionEditError, match="TimePosition"):
        set_time_position(source, tmp_path / "output.bin", invalid)  # type: ignore[arg-type]


@pytest.mark.parametrize("size", (0, STATIC_DIY_SIZE - 1, STATIC_DIY_SIZE + 1))
def test_rejects_unsupported_sizes_without_output(tmp_path: Path, size: int) -> None:
    source = tmp_path / "input.bin"
    source.write_bytes(bytes(size))
    output = tmp_path / "output.bin"
    with pytest.raises(UnsupportedStaticDiySizeError):
        set_time_position(source, output, TimePosition.BOTTOM)
    assert not output.exists()


def test_rejects_invalid_existing_position_without_output(tmp_path: Path) -> None:
    source = tmp_path / "input.bin"
    source.write_bytes(b"\x02" + bytes(STATIC_DIY_SIZE - 1))
    output = tmp_path / "output.bin"
    with pytest.raises(InvalidExistingTimePositionError):
        set_time_position(source, output, TimePosition.BOTTOM)
    assert not output.exists()


def test_rejects_missing_input_without_output(tmp_path: Path) -> None:
    output = tmp_path / "output.bin"
    with pytest.raises(FileReadError, match="不存在"):
        set_time_position(tmp_path / "missing.bin", output, TimePosition.BOTTOM)
    assert not output.exists()


def test_rejects_same_input_and_output_path(tmp_path: Path) -> None:
    source = _write_static(tmp_path / "input.bin", TimePosition.TOP)
    with pytest.raises(InputOutputSamePathError):
        set_time_position(source, source, TimePosition.BOTTOM)


@pytest.mark.parametrize("existing_kind", ("output", "json", "report"))
def test_any_existing_target_rejects_before_creating_files(
    tmp_path: Path,
    existing_kind: str,
) -> None:
    source = _write_static(tmp_path / "input.bin", TimePosition.TOP)
    targets = {
        "output": tmp_path / "output.bin",
        "json": tmp_path / "result.json",
        "report": tmp_path / "result.md",
    }
    targets[existing_kind].write_text("保留", encoding="utf-8")

    with pytest.raises(EditOutputExistsError):
        set_time_position(
            source,
            targets["output"],
            TimePosition.BOTTOM,
            targets["json"],
            targets["report"],
        )

    assert targets[existing_kind].read_text(encoding="utf-8") == "保留"
    for kind, path in targets.items():
        if kind != existing_kind:
            assert not path.exists()


def test_duplicate_output_targets_are_rejected(tmp_path: Path) -> None:
    source = _write_static(tmp_path / "input.bin", TimePosition.TOP)
    output = tmp_path / "same-path"
    with pytest.raises(TimePositionEditError, match="重复"):
        set_time_position(source, output, TimePosition.BOTTOM, output)
    assert not output.exists()


def test_json_and_markdown_contain_complete_audit_fields(tmp_path: Path) -> None:
    source = _write_static(tmp_path / "input.bin", TimePosition.TOP)
    output = tmp_path / "output.bin"
    json_path = tmp_path / "result.json"
    report_path = tmp_path / "result.md"

    result = set_time_position(
        source,
        output,
        TimePosition.BOTTOM,
        json_path,
        report_path,
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    required = {
        "status",
        "feature",
        "container",
        "scope",
        "input_path",
        "input_size",
        "input_sha256_before",
        "input_sha256_after",
        "input_unchanged",
        "detected_input_position",
        "requested_position",
        "output_position",
        "output_path",
        "output_size",
        "output_sha256",
        "field_offset",
        "field_offset_hex",
        "field_width",
        "before_hex",
        "after_hex",
        "changed_byte_count",
        "changed_offsets",
        "unchanged_byte_count",
        "output_revalidated",
        "validation_passed",
        "exact_golden_match",
        "golden_target_sha256",
        "real_ble_usage",
        "errors",
    }
    assert required <= payload.keys()
    assert payload["changed_offsets"] == [0]
    assert payload["external_usage"] == {
        "ble": 0,
        "adb": 0,
        "frida": 0,
        "uploader": 0,
    }
    assert payload["output_sha256"] == result.output_sha256

    report = report_path.read_text(encoding="utf-8")
    assert "Stage 7B-1" in report
    assert "offset `0x00000000`" in report
    assert "changed byte count: `1`" in report
    assert "BLE: `0`" in report
    assert "Builder" in report


def test_nested_output_directories_follow_existing_create_parent_policy(tmp_path: Path) -> None:
    source = _write_static(tmp_path / "input.bin", TimePosition.TOP)
    output = tmp_path / "nested" / "bin" / "output.bin"
    json_path = tmp_path / "nested" / "json" / "result.json"
    report_path = tmp_path / "nested" / "report" / "result.md"

    set_time_position(source, output, TimePosition.BOTTOM, json_path, report_path)

    assert output.is_file()
    assert json_path.is_file()
    assert report_path.is_file()


def test_failed_output_revalidation_removes_current_call_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_static(tmp_path / "input.bin", TimePosition.TOP)
    output = tmp_path / "output.bin"
    json_path = tmp_path / "result.json"
    report_path = tmp_path / "result.md"
    original_inspect = time_position_module.inspect_static_diy
    calls = 0

    def fail_second_inspection(path: str | Path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise EditVerificationError("模拟输出复验失败")
        return original_inspect(path)

    monkeypatch.setattr(time_position_module, "inspect_static_diy", fail_second_inspection)
    with pytest.raises(EditVerificationError, match="模拟"):
        set_time_position(
            source,
            output,
            TimePosition.BOTTOM,
            json_path,
            report_path,
        )

    assert not output.exists()
    assert not json_path.exists()
    assert not report_path.exists()


def test_report_write_failure_rolls_back_binary_and_current_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_static(tmp_path / "input.bin", TimePosition.TOP)
    output = tmp_path / "output.bin"
    json_path = tmp_path / "result.json"
    report_path = tmp_path / "result.md"
    original_write = time_position_module._write_text_exclusive

    def fail_markdown(path: Path, text: str) -> None:
        if path.suffix == ".md":
            raise EditVerificationError("模拟报告写入失败")
        original_write(path, text)

    monkeypatch.setattr(time_position_module, "_write_text_exclusive", fail_markdown)
    with pytest.raises(EditVerificationError, match="模拟"):
        set_time_position(
            source,
            output,
            TimePosition.BOTTOM,
            json_path,
            report_path,
        )

    assert not output.exists()
    assert not json_path.exists()
    assert not report_path.exists()


def test_editor_core_has_no_hardware_or_uploader_imports() -> None:
    source_root = ROOT / "src" / "ultra3_editor"
    module_paths = (source_root / "time_position.py", source_root / "cli.py")
    imported: set[str] = set()
    for path in module_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
    assert not any(
        name == forbidden or name.startswith(forbidden + ".")
        for name in imported
        for forbidden in ("bleak", "ultra3_uploader", "subprocess")
    )


def test_only_gui_controller_imports_time_position_editor() -> None:
    gui_root = ROOT / "src" / "ultra3_editor" / "gui"
    for path in gui_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports_editor = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if any(alias.name == "set_time_position" for alias in node.names):
                    imports_editor = True
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "set_time_position":
                    assert path.name == "controllers.py"
        assert imports_editor is (path.name == "controllers.py")
