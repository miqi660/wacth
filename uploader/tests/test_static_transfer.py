from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ultra3_uploader.bc_frames import build_c9
from ultra3_uploader.errors import StaticTransferPlanError
from ultra3_uploader.static_transfer import (
    STATIC_FINAL_FRAME_SIZE,
    STATIC_FINAL_REGION_SIZE,
    STATIC_FRAME_COUNT,
    STATIC_NORMAL_FRAME_SIZE,
    STATIC_NORMAL_REGION_SIZE,
    STATIC_PAYLOAD_SIZE,
    build_static_transfer_plan,
    inspect_static_plan,
    verify_static_plan,
    verify_static_transfer_frames,
    write_static_transfer_plan,
)

from .static_transfer_fixtures import FIRMWARE, make_static_bundle


def build_plan(tmp_path: Path):
    manifest, payload, digest = make_static_bundle(tmp_path)
    plan = build_static_transfer_plan(
        manifest,
        payload_path=payload,
        expected_payload_sha256=digest,
        bundle_root=tmp_path,
        target_firmware=FIRMWARE,
    )
    return plan, manifest, payload, digest


def test_build_static_plan_has_frozen_shape(tmp_path: Path) -> None:
    plan, _manifest, payload, digest = build_plan(tmp_path)

    assert plan.source_size == 351617
    assert plan.payload_size == STATIC_PAYLOAD_SIZE == payload.stat().st_size
    assert plan.payload_sha256 == digest
    assert len(plan.c9_frames) == STATIC_FRAME_COUNT == 1529
    assert [item.sequence for item in plan.c9_frames] == list(range(STATIC_FRAME_COUNT))
    assert all(len(item.region) == STATIC_NORMAL_REGION_SIZE for item in plan.c9_frames[:-1])
    assert len(plan.c9_frames[-1].region) == STATIC_FINAL_REGION_SIZE
    assert all(len(item.frame) == STATIC_NORMAL_FRAME_SIZE for item in plan.c9_frames[:-1])
    assert len(plan.c9_frames[-1].frame) == STATIC_FINAL_FRAME_SIZE
    assert plan.c8_frame is None
    assert plan.ca_frame is None
    assert plan.verification.result == "PASS"
    assert plan.verification.checksum_failures == ()
    assert plan.verification.exact_match


def test_static_region_is_data_plus_existing_checksum(tmp_path: Path) -> None:
    plan, _manifest, _payload, _digest = build_plan(tmp_path)
    first = plan.c9_frames[0]
    assert len(first.data) == 230
    assert first.region == first.data + bytes((first.checksum,))
    assert first.frame == build_c9(0, first.data)


def test_repeated_build_is_deterministic(tmp_path: Path) -> None:
    plan, manifest, payload, digest = build_plan(tmp_path)
    repeated = build_static_transfer_plan(
        manifest,
        payload_path=payload,
        expected_payload_sha256=digest.upper(),
        bundle_root=tmp_path,
        target_firmware=FIRMWARE,
    )
    assert repeated.to_manifest_dict() == plan.to_manifest_dict()
    assert tuple(item.frame for item in repeated.c9_frames) == tuple(
        item.frame for item in plan.c9_frames
    )


def test_write_and_verify_static_plan(tmp_path: Path) -> None:
    plan, _manifest, _payload, digest = build_plan(tmp_path)
    output = tmp_path / "plan"
    write_static_transfer_plan(plan, output)

    result = verify_static_plan(output)
    metadata = inspect_static_plan(output)
    assert result.result == "PASS"
    assert result.reconstructed_sha256 == digest
    assert result.reconstructed_size == STATIC_PAYLOAD_SIZE
    assert result.exact_match
    assert metadata["c9"]["frame_count"] == STATIC_FRAME_COUNT
    assert metadata["c8"]["status"] == "not_implemented"
    assert metadata["ca"]["status"] == "not_implemented"


