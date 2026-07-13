from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import EditorError, ReportExistsError
from .hexdump import format_hexdump
from .known_patch import known_patch_failures
from .models import BCSDIALFileInfo, DiffRange, DiffResult, InspectionResult


def file_info_dict(info: BCSDIALFileInfo) -> dict[str, Any]:
    return {
        "path": str(info.path),
        "size": info.size,
        "sha256": info.sha256,
        "header_hex": info.header.hex().upper(),
        "footer_hex": info.footer.hex().upper(),
        "header_ascii": info.header_ascii,
        "header_valid": info.header_valid,
        "footer_valid": info.footer_valid,
        "valid": info.valid,
    }


def inspection_dict(result: InspectionResult) -> dict[str, Any]:
    return {
        "file": file_info_dict(result.info),
        "first_64_hex": result.first_64.hex().upper(),
        "last_64_hex": result.last_64.hex().upper(),
        "selected_offset": result.selected_offset,
        "selected_offset_hex": (
            f"0x{result.selected_offset:08X}"
            if result.selected_offset is not None
            else None
        ),
        "context_start": result.context_start,
        "context_end": result.context_end,
        "context_hex": result.context_bytes.hex().upper(),
        "statistics": {
            "zero_count": result.statistics.zero_count,
            "nonzero_count": result.statistics.nonzero_count,
            "unique_byte_count": result.statistics.unique_byte_count,
            "most_common_byte": result.statistics.most_common_byte,
            "most_common_byte_hex": f"{result.statistics.most_common_byte:02X}",
            "most_common_count": result.statistics.most_common_count,
        },
    }


def _range_dict(item: DiffRange) -> dict[str, Any]:
    return {
        "start": item.start,
        "start_hex": f"0x{item.start:08X}",
        "end": item.end,
        "end_hex": f"0x{item.end:08X}",
        "length": item.length,
        "before_hex": item.before_bytes.hex().upper(),
        "after_hex": item.after_bytes.hex().upper(),
        "context_start": item.context_start,
        "context_start_hex": f"0x{item.context_start:08X}",
        "context_end": item.context_end,
        "context_end_hex": f"0x{item.context_end:08X}",
        "before_context_hex": item.before_context.hex().upper(),
        "after_context_hex": item.after_context.hex().upper(),
    }


def diff_dict(result: DiffResult) -> dict[str, Any]:
    return {
        "before": file_info_dict(result.before_info),
        "after": file_info_dict(result.after_info),
        "same_size": result.same_size,
        "changed_byte_count": result.changed_byte_count,
        "unchanged_byte_count": result.unchanged_byte_count,
        "changed_percentage": result.changed_percentage,
        "range_count": len(result.ranges),
        "first_difference": result.first_difference,
        "first_difference_hex": (
            f"0x{result.first_difference:08X}"
            if result.first_difference is not None
            else None
        ),
        "last_difference": result.last_difference,
        "last_difference_hex": (
            f"0x{result.last_difference:08X}"
            if result.last_difference is not None
            else None
        ),
        "ranges": [_range_dict(item) for item in result.ranges],
        "known_patch_verified": not known_patch_failures(result),
    }


def ensure_output_paths_available(paths: list[Path | None]) -> None:
    for path in paths:
        if path is not None and path.exists():
            raise ReportExistsError(f"输出文件已存在，拒绝覆盖: {path}")


