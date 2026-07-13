from __future__ import annotations

from pathlib import Path

from ultra3_editor.gui.controllers import OfflineGuiController
from ultra3_editor.static_diy import TimePosition


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "stage8a2_gui_edit"
TOP = ROOT / "samples" / "stage7a2_diy_root_capture" / "A0_repeat_1" / "reconstructed.bin"
BOTTOM = ROOT / "samples" / "stage7a2_diy_root_capture" / "P1_time_bottom" / "reconstructed.bin"


def main() -> int:
    controller = OfflineGuiController()
    cases = (
        (TOP, TimePosition.BOTTOM, OUTPUT / "gui_top_to_bottom.bin"),
        (BOTTOM, TimePosition.TOP, OUTPUT / "gui_bottom_to_top.bin"),
    )
    targets = [
        path
        for _, _, output in cases
        for path in (output, output.with_suffix(".json"), output.with_suffix(".md"))
    ]
    existing = [path for path in targets if path.exists()]
    if existing:
        raise FileExistsError(f"拒绝覆盖已有 Stage 8A.2 产物: {existing[0]}")

    for source, target, output in cases:
        plan = controller.prepare_time_position_edit(
            controller.load_file(source),
            output,
            target,
            include_json=True,
            include_report=True,
        )
        result = controller.execute_time_position_edit(plan)
        print(
            f"[OK] {source.name}: {result.detected_input_position.value} -> "
            f"{result.output_position.value} {result.output_sha256} "
            f"exact={result.exact_golden_match}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
