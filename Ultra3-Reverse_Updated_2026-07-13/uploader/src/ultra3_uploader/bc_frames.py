from __future__ import annotations

from collections.abc import Iterator

from .checksum import c8_checksum, c9_checksum
from .constants import BCSDIAL_MODE, C9_CHUNK_SIZE, MAX_PACKET_COUNT
from .errors import FrameError
from .models import C9Packet


def packet_count_for_size(file_size: int) -> int:
    if file_size <= 0:
        raise FrameError("文件大小必须大于 0")
    count = (file_size + C9_CHUNK_SIZE - 1) // C9_CHUNK_SIZE
    if count > MAX_PACKET_COUNT:
        raise FrameError(f"C9 分包数 {count} 超过 LE16 可表示上限 {MAX_PACKET_COUNT}")
    return count


def build_c8(file_size: int, packet_count: int | None = None) -> bytes:
    count = packet_count_for_size(file_size) if packet_count is None else packet_count
    if not 1 <= count <= MAX_PACKET_COUNT:
        raise FrameError("C8 packet_count 必须在 1..65535")
    expected = packet_count_for_size(file_size)
    if count != expected:
        raise FrameError(f"C8 packet_count={count} 与文件大小计算值 {expected} 不一致")
    size_le = file_size.to_bytes(4, "little")
    count_le = count.to_bytes(2, "little")
    checksum = c8_checksum(BCSDIAL_MODE, size_le, count_le)
    return b"\xBC\xC8\x02\x07" + bytes((BCSDIAL_MODE,)) + size_le + count_le + bytes((checksum,))


def build_c9(sequence: int, data: bytes) -> bytes:
    if not 0 <= sequence <= 0xFFFF:
        raise FrameError("C9 sequence 必须在 0..65535")
    if not 1 <= len(data) <= C9_CHUNK_SIZE:
        raise FrameError("C9 DATA 长度必须在 1..230")
    sequence_le = sequence.to_bytes(2, "little")
    return (
        b"\xBC\xC9\x02"
        + bytes((2 + len(data),))
        + sequence_le
        + data
        + bytes((c9_checksum(sequence, data),))
    )


def iter_c9(payload: bytes) -> Iterator[bytes]:
    packet_count_for_size(len(payload))
    for sequence, offset in enumerate(range(0, len(payload), C9_CHUNK_SIZE)):
        yield build_c9(sequence, payload[offset:offset + C9_CHUNK_SIZE])


def parse_c9(frame: bytes, line_number: int | None = None) -> C9Packet:
    if len(frame) < 8 or frame[:3] != b"\xBC\xC9\x02":
        raise FrameError("不是有效的 C9 写入帧")
    if frame[3] != len(frame) - 5:
        raise FrameError("C9 LEN 与完整帧长度不一致")
    sequence = int.from_bytes(frame[4:6], "little")
    data = frame[6:-1]
    return C9Packet(
        sequence=sequence,
        data=data,
        frame=frame,
        checksum_valid=frame[-1] == c9_checksum(sequence, data),
        line_number=line_number,
    )

