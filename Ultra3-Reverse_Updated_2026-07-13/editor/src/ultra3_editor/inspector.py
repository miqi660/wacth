from __future__ import annotations

from collections import Counter
from pathlib import Path

from .bcsdial import read_bcsdial
from .errors import OffsetError
from .models import ByteStatistics, InspectionResult
from .ranges import validate_offset


def inspect_bcsdial(
    path: str | Path,
    *,
    offset: int | None = None,
    context: int = 32,
) -> InspectionResult:
    if context < 0:
        raise OffsetError("context 不能为负数")
    loaded = read_bcsdial(path, require_valid=False)
    data = loaded.data
    counts = Counter(data)
    most_common_byte, most_common_count = counts.most_common(1)[0]

    context_start: int | None = None
    context_end: int | None = None
    context_bytes = b""
    if offset is not None:
        validate_offset(offset, len(data))
        context_start = max(0, offset - context)
        context_end = min(len(data) - 1, offset + context)
        context_bytes = data[context_start : context_end + 1]

    zero_count = counts.get(0, 0)
    return InspectionResult(
        info=loaded.info,
        first_64=data[:64],
        last_64=data[-64:],
        statistics=ByteStatistics(
            zero_count=zero_count,
            nonzero_count=len(data) - zero_count,
            unique_byte_count=len(counts),
            most_common_byte=most_common_byte,
            most_common_count=most_common_count,
        ),
        selected_offset=offset,
        context_start=context_start,
        context_end=context_end,
        context_bytes=context_bytes,
    )
