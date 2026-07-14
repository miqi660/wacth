from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import QLabel

from ultra3_editor import BuildDeterminismStatus, GoldenBuildStatus
from ultra3_editor.errors import (
    BuildOutputExistsError,
    BuildRollbackError,
    UnsupportedPillowVersionError,
    UnsupportedTemplateError,
)
from ultra3_editor.gui import controllers
from ultra3_editor.gui.controllers import GreenLionGuiBuildPlan, OfflineGuiController
from ultra3_editor.gui.main_window import MainWindow


ROOT = Path(__file__).resolve().parents[2]


def _make_image(path: Path) -> Path:
    image = QImage(96, 72, QImage.Format.Format_RGB32)
    image.fill(QColor("#2D7DD2"))
    assert image.save(str(path), "PNG")
    return path


def _ready_window(qapp, tmp_path: Path) -> tuple[MainWindow, Path, Path, Path]:
    image = _make_image(tmp_path / "source.png")
    template = tmp_path / "template.bin"
    template.write_bytes(b"template selected; core validates it")
    output = tmp_path / "output.bin"
    window = MainWindow()
    window.show()
    assert window.select_builder_image(image, show_error=False)
    window.select_builder_template(template)
    window.builder_output_path.setText(str(output))
    qapp.processEvents()
    return window, image, template, output


def _fake_result(output: Path, golden: GoldenBuildStatus = GoldenBuildStatus.MATCH):
    usage = SimpleNamespace(
        hardware_initializations=0,
        hardware_scans=0,
        hardware_connections=0,
        hardware_writes=0,
        external_processes=0,
        network_operations=0,
        real_uploads=0,
    )
    return SimpleNamespace(
        output_path=output,
        output_size=351_617,
        output_sha256="A" * 64,
        builder_version="0.2.4-greenlion-exact",
        template_header_preserved=True,
        template_offset_zero=2,
        main_resource_size=(320, 384),
        thumbnail_resource_size=(210, 252),
        output_revalidated=True,
        image_unchanged=True,
        template_unchanged=True,
        determinism_status=BuildDeterminismStatus.NOT_EVALUATED,
        repeated_build_sha256=None,
        golden_status=golden,
        exact_golden_match=True if golden is GoldenBuildStatus.MATCH else None,
        external_usage=usage,
    )


def _dialog_text(window: MainWindow) -> str:
    return "\n".join(label.text() for label in window.last_dialog.findChildren(QLabel))


def test_builder_plan_is_immutable(tmp_path: Path) -> None:
    plan = OfflineGuiController().prepare_greenlion_build(
        tmp_path / "image.png",
        tmp_path / "template.bin",
        tmp_path / "output.bin",
        json_path=None,
        report_path=None,
    )
    with pytest.raises(FrozenInstanceError):
        plan.output_path = tmp_path / "other.bin"


def test_controller_execute_calls_public_core_once(monkeypatch, tmp_path: Path) -> None:
    calls = []
    expected = object()

    def fake_core(build_input, *, json_path, report_path):
        calls.append((build_input, json_path, report_path))
        return expected

    monkeypatch.setattr(controllers, "build_greenlion_static_diy", fake_core)
    plan = GreenLionGuiBuildPlan(
        tmp_path / "image.png",
        tmp_path / "template.bin",
        tmp_path / "output.bin",
        tmp_path / "output.json",
        tmp_path / "output.md",
        "fixed",
    )
    assert OfflineGuiController.execute_greenlion_build(plan) is expected
    assert len(calls) == 1
    assert calls[0][0].image_path == plan.image_path


