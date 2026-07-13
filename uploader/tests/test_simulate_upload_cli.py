from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from ultra3_uploader.bcsdial import BCSDIALPayload
from ultra3_uploader.cli import main
from ultra3_uploader.errors import UploadSafetyError
from ultra3_uploader.upload_bcsdial import upload_bcsdial


def watchface(tmp_path: Path) -> Path:
    path = tmp_path / "watchface.bin"
    path.write_bytes(b"BCSDIAL" + b"\x00" * 489 + b"BCBC")
    return path


def test_simulate_cli_uses_fake_only_and_writes_jsonl(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from ultra3_uploader import bleak_transport

    class ForbiddenBleakTransport:
        def __init__(self) -> None:
            raise AssertionError("simulate CLI 不得初始化 BleakTransport")

    monkeypatch.setattr(bleak_transport, "BleakTransport", ForbiddenBleakTransport)
    path = watchface(tmp_path)
    log = tmp_path / "simulation.jsonl"
    code = main([
        "simulate-upload-bcsdial",
        "--file", str(path),
        "--packet-delay-ms", "45",
        "--log-file", str(log),
    ])
    assert code == 0
    output = capsys.readouterr().out
    assert "C8 writes: 1" in output
    assert "C9 writes: 3" in output
    assert "CA writes: 1" in output
    assert "real BLE connections: 0" in output

    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    writes = [record for record in records if record["event"] == "write"]
    assert [record["command"] for record in writes] == ["C8", "C9", "C9", "C9", "CA"]


def test_simulate_cli_refuses_existing_log_without_force(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = watchface(tmp_path)
    log = tmp_path / "existing.jsonl"
    log.write_text("keep", encoding="utf-8")
    code = main([
        "simulate-upload-bcsdial", "--file", str(path), "--log-file", str(log)
    ])
    assert code == 2
    assert log.read_text(encoding="utf-8") == "keep"
    assert "使用 --force" in capsys.readouterr().err


def test_simulate_cli_force_replaces_existing_log(tmp_path: Path) -> None:
    path = watchface(tmp_path)
    log = tmp_path / "existing.jsonl"
    log.write_text("old", encoding="utf-8")
    assert main([
        "simulate-upload-bcsdial",
        "--file", str(path),
        "--log-file", str(log),
        "--force",
    ]) == 0
    assert not log.read_text(encoding="utf-8").startswith("old")


def test_real_upload_cli_is_locked_but_dry_run_is_available(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = watchface(tmp_path)
    assert main(["upload-bcsdial", "--file", str(path)]) == 2
    assert "does not permit real BLE upload" in capsys.readouterr().err
    assert main(["upload-bcsdial", "--file", str(path), "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "真实 BLE 连接: 0" in output
    assert "FF02 writes: 0" in output


def test_upload_function_rejects_non_fake_transport() -> None:
    value = BCSDIALPayload(b"BCSDIALBCBC")
    with pytest.raises(UploadSafetyError, match="does not permit real BLE upload"):
        asyncio.run(upload_bcsdial(object(), value))  # type: ignore[arg-type]

