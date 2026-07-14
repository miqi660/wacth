from __future__ import annotations

import json
from pathlib import Path

from ultra3_uploader.cli import main

from .static_transfer_fixtures import FIRMWARE, make_static_bundle


def test_static_plan_cli_build_inspect_verify(tmp_path: Path, capsys) -> None:
    manifest, payload, digest = make_static_bundle(tmp_path)
    output = tmp_path / "plan"
    assert main([
        "build-static-plan",
        "--manifest", str(manifest),
        "--payload", str(payload),
        "--expected-payload-sha256", digest,
        "--bundle-root", str(tmp_path),
        "--target-firmware", FIRMWARE,
        "--output", str(output),
        "--json",
    ]) == 0
    built = json.loads(capsys.readouterr().out)
    assert built["result"] == "PASS"
    assert built["c9_frame_count"] == 1529

    assert main(["inspect-static-plan", "--plan", str(output), "--json"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["format"] == "ultra3-static-transfer-plan/v1"
    assert inspected["payload"]["size"] == 353146

    assert main(["verify-static-plan", "--plan", str(output), "--json"]) == 0
    verified = json.loads(capsys.readouterr().out)
    assert list(verified) == [
        "result",
        "payload_size",
        "payload_sha256",
        "c9_frame_count",
        "sequence_range",
        "missing",
        "duplicates",
        "out_of_order",
        "out_of_range_sequences",
        "checksum_failures",
        "normal_region_size",
        "final_region_size",
        "normal_frame_size",
        "final_frame_size",
        "reconstructed_size",
        "reconstructed_sha256",
        "exact_match",
        "errors",
        "external_usage",
    ]
    assert verified["result"] == "PASS"


def test_verify_static_plan_cli_failure_is_nonzero(tmp_path: Path, capsys) -> None:
    manifest, payload, digest = make_static_bundle(tmp_path)
    output = tmp_path / "plan"
    assert main([
        "build-static-plan",
        "--manifest", str(manifest),
        "--payload", str(payload),
        "--expected-payload-sha256", digest,
        "--bundle-root", str(tmp_path),
        "--target-firmware", FIRMWARE,
        "--output", str(output),
        "--json",
    ]) == 0
    capsys.readouterr()
    frames = output / "c9_frames.bin"
    raw = bytearray(frames.read_bytes())
    raw[20] ^= 1
    frames.write_bytes(raw)

    assert main(["verify-static-plan", "--plan", str(output), "--json"]) != 0
    result = json.loads(capsys.readouterr().out)
    assert result["result"] == "FAIL"


def test_static_cli_does_not_register_ble_arguments() -> None:
    from ultra3_uploader.cli import make_parser

    parser = make_parser()
    for command in ("build-static-plan", "inspect-static-plan", "verify-static-plan"):
        help_text = parser._subparsers._group_actions[0].choices[command].format_help()
        assert "--device" not in help_text
        assert "--scan" not in help_text
