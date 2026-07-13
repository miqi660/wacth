from __future__ import annotations

import ast
from pathlib import Path

import pytest
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QLabel, QPushButton

from ultra3_editor.errors import (
    EditOutputExistsError,
    EditVerificationError,
    FileReadError,
    InputOutputSamePathError,
    InvalidExistingTimePositionError,
    NoChangeRequestedError,
    UnexpectedChangedBytesError,
    UnsupportedStaticDiySizeError,
)
from ultra3_editor.gui.controllers import OfflineGuiController
from ultra3_editor.gui.main_window import MainWindow
from ultra3_editor.static_diy import STATIC_DIY_SIZE, TimePosition
from ultra3_editor.time_position import BOTTOM_GOLDEN_SHA256, TOP_GOLDEN_SHA256


ROOT = Path(__file__).resolve().parents[2]
TOP = ROOT / "samples" / "stage7a2_diy_root_capture" / "A0_repeat_1" / "reconstructed.bin"
BOTTOM = ROOT / "samples" / "stage7a2_diy_root_capture" / "P1_time_bottom" / "reconstructed.bin"


def make_window(qapp, controller: OfflineGuiController | None = None) -> MainWindow:
    window = MainWindow(controller)
    window.show()
    qapp.processEvents()
    return window


@pytest.mark.parametrize(
    ("source", "target", "expected_json", "expected_report"),
    (
        (TOP, TimePosition.BOTTOM, True, True),
        (BOTTOM, TimePosition.TOP, False, True),
        (TOP, TimePosition.BOTTOM, True, False),
        (BOTTOM, TimePosition.TOP, False, False),
    ),
)
def test_controller_prepares_paths_and_summary(
    tmp_path: Path,
    source: Path,
    target: TimePosition,
    expected_json: bool,
    expected_report: bool,
) -> None:
    controller = OfflineGuiController()
    info = controller.load_file(source)
    output = tmp_path / "edited.bin"
    plan = controller.prepare_time_position_edit(
        info,
        output,
        target,
        include_json=expected_json,
        include_report=expected_report,
    )
    assert plan.input_path == info.path
    assert plan.output_path == output.resolve()
    assert plan.target_position is target
    assert plan.json_path == (output.resolve().with_suffix(".json") if expected_json else None)
    assert plan.report_path == (output.resolve().with_suffix(".md") if expected_report else None)
    assert plan.field_offset_hex == "0x00000000"
    assert plan.changed_byte_count == 1
    assert plan.unchanged_byte_count == 351616
    assert (plan.before_hex, plan.after_hex) == (
        ("00", "01") if target is TimePosition.BOTTOM else ("01", "00")
    )


def test_controller_execute_calls_public_core_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = OfflineGuiController()
    info = controller.load_file(TOP)
    plan = controller.prepare_time_position_edit(
        info,
        tmp_path / "edited.bin",
        TimePosition.BOTTOM,
        include_json=True,
        include_report=True,
    )
    calls = []
    expected = object()

    def fake_set_time_position(**kwargs):
        calls.append(kwargs)
        return expected

    monkeypatch.setattr("ultra3_editor.gui.controllers.set_time_position", fake_set_time_position)
    assert controller.execute_time_position_edit(plan) is expected
    assert calls == [
        {
            "input_path": plan.input_path,
            "output_path": plan.output_path,
            "position": TimePosition.BOTTOM,
            "json_path": plan.json_path,
            "report_path": plan.report_path,
        }
    ]


@pytest.mark.parametrize(
    ("error", "title", "message"),
    (
        (NoChangeRequestedError("x"), "没有变化", "未创建输出"),
        (InputOutputSamePathError("x"), "输出路径无效", "相同"),
        (EditOutputExistsError("x"), "输出文件已经存在", "不提供覆盖"),
        (UnsupportedStaticDiySizeError("x"), "不支持的文件大小", "351617"),
        (InvalidExistingTimePositionError("x"), "无法识别当前时间位置", "00 或 01"),
        (UnexpectedChangedBytesError("x"), "检测到预期之外的字节变化", "未保留"),
        (EditVerificationError("x"), "输出验证失败", "已经清理"),
        (FileReadError("x"), "无法读取输入文件", "读取权限"),
    ),
)
def test_controller_maps_edit_errors(error, title: str, message: str) -> None:
    mapped = OfflineGuiController.user_error(error)
    assert mapped.title == title
    assert message in mapped.message
    assert mapped.technical_details == "x"


