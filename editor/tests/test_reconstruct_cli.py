from __future__ import annotations

import builtins
import hashlib
import json
from pathlib import Path

from reconstruction_helpers import build_c8, frames_for, payload, write_hex_lines
from ultra3_editor.cli import main


def test_success_writes_bin_json_and_markdown_exclusively(tmp_path: Path) -> None:
    data = payload(500)
    capture = write_hex_lines(tmp_path / "capture.log", frames_for(data))
    output = tmp_path / "out" / "reconstructed.bin"
    json_path = tmp_path / "out" / "reconstruction.json"
    report_path = tmp_path / "out" / "reconstruction.md"
    assert main([
        "reconstruct-c9",
        str(capture),
        "--format",
        "auto",
        "--output",
        str(output),
        "--json",
        str(json_path),
        "--report",
        str(report_path),
    ]) == 0
    assert output.read_bytes() == data
    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["status"] == "COMPLETE"
    assert report["actual_packet_count"] == 3
    assert report["first_sequence"] == 0
    assert report["last_sequence"] == 2
    assert report["checksum_passed"] == 3
    assert "Real BLE usage" in report_path.read_text(encoding="utf-8")


def test_existing_output_prevents_all_writes(tmp_path: Path) -> None:
    data = payload(20)
    capture = write_hex_lines(tmp_path / "capture.log", frames_for(data))
    output = tmp_path / "existing.bin"
    json_path = tmp_path / "new.json"
    output.write_bytes(b"keep")
    assert main([
        "reconstruct-c9",
        str(capture),
        "--output",
        str(output),
        "--json",
        str(json_path),
    ]) == 2
    assert output.read_bytes() == b"keep"
    assert not json_path.exists()


def test_failed_session_never_writes_bin_but_can_write_diagnostics(
    tmp_path: Path,
) -> None:
    data = payload(20)
    capture = write_hex_lines(tmp_path / "failed.log", [build_c8(data)])
    output = tmp_path / "must-not-exist.bin"
    json_path = tmp_path / "failed.json"
    report_path = tmp_path / "failed.md"
    assert main([
        "reconstruct-c9",
        str(capture),
        "--output",
        str(output),
        "--json",
        str(json_path),
        "--report",
        str(report_path),
    ]) == 2
    assert not output.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "FAILED"
    assert "Status: `FAILED`" in report_path.read_text(encoding="utf-8")


def test_input_capture_content_is_unchanged(tmp_path: Path) -> None:
    data = payload(20)
    capture = write_hex_lines(tmp_path / "capture.log", frames_for(data))
    digest = hashlib.sha256(capture.read_bytes()).hexdigest()
    assert main(["reconstruct-c9", str(capture)]) == 0
    assert hashlib.sha256(capture.read_bytes()).hexdigest() == digest


def test_reconstruct_never_imports_bleak(tmp_path: Path, monkeypatch) -> None:
    data = payload(20)
    capture = write_hex_lines(tmp_path / "capture.log", frames_for(data))
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "bleak" or name.startswith("bleak."):
            raise AssertionError("reconstruct-c9 不得导入 Bleak")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    assert main(["reconstruct-c9", str(capture)]) == 0


def test_editor_source_contains_no_ble_operations() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "ultra3_editor"
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_root.glob("*.py"))
    for forbidden in (
        "BleakClient",
        "BleakScanner",
        "write_without_response",
        "async def scan",
        "async def connect",
    ):
        assert forbidden not in source
