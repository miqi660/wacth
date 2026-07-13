from __future__ import annotations

import hashlib
from pathlib import Path

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QLabel, QPushButton

from ultra3_editor import cli
from ultra3_editor.errors import UnsupportedStaticDiySizeError
from ultra3_editor.gui import app as gui_app
from ultra3_editor.gui.controllers import OfflineGuiController
from ultra3_editor.gui.main_window import MainWindow
from ultra3_editor.gui.theme import TOKENS, _stylesheet
from ultra3_editor.gui.widgets import StatusBadge
from ultra3_editor.resource_geometry import MAIN_RESOURCE, THUMBNAIL_RESOURCE
from ultra3_editor.static_diy import STATIC_DIY_SIZE, StaticDiyInspection, TimePosition


ROOT = Path(__file__).resolve().parents[2]
TOP = ROOT / "samples" / "stage7a2_diy_root_capture" / "A0_repeat_1" / "reconstructed.bin"
BOTTOM = ROOT / "samples" / "stage7a2_diy_root_capture" / "P1_time_bottom" / "reconstructed.bin"


def make_window(qapp) -> MainWindow:
    window = MainWindow()
    window.show()
    qapp.processEvents()
    return window


def test_gui_initializes_with_empty_offline_state(qapp) -> None:
    window = make_window(qapp)
    assert window.current_info is None
    assert window.status_label.text() == "No file loaded"
    assert window.ble_label.text() == "BLE usage: 0"
    assert window.current_file_label.text() == "未加载文件"
    window.close()


def test_gui_source_has_no_hardware_or_uploader_calls() -> None:
    source_root = ROOT / "src" / "ultra3_editor" / "gui"
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_root.glob("*.py"))
    for forbidden in (
        "BleakClient(",
        "BleakScanner(",
        "ultra3_uploader",
        "subprocess.",
        "os.system(",
        "write_without_response(",
    ):
        assert forbidden not in source


def test_gui_cli_entry_uses_lazy_run(monkeypatch) -> None:
    monkeypatch.setattr(gui_app, "run", lambda: 17)
    assert cli.main(["gui"]) == 17


def test_loads_golden_top_file(qapp) -> None:
    window = make_window(qapp)
    assert window.load_file(TOP, show_error=False)
    assert window.current_info.time_position is TimePosition.TOP
    assert window.top_radio.isChecked()
    assert window.position_value.text() == "上方"
    assert window.current_info.sha256 == "9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635"
    window.close()


def test_loads_golden_bottom_file(qapp) -> None:
    window = make_window(qapp)
    assert window.load_file(BOTTOM, show_error=False)
    assert window.current_info.time_position is TimePosition.BOTTOM
    assert window.bottom_radio.isChecked()
    assert window.position_value.text() == "下方"
    assert window.current_info.sha256 == "3B8302F6746AB2B78FA48599328DB7907788FA322D18ADF297280C8A5D3370C0"
    window.close()


def test_file_information_is_complete_and_copyable(qapp) -> None:
    window = make_window(qapp)
    window.load_file(TOP, show_error=False)
    assert window.size_value.text() == "351617 bytes"
    assert window.first_byte_value.text() == "00"
    assert window.sha_value.toPlainText() == window.current_info.sha256
    window._copy_sha()
    assert QGuiApplication.clipboard().text() == window.current_info.sha256
    window._copy_path()
    assert QGuiApplication.clipboard().text() == str(window.current_info.path)
    assert "Administrator" not in window.path_value.text()
    window.close()


def test_invalid_size_maps_to_readable_error(qapp, tmp_path: Path) -> None:
    path = tmp_path / "invalid.bin"
    path.write_bytes(b"bad")
    window = make_window(qapp)
    assert not window.load_file(path, show_error=False)
    assert window.last_error == "当前 GUI 仅允许检查已验证的 351617 字节 GreenLion 静态 DIY 文件。"
    assert window.status_label.text() == "ERROR · No output created"
    window.close()


