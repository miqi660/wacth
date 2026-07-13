from __future__ import annotations

from pathlib import Path

import pytest

from ultra3_uploader import cli
from ultra3_uploader.bcsdial import BCSDIALPayload


def watchface(tmp_path: Path) -> Path:
    path = tmp_path / "watchface.bin"
    path.write_bytes(b"BCSDIAL" + b"\x00" * 489 + b"BCBC")
    return path


def base_args(path: Path, log: Path) -> list[str]:
    return [
        "upload-bcsdial",
        "--device",
        "REAL-STUB",
        "--file",
        str(path),
        "--packet-delay-ms",
        "45",
        "--expected-sha256",
        BCSDIALPayload.from_path(path).sha256,
        "--confirm-real-upload",
        "--log-file",
        str(log),
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_confirm",
        "missing_sha",
        "invalid_sha",
        "mismatch_sha",
        "wrong_delay",
        "existing_log",
    ],
)
def test_cli_local_gate_rejects_before_transport_factory(
    mutation: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = watchface(tmp_path)
    log = tmp_path / "real.jsonl"
    args = base_args(path, log)
    if mutation == "missing_confirm":
        args.remove("--confirm-real-upload")
    elif mutation == "missing_sha":
        index = args.index("--expected-sha256")
        del args[index:index + 2]
    elif mutation == "invalid_sha":
        args[args.index("--expected-sha256") + 1] = "XYZ"
    elif mutation == "mismatch_sha":
        args[args.index("--expected-sha256") + 1] = "0" * 64
    elif mutation == "wrong_delay":
        args[args.index("--packet-delay-ms") + 1] = "44"
    else:
        log.write_text("keep", encoding="utf-8")

    factory_calls = 0

    def forbidden_factory():
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("本地安全门失败时不得创建 Transport")

    monkeypatch.setattr(cli, "_create_real_transport", forbidden_factory)
    assert cli.main(args) == 2
    assert factory_calls == 0
    if mutation == "existing_log":
        assert log.read_text(encoding="utf-8") == "keep"


def test_dry_run_has_no_factory_and_creates_no_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = watchface(tmp_path)
    log = tmp_path / "must-not-exist.jsonl"

    def forbidden_factory():
        raise AssertionError("dry-run 不得创建 Transport")

    monkeypatch.setattr(cli, "_create_real_transport", forbidden_factory)
    assert cli.main([
        "upload-bcsdial",
        "--file",
        str(path),
        "--log-file",
        str(log),
        "--dry-run",
    ]) == 0
    output = capsys.readouterr().out
    assert f"[OK] SHA-256: {BCSDIALPayload.from_path(path).sha256}" in output
    assert "[OK] real BLE connections: 0" in output
    assert "[OK] FF02 writes: 0" in output
    assert not log.exists()
