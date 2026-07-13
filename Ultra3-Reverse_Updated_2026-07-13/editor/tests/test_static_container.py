from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from reconstruction_helpers import build_c8, build_c9, frames_for, write_hex_lines
from ultra3_editor.cli import main
from ultra3_editor.models import ContainerKind, ValidationCheck
from ultra3_editor.reconstructor import reconstruct_capture


def static_payload(size: int = 407) -> bytes:
    return bytes((index % 251 for index in range(size)))


def reconstruct_static(tmp_path: Path, frames: list[bytes]):
    capture = write_hex_lines(tmp_path / "capture.log", frames)
    return reconstruct_capture(
        capture,
        capture_format="hex-lines",
        container=ContainerKind.GREENLION_STATIC,
    )


def test_default_bcsdial_policy_still_rejects_static_container(tmp_path: Path) -> None:
    result = reconstruct_capture(
        write_hex_lines(tmp_path / "capture.log", frames_for(static_payload())),
        capture_format="hex-lines",
    )
    assert result.status == "FAILED"
    assert result.container is ContainerKind.BCSDIAL
    assert result.header_check is ValidationCheck.FAILED
    assert result.footer_check is ValidationCheck.FAILED


def test_static_container_preserves_all_c9_data_without_transformation(
    tmp_path: Path,
) -> None:
    data = b"\xE8" + static_payload()[1:]
    frames = frames_for(data)
    result = reconstruct_static(tmp_path, frames)

    assert frames[1][3] == 0xE8
    assert len(result.selected_session.c9_packets[0].data) == 230
    assert frames[-1][3] == 0xB3
    assert len(result.selected_session.c9_packets[-1].data) == 177
    assert result.status == "COMPLETE"
    assert result.container_validation_passed
    assert result.header_check is ValidationCheck.NOT_REQUIRED
    assert result.footer_check is ValidationCheck.NOT_REQUIRED
    assert result.header_valid is None
    assert result.footer_valid is None
    assert result.selected_session.reconstructed_data == data
    assert result.selected_session.reconstructed_data[0] == 0xE8
    assert result.raw_data_size == result.reconstructed_size == len(data)
    assert result.raw_data_sha256 == result.reconstructed_sha256
    assert result.transformation == "none"


@pytest.mark.parametrize("case", ("missing", "duplicate", "out-of-order", "checksum"))
def test_static_container_keeps_common_c9_rejections(
    case: str,
    tmp_path: Path,
) -> None:
    data = static_payload(500)
    cases = {
        "missing": [build_c8(data), build_c9(0, data[:230]), build_c9(2, data[460:])],
        "duplicate": [
            build_c8(data),
            build_c9(0, data[:230]),
            build_c9(1, data[230:460]),
            build_c9(1, data[460:]),
        ],
        "out-of-order": [
            build_c8(data),
            build_c9(0, data[:230]),
            build_c9(2, data[460:]),
            build_c9(1, data[230:460]),
        ],
        "checksum": [
            build_c8(data),
            build_c9(0, data[:230], checksum_delta=1),
            build_c9(1, data[230:460]),
            build_c9(2, data[460:]),
        ],
    }
    result = reconstruct_static(tmp_path, cases[case])
    assert result.status == "FAILED"


def test_static_container_rejects_invalid_len(tmp_path: Path) -> None:
    data = static_payload(20)
    frame = bytearray(build_c9(0, data))
    frame[3] += 1
    result = reconstruct_static(tmp_path, [build_c8(data), bytes(frame)])
    assert result.status == "FAILED"
    assert any("LEN" in error for error in result.errors)


def test_static_container_requires_exact_declared_size(tmp_path: Path) -> None:
    data = static_payload()
    result = reconstruct_static(tmp_path, [
        build_c8(data),
        build_c9(0, data[:230]),
        build_c9(1, data[230:-1]),
    ])
    assert result.status == "FAILED"
    assert not result.container_validation_passed
    assert any("重组大小与声明不符" in error for error in result.errors)


def test_static_cli_and_alias_share_identical_reconstruction(tmp_path: Path) -> None:
    data = static_payload()
    capture = write_hex_lines(tmp_path / "capture.log", frames_for(data))
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    assert main([
        "reconstruct-c9",
        str(capture),
        "--container",
        "greenlion-static",
        "--output",
        str(first),
    ]) == 0
    assert main([
        "reconstruct-static-diy",
        str(capture),
        "--output",
        str(second),
    ]) == 0
    assert first.read_bytes() == second.read_bytes() == data


def test_static_cli_refuses_existing_output(tmp_path: Path) -> None:
    data = static_payload(20)
    capture = write_hex_lines(tmp_path / "capture.log", frames_for(data))
    output = tmp_path / "existing.bin"
    output.write_bytes(b"keep")
    assert main([
        "reconstruct-c9",
        str(capture),
        "--container",
        "greenlion-static",
        "--output",
        str(output),
    ]) == 2
    assert output.read_bytes() == b"keep"


def test_a0_repeat_1_reconstructs_exact_static_file(tmp_path: Path) -> None:
    capture = (
        Path(__file__).resolve().parents[1]
        / "samples"
        / "stage7a2_diy_root_capture"
        / "A0_repeat_1"
        / "capture_raw.log"
    )
    capture_digest = hashlib.sha256(capture.read_bytes()).hexdigest().upper()
    result = reconstruct_capture(
        capture,
        capture_format="auto",
        container=ContainerKind.GREENLION_STATIC,
    )

    assert capture_digest == "78734E68052D25FA9E09DD709134B288814A1162F4B3174987B3DD0C4D16C38E"
    assert result.status == "COMPLETE"
    assert result.selected_session.c8_record.payload.hex().upper() == "BCC8020701815D0500F905E2"
    assert result.selected_session.c8_packet.declared_size == 351617
    assert result.selected_session.c8_packet.declared_packet_count == 1529
    assert len(result.selected_session.c9_packets) == 1529
    assert result.selected_session.c9_packets[0].sequence == 0
    assert result.selected_session.c9_packets[-1].sequence == 1528
    assert len(result.selected_session.c9_packets[0].data) == 230
    assert len(result.selected_session.c9_packets[-1].data) == 177
    assert sum(packet.data[:1] == b"\xE8" for packet in result.selected_session.c9_packets) == 0
    assert result.raw_data_size == result.reconstructed_size == 351617
    assert result.raw_data_sha256 == result.reconstructed_sha256 == (
        "9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635"
    )
    assert hashlib.sha256(capture.read_bytes()).hexdigest().upper() == capture_digest


def test_static_json_reports_not_required_checks(tmp_path: Path) -> None:
    data = static_payload(20)
    capture = write_hex_lines(tmp_path / "capture.log", frames_for(data))
    report_path = tmp_path / "reconstruction.json"
    assert main([
        "reconstruct-c9",
        str(capture),
        "--container",
        "greenlion-static",
        "--json",
        str(report_path),
    ]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["container"] == "greenlion-static"
    assert report["header_requirement"] is None
    assert report["footer_requirement"] is None
    assert report["header_check"] == "NOT_REQUIRED"
    assert report["footer_check"] == "NOT_REQUIRED"
    assert report["raw_data_size"] == report["reconstructed_size"]
    assert report["raw_data_sha256"] == report["reconstructed_sha256"]
    assert report["transformation"] == "none"
