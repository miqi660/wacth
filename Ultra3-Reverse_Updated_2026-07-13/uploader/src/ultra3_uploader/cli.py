from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .bcsdial import BCSDIALPayload
from .capture_parser import compare_capture, parse_capture
from .errors import OutputExistsError, Ultra3UploaderError


def _payload(path: str) -> BCSDIALPayload:
    return BCSDIALPayload.from_path(Path(path))


def inspect_file(path: str) -> int:
    payload = _payload(path)
    print("[OK] BCSDIAL header")
    print("[OK] BCBC footer")
    print(f"文件大小: {payload.size}")
    print(f"SHA-256: {payload.sha256}")
    print(f"C9 包数: {payload.packet_count}")
    print(f"最后一包 DATA: {payload.final_chunk_size}")
    print(f"C8 HEX: {payload.build_prepare_frame().hex().upper()}")
    return 0


def build_packets(path: str, output: str, force: bool) -> int:
    payload = _payload(path)
    output_path = Path(output)
    if output_path.exists() and not force:
        raise OutputExistsError(f"输出文件已存在: {output_path}；使用 --force 才可覆盖")
    records = [{
        "type": "C8",
        "length": len(payload.build_prepare_frame()),
        "hex": payload.build_prepare_frame().hex().upper(),
    }]
    records.extend({
        "type": "C9",
        "sequence": sequence,
        "length": len(frame),
        "hex": frame.hex().upper(),
    } for sequence, frame in enumerate(payload.iter_data_frames()))
    try:
        with output_path.open("x" if not force else "w", encoding="utf-8", newline="\n") as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError as exc:
        raise Ultra3UploaderError(f"无法写入输出文件 {output_path}: {exc}") from exc
    print(f"已生成: {output_path}")
    print(f"C8: 1，C9: {payload.packet_count}")
    return 0


def _status(ok: bool, text: str) -> str:
    return f"[{'OK' if ok else 'FAIL'}] {text}"


def compare(path: str, capture_path: str) -> int:
    payload = _payload(path)
    result = compare_capture(payload, parse_capture(Path(capture_path)))
    print(_status(result.header_ok, "BCSDIAL header"))
    print(_status(result.footer_ok, "BCBC footer"))
    print(_status(True, f"file size: {result.file_size}"))
    print(_status(result.c8_exact, "C8 exact match"))
    print(_status(result.expected_packets == result.captured_packets, f"C9 packets: {result.captured_packets}"))
    end = result.captured_packets - 1
    print(_status(result.sequence_exact, f"sequence: 0..{end}"))
    print(_status(result.valid_checksums == result.captured_packets, f"checksums: {result.valid_checksums}/{result.captured_packets}"))
    print(_status(not result.missing_sequences, f"missing packets: {len(result.missing_sequences)}"))
    print(_status(not result.duplicate_sequences, f"duplicate packets: {len(result.duplicate_sequences)}"))
    print(_status(not result.out_of_order, "packet order"))
    print(_status(result.full_packet_exact, "full packet comparison: exact"))
    print(_status(result.reconstructed_exact, "reconstructed file matches input"))
    return 0 if result.ok else 1


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ultra3_uploader")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("file")
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("file")
    build_parser.add_argument("--output", required=True)
    build_parser.add_argument("--force", action="store_true")
    compare_parser = subparsers.add_parser("compare-capture")
    compare_parser.add_argument("--file", required=True)
    compare_parser.add_argument("--capture", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    try:
        if args.command == "inspect":
            return inspect_file(args.file)
        if args.command == "build":
            return build_packets(args.file, args.output, args.force)
        return compare(args.file, args.capture)
    except Ultra3UploaderError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2

