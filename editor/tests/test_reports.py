from __future__ import annotations

import json
from pathlib import Path

import pytest

from ultra3_editor.differ import diff_bcsdial
from ultra3_editor.errors import ReportExistsError
from ultra3_editor.inspector import inspect_bcsdial
from ultra3_editor.reports import (
    write_inspection_report,
    write_json_report,
    write_markdown_report,
)


def changed_pair(tmp_path: Path, valid_data: bytes):
    before = tmp_path / "before.bin"
    after = tmp_path / "after.bin"
    changed = bytearray(valid_data)
    changed[12] ^= 1
    before.write_bytes(valid_data)
    after.write_bytes(changed)
    return diff_bcsdial(before, after, context=2)


def test_json_report_contains_complete_diff(
    tmp_path: Path,
    valid_data: bytes,
) -> None:
    result = changed_pair(tmp_path, valid_data)
    output = tmp_path / "artifacts" / "diff.json"
    write_json_report(result, output)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["changed_byte_count"] == 1
    assert report["range_count"] == 1
    assert report["ranges"][0]["start"] == 12
    assert report["ranges"][0]["before_context_hex"]


def test_markdown_report_contains_range_and_safety_notes(
    tmp_path: Path,
    valid_data: bytes,
) -> None:
    result = changed_pair(tmp_path, valid_data)
    output = tmp_path / "diff.md"
    write_markdown_report(result, output)
    report = output.read_text(encoding="utf-8")
    assert "Changed bytes: `1`" in report
    assert "0x0000000C" in report
    assert "Frozen changes = 0" in report
    assert "Stage 7A-2 样本矩阵" in report


@pytest.mark.parametrize("writer", [write_json_report, write_markdown_report])
def test_existing_report_is_never_overwritten(
    writer,
    tmp_path: Path,
    valid_data: bytes,
) -> None:
    result = changed_pair(tmp_path, valid_data)
    output = tmp_path / "existing.out"
    output.write_text("keep", encoding="utf-8")
    with pytest.raises(ReportExistsError):
        writer(result, output)
    assert output.read_text(encoding="utf-8") == "keep"


def test_inspection_markdown_report_is_created_exclusively(
    valid_file: Path,
    tmp_path: Path,
) -> None:
    output = tmp_path / "inspect.md"
    write_inspection_report(inspect_bcsdial(valid_file, offset=5), output)
    assert "BCSDIAL Inspection Report" in output.read_text(encoding="utf-8")
    with pytest.raises(ReportExistsError):
        write_inspection_report(inspect_bcsdial(valid_file), output)