def test_controller_and_gui_do_not_copy_builder_private_algorithms() -> None:
    gui_root = ROOT / "src" / "ultra3_editor" / "gui"
    sources = {
        path.name: path.read_text(encoding="utf-8") for path in gui_root.glob("*.py")
    }
    joined = "\n".join(sources.values())
    for forbidden in (
        "_fit_cover_exact",
        "_image_to_rgb565_le_exact",
        "_apply_greenlion_next_high",
        "Image.Resampling",
        "payload_353146",
        "1529 chunks",
        "set_time_position(",
        "Bleak",
        "FF02",
        "ultra3_uploader",
        "subprocess",
    ):
        assert forbidden not in joined
    for source in sources.values():
        tree = ast.parse(source)
        assert not any(
            isinstance(node, ast.BinOp)
            and isinstance(node.op, (ast.LShift, ast.RShift))
            for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, ast.BinOp)
            and isinstance(node.op, (ast.BitAnd, ast.BitOr))
            and any(
                isinstance(side, ast.Constant)
                and isinstance(side.value, int)
                and not isinstance(side.value, bool)
                for side in (node.left, node.right)
            )
            for node in ast.walk(tree)
        )


def test_builder_starts_not_ready_and_thumbnail_is_read_only(qapp) -> None:
    window = MainWindow()
    assert window.builder_state_badge.text() == "NOT READY"
    assert not window.builder_generate_button.isEnabled()
    assert window.thumbnail_resource_status.text() == "AUTO FROM MAIN IMAGE · 210 × 252"
    assert not window.choose_thumbnail_button.isEnabled()
    window.close()


def test_image_selection_shows_filename_format_dimensions_and_preview(qapp, tmp_path: Path) -> None:
    window = MainWindow()
    image = _make_image(tmp_path / "source.png")
    assert window.select_builder_image(image, show_error=False)
    assert window.main_resource_status.text() == "source.png"
    assert "PNG" in window.builder_image_meta.text()
    assert "96 × 72" in window.builder_image_meta.text()
    pixmap = window.builder_source_preview.pixmap()
    assert isinstance(pixmap, QPixmap) and not pixmap.isNull()
    assert "不代表最终 RGB565" in window.builder_preview_notice.text()
    window.close()


def test_template_selection_remains_validation_pending(qapp, tmp_path: Path) -> None:
    window = MainWindow()
    template = tmp_path / "template.bin"
    template.write_bytes(b"not validated by GUI")
    window.select_builder_template(template)
    assert window.builder_template_status.text() == "template.bin"
    assert window.template_status_badge.text() == "SELECTED · VALIDATION PENDING"
    window.close()


def test_exact_profile_is_fixed_and_read_only(qapp) -> None:
    window = MainWindow()
    text = window.builder_profile.text()
    for expected in (
        "GreenLion Static DIY",
        "NJ-LEJ-2.1.7",
        "320×384",
        "210×252",
        "cover",
        "bilinear",
        "truncate RGB565",
        "greenlion-next-high",
        "Pillow 10.4.0",
        "351617 bytes",
        "offset 0 preserved",
    ):
        assert expected in text
    assert not window.fit_mode.isEnabled()
    window.close()


def test_builder_requires_image_template_and_output(qapp, tmp_path: Path) -> None:
    window = MainWindow()
    output = tmp_path / "output.bin"
    window.builder_output_path.setText(str(output))
    assert not window.builder_generate_button.isEnabled()
    image = _make_image(tmp_path / "source.png")
    window.select_builder_image(image, show_error=False)
    assert not window.builder_generate_button.isEnabled()
    template = tmp_path / "template.bin"
    template.write_bytes(b"template")
    window.select_builder_template(template)
    assert window.builder_generate_button.isEnabled()
    window.close()


def test_obviously_duplicate_paths_keep_builder_disabled(qapp, tmp_path: Path) -> None:
    window, image, _, _ = _ready_window(qapp, tmp_path)
    window.builder_output_path.setText(str(image))
    assert not window.builder_generate_button.isEnabled()
    window.close()