def test_existing_plan_directory_is_rejected(tmp_path: Path) -> None:
    plan, _manifest, _payload, _digest = build_plan(tmp_path)
    output = tmp_path / "plan"
    output.mkdir()
    with pytest.raises(StaticTransferPlanError, match="已存在"):
        write_static_transfer_plan(plan, output)


@pytest.mark.parametrize("delta", [-1, 1])
def test_payload_size_mismatch_is_rejected(tmp_path: Path, delta: int) -> None:
    manifest, payload, _digest = make_static_bundle(tmp_path)
    data = payload.read_bytes()
    payload.write_bytes(data[:-1] if delta < 0 else data + b"\0")
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    with pytest.raises(StaticTransferPlanError, match="payload 大小"):
        build_static_transfer_plan(
            manifest,
            payload_path=payload,
            expected_payload_sha256=digest,
            bundle_root=tmp_path,
            target_firmware=FIRMWARE,
        )


def test_payload_sha_mismatch_is_rejected(tmp_path: Path) -> None:
    manifest, payload, _digest = make_static_bundle(tmp_path)
    with pytest.raises(StaticTransferPlanError, match="SHA-256"):
        build_static_transfer_plan(
            manifest,
            payload_path=payload,
            expected_payload_sha256="0" * 64,
            bundle_root=tmp_path,
            target_firmware=FIRMWARE,
        )


@pytest.mark.parametrize("value", ["", "a" * 63, "g" * 64, "a" * 65])
def test_invalid_expected_payload_sha_is_rejected(tmp_path: Path, value: str) -> None:
    manifest, payload, _digest = make_static_bundle(tmp_path)
    with pytest.raises(StaticTransferPlanError, match="64 位十六进制"):
        build_static_transfer_plan(
            manifest,
            payload_path=payload,
            expected_payload_sha256=value,
            bundle_root=tmp_path,
            target_firmware=FIRMWARE,
        )


def test_payload_checksum_error_is_rejected(tmp_path: Path) -> None:
    manifest, payload, _digest = make_static_bundle(tmp_path)
    data = bytearray(payload.read_bytes())
    data[230] ^= 1
    payload.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    with pytest.raises(StaticTransferPlanError, match="checksum"):
        build_static_transfer_plan(
            manifest,
            payload_path=payload,
            expected_payload_sha256=digest,
            bundle_root=tmp_path,
            target_firmware=FIRMWARE,
        )


def test_invalid_handoff_is_rejected(tmp_path: Path) -> None:
    manifest, payload, digest = make_static_bundle(tmp_path)
    source = tmp_path / "watchface.bin"
    source.write_bytes(source.read_bytes()[:-1] + b"X")
    with pytest.raises(StaticTransferPlanError, match="Handoff"):
        build_static_transfer_plan(
            manifest,
            payload_path=payload,
            expected_payload_sha256=digest,
            bundle_root=tmp_path,
            target_firmware=FIRMWARE,
        )


def test_unsupported_firmware_is_rejected(tmp_path: Path) -> None:
    manifest, payload, digest = make_static_bundle(tmp_path)
    with pytest.raises(StaticTransferPlanError, match="Handoff"):
        build_static_transfer_plan(
            manifest,
            payload_path=payload,
            expected_payload_sha256=digest,
            bundle_root=tmp_path,
            target_firmware="OTHER",
        )


def test_payload_outside_bundle_is_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    manifest, payload, digest = make_static_bundle(bundle)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(payload.read_bytes())
    with pytest.raises(StaticTransferPlanError, match="bundle_root"):
        build_static_transfer_plan(
            manifest,
            payload_path=outside,
            expected_payload_sha256=digest,
            bundle_root=bundle,
            target_firmware=FIRMWARE,
        )


def test_payload_cannot_be_bundle_directory(tmp_path: Path) -> None:
    manifest, _payload, digest = make_static_bundle(tmp_path)
    with pytest.raises(StaticTransferPlanError, match="普通文件"):
        build_static_transfer_plan(
            manifest,
            payload_path=tmp_path,
            expected_payload_sha256=digest,
            bundle_root=tmp_path,
            target_firmware=FIRMWARE,
        )


