from __future__ import annotations

from pathlib import Path

from .bcsdial import read_bcsdial
from .errors import OffsetError
from .models import DiffByte, DiffRange, DiffResult
from .ranges import merge_adjacent_offsets


def diff_bcsdial(
    before_path: str | Path,
    after_path: str | Path,
    *,
    context: int = 32,
) -> DiffResult:
    if context < 0:
        raise OffsetError("context 不能为负数")
    before = read_bcsdial(before_path, require_valid=False)
    after = read_bcsdial(after_path, require_valid=False)
    before_data = before.data
    after_data = after.data
    maximum_size = max(len(before_data), len(after_data))

    differences: list[DiffByte] = []
    for offset in range(maximum_size):
        before_value = before_data[offset] if offset < len(before_data) else None
        after_value = after_data[offset] if offset < len(after_data) else None
        if before_value != after_value:
            differences.append(DiffByte(offset, before_value, after_value))

    ranges: list[DiffRange] = []
    for start, end in merge_adjacent_offsets(item.offset for item in differences):
        context_start = max(0, start - context)
        context_end = min(maximum_size - 1, end + context)
        ranges.append(DiffRange(
            start=start,
            end=end,
            length=end - start + 1,
            before_bytes=before_data[start : min(end + 1, len(before_data))],
            after_bytes=after_data[start : min(end + 1, len(after_data))],
            context_start=context_start,
            context_end=context_end,
            before_context=before_data[
                context_start : min(context_end + 1, len(before_data))
            ],
            after_context=after_data[
                context_start : min(context_end + 1, len(after_data))
            ],
        ))

    changed_count = len(differences)
    return DiffResult(
        before_info=before.info,
        after_info=after.info,
        same_size=before.info.size == after.info.size,
        changed_byte_count=changed_count,
        unchanged_byte_count=maximum_size - changed_count,
        ranges=tuple(ranges),
        first_difference=differences[0].offset if differences else None,
        last_difference=differences[-1].offset if differences else None,
    )
