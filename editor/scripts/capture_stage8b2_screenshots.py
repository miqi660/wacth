from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog

from ultra3_editor.errors import BuildRollbackError
from ultra3_editor.gui.app import create_application
from ultra3_editor.gui.controllers import OfflineGuiController
from ultra3_editor.gui.main_window import MainWindow


ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS = ROOT / "artifacts" / "stage8b2_gui" / "screenshots"
BUILDS = ROOT / "artifacts" / "stage8b2_gui_builder"
SHOTS = (
    "builder_initial.png",
    "image_selected.png",
    "source_preview_notice.png",
    "template_selected_pending.png",
    "exact_profile.png",
    "ready_to_build.png",
    "confirmation.png",
    "golden_match_success.png",
    "custom_not_applicable_success.png",
    "template_error.png",
    "rollback_error.png",
    "unexpected_error_recovered.png",
    "time_position_separation_notice.png",
)


def baseline_paths(baseline: Path) -> tuple[Path, Path]:
    image = baseline / "evidence" / "local_additions" / "test_photos" / "1.JPG"
    template = baseline / "sample" / "official_calibration_351617.bin"
    if not image.is_file() or not template.is_file():
        raise FileNotFoundError("冻结图片或模板不存在")
    return image, template


def make_custom_image(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"拒绝覆盖自定义输入: {path}")
    image = QImage(420, 300, QImage.Format.Format_RGB32)
    image.fill(QColor("#16324F"))
    for y in range(40, 260):
        color = QColor(35 + y // 3, 90, 180 - y // 5)
        for x in range(80, 340):
            image.setPixelColor(x, y, color)
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"无法创建离线自定义输入: {path}")


def generate_artifacts(baseline: Path) -> int:
    if BUILDS.exists():
        raise FileExistsError(f"拒绝覆盖 Builder 证据目录: {BUILDS}")
    BUILDS.mkdir(parents=True)
    golden_image, template = baseline_paths(baseline)
    custom_image = BUILDS / "custom_input.png"
    make_custom_image(custom_image)
    controller = OfflineGuiController()
    plans = (
        controller.prepare_greenlion_build(
            golden_image,
            template,
            BUILDS / "golden_match.bin",
            json_path=BUILDS / "golden_match.json",
            report_path=BUILDS / "golden_match.md",
        ),
        controller.prepare_greenlion_build(
            custom_image,
            template,
            BUILDS / "custom_not_applicable.bin",
            json_path=BUILDS / "custom_not_applicable.json",
            report_path=BUILDS / "custom_not_applicable.md",
        ),
    )
    for plan in plans:
        result = controller.execute_greenlion_build(plan)
        print(
            f"{result.output_path.name}: {result.output_sha256} "
            f"golden={result.golden_status.value} offset0={result.template_offset_zero:02X}"
        )
    return 0


def save(widget, name: str, app) -> None:
    if isinstance(widget, QDialog):
        widget.adjustSize()
    widget.show()
    QTest.qWait(100)
    widget.repaint()
    app.processEvents()
    path = SCREENSHOTS / name
    if path.exists():
        raise FileExistsError(f"拒绝覆盖截图: {path}")
    image = QPixmap(widget.size())
    widget.render(image)
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"无法保存截图: {path}")


def prepare_ready(window: MainWindow, image: Path, template: Path, output: str) -> None:
    window.select_builder_image(image, show_error=False)
    window.select_builder_template(template)
    window.builder_output_path.setText(output)


def capture_one(name: str, baseline: Path) -> int:
    app = create_application([])
    image, template = baseline_paths(baseline)
    window = MainWindow()
    window.resize(1360, 900)
    target = window
    temp = tempfile.TemporaryDirectory()
    temp_path = Path(temp.name)
    try:
        if name == "builder_initial.png":
            window.properties_scroll.ensureWidgetVisible(window.builder_state_badge)
        elif name == "image_selected.png":
            window.select_builder_image(image, show_error=False)
            window.properties_scroll.ensureWidgetVisible(window.builder_source_preview)
        elif name == "source_preview_notice.png":
            window.select_builder_image(image, show_error=False)
            window.properties_scroll.ensureWidgetVisible(window.builder_preview_notice)
        elif name == "template_selected_pending.png":
            window.select_builder_image(image, show_error=False)
            window.select_builder_template(template)
            window.properties_scroll.ensureWidgetVisible(window.template_status_badge)
        elif name == "exact_profile.png":
            window.select_builder_image(image, show_error=False)
            window.select_builder_template(template)
            window.properties_scroll.ensureWidgetVisible(window.builder_profile)
        elif name == "ready_to_build.png":
            prepare_ready(window, image, template, "stage8b2_preview.bin")
            window.properties_scroll.ensureWidgetVisible(window.builder_generate_button)
        elif name == "confirmation.png":
            prepare_ready(window, image, template, "stage8b2_preview.bin")
            target = window.show_builder_confirmation(window._current_builder_plan())
        elif name in (
            "golden_match_success.png",
            "time_position_separation_notice.png",
        ):
            output = temp_path / "golden_match.bin"
            prepare_ready(window, image, template, str(output))
            window._confirm_builder = lambda plan: True
            window._generate_builder_bin()
            target = window.last_dialog
        elif name == "custom_not_applicable_success.png":
            custom = temp_path / "custom.png"
            make_custom_image(custom)
            prepare_ready(window, custom, template, str(temp_path / "custom.bin"))
            window._confirm_builder = lambda plan: True
            window._generate_builder_bin()
            target = window.last_dialog
        elif name == "template_error.png":
            invalid = temp_path / "invalid_template.bin"
            invalid.write_bytes(b"invalid")
            prepare_ready(window, image, invalid, str(temp_path / "rejected.bin"))
            window._confirm_builder = lambda plan: True
            window._generate_builder_bin()
            target = window.last_dialog
        elif name == "rollback_error.png":
            prepare_ready(window, image, template, str(temp_path / "rollback.bin"))
            window._confirm_builder = lambda plan: True
            error = BuildRollbackError(
                RuntimeError("模拟写后复核失败"),
                (Path("unfinished_stage8b2.bin"),),
            )
            window.controller.execute_greenlion_build = lambda plan: (_ for _ in ()).throw(error)
            window._generate_builder_bin()
            target = window.last_dialog
        elif name == "unexpected_error_recovered.png":
            prepare_ready(window, image, template, str(temp_path / "unexpected.bin"))
            window._confirm_builder = lambda plan: True
            window.controller.execute_greenlion_build = lambda plan: (_ for _ in ()).throw(
                RuntimeError("模拟 Builder 意外异常")
            )
            window._generate_builder_bin()
            target = window.last_dialog

        save(target, name, app)
        if target is not window:
            target.close()
        window.close()
        return 0
    finally:
        temp.cleanup()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--shot", choices=SHOTS)
    parser.add_argument("--generate-artifacts", action="store_true")
    args = parser.parse_args(argv)
    baseline = args.baseline.resolve()
    if args.generate_artifacts:
        return generate_artifacts(baseline)
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    if args.shot:
        return capture_one(args.shot, baseline)
    environment = os.environ.copy()
    source = str(ROOT / "src")
    environment["PYTHONPATH"] = source + os.pathsep + environment.get("PYTHONPATH", "")
    for name in SHOTS:
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--baseline",
                str(baseline),
                "--shot",
                name,
            ],
            check=True,
            cwd=ROOT,
            env=environment,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