def test_json_and_markdown_outputs_are_optional(qapp, tmp_path: Path) -> None:
    window, _, _, output = _ready_window(qapp, tmp_path)
    plan = window._current_builder_plan()
    assert plan.json_path == output.with_suffix(".json").resolve()
    assert plan.report_path == output.with_suffix(".md").resolve()
    window.builder_json_checkbox.setChecked(False)
    window.builder_report_checkbox.setChecked(False)
    plan = window._current_builder_plan()
    assert plan.json_path is None
    assert plan.report_path is None
    assert window.builder_generate_button.isEnabled()
    window.close()


def test_confirmation_cancel_calls_core_zero_times(qapp, tmp_path: Path, monkeypatch) -> None:
    window, _, _, output = _ready_window(qapp, tmp_path)
    calls = []
    monkeypatch.setattr(window, "_confirm_builder", lambda plan: False)
    monkeypatch.setattr(window.controller, "execute_greenlion_build", calls.append)
    window._generate_builder_bin()
    assert calls == []
    assert not output.exists()
    assert window.builder_state_badge.text() == "READY"
    window.close()


def test_confirmation_summary_contains_safety_boundaries(qapp, tmp_path: Path) -> None:
    window, _, _, _ = _ready_window(qapp, tmp_path)
    dialog = window.show_builder_confirmation(window._current_builder_plan())
    text = "\n".join(label.text() for label in dialog.findChildren(QLabel))
    for expected in (
        "320×384",
        "210×252",
        "351617 bytes",
        "offset 0 将保持模板值",
        "不修改时间位置",
        "不执行上传",
        "不覆盖已有文件",
    ):
        assert expected in text
    dialog.close()
    window.close()


@pytest.mark.parametrize(
    ("golden", "expected"),
    (
        (GoldenBuildStatus.MATCH, "VERIFIED GOLDEN MATCH"),
        (GoldenBuildStatus.NOT_APPLICABLE, "CUSTOM VALID BUILD"),
    ),
)
def test_success_displays_builder_result_and_isolation(
    qapp, tmp_path: Path, monkeypatch, golden, expected
) -> None:
    window, _, _, output = _ready_window(qapp, tmp_path)
    output.write_bytes(b"result")
    calls = []

    def execute(plan):
        calls.append(plan)
        return _fake_result(output, golden)

    monkeypatch.setattr(window, "_confirm_builder", lambda plan: True)
    monkeypatch.setattr(window.controller, "execute_greenlion_build", execute)
    monkeypatch.setattr(
        window.controller,
        "execute_time_position_edit",
        lambda plan: pytest.fail("Builder 不得调用时间位置核心"),
    )
    window._generate_builder_bin()
    text = _dialog_text(window)
    assert len(calls) == 1
    assert expected in text
    assert "351617" in text
    assert "Template offset 0：02" in text
    assert "NOT_EVALUATED" in text
    assert "None / Not evaluated" in text
    assert "offset 0=02" in text
    assert "00/01 时间位置编辑流程" in text
    assert window.current_info is None
    assert window.builder_state_badge.text() == "COMPLETE"
    window.last_dialog.close()
    window.close()


@pytest.mark.parametrize(
    ("error", "expected"),
    (
        (UnsupportedPillowVersionError("wrong"), "Pillow 10.4.0"),
        (UnsupportedTemplateError("bad template"), "17 字节头"),
        (BuildOutputExistsError("exists"), "不提供覆盖"),
    ),
)
def test_known_builder_errors_are_mapped_and_restore_ready(
    qapp, tmp_path: Path, monkeypatch, error, expected
) -> None:
    window, _, _, _ = _ready_window(qapp, tmp_path)
    monkeypatch.setattr(window, "_confirm_builder", lambda plan: True)
    monkeypatch.setattr(
        window.controller,
        "execute_greenlion_build",
        lambda plan: (_ for _ in ()).throw(error),
    )
    window._generate_builder_bin()
    assert window._busy is False
    assert window.builder_generate_button.isEnabled()
    assert window.builder_state_badge.text() == "ERROR"
    assert window.status_label.text() == "ERROR · No output created · BLE usage: 0"
    assert expected in _dialog_text(window)
    window.last_dialog.close()
    window.close()


