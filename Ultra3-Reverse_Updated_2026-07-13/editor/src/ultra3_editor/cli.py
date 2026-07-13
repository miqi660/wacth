from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .differ import diff_bcsdial
from .errors import EditorError
from .hexdump import format_hexdump, hex_bytes
from .inspector import inspect_bcsdial
from .known_patch import verify_known_patch
from .models import ContainerKind
from .ranges import parse_offset
from .capture_reader import CAPTURE_FORMATS
from .reconstruction_reports import (
    write_reconstructed_binary,
    write_reconstruction_json,
    write_reconstruction_markdown,
)
from .reconstructor import reconstruct_capture
from .reports import (
    ensure_output_paths_available,
    inspection_dict,
    write_inspection_report,
    write_json_report,
    write_markdown_report,
)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ultra3_editor")
    commands = parser.add_subparsers(dest="command", required=True)

    inspect_parser = commands.add_parser("inspect")
    inspect_parser.add_argument("file")
    inspect_parser.add_argument("--offset", type=parse_offset)
    inspect_parser.add_argument("--context", type=int, default=32)
    inspect_parser.add_argument("--json", action="store_true")
    inspect_parser.add_argument("--report", type=Path)

    diff_parser = commands.add_parser("diff")
    diff_parser.add_argument("before")
    diff_parser.add_argument("after")
    diff_parser.add_argument("--context", type=int, default=32)
    diff_parser.add_argument("--max-ranges", type=int, default=20)
    diff_parser.add_argument("--json", type=Path)
    diff_parser.add_argument("--report", type=Path)

    verify_parser = commands.add_parser("verify-known-patch")
    verify_parser.add_argument("before")
    verify_parser.add_argument("after")

    reconstruct_parser = commands.add_parser("reconstruct-c9")
    reconstruct_parser.add_argument("capture_file")
    reconstruct_parser.add_argument(
        "--format",
        choices=CAPTURE_FORMATS,
        default="auto",
    )
    reconstruct_parser.add_argument("--session-index", type=int)
    reconstruct_parser.add_argument(
        "--container",
        choices=[kind.value for kind in ContainerKind],
        default=ContainerKind.BCSDIAL.value,
    )
    reconstruct_parser.add_argument("--output", type=Path)
    reconstruct_parser.add_argument("--json", type=Path)
    reconstruct_parser.add_argument("--report", type=Path)

    static_parser = commands.add_parser("reconstruct-static-diy")
    static_parser.add_argument("capture_file")
    static_parser.add_argument(
        "--format",
        choices=CAPTURE_FORMATS,
        default="auto",
    )
    static_parser.add_argument("--session-index", type=int)
    static_parser.add_argument("--output", type=Path)
    static_parser.add_argument("--json", type=Path)
    static_parser.add_argument("--report", type=Path)
    static_parser.set_defaults(container=ContainerKind.GREENLION_STATIC.value)
    return parser


def _inspect_command(args: argparse.Namespace) -> int:
    ensure_output_paths_available([args.report])
    result = inspect_bcsdial(args.file, offset=args.offset, context=args.context)
    if args.report is not None:
        write_inspection_report(result, args.report)
    if args.json:
        print(json.dumps(inspection_dict(result), ensure_ascii=False, indent=2))
    else:
        info = result.info
        print(f"Path: {info.path}")
        print(f"Size: {info.size}")
        print(f"SHA-256: {info.sha256}")
        print(f"Header valid: {info.header_valid}")
        print(f"Footer valid: {info.footer_valid}")
        print(f"Header ASCII: {info.header_ascii}")
        print(f"First 64 HEX: {result.first_64.hex().upper()}")
        print(f"Last 64 HEX: {result.last_64.hex().upper()}")
        stats = result.statistics
        print(
            "Byte statistics: "
            f"zero={stats.zero_count} nonzero={stats.nonzero_count} "
            f"unique={stats.unique_byte_count} "
            f"most_common={stats.most_common_byte:02X}:{stats.most_common_count}"
        )
        if result.selected_offset is not None:
            print(f"Offset: 0x{result.selected_offset:08X}")
            print(
                f"Context: 0x{result.context_start:08X}..0x{result.context_end:08X}"
            )
            print(format_hexdump(
                result.context_bytes,
                start_offset=result.context_start or 0,
            ))
        print(f"BCSDIAL valid: {info.valid}")
    return 0 if result.info.valid else 1


