from __future__ import annotations

import builtins
import json
from pathlib import Path

from ultra3_editor.cli import main


def test_inspect_json_supports_hex_offset(
    valid_file: Path,
    capsys,
) -> None:
    assert main([
        "inspect",
        str(valid_file),
        "--offset",
        "0x10",
        "--context",
        "2",
        "--json",
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["selected_offset"] == 16
    assert report["file"]["valid"]


def test_diff_terminal_output_is_range_limited(
    tmp_path: Path,
    valid_data: bytes,
    capsys,
) -> None:
    before = tmp_path / "before.bin"
    after = tmp_path / "after.bin"
    changed = bytearray(valid_data)
    changed[10] ^= 1
    changed[20] ^= 1
    before.write_bytes(valid_data)
    after.write_bytes(changed)
    assert main([
        "diff",
        str(before),
        str(after),
        "--max-ranges",
        "1",
    ]) == 0
    output = capsys.readouterr().out
    assert "Changed bytes: 2" in output
    assert "... 1 ranges omitted" in output


def test_existing_second_output_prevents_all_report_creation(
    tmp_path: Path,
    valid_data: bytes,
) -> None:
    before = tmp_path / "before.bin"
    after = tmp_path / "after.bin"
    json_path = tmp_path / "new.json"
    report_path = tmp_path / "existing.md"
    before.write_bytes(valid_data)
    after.write_bytes(valid_data)
    report_path.write_text("keep", encoding="utf-8")
    assert main([
        "diff",
        str(before),
        str(after),
        "--json",
        str(json_path),
        "--report",
        str(report_path),
    ]) == 2
    assert not json_path.exists()
    assert report_path.read_text(encoding="utf-8") == "keep"


def test_editor_commands_never_import_bleak(
    valid_file: Path,
    monkeypatch,
) -> None:
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "bleak" or name.startswith("bleak."):
            raise AssertionError("editor 不得导入 Bleak")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    assert main(["inspect", str(valid_file)]) == 0
    assert main(["diff", str(valid_file), str(valid_file)]) == 0


def test_editor_source_has_no_ble_operations() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "ultra3_editor"
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_root.glob("*.py"))
    for forbidden in (
        "BleakClient",
        "BleakScanner",
        "write_without_response",
        "FF02_UUID",
        "async def scan",
        "async def connect",
    ):
        assert forbidden not in source