def test_unknown_first_byte_is_rejected(qapp, tmp_path: Path) -> None:
    path = tmp_path / "unknown.bin"
    path.write_bytes(b"\x02" + bytes(STATIC_DIY_SIZE - 1))
    window = make_window(qapp)
    assert not window.load_file(path, show_error=False)
    assert window.last_error == "offset 0x00000000 的值不是 00 或 01。"
    window.close()


def test_missing_file_is_rejected(qapp, tmp_path: Path) -> None:
    window = make_window(qapp)
    assert not window.load_file(tmp_path / "missing.bin", show_error=False)
    assert window.last_error == "请选择存在且可读取的普通 BIN 文件。"
    window.close()


def test_loading_never_modifies_input(qapp) -> None:
    before = hashlib.sha256(TOP.read_bytes()).hexdigest()
    window = make_window(qapp)
    window.load_file(TOP, show_error=False)
    assert hashlib.sha256(TOP.read_bytes()).hexdigest() == before
    window.close()


def test_edit_and_export_controls_are_hard_disabled(qapp) -> None:
    window = make_window(qapp)
    window.load_file(TOP, show_error=False)
    assert not window.top_radio.isEnabled()
    assert not window.bottom_radio.isEnabled()
    assert not window.output_path.isEnabled()
    assert not window.json_checkbox.isEnabled()
    assert not window.markdown_checkbox.isEnabled()
    assert not window.generate_button.isEnabled()
    assert window.changed_label.text() == "Changed bytes: 0"
    window.close()


def test_unknown_and_unsupported_controls_cannot_trigger(qapp) -> None:
    window = make_window(qapp)
    assert all(not control.isEnabled() for control in window.unsupported_controls)
    badges = window.findChildren(StatusBadge)
    assert any(badge.text() == "VERIFIED" for badge in badges)
    assert any(badge.text() == "UNKNOWN" for badge in badges)
    assert any(badge.text() == "UNSUPPORTED" for badge in badges)
    window.close()


def test_navigation_shows_honest_placeholder(qapp) -> None:
    window = make_window(qapp)
    window.nav_buttons["BIN 编辑"].click()
    qapp.processEvents()
    assert window.workspace.currentWidget() is window.placeholder_page
    assert window.placeholder_title.text() == "BIN 编辑"
    assert "仅支持命令行" in window.placeholder_message.text()
    window.close()


def test_about_dialog_states_verified_scope_and_limits(qapp) -> None:
    window = make_window(qapp)
    dialog = window.show_about_dialog()
    qapp.processEvents()
    text = "\n".join(label.text() for label in dialog.findChildren(QLabel))
    assert "NJ-LEJ-2.1.7" in text
    assert "351617-byte container" in text
    assert "Main resource：320 × 384" in text
    assert "Thumbnail resource：210 × 252" in text
    assert "Physical display geometry：UNKNOWN" in text
    assert "BIN 编辑与 GUI 上传" in text
    dialog.close()
    window.close()


def test_controller_calls_public_core_inspector(monkeypatch, tmp_path: Path) -> None:
    expected = StaticDiyInspection(
        path=tmp_path / "sample.bin",
        size=STATIC_DIY_SIZE,
        sha256="A" * 64,
        first_byte=0,
        time_position=TimePosition.TOP,
    )
    calls = []

    def fake_inspect(path):
        calls.append(path)
        return expected

    monkeypatch.setattr("ultra3_editor.gui.controllers.inspect_static_diy", fake_inspect)
    assert OfflineGuiController().load_file("sample.bin") is expected
    assert calls == ["sample.bin"]


def test_controller_maps_core_error_without_traceback() -> None:
    mapped = OfflineGuiController.user_error(UnsupportedStaticDiySizeError("technical"))
    assert mapped.title == "不支持的文件大小"
    assert "351617" in mapped.message
    assert mapped.technical_details == "technical"
    assert "Traceback" not in mapped.message


def test_only_one_primary_button_exists(qapp) -> None:
    window = make_window(qapp)
    primary = [
        button
        for button in window.findChildren(QPushButton)
        if button.objectName() == "primaryButton"
    ]
    assert primary == [window.generate_button]
    window.close()


def test_window_resizes_without_losing_required_panels(qapp) -> None:
    window = make_window(qapp)
    window.resize(1050, 680)
    qapp.processEvents()
    assert window.preview.isVisible()
    assert window.properties_scroll.isVisible()
    assert window.generate_button.isVisible()
    assert window.ble_label.isVisible()
    window.close()