def test_rollback_error_preserves_failed_cleanup_paths(qapp, tmp_path: Path, monkeypatch) -> None:
    window, _, _, _ = _ready_window(qapp, tmp_path)
    leftover = tmp_path / "unfinished.bin"
    error = BuildRollbackError(RuntimeError("write failed"), (leftover,))
    monkeypatch.setattr(window, "_confirm_builder", lambda plan: True)
    monkeypatch.setattr(
        window.controller,
        "execute_greenlion_build",
        lambda plan: (_ for _ in ()).throw(error),
    )
    window._generate_builder_bin()
    detail = window.last_dialog.detailedText()
    assert "可能存在未完成文件" in _dialog_text(window)
    assert str(leftover) in detail
    assert "RuntimeError" in detail
    window.last_dialog.close()
    window.close()


def test_unexpected_exception_restores_builder_state(qapp, tmp_path: Path, monkeypatch) -> None:
    window, _, _, output = _ready_window(qapp, tmp_path)
    calls = 0

    def explode(plan):
        nonlocal calls
        calls += 1
        raise RuntimeError("模拟 Builder 意外异常")

    monkeypatch.setattr(window, "_confirm_builder", lambda plan: True)
    monkeypatch.setattr(window.controller, "execute_greenlion_build", explode)
    window._generate_builder_bin()
    assert calls == 1
    assert window._busy is False
    assert window.builder_last_result is None
    assert window.builder_generate_button.isEnabled()
    assert window.builder_state_badge.text() == "ERROR"
    assert window.status_label.text() == "ERROR · No output created · BLE usage: 0"
    assert not output.exists()
    assert "发生未预期错误" in window.builder_last_error
    assert "RuntimeError" in window.last_dialog.detailedText()
    assert "模拟 Builder 意外异常" in window.last_dialog.detailedText()
    window.last_dialog.close()
    window.close()


def test_builder_success_does_not_replace_loaded_time_position_file(
    qapp, tmp_path: Path, monkeypatch
) -> None:
    top = ROOT / "samples" / "stage7a2_diy_root_capture" / "A0_repeat_1" / "reconstructed.bin"
    window, _, _, output = _ready_window(qapp, tmp_path)
    assert window.load_file(top, show_error=False)
    original = window.current_info
    output.write_bytes(b"result")
    monkeypatch.setattr(window, "_confirm_builder", lambda plan: True)
    monkeypatch.setattr(
        window.controller,
        "execute_greenlion_build",
        lambda plan: _fake_result(output),
    )
    window._generate_builder_bin()
    assert window.current_info is original
    assert window.current_info.path == top.resolve()
    window.last_dialog.close()
    window.close()


def test_builder_result_sha_is_copyable(qapp, tmp_path: Path, monkeypatch) -> None:
    window, _, _, output = _ready_window(qapp, tmp_path)
    result = _fake_result(output)
    monkeypatch.setattr(window, "_confirm_builder", lambda plan: True)
    monkeypatch.setattr(window.controller, "execute_greenlion_build", lambda plan: result)
    window._generate_builder_bin()
    window._copy_builder_output_sha()
    from PyQt6.QtGui import QGuiApplication

    assert QGuiApplication.clipboard().text() == "A" * 64
    window.last_dialog.close()
    window.close()


def test_controller_builder_errors_preserve_structured_fields(tmp_path: Path) -> None:
    leftover = tmp_path / "leftover.bin"
    error = BuildRollbackError(ValueError("original"), (leftover,))
    mapped = OfflineGuiController.user_error(error)
    assert mapped.error_code == "build_rollback_error"
    assert mapped.path == leftover
    assert mapped.failed_cleanup_paths == (leftover,)
    assert mapped.original_error_type == "ValueError"
    assert mapped.original_error_message == "original"
    assert "failed_cleanup_paths" in mapped.technical_details
