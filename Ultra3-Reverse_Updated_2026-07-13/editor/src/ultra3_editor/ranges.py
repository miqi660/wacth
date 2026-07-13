from __future__ import annotations

from collections.abc import Iterable

from .errors import OffsetError


def parse_offset(value: str) -> int:
    text = value.strip()
    try:
        offset = int(text, 16 if text.lower().startswith("0x") else 10)
    except ValueError as exc:
        raise OffsetError(f"无效偏移: {value}") from exc
    if offset < 0:
        raise OffsetError("偏移不能为负数")
    return offset


def validate_offset(offset: int, size: int) -> None:
    if offset < 0 or offset >= size:
        raise OffsetError(f"偏移 0x{offset:X} 超出文件范围 0..0x{size - 1:X}")


def merge_adjacent_offsets(offsets: Iterable[int]) -> tuple[tuple[int, int], ...]:
    ordered = sorted(set(offsets))
    if not ordered:
        return ()
    ranges: list[tuple[int, int]] = []
    start = previous = ordered[0]
    for offset in ordered[1:]:
        if offset == previous + 1:
            previous = offset
            continue
        ranges.append((start, previous))
        start = previous = offset
    ranges.append((start, previous))
    return tuple(ranges)
