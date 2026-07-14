from __future__ import annotations

import json
from pathlib import Path

import pytest

from ultra3_uploader import cli

from .test_handoff import FIRMWARE, artifact_bytes, document_for, write_manifest


@pytest.fixture
def cli_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    artifact = tmp_path / "watchface.bin"
    artifact.write_bytes(artifact_bytes())
    manifest = write_manifest(tmp_path / "watchface.handoff.json", document_for(artifact))
    monkeypatch.chdir(tmp_path)
    return Path(manifest.name), Path(artifact.name)


def test_human_output_success(
    cli_bundle: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    manifest, _artifact = cli_bundle
    code = cli.main([
        "validate-handoff",
        "--manifest", str(manifest),
        "--target-firmware", FIRMWARE,
    ])
    assert code == 0
    output = capsys.readouterr().out
    for expected in (
        "status: valid",
        "schema: ultra3-handoff/v1",
        "artifact relative path: watchface.bin",
        "artifact size: 351617",
        "header valid: True",
        "offset 0 valid: True",
        "layout valid: True",
        "artifact unchanged: True",
        f"firmware scope: {FIRMWARE}",
        "firmware compatible: True",
        "transfer unprepared: True",
        "device evidence: C",
        "Golden status: not_applicable",
        "safe_to_prepare_transfer: True",
        "external usage:",
        "离线预检通过不表示",
    ):
        assert expected in output


def test_json_output_success_and_creates_no_file(
    cli_bundle: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    manifest, _artifact = cli_bundle
    before = {path.name for path in Path.cwd().iterdir()}
    assert cli.main([
        "validate-handoff",
        "--manifest", str(manifest),
        "--bundle-root", ".",
        "--target-firmware", FIRMWARE,
        "--json",
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "valid"
    assert result["safe_to_prepare_transfer"] is True
    assert result["artifact_path"] == "watchface.bin"
    assert all(value == 0 for value in result["external_usage"].values())
    assert {path.name for path in Path.cwd().iterdir()} == before


def test_missing_firmware_is_valid_but_not_safe(
    cli_bundle: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    manifest, _artifact = cli_bundle
    assert cli.main(["validate-handoff", "--manifest", str(manifest), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "valid"
    assert result["firmware_compatible"] is None
    assert result["safe_to_prepare_transfer"] is False
    assert "target_firmware_not_provided" in {
        issue["error_code"] for issue in result["warnings"]
    }


def test_invalid_returns_one_without_traceback(
    cli_bundle: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    manifest, _artifact = cli_bundle
    Path(manifest).write_text("{}", encoding="utf-8")
    assert cli.main(["validate-handoff", "--manifest", str(manifest)]) == 1
    captured = capsys.readouterr()
    assert "status: invalid" in captured.out
    assert "schema_validation_failed" in captured.out
    assert "Traceback" not in captured.out + captured.err


def test_json_invalid_returns_one(
    cli_bundle: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    manifest, _artifact = cli_bundle
    Path(manifest).write_text("not json", encoding="utf-8")
    assert cli.main(["validate-handoff", "--manifest", str(manifest), "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "invalid"
    assert result["errors"][0]["error_code"] == "manifest_invalid_json"


def test_missing_required_argument_exits_two() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["validate-handoff"])
    assert exc.value.code == 2


@pytest.mark.parametrize("option", ["--upload", "--device", "--force", "--payload", "--chunks", "--prepare", "--connect"])
def test_forbidden_options_are_not_exposed(option: str) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["validate-handoff", "--manifest", "x.json", option])
    assert exc.value.code == 2


def test_validate_cli_never_creates_transport(
    cli_bundle: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, _artifact = cli_bundle

    def forbidden():
        raise AssertionError("离线 Handoff 验证不得创建 Transport")

    monkeypatch.setattr(cli, "_create_real_transport", forbidden)
    assert cli.main(["validate-handoff", "--manifest", str(manifest)]) == 0
