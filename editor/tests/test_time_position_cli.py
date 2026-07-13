from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ultra3_editor.cli import main, make_parser
from ultra3_editor.static_diy import STATIC_DIY_SIZE


def _write_static(path: Path, first_byte: int) -> Path:
    path.write_bytes(bytes([first_byte]) + bytes([0x61]) * (STATIC_DIY_SIZE - 1))
    return path


def test_cli_set_time_position_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _write_static(tmp_path / "input.bin", 0)
    output = tmp_path / "output.bin"
    json_path = tmp_path / "result.json"
    report_path = tmp_path / "result.md"

    rc = main(
        [
            "set-time-position",
            "--input",
            str(source),
            "--position",
            "bottom",
            "--output",
            str(output),
            "--json",
            str(json_path),
            "--report",
            str(report_path),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    assert "[OK] feature: set-time-position" in captured.out
    assert "[OK] container: greenlion-static" in captured.out
    assert "[OK] input position: top" in captured.out
    assert "[OK] output position: bottom" in captured.out
    assert "[OK] offset: 0x00000000" in captured.out
    assert "[OK] value: 00 -> 01" in captured.out
    assert "[OK] changed bytes: 1" in captured.out
    assert f"[OK] unchanged bytes: {STATIC_DIY_SIZE - 1}" in captured.out
    assert "[OK] exact golden match: not-applicable" in captured.out
    assert "[OK] real BLE usage: 0" in captured.out
    assert f"[OK] output SHA-256: {hashlib.sha256(output.read_bytes()).hexdigest().upper()}" in captured.out
    assert output.is_file()
    assert json_path.is_file()
    assert report_path.is_file()


def test_cli_top_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _write_static(tmp_path / "input.bin", 1)
    output = tmp_path / "output.bin"

    rc = main(
        [
            "set-time-position",
            "--input",
            str(source),
            "--position",
            "top",
            "--output",
            str(output),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    assert "[OK] input position: bottom" in captured.out
    assert "[OK] output position: top" in captured.out
    assert "[OK] value: 01 -> 00" in captured.out
    assert output.read_bytes()[0] == 0


@pytest.mark.parametrize("invalid", ("TOP", "Bottom", "0", "1", "上方", "下方"))
def test_cli_accepts_only_exact_lowercase_positions(invalid: str) -> None:
    parser = make_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(
            [
                "set-time-position",
                "--input",
                "input.bin",
                "--position",
                invalid,
                "--output",
                "output.bin",
            ]
        )
    assert exc_info.value.code != 0


def test_cli_no_change_returns_nonzero_and_writes_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_static(tmp_path / "input.bin", 0)
    output = tmp_path / "output.bin"
    rc = main(
        [
            "set-time-position",
            "--input",
            str(source),
            "--position",
            "top",
            "--output",
            str(output),
        ]
    )
    assert rc == 2
    assert "无需修改" in capsys.readouterr().err
    assert not output.exists()


def test_cli_existing_output_returns_nonzero_without_overwrite(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_static(tmp_path / "input.bin", 0)
    output = tmp_path / "output.bin"
    existing = "保留".encode("utf-8")
    output.write_bytes(existing)
    rc = main(
        [
            "set-time-position",
            "--input",
            str(source),
            "--position",
            "bottom",
            "--output",
            str(output),
        ]
    )
    assert rc == 2
    assert "已存在" in capsys.readouterr().err
    assert output.read_bytes() == existing


def test_cli_parser_requires_all_edit_arguments() -> None:
    parser = make_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["set-time-position"])
    assert exc_info.value.code != 0