def _diff_command(args: argparse.Namespace) -> int:
    if args.max_ranges < 0:
        raise EditorError("--max-ranges 不能为负数")
    ensure_output_paths_available([args.json, args.report])
    result = diff_bcsdial(args.before, args.after, context=args.context)
    if args.json is not None:
        write_json_report(result, args.json)
    if args.report is not None:
        write_markdown_report(result, args.report)

    print(f"Before: {result.before_info.path}")
    print(f"Before size/SHA-256: {result.before_info.size} {result.before_info.sha256}")
    print(f"After: {result.after_info.path}")
    print(f"After size/SHA-256: {result.after_info.size} {result.after_info.sha256}")
    print(f"Same size: {result.same_size}")
    print(f"Changed bytes: {result.changed_byte_count}")
    print(f"Range count: {len(result.ranges)}")
    print(f"Unchanged bytes: {result.unchanged_byte_count}")
    print(f"Changed percentage: {result.changed_percentage:.12f}%")
    print(f"First difference: {_offset_text(result.first_difference)}")
    print(f"Last difference: {_offset_text(result.last_difference)}")
    for item in result.ranges[: args.max_ranges]:
        print(
            f"Range 0x{item.start:08X}..0x{item.end:08X} "
            f"length={item.length} before={hex_bytes(item.before_bytes)} "
            f"after={hex_bytes(item.after_bytes)}"
        )
    hidden = len(result.ranges) - min(len(result.ranges), args.max_ranges)
    if hidden:
        print(f"... {hidden} ranges omitted from terminal output")
    return 0


def _offset_text(offset: int | None) -> str:
    return "none" if offset is None else f"0x{offset:08X}"


def _verify_command(args: argparse.Namespace) -> int:
    result = diff_bcsdial(args.before, args.after, context=32)
    verify_known_patch(result)
    item = result.ranges[0]
    print("[OK] known patch verified")
    print(f"[OK] changed bytes: {result.changed_byte_count}")
    print(f"[OK] offset: 0x{item.start:08X}")
    print(f"[OK] before: {item.before_bytes.hex().upper()}")
    print(f"[OK] after: {item.after_bytes.hex().upper()}")
    print(f"[OK] unchanged bytes: {result.unchanged_byte_count}")
    return 0


def _reconstruct_command(args: argparse.Namespace) -> int:
    ensure_output_paths_available([args.output, args.json, args.report])
    result = reconstruct_capture(
        args.capture_file,
        capture_format=args.format,
        session_index=args.session_index,
        container=args.container,
    )
    if result.status == "COMPLETE" and args.output is not None:
        write_reconstructed_binary(result.selected_session.reconstructed_data, args.output)
    if args.json is not None:
        write_reconstruction_json(result, args.json, output_path=args.output)
    if args.report is not None:
        write_reconstruction_markdown(result, args.report, output_path=args.output)

    session = result.selected_session
    c8 = session.c8_packet
    if result.status != "COMPLETE" or c8 is None:
        print("[FAIL] reconstruction rejected", file=sys.stderr)
        for error in result.errors:
            print(f"[FAIL] {error}", file=sys.stderr)
        return 2
    print(f"[OK] upload session: {session.index}")
    print(f"[OK] container: {result.container.value}")
    print(f"[OK] C8: {session.c8_record.payload.hex().upper()}")
    print(f"[OK] declared size: {c8.declared_size}")
    print(f"[OK] packet count: {c8.declared_packet_count}")
    print(
        f"[OK] sequence: {session.c9_packets[0].sequence}.."
        f"{session.c9_packets[-1].sequence}"
    )
    checksum_passed = sum(packet.checksum_valid for packet in session.c9_packets)
    print(f"[OK] checksum: {checksum_passed}/{len(session.c9_packets)}")
    print(f"[OK] reconstructed size: {result.reconstructed_size}")
    if result.container is ContainerKind.BCSDIAL:
        print("[OK] BCSDIAL header")
        print("[OK] BCBC footer")
    else:
        print(f"[OK] header check: {result.header_check.value}")
        print(f"[OK] footer check: {result.footer_check.value}")
    print(f"[OK] raw DATA size: {result.raw_data_size}")
    print(f"[OK] transformation: {result.transformation}")
    print(f"[OK] SHA-256: {result.reconstructed_sha256}")
    print("[OK] real BLE usage: 0")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        args = make_parser().parse_args(argv)
        if args.command == "inspect":
            return _inspect_command(args)
        if args.command == "diff":
            return _diff_command(args)
        if args.command == "verify-known-patch":
            return _verify_command(args)
        return _reconstruct_command(args)
    except EditorError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