@pytest.mark.parametrize(
    ("source", "target", "expected", "expected_sha"),
    (
        (TOP, TimePosition.BOTTOM, BOTTOM, BOTTOM_GOLDEN_SHA256),
        (BOTTOM, TimePosition.TOP, TOP, TOP_GOLDEN_SHA256),
    ),
)
def test_controller_golden_edit_is_exact(
    tmp_path: Path,
    source: Path,
    target: TimePosition,
    expected: Path,
    expected_sha: str,
) -> None:
    controller = OfflineGuiController()
    info = controller.load_file(source)
    plan = controller.prepare_time_position_edit(
        info,
        tmp_path / "edited.bin",
        target,
        include_json=True,
        include_report=True,
    )
    result = controller.execute_time_position_edit(plan)
    assert plan.output_path.read_bytes() == expected.read_bytes()
    assert result.output_sha256 == expected_sha
    assert result.changed_offsets == (0,)
    assert result.exact_golden_match is True
    assert result.input_unchanged is True
    assert result.output_revalidated is True


def test_non_golden_file_is_editable_through_controller(tmp_path: Path) -> None:
    source = tmp_path / "custom.bin"
    source.write_bytes(b"\x00" + bytes([0x5A]) * (STATIC_DIY_SIZE - 1))
    controller = OfflineGuiController()
    plan = controller.prepare_time_position_edit(
        controller.load_file(source),
        tmp_path / "custom_bottom.bin",
        TimePosition.BOTTOM,
        include_json=False,
        include_report=False,
    )
    result = controller.execute_time_position_edit(plan)
    assert result.exact_golden_match == "not_applicable"


@pytest.mark.parametrize(
    ("source", "target", "value_text"),
    (
        (TOP, TimePosition.BOTTOM, "00 → 01"),
        (BOTTOM, TimePosition.TOP, "01 → 00"),
    ),
)
def test_window_enables_export_only_for_complete_changed_state(
    qapp,
    tmp_path: Path,
    source: Path,
    target: TimePosition,
    value_text: str,
) -> None:
    window = make_window(qapp)
    assert window.load_file(source, show_error=False)
    assert not window.generate_button.isEnabled()
    (window.bottom_radio if target is TimePosition.BOTTOM else window.top_radio).click()
    assert not window.generate_button.isEnabled()
    window.output_path.setText(str(tmp_path / "edited.bin"))
    assert window.generate_button.isEnabled()
    assert "Offset: 0x00000000" in window.change_summary.text()
    assert f"Value: {value_text}" in window.change_summary.text()
    assert "Changed: 1 byte" in window.change_summary.text()
    assert "Unchanged: 351616 bytes" in window.change_summary.text()
    assert window.changed_label.text() == "Changed bytes: 1"
    assert window.status_label.text() == "VERIFIED · READY TO EXPORT"
    window.close()


