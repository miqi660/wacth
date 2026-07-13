from __future__ import annotations

from .errors import FrameValidationError
from .models import C8Packet, C9Packet

C9_DATA_SIZE = 230
MAX_PACKET_COUNT = 0xFFFF


def sum8(data: bytes) -> int:
    return sum(data) & 0xFF


def c8_checksum(mode: int, size_le: bytes, packet_count_le: bytes) -> int:
    return sum8(bytes((mode,)) + size_le + packet_count_le)


def c9_checksum(sequence: int, data: bytes) -> int:
    return ((sequence & 0xFF) + ((sequence >> 8) & 0xFF) + sum(data)) & 0xFF


def packet_count_for_size(file_size: int) -> int:
    if file_size <= 0:
        raise FrameValidationError("C8 声明文件大小必须大于 0")
    count = (file_size + C9_DATA_SIZE - 1) // C9_DATA_SIZE
    if count > MAX_PACKET_COUNT:
        raise FrameValidationError("C8 声明文件需要超过 65535 个 C9 包")
    return count


def parse_c8(frame: bytes) -> C8Packet:
    if len(frame) != 12 or frame[:3] != b"\xBC\xC8\x02":
        raise FrameValidationError("不是结构完整的 C8 request")
    if frame[3] != 0x07:
        raise FrameValidationError("C8 LEN 字段不是 0x07")
    mode = frame[4]
    size_le = frame[5:9]
    count_le = frame[9:11]
    return C8Packet(
        frame=frame,
        mode=mode,
        declared_size=int.from_bytes(size_le, "little"),
        declared_packet_count=int.from_bytes(count_le, "little"),
        checksum_valid=frame[-1] == c8_checksum(mode, size_le, count_le),
    )


def parse_c9(frame: bytes, *, line_number: int) -> C9Packet:
    if len(frame) < 8 or frame[:3] != b"\xBC\xC9\x02":
        raise FrameValidationError("不是有效的 C9 写入帧")
    if frame[3] != len(frame) - 5:
        raise FrameValidationError("C9 LEN 与完整帧长度不一致")
    sequence = int.from_bytes(frame[4:6], "little")
    data = frame[6:-1]
    if not 1 <= len(data) <= C9_DATA_SIZE:
        raise FrameValidationError("C9 DATA 长度必须在 1..230")
    return C9Packet(
        frame=frame,
        sequence=sequence,
        data=data,
        checksum_valid=frame[-1] == c9_checksum(sequence, data),
        line_number=line_number,
    )
