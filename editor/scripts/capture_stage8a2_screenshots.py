from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog

from ultra3_editor.gui.app import create_application
from ultra3_editor.gui.main_window import MainWindow
from ultra3_editor.static_diy import STATIC_DIY_SIZE


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "stage8a2_gui" / "screenshots"
TOP = ROOT / "samples" / "stage7a2_diy_root_capture" / "A0_repeat_1" / "reconstructed.bin"
SHOTS = (
    "top_loaded_ready.png",
    "bottom_selected_ready.png",
    "output_path_selected.png",
    "export_confirmation_active.png",
    "export_success_golden.png",
    "export_success_custom.png",
    "output_exists_error.png",
    "same_path_error.png",
    "no_change_disabled.png",
    "builder_still_unavailable.png",
    "unsupported_features.png",
    "about_stage8a2.png",
)


def save(widget, name: str, app) -> None:
    if isinstance(widget, QDialog):
        widget.adjustSize()
    widget.show()
    QTest.qWait(100)
    widget.repaint()
    QTest.qWait(50)
    app.processEvents()
    path = OUTPUT / name
    if path.exists():
        raise FileExistsError(f"拒绝覆盖截图: {path}")
    image = QPixmap(widget.size())
    widget.render(image)
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"无法保存截图: {path}")


def prepare_changed(window: MainWindow, output: str | Path) -> None:
    window.load_file(TOP, show_error=False)
    window.bottom_radio.click()
    window.output_path.setText(str(output))


def capture_one(name: str) -> int:
    app = create_application([])
    window = MainWindow()
    target = window
    temp = tempfile.TemporaryDirectory()
    temp_path = Path(temp.name)
    try:
        if name in ("top_loaded_ready.png", "no_change_disabled.png"):
            window.load_file(TOP, show_error=False)
        elif name == "bottom_selected_ready.png":
            window.load_file(TOP, show_error=False)
            window.bottom_radio.click()
        elif name == "output_path_selected.png":
            prepare_changed(window, "greenlion_bottom.bin")
        elif name == "export_confirmation_active.png":
            prepare_changed(window, "greenlion_bottom.bin")
            target = window.show_export_confirmation(window._current_plan())
        elif name == "export_success_golden.png":
            prepare_changed(window, temp_path / "golden_bottom.bin")
            window._confirm_export = lambda plan: True
            window._generate_new_bin()
            target = window.last_dialog
        elif name == "export_success_custom.png":
            custom = temp_path / "custom_valid.bin"
            custom.write_bytes(b"\x00" + bytes([0x5A]) * (STATIC_DIY_SIZE - 1))
            window.load_file(custom, show_error=False)
            window.bottom_radio.click()
            window.output_path.setText(str(temp_path / "custom_bottom.bin"))
            window.json_checkbox.setChecked(False)
            window.markdown_checkbox.setChecked(False)
            window._confirm_export = lambda plan: True
            window._generate_new_bin()
            target = window.last_dialog
        elif name == "output_exists_error.png":
            existing = temp_path / "existing.bin"
            existing.write_text("保留", encoding="utf-8")
            prepare_changed(window, existing)
            window._confirm_export = lambda plan: True
            window._generate_new_bin()
            target = window.last_dialog
        elif name == "same_path_error.png":
            prepare_changed(window, TOP)
            window._confirm_export = lambda plan: True
            window._generate_new_bin()
            target = window.last_dialog
        elif name == "builder_still_unavailable.png":
            window.load_file(TOP, show_error=False)
            window.show()
            QTest.qWait(50)
            window.properties_scroll.ensureWidgetVisible(window.builder_generate_button)
        elif name == "unsupported_features.png":
            window.load_file(TOP, show_error=False)
            window.show()
            QTest.qWait(50)
            window.properties_scroll.ensureWidgetVisible(window.scope_card)
        elif name == "about_stage8a2.png":
            window.show()
            QTest.qWait(50)
            target = window.show_about_dialog()

        save(target, name, app)
        if target is not window:
            target.close()
        window.close()
        return 0
    finally:
        temp.cleanup()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shot", choices=SHOTS)
    args = parser.parse_args(argv)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if args.shot:
        return capture_one(args.shot)
    environment = os.environ.copy()
    source = str(ROOT / "src")
    environment["PYTHONPATH"] = source + os.pathsep + environment.get("PYTHONPATH", "")
    for name in SHOTS:
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--shot", name],
            check=True,
            cwd=ROOT,
            env=environment,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
