import pytest

from ultra3_uploader.bc_frames import build_c8, packet_count_for_size
from ultra3_uploader.errors import FrameError


def test_golden_c8_exact() -> None:
    assert packet_count_for_size(891180) == 3875
    assert build_c8(891180).hex().upper() == "BCC80207012C990D00230F05"


def test_c8_is_derived_from_size() -> None:
    assert build_c8(231).hex().upper() == "BCC8020701E70000000200EA"


def test_c8_rejects_mismatched_packet_count() -> None:
    with pytest.raises(FrameError, match="不一致"):
        build_c8(231, 1)


def test_packet_count_must_fit_le16() -> None:
    with pytest.raises(FrameError, match="65535"):
        packet_count_for_size(230 * 65535 + 1)