def test_selecting_current_position_disables_export_and_calls_no_core(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = make_window(qapp)
    window.load_file(TOP, show_error=False)
    window.bottom_radio.click()
    window.output_path.setText(str(tmp_path / "edited.bin"))
    assert window.generate_button.isEnabled()
    calls = []
    monkeypatch.setattr(window.controller, "execute_time_position_edit", lambda plan: calls.append(plan))
    window.top_radio.click()
    window._generate_new_bin()
    assert not window.generate_button.isEnabled()
    assert "没有变化" in window.change_summary.text()
    assert calls == []
    window.close()


def test_confirmation_cancel_creates_nothing_and_calls_no_core(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "edited.bin"
    window = make_window(qapp)
    window.load_file(TOP, show_error=False)
    window.bottom_radio.click()
    window.output_path.setText(str(output))
    calls = []
    monkeypatch.setattr(window, "_confirm_export", lambda plan: False)
    monkeypatch.setattr(window.controller, "execute_time_position_edit", lambda plan: calls.append(plan))
    window._generate_new_bin()
    assert calls == []
    assert not output.exists()
    window.close()


def test_confirmation_dialog_is_localized_and_complete(qapp, tmp_path: Path) -> None:
    window = make_window(qapp)
    window.load_file(TOP, show_error=False)
    window.bottom_radio.click()
    window.output_path.setText(str(tmp_path / "edited.bin"))
    plan = window._current_plan()
    dialog = window.show_export_confirmation(plan)
    qapp.processEvents()
    text = "\n".join(label.text() for label in dialog.findChildren(QLabel))
    buttons = {button.text() for button in dialog.findChildren(QPushButton)}
    assert dialog.windowTitle() == "确认生成新 BIN"
    assert TOP.name in text
    assert "edited.bin" in text
    assert "上方 → 下方" in text
    assert "0x00000000" in text
    assert "00 → 01" in text
    assert "Changed bytes: 1" in text
    assert "输入文件不会被修改" in text
    assert "不执行 BLE 上传" in text
    assert {"生成", "取消"} <= buttons
    assert "OK" not in buttons and "确定" not in buttons
    dialog.close()
    window.close()


def test_confirmed_window_export_uses_core_and_keeps_original_loaded(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "edited.bin"
    window = make_window(qapp)
    window.load_file(TOP, show_error=False)
    original_info = window.current_info
    window.bottom_radio.click()
    window.output_path.setText(str(output))
    monkeypatch.setattr(window, "_confirm_export", lambda plan: True)
    window._generate_new_bin()
    assert output.read_bytes() == BOTTOM.read_bytes()
    assert window.current_info is original_info
    assert window.current_info.time_position is TimePosition.TOP
    assert window.last_result.output_sha256 == BOTTOM_GOLDEN_SHA256
    assert window.status_label.text() == "COMPLETE · Changed bytes: 1"
    window.last_dialog.close()
    window.close()


@pytest.mark.parametrize("scenario", ("existing", "same"))
def test_core_path_errors_are_shown_and_controls_recover(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    output = TOP if scenario == "same" else tmp_path / "existing.bin"
    if scenario == "existing":
        output.write_text("保留", encoding="utf-8")
    window = make_window(qapp)
    window.load_file(TOP, show_error=False)
    window.bottom_radio.click()
    window.output_path.setText(str(output))
    monkeypatch.setattr(window, "_confirm_export", lambda plan: True)
    window._generate_new_bin()
    assert window.last_result is None
    assert window.status_label.text() == "ERROR · No output created"
    assert window.generate_button.isEnabled()
    assert ("相同" if scenario == "same" else "不提供覆盖") in window.last_error
    if scenario == "existing":
        assert output.read_text(encoding="utf-8") == "保留"
    window.last_dialog.close()
    window.close()


def test_failure_restores_button_and_leaves_no_partial_output(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "edited.bin"
    window = make_window(qapp)
    window.load_file(TOP, show_error=False)
    window.bottom_radio.click()
    window.output_path.setText(str(output))
    monkeypatch.setattr(window, "_confirm_export", lambda plan: True)
    monkeypatch.setattr(
        window.controller,
        "execute_time_position_edit",
        lambda plan: (_ for _ in ()).throw(EditVerificationError("模拟失败")),
    )
    window._generate_new_bin()
    assert not output.exists()
    assert window.generate_button.isEnabled()
    assert not window._busy
    window.last_dialog.close()
    window.close()


def test_unexpected_exception_restores_gui_state(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "edited.bin"
    window = make_window(qapp)
    window.load_file(TOP, show_error=False)
    window.bottom_radio.click()
    window.output_path.setText(str(output))
    monkeypatch.setattr(window, "_confirm_export", lambda plan: True)
    calls = 0

    def fail_unexpectedly(plan) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("模拟意外异常")

    monkeypatch.setattr(
        window.controller,
        "execute_time_position_edit",
        fail_unexpectedly,
    )
    window._generate_new_bin()

    assert window._busy is False
    assert window.last_result is None
    assert window.generate_button.isEnabled() is True
    assert window.status_label.text() == "ERROR · No output created"
    assert not output.exists()
    assert "发生未预期错误，操作未完成。" in window.last_error
    assert "RuntimeError" in window.last_dialog.detailedText()
    assert "模拟意外异常" in window.last_dialog.detailedText()
    assert calls == 1
    window.last_dialog.close()
    window.close()


def test_busy_guard_prevents_second_execution(qapp, tmp_path: Path) -> None:
    window = make_window(qapp)
    window.load_file(TOP, show_error=False)
    window.bottom_radio.click()
    window.output_path.setText(str(tmp_path / "edited.bin"))
    window._busy = True
    calls = []
    window.controller.execute_time_position_edit = lambda plan: calls.append(plan)  # type: ignore[method-assign]
    window._generate_new_bin()
    assert calls == []
    window.close()


def test_success_dialog_shows_result_and_report_buttons(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = make_window(qapp)
    window.load_file(TOP, show_error=False)
    window.bottom_radio.click()
    window.output_path.setText(str(tmp_path / "edited.bin"))
    monkeypatch.setattr(window, "_confirm_export", lambda plan: True)
    window._generate_new_bin()
    dialog = window.last_dialog
    text = "\n".join(label.text() for label in dialog.findChildren(QLabel))
    buttons = {button.text(): button for button in dialog.findChildren(QPushButton)}
    assert "生成成功" in text
    assert BOTTOM_GOLDEN_SHA256 in text
    assert "上方 → 下方" in text
    assert "输入文件未改变：是" in text
    assert "输出写后复核：通过" in text
    assert "VERIFIED GOLDEN MATCH" in text
    assert "BLE：0" in text and "ADB：0" in text and "Frida：0" in text and "Uploader：0" in text
    assert {"打开输出文件夹", "复制 SHA-256", "打开 JSON", "打开 Markdown", "关闭"} <= buttons.keys()
    buttons["复制 SHA-256"].click()
    assert QGuiApplication.clipboard().text() == BOTTOM_GOLDEN_SHA256
    dialog.close()
    window.close()


def test_success_dialog_disables_unrequested_report_buttons(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = make_window(qapp)
    window.load_file(TOP, show_error=False)
    window.bottom_radio.click()
    window.output_path.setText(str(tmp_path / "edited.bin"))
    window.json_checkbox.setChecked(False)
    window.markdown_checkbox.setChecked(False)
    monkeypatch.setattr(window, "_confirm_export", lambda plan: True)
    window._generate_new_bin()
    buttons = {button.text(): button for button in window.last_dialog.findChildren(QPushButton)}
    assert not buttons["打开 JSON"].isEnabled()
    assert not buttons["打开 Markdown"].isEnabled()
    window.last_dialog.close()
    window.close()


def test_gui_source_has_no_direct_bin_editing_or_external_calls() -> None:
    gui_root = ROOT / "src" / "ultra3_editor" / "gui"
    main_source = (gui_root / "main_window.py").read_text(encoding="utf-8")
    for forbidden in ("read_bytes", "write_bytes", "Path.open", "hashlib", "data[0]", "ultra3_uploader"):
        assert forbidden not in main_source
    imported: set[str] = set()
    for path in gui_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
    assert not any(name.startswith(("bleak", "ultra3_uploader", "subprocess")) for name in imported)


def test_builder_and_resource_controls_remain_locked(qapp) -> None:
    window = make_window(qapp)
    window.load_file(TOP, show_error=False)
    assert all(not control.isEnabled() for control in window.resource_controls)
    assert not window.builder_generate_button.isEnabled()
    assert window.builder_status.text() == "NOT AVAILABLE"
    assert window.generate_button.text() == "生成新 BIN"
    window.close()


def test_long_output_path_does_not_hide_primary_button(qapp, tmp_path: Path) -> None:
    window = make_window(qapp)
    window.load_file(TOP, show_error=False)
    window.bottom_radio.click()
    window.output_path.setText(str(tmp_path / (("很长的输出文件名" * 20) + ".bin")))
    window.resize(1050, 680)
    qapp.processEvents()
    assert window.generate_button.isVisible()
    assert window.output_path.hasAcceptableInput()
    window.close()
