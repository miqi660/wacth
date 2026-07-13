from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ultra3_editor.gui.app import create_application
from ultra3_editor.gui.main_window import MainWindow
from PyQt6.QtGui import QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "stage8a_gui" / "screenshots"
TOP = ROOT / "samples" / "stage7a2_diy_root_capture" / "A0_repeat_1" / "reconstructed.bin"
BOTTOM = ROOT / "samples" / "stage7a2_diy_root_capture" / "P1_time_bottom" / "reconstructed.bin"
SHOTS = (
    "empty_state.png",
    "top_loaded.png",
    "bottom_selected.png",
    "thumbnail_resource.png",
    "export_confirmation.png",
    "export_success.png",
    "invalid_file_error.png",
    "unsupported_features.png",
    "about_scope.png",
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


def capture_one(name: str) -> int:
    app = create_application([])
    window = MainWindow()
    target = window
    if name == "top_loaded.png":
        window.load_file(TOP, show_error=False)
    elif name == "bottom_selected.png":
        window.load_file(BOTTOM, show_error=False)
    elif name == "thumbnail_resource.png":
        window.load_file(TOP, show_error=False)
        window.show()
        QTest.qWait(50)
        window.resource_tabs.setCurrentIndex(1)
        window.hide()
        QTest.qWait(20)
        window.show()
    elif name in ("export_confirmation.png", "export_success.png"):
        window.show()
        QTest.qWait(50)
        title = "导出确认 · 功能已锁定" if name.startswith("export_confirmation") else "导出结果 · 未执行"
        target = window.show_stage_gate_dialog(title)
    elif name == "invalid_file_error.png":
        window.show()
        QTest.qWait(50)
        with tempfile.TemporaryDirectory() as temp:
            invalid = Path(temp) / "invalid.bin"
            invalid.write_bytes(b"invalid")
            window.load_file(invalid, show_error=True)
            target = window.last_dialog
            save(target, name, app)
        target.close()
        window.close()
        return 0
    elif name == "unsupported_features.png":
        window.load_file(TOP, show_error=False)
        window.show()
        QTest.qWait(50)
        window.properties_scroll.ensureWidgetVisible(window.scope_card)
        window.hide()
        QTest.qWait(20)
        window.show()
        target = window.properties_scroll
    elif name == "about_scope.png":
        window.show()
        QTest.qWait(50)
        target = window.show_about_dialog()

    save(target, name, app)
    if target is not window:
        target.close()
    window.close()
    return 0


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
