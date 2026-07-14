from __future__ import annotations

import json
from pathlib import Path

from ultra3_uploader.cli import main


def _container() -> bytes:
    return bytes(range(256)) * 1373 + bytes(range(129))


def test_build_fixed_static_plan_cli(tmp_path: Path, capsys) -> None:
    source = tmp_path / "watchface.bin"
    source.write_bytes(_container())
    output = tmp_path / "transfer_plan"
    assert main([
        "build-fixed-static-plan",
        "--source", str(source),
        "--output", str(output),
        "--profile", "njlej-2.1.7-fixed-static",
        "--json",
    ]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["verification"]["result"] == "PASS"
    assert document["write_order"] == "C8 -> C9[0..1528] -> CA"
    assert (output / "c8.bin").read_bytes().hex().upper() == "BCC8020701815D0500F905E2"
    assert (output / "ca.bin").read_bytes().hex().upper() == "BCCA02010505"
    assert (output / "c9_frames.bin").stat().st_size == 362320
    assert (output / "full_transfer_stream.bin").stat().st_size == 362338


def test_build_fixed_static_plan_cli_rejects_wrong_size(
    tmp_path: Path, capsys
) -> None:
    source = tmp_path / "watchface.bin"
    source.write_bytes(b"X" * 351616)
    assert main([
        "build-fixed-static-plan",
        "--source", str(source),
        "--output", str(tmp_path / "plan"),
    ]) == 2
    assert "static_container 大小错误" in capsys.readouterr().err
    assert not (tmp_path / "plan").exists()


def test_fixed_static_cli_has_no_ble_arguments() -> None:
    from ultra3_uploader.cli import make_parser

    parser = make_parser()
    help_text = parser._subparsers._group_actions[0].choices[
        "build-fixed-static-plan"
    ].format_help()
    assert "--device" not in help_text
    assert "--scan" not in help_text
    assert "--connect" not in help_text