def test_theme_tokens_and_focus_states_are_centralized() -> None:
    required = {
        "background_primary",
        "background_sidebar",
        "background_panel",
        "border_default",
        "text_primary",
        "text_secondary",
        "accent",
        "state_verified",
        "state_experimental",
        "state_unknown",
        "state_unsupported",
        "state_error",
    }
    assert required <= TOKENS.keys()
    assert ":focus" in _stylesheet()
    assert "QPushButton#primaryButton:disabled" in _stylesheet()


def test_stage_gate_dialog_explicitly_says_not_executed(qapp) -> None:
    window = make_window(qapp)
    dialog = window.show_stage_gate_dialog()
    qapp.processEvents()
    labels = "\n".join(label.text() for label in dialog.findChildren(QLabel))
    assert "NOT EXECUTED" in labels
    assert "Builder v0.2.4-greenlion-exact" in labels
    assert "set_time_position()" in labels
    assert any(button.text() == "关闭" for button in dialog.findChildren(QPushButton))
    dialog.close()
    window.close()


def test_error_dialog_buttons_are_localized(qapp, tmp_path: Path) -> None:
    path = tmp_path / "invalid.bin"
    path.write_bytes(b"invalid")
    window = make_window(qapp)
    assert not window.load_file(path, show_error=True)
    qapp.processEvents()
    buttons = {button.text() for button in window.last_dialog.findChildren(QPushButton)}
    assert "关闭" in buttons
    assert "查看技术详情" in buttons
    window.last_dialog.close()
    window.close()


def test_resource_tabs_select_independent_verified_canvases(qapp) -> None:
    window = make_window(qapp)
    assert window.resource_tabs.tabText(0) == "主图 320×384"
    assert window.resource_tabs.tabText(1) == "缩略图 210×252"
    assert window.preview.resource is MAIN_RESOURCE
    window.resource_tabs.setCurrentIndex(1)
    qapp.processEvents()
    assert window.preview.resource is THUMBNAIL_RESOURCE
    assert "210×252" in window.preview.accessibleName()
    window.close()


def test_resource_information_never_claims_physical_geometry(qapp) -> None:
    window = make_window(qapp)
    assert window.main_size_value.text() == "320 × 384"
    assert window.thumbnail_size_value.text() == "210 × 252"
    assert window.aspect_ratio_value.text() == "5:6"
    assert window.physical_geometry_value.text() == "UNKNOWN"
    assert window.visible_area_value.text() == "UNKNOWN"
    window.close()


def test_resource_build_controls_stay_locked_without_builder(qapp) -> None:
    window = make_window(qapp)
    assert window.main_resource_status.text() == "NOT LOADED"
    assert window.thumbnail_resource_status.text() == "NOT LOADED"
    assert all(not control.isEnabled() for control in window.resource_controls)
    assert window.fit_mode.count() == 3
    assert window.fit_mode.itemText(0) == "裁剪填充（cover）"
    assert not window.generate_button.isEnabled()
    assert not hasattr(window.controller, "build")
    window.close()


def test_preview_scaling_changes_only_display_scale(qapp) -> None:
    window = make_window(qapp)
    before = window.preview.resource
    window.preview.set_scale(1.2)
    assert window.preview.scale == 1.2
    assert window.preview.resource is before
    assert (before.width, before.height) == (320, 384)
    window.close()


def test_gui_has_no_rgb565_or_builder_reimplementation() -> None:
    source_root = ROOT / "src" / "ultra3_editor" / "gui"
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_root.glob("*.py"))
    lowered = source.lower()
    assert "rgb565" not in lowered
    assert "wire.low" not in lowered
    assert "wire.high" not in lowered
    assert "data[0] =" not in lowered


def test_gui_source_has_no_obsolete_static_diy_canvas_size() -> None:
    source_root = ROOT / "src" / "ultra3_editor" / "gui"
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_root.glob("*.py"))
    for separator in ("×", " × ", ":"):
        obsolete = "320" + separator + "505"
        assert obsolete not in source