def frames_from_plan(tmp_path: Path) -> tuple[list[bytes], str]:
    plan, _manifest, _payload, digest = build_plan(tmp_path)
    return [item.frame for item in plan.c9_frames], digest


def test_modified_frame_fails_verification(tmp_path: Path) -> None:
    frames, digest = frames_from_plan(tmp_path)
    changed = bytearray(frames[5])
    changed[20] ^= 1
    frames[5] = bytes(changed)
    result = verify_static_transfer_frames(frames, digest)
    assert result.result == "FAIL"
    assert result.checksum_failures == (5,)
    assert not result.exact_match


def test_missing_frame_is_detected(tmp_path: Path) -> None:
    frames, digest = frames_from_plan(tmp_path)
    del frames[10]
    result = verify_static_transfer_frames(frames, digest)
    assert result.missing_sequences == (10,)
    assert result.result == "FAIL"


def test_duplicate_frame_is_detected(tmp_path: Path) -> None:
    frames, digest = frames_from_plan(tmp_path)
    frames.insert(10, frames[10])
    result = verify_static_transfer_frames(frames, digest)
    assert result.duplicate_sequences == (10,)
    assert result.result == "FAIL"


def test_out_of_order_frame_is_detected(tmp_path: Path) -> None:
    frames, digest = frames_from_plan(tmp_path)
    frames[10], frames[11] = frames[11], frames[10]
    result = verify_static_transfer_frames(frames, digest)
    assert result.out_of_order
    assert result.result == "FAIL"


def test_out_of_range_sequence_is_detected(tmp_path: Path) -> None:
    frames, digest = frames_from_plan(tmp_path)
    frames[0] = build_c9(2000, frames[0][6:-1])
    result = verify_static_transfer_frames(frames, digest)
    assert 2000 in result.out_of_range_sequences
    assert result.result == "FAIL"


def test_wrong_final_region_size_is_detected(tmp_path: Path) -> None:
    frames, digest = frames_from_plan(tmp_path)
    frames[-1] = build_c9(STATIC_FRAME_COUNT - 1, b"X" * 176)
    result = verify_static_transfer_frames(frames, digest)
    assert result.final_region_size == 177
    assert result.result == "FAIL"


def test_saved_plan_detects_frame_stream_mutation(tmp_path: Path) -> None:
    plan, _manifest, _payload, _digest = build_plan(tmp_path)
    output = tmp_path / "plan"
    write_static_transfer_plan(plan, output)
    frames_path = output / "c9_frames.bin"
    raw = bytearray(frames_path.read_bytes())
    raw[20] ^= 1
    frames_path.write_bytes(raw)
    result = verify_static_plan(output)
    assert result.result == "FAIL"
    assert not result.exact_match


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        (None, "firmware", "OTHER"),
        ("source", "size", 1),
        ("payload", "identifier", "sha256:" + "0" * 64),
        ("c8", "status", "implemented"),
        ("ca", "status", "implemented"),
    ],
)
def test_saved_plan_rejects_metadata_changes(
    tmp_path: Path,
    section: str | None,
    key: str,
    value: object,
) -> None:
    plan, _manifest, _payload, _digest = build_plan(tmp_path)
    output = tmp_path / "plan"
    write_static_transfer_plan(plan, output)
    manifest_path = output / "manifest.json"
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = document if section is None else document[section]
    target[key] = value
    manifest_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    result = verify_static_plan(output)
    assert result.result == "FAIL"
    assert not result.exact_match


def test_plan_manifest_is_deterministic_json(tmp_path: Path) -> None:
    plan, _manifest, _payload, _digest = build_plan(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_static_transfer_plan(plan, first)
    write_static_transfer_plan(plan, second)
    assert (first / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()
    assert (first / "c9_frames.bin").read_bytes() == (second / "c9_frames.bin").read_bytes()
    parsed = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert parsed["format"] == "ultra3-static-transfer-plan/v1"
    assert "created_at" not in parsed