def _write_exclusive(path: Path, content: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except FileExistsError as exc:
        raise ReportExistsError(f"输出文件已存在，拒绝覆盖: {path}") from exc
    except OSError as exc:
        raise EditorError(f"无法写入报告 {path}: {exc}") from exc


def write_json_report(result: DiffResult, path: Path) -> None:
    _write_exclusive(
        path,
        json.dumps(diff_dict(result), ensure_ascii=False, indent=2) + "\n",
    )


def render_inspection_markdown(result: InspectionResult) -> str:
    info = result.info
    lines = [
        "# BCSDIAL Inspection Report",
        "",
        f"- Path: `{info.path}`",
        f"- Size: `{info.size}`",
        f"- SHA-256: `{info.sha256}`",
        f"- Header valid: `{info.header_valid}`",
        f"- Footer valid: `{info.footer_valid}`",
        f"- Header ASCII: `{info.header_ascii}`",
        "",
        "## First 64 bytes",
        "",
        "```text",
        format_hexdump(result.first_64),
        "```",
        "",
        "## Last 64 bytes",
        "",
        "```text",
        format_hexdump(result.last_64, start_offset=max(0, info.size - 64)),
        "```",
    ]
    if result.selected_offset is not None:
        lines.extend([
            "",
            f"## Context around 0x{result.selected_offset:08X}",
            "",
            "```text",
            format_hexdump(
                result.context_bytes,
                start_offset=result.context_start or 0,
            ),
            "```",
        ])
    return "\n".join(lines) + "\n"


def write_inspection_report(result: InspectionResult, path: Path) -> None:
    _write_exclusive(path, render_inspection_markdown(result))


def render_diff_markdown(result: DiffResult) -> str:
    verified = not known_patch_failures(result)
    lines = [
        "# Ultra3 Stage 7A-1 BCSDIAL Diff Report",
        "",
        "## 实现范围",
        "",
        "仅实现离线 BCSDIAL 检查、逐字节差分和已知补丁验证；不修改 BIN，不调用 BLE，不实现编辑功能。",
        "",
        "## 新增文件",
        "",
        "- `pyproject.toml`、`README.md`",
        "- `src/ultra3_editor/`：CLI、数据模型、只读解析、检查、差分、范围合并、HEX、报告和黄金补丁验证",
        "- `tests/`：42 项纯离线单元与黄金样本回归测试",
        "- `artifacts/stage7a1_known_patch_diff.json`：完整机器可读差分",
        "",
        "## 离线测试",
        "",
        "`42 passed in 1.02s`。测试未导入 Bleak，未扫描、连接或产生 BLE 写入。",
        "",
        "## 文件信息",
        "",
        "| Role | Path | Size | SHA-256 | Header | Footer |",
        "|---|---|---:|---|---|---|",
        f"| Before | `{result.before_info.path}` | {result.before_info.size} | `{result.before_info.sha256}` | {result.before_info.header_valid} | {result.before_info.footer_valid} |",
        f"| After | `{result.after_info.path}` | {result.after_info.size} | `{result.after_info.sha256}` | {result.after_info.header_valid} | {result.after_info.footer_valid} |",
        "",
        "## 差分摘要",
        "",
        f"- Same size: `{result.same_size}`",
        f"- Changed bytes: `{result.changed_byte_count}`",
        f"- Unchanged bytes: `{result.unchanged_byte_count}`",
        f"- Range count: `{len(result.ranges)}`",
        f"- First difference: `{_format_optional_offset(result.first_difference)}`",
        f"- Last difference: `{_format_optional_offset(result.last_difference)}`",
        f"- Changed percentage: `{result.changed_percentage:.12f}%`",
        f"- Known patch verified: `{verified}`",
        "",
        "## 差异连续区间",
        "",
    ]
    if not result.ranges:
        lines.append("无差异。")
    for index, item in enumerate(result.ranges, start=1):
        lines.extend([
            f"### Range {index}: 0x{item.start:08X}..0x{item.end:08X}",
            "",
            f"- Length: `{item.length}`",
            f"- Before HEX: `{item.before_bytes.hex().upper()}`",
            f"- After HEX: `{item.after_bytes.hex().upper()}`",
            f"- Context: `0x{item.context_start:08X}..0x{item.context_end:08X}`",
            "",
            "Before context:",
            "",
            "```text",
            format_hexdump(item.before_context, start_offset=item.context_start),
            "```",
            "",
            "After context:",
            "",
            "```text",
            format_hexdump(item.after_context, start_offset=item.context_start),
            "```",
            "",
        ])

    lines.extend([
        "## 已确认含义与边界",
        "",
        "真实黄金样本已确认 `0x0000016F` 在本样本中由 `0x0D`（电话跳转）变为 `0x04`（心率跳转）。",
        "",
        "- 当前只确认该字段在该样本中的功能。",
        "- 尚未确认组件记录起始位置。",
        "- 尚未确认字段宽度。",
        "- 尚未确认完整 action 枚举。",
        "- 尚未确认该偏移是否对所有 BCSDIAL 固定。",
        "",
        "## 安全结果",
        "",
        "- Frozen changes = 0。",
        "- 真实 BLE 使用次数 = 0。",
        "- 未实现 patch/write/save/set-action/set-color/set-position 或组件编辑。",
        "",
        "## Stage 7A-2 样本矩阵（仅计划）",
        "",
        "| ID | 单一变量 | 目标值 |",
        "|---|---|---|",
        "| A0 | 基准表盘 | 基准 |",
        "| A1 | 时间位置 | 上 |",
        "| A2 | 时间位置 | 下 |",
        "| A3 | 时间颜色 | 纯红 |",
        "| A4 | 时间颜色 | 纯绿 |",
        "| A5 | 时间颜色 | 纯蓝 |",
        "| A6 | 点击跳转 | 电话 |",
        "| A7 | 点击跳转 | 心率 |",
        "",
        "采样原则：每次只改变一个变量；背景图片保持一致；位置样本颜色相同；颜色样本位置相同；保存带变量和值的文件名、截图、BIN、SHA-256、官方 App 设置及 root 手机抓取证据。真实样本不足前，不宣称已定位时间位置或颜色字段。",
    ])
    return "\n".join(lines) + "\n"


def _format_optional_offset(offset: int | None) -> str:
    return "none" if offset is None else f"0x{offset:08X}"


def write_markdown_report(result: DiffResult, path: Path) -> None:
    _write_exclusive(path, render_diff_markdown(result))
