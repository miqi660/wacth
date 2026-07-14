from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from ultra3_uploader.errors import (
    FixedStaticControlFrameError,
    FixedStaticOutputError,
    FixedStaticProfileError,
)
from ultra3_uploader.fixed_static import (
    NJLEJ_217_FIXED_STATIC,
    build_fixed_static_transfer_plan,
    build_njlej_217_static_c8,
    build_njlej_217_static_ca,
    parse_njlej_217_static_c8,
    parse_njlej_217_static_ca,
    verify_fixed_static_transfer_plan,
    write_fixed_static_transfer_plan,
)


@pytest.fixture(scope="module")
def static_container() -> bytes:
    profile = NJLEJ_217_FIXED_STATIC
    pattern = bytes(range(256))
    return (pattern * (profile.static_container_size // len(pattern) + 1))[
        :profile.static_container_size
    ]


@pytest.fixture(scope="module")
def fixed_plan(static_container: bytes):
    return build_fixed_static_transfer_plan(static_container)


def test_fixed_profile_frozen_values() -> None:
    profile = NJLEJ_217_FIXED_STATIC
    assert profile.firmware == "NJ-LEJ-2.1.7"
    assert profile.static_container_size == 351617
    assert profile.c9_count == 1529
    assert profile.c8_hex == "BCC8020701815D0500F905E2"
    assert profile.ca_hex == "BCCA02010505"


def test_build_fixed_c8_exact() -> None:
    frame = build_njlej_217_static_c8(static_container_size=351617, c9_count=1529)
    assert frame.hex().upper() == "BCC8020701815D0500F905E2"


def test_parse_fixed_c8_fields() -> None:
    parsed = parse_njlej_217_static_c8(bytes.fromhex("BCC8020701815D0500F905E2"))
    assert parsed.direction == 2
    assert parsed.command == "C8"
    assert parsed.declared_length == 7
    assert parsed.profile_mode == 1
    assert parsed.static_container_size == 351617
    assert parsed.c9_count == 1529
    assert parsed.checksum == 0xE2


@pytest.mark.parametrize(
    ("size", "count", "message"),
    [(351616, 1529, "大小"), (351617, 1528, "数量")],
)
def test_build_fixed_c8_rejects_non_profile_values(
    size: int, count: int, message: str
) -> None:
    with pytest.raises(FixedStaticProfileError, match=message):
        build_njlej_217_static_c8(static_container_size=size, c9_count=count)


@pytest.mark.parametrize("index", [0, 3, 4, 5, 9, 11])
def test_parse_fixed_c8_rejects_modified_byte(index: int) -> None:
    frame = bytearray.fromhex("BCC8020701815D0500F905E2")
    frame[index] ^= 1
    with pytest.raises(FixedStaticControlFrameError):
        parse_njlej_217_static_c8(bytes(frame))


@pytest.mark.parametrize("frame", [bytes(11), bytes(13)])
def test_parse_fixed_c8_rejects_wrong_length(frame: bytes) -> None:
    with pytest.raises(FixedStaticControlFrameError, match="长度"):
        parse_njlej_217_static_c8(frame)


def test_build_fixed_ca_exact() -> None:
    assert build_njlej_217_static_ca().hex().upper() == "BCCA02010505"
    assert parse_njlej_217_static_ca(build_njlej_217_static_ca()).frame == bytes.fromhex(
        "BCCA02010505"
    )


@pytest.mark.parametrize("index", range(6))
def test_parse_fixed_ca_rejects_every_single_byte_change(index: int) -> None:
    frame = bytearray.fromhex("BCCA02010505")
    frame[index] ^= 1
    with pytest.raises(FixedStaticControlFrameError):
        parse_njlej_217_static_ca(bytes(frame))


@pytest.mark.parametrize("frame", [b"", bytes(5), bytes(7)])
def test_parse_fixed_ca_rejects_wrong_length(frame: bytes) -> None:
    with pytest.raises(FixedStaticControlFrameError):
        parse_njlej_217_static_ca(frame)


@pytest.mark.parametrize("size", [0, 351616, 351618])
def test_plan_rejects_non_fixed_container_size(size: int) -> None:
    with pytest.raises(FixedStaticProfileError, match="大小错误"):
        build_fixed_static_transfer_plan(bytes(size))


@pytest.mark.parametrize(
    "unknown",
    [
        replace(NJLEJ_217_FIXED_STATIC, name="unknown"),
        replace(NJLEJ_217_FIXED_STATIC, firmware="OTHER"),
    ],
)
def test_plan_rejects_unknown_profile(static_container: bytes, unknown) -> None:
    with pytest.raises(FixedStaticProfileError, match="不支持"):
        build_fixed_static_transfer_plan(static_container, profile=unknown)


def test_plan_has_exact_frozen_order_and_sizes(fixed_plan) -> None:
    assert len(fixed_plan.frames) == 1531
    assert fixed_plan.frames[0].hex().upper() == "BCC8020701815D0500F905E2"
    assert fixed_plan.frames[1] == fixed_plan.c9_frames[0]
    assert fixed_plan.frames[-2] == fixed_plan.c9_frames[-1]
    assert fixed_plan.frames[-1].hex().upper() == "BCCA02010505"
    assert len(fixed_plan.region_stream) == 353146
    assert len(fixed_plan.c9_frame_stream) == 362320
    assert len(fixed_plan.full_transfer_stream) == 362338


def test_plan_c9_sequences_and_data_sizes(fixed_plan) -> None:
    sequences = [int.from_bytes(frame[4:6], "little") for frame in fixed_plan.c9_frames]
    assert sequences == list(range(1529))
    assert all(len(frame[6:-1]) == 230 for frame in fixed_plan.c9_frames[:-1])
    assert len(fixed_plan.c9_frames[-1][6:-1]) == 177
    assert fixed_plan.c9_frames[0][3] == 0xE8
    assert fixed_plan.c9_frames[-1][3] == 0xB3


def test_plan_reconstructs_static_container_without_transformation(
    fixed_plan, static_container: bytes
) -> None:
    reconstructed = b"".join(frame[6:-1] for frame in fixed_plan.c9_frames)
    assert reconstructed == static_container
    assert fixed_plan.verification.static_container_exact
    assert fixed_plan.static_container_sha256 == hashlib.sha256(static_container).hexdigest().upper()


def test_plan_verification_passes(fixed_plan) -> None:
    result = verify_fixed_static_transfer_plan(fixed_plan)
    assert result.result == "PASS"
    assert result.order_valid
    assert result.c8_checksum_valid
    assert result.checksum_failures == ()
    assert result.external_usage.ble_connections == 0
    assert result.external_usage.ff02_writes == 0


def test_modified_c8_fails_plan_verification(fixed_plan) -> None:
    changed = bytearray(fixed_plan.c8_frame)
    changed[-1] ^= 1
    result = verify_fixed_static_transfer_plan(replace(fixed_plan, c8_frame=bytes(changed)))
    assert result.result == "FAIL"
    assert not result.c8_checksum_valid
    assert not result.order_valid


def test_modified_ca_fails_plan_verification(fixed_plan) -> None:
    changed = bytearray(fixed_plan.ca_frame)
    changed[4] ^= 1
    result = verify_fixed_static_transfer_plan(replace(fixed_plan, ca_frame=bytes(changed)))
    assert result.result == "FAIL"
    assert not result.ca_exact
    assert not result.order_valid


def test_missing_c9_fails_plan_verification(fixed_plan) -> None:
    frames = fixed_plan.c9_frames[:10] + fixed_plan.c9_frames[11:]
    result = verify_fixed_static_transfer_plan(replace(fixed_plan, c9_frames=frames))
    assert result.result == "FAIL"
    assert result.missing_sequences == (10,)


def test_duplicate_c9_fails_plan_verification(fixed_plan) -> None:
    frames = fixed_plan.c9_frames[:10] + (fixed_plan.c9_frames[10],) + fixed_plan.c9_frames[10:]
    result = verify_fixed_static_transfer_plan(replace(fixed_plan, c9_frames=frames))
    assert result.result == "FAIL"
    assert result.duplicate_sequences == (10,)


def test_swapped_c9_fails_plan_verification(fixed_plan) -> None:
    frames = list(fixed_plan.c9_frames)
    frames[10], frames[11] = frames[11], frames[10]
    result = verify_fixed_static_transfer_plan(
        replace(fixed_plan, c9_frames=tuple(frames))
    )
    assert result.result == "FAIL"
    assert result.out_of_order


def test_corrupt_c9_checksum_fails_plan_verification(fixed_plan) -> None:
    frames = list(fixed_plan.c9_frames)
    changed = bytearray(frames[10])
    changed[20] ^= 1
    frames[10] = bytes(changed)
    result = verify_fixed_static_transfer_plan(
        replace(fixed_plan, c9_frames=tuple(frames))
    )
    assert result.result == "FAIL"
    assert result.checksum_failures == (10,)


def test_corrupt_c9_len_fails_plan_verification(fixed_plan) -> None:
    frames = list(fixed_plan.c9_frames)
    changed = bytearray(frames[10])
    changed[3] -= 1
    frames[10] = bytes(changed)
    result = verify_fixed_static_transfer_plan(
        replace(fixed_plan, c9_frames=tuple(frames))
    )
    assert result.result == "FAIL"
    assert any("LEN" in error for error in result.errors)


def test_manifest_uses_frozen_terminology(fixed_plan) -> None:
    document = fixed_plan.to_manifest_dict()
    assert document["profile"] == "njlej-2.1.7-fixed-static"
    assert document["static_container_size"] == 351617
    assert document["region_stream_size"] == 353146
    assert document["c9_frame_stream_size"] == 362320
    assert document["full_transfer_stream_size"] == 362338
    assert document["total_write_count"] == 1531
    assert document["c8"]["evidence"] == "stage8c3b-two-successful-binder-captures"
    assert document["ca"]["generation_scope"] == "fixed-profile-only"
    assert document["ble_supported"] is False
    assert "source" not in document


def test_write_fixed_plan_creates_exact_files(tmp_path: Path, fixed_plan) -> None:
    output = tmp_path / "plan"
    write_fixed_static_transfer_plan(fixed_plan, output)
    assert sorted(path.name for path in output.iterdir()) == [
        "c8.bin",
        "c9_frames.bin",
        "ca.bin",
        "full_transfer_stream.bin",
        "manifest.json",
    ]
    assert (output / "c8.bin").stat().st_size == 12
    assert (output / "c9_frames.bin").stat().st_size == 362320
    assert (output / "ca.bin").stat().st_size == 6
    assert (output / "full_transfer_stream.bin").stat().st_size == 362338


def test_write_fixed_plan_refuses_existing_output(tmp_path: Path, fixed_plan) -> None:
    output = tmp_path / "plan"
    output.mkdir()
    with pytest.raises(FixedStaticOutputError, match="已存在"):
        write_fixed_static_transfer_plan(fixed_plan, output)
