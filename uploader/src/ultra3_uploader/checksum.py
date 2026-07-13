def sum8(data: bytes) -> int:
    return sum(data) & 0xFF


def c8_checksum(mode: int, size_le: bytes, packet_count_le: bytes) -> int:
    return sum8(bytes((mode,)) + size_le + packet_count_le)


def c9_checksum(sequence: int, data: bytes) -> int:
    return ((sequence & 0xFF) + ((sequence >> 8) & 0xFF) + sum(data)) & 0xFF

