from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .bcsdial import BCSDIALPayload
from .capture_parser import compare_capture, parse_capture
from .constants import DEFAULT_DEVICE_NAME, REQUIRED_WRITE_WITHOUT_RESPONSE_SIZE
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
    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("--timeout", type=float, default=10.0)
    scan_parser.add_argument("--name", default=DEFAULT_DEVICE_NAME)
    scan_parser.add_argument("--json", action="store_true")
    scan_parser.add_argument("--log-file", type=Path)
    info_parser = subparsers.add_parser("info")
    info_parser.add_argument("--device", required=True)
    info_parser.add_argument("--connect-timeout", type=float, default=20.0)
    info_parser.add_argument("--log-file", type=Path)
    listen_parser = subparsers.add_parser("listen")
    listen_parser.add_argument("--device", required=True)
    listen_parser.add_argument("--seconds", type=float, default=30.0)
    listen_parser.add_argument("--connect-timeout", type=float, default=20.0)
    listen_parser.add_argument("--log-file", type=Path)
    subparsers.add_parser("transport-self-test")
    prepare_parser = subparsers.add_parser("prepare-bcsdial")
    prepare_parser.add_argument("--device")
    prepare_parser.add_argument("--file", required=True)
    prepare_parser.add_argument("--ready-timeout", type=float, default=60.0)
    prepare_parser.add_argument("--connect-timeout", type=float, default=20.0)
    prepare_parser.add_argument("--log-file", type=Path)
    prepare_parser.add_argument("--dry-run", action="store_true")
    return parser


def _logger(path: Path | None) -> "Stage5Logger":
    from .logging_utils import Stage5Logger

    return Stage5Logger(path, human_output=False)


async def _scan_command(args: argparse.Namespace) -> int:
    from .bleak_transport import BleakTransport
    from .stage5 import run_scan

    result = await run_scan(
        BleakTransport(), timeout=args.timeout, target_name=args.name, logger=_logger(args.log_file)
    )
    rows = [
        {
            "name": device.name,
            "device_id": device.device_id,
            "rssi": device.rssi,
            "matches_target": device.name == args.name,
            "platform": device.platform,
        }
        for device in result.devices
    ]
    if args.json:
        print(json.dumps({
            "target_name": args.name,
            "matching_count": result.matching_count,
            "devices": rows,
        }, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            rssi = row["rssi"] if row["rssi"] is not None else "unknown"
            print(
                f"名称={row['name'] or 'unknown'} 设备ID={row['device_id']} "
                f"RSSI={rssi} 匹配={row['matches_target']}"
            )
        print(f"目标名称重复数量: {result.matching_count}")
    return 0 if result.matching_count else 1


def _print_gatt(validation: "GattValidation", disconnected: bool) -> int:
    checks = (
        (validation.service_found, "service found"),
        (validation.ff02_found, "FF02 found"),
        (validation.ff02_write_without_response, "FF02 supports write without response"),
        (validation.ff03_found, "FF03 found"),
        (validation.ff03_notify, "FF03 supports notify"),
    )
    print("[OK] connected")
    for ok, label in checks:
        print(f"[{'OK' if ok else 'FAIL'}] {label}")
    maximum = validation.maximum_write_without_response
    print(f"[INFO] maximum write without response: {maximum if maximum is not None else 'unknown'}")
    if maximum is None:
        print("[WARN] cannot confirm 237-byte Write Without Response capacity")
    elif maximum < REQUIRED_WRITE_WITHOUT_RESPONSE_SIZE:
        print("[FAIL] maximum write without response is below 237 bytes")
    print(f"[INFO] MTU: {validation.mtu_size if validation.mtu_size is not None else 'unknown'}")
    print(f"[INFO] platform: {validation.platform}")
    print(f"[{'OK' if disconnected else 'FAIL'}] disconnected")
    return 0 if validation.required_gatt_ok and not validation.capacity_below_required and disconnected else 1


async def _info_command(args: argparse.Namespace) -> int:
    from .bleak_transport import BleakTransport
    from .stage5 import run_info

    result = await run_info(
        BleakTransport(),
        device_id=args.device,
        timeout=args.connect_timeout,
        logger=_logger(args.log_file),
    )
    return _print_gatt(result.validation, result.disconnected)


async def _listen_command(args: argparse.Namespace) -> int:
    from .bleak_transport import BleakTransport
    from .stage5 import run_listen

    result = await run_listen(
        BleakTransport(),
        device_id=args.device,
        seconds=args.seconds,
        timeout=args.connect_timeout,
        logger=_logger(args.log_file),
    )
    print("[OK] connected")
    print("[OK] GATT validated")
    print("[OK] FF03 notify subscribed")
    print(f"[INFO] notifications: {result.notifications}")
    print(f"[{'OK' if result.disconnected else 'FAIL'}] disconnected")
    print("[OK] FF02 writes: 0")
    return 0 if result.disconnected else 1


async def _transport_self_test() -> int:
    from .constants import FF02_UUID
    from .fake_transport import FakeBleTransport
    from .stage5 import run_info, run_listen, run_scan

    transport = FakeBleTransport(notifications_on_subscribe=[bytes.fromhex("BC7203021E001E")])
    logger = _logger(None)
    scan = await run_scan(transport, timeout=0, target_name=DEFAULT_DEVICE_NAME, logger=logger)
    info = await run_info(transport, device_id="FAKE-ULTRA3-1", timeout=1, logger=logger)
    listen = await run_listen(
        transport, device_id="FAKE-ULTRA3-1", seconds=0, timeout=1, logger=logger
    )
    ok = (
        scan.matching_count == 1
        and info.validation.required_gatt_ok
        and listen.notifications == 1
        and not transport.writes
        and all(uuid != FF02_UUID for uuid, _data in transport.writes)
    )
    print(f"[{'OK' if ok else 'FAIL'}] fake scan/connect/GATT/notify/disconnect")
    print(f"[{'OK' if not transport.writes else 'FAIL'}] FF02 writes: {len(transport.writes)}")
    return 0 if ok else 1


async def _prepare_command(args: argparse.Namespace) -> int:
    payload = BCSDIALPayload.from_path(Path(args.file))
    if args.dry_run:
        print(f"文件大小: {payload.size}")
        print(f"包数: {payload.packet_count}")
        print(f"C8 HEX: {payload.build_prepare_frame().hex().upper()}")
        print("FF02 writes: 0")
        return 0
    if not args.device:
        raise Ultra3UploaderError("非 dry-run 模式必须提供 --device")
    if args.ready_timeout <= 0 or args.connect_timeout <= 0:
        raise Ultra3UploaderError("timeout 必须大于 0")
    from .bleak_transport import BleakTransport
    from .prepare_bcsdial import run_prepare_bcsdial

    result = await run_prepare_bcsdial(
        BleakTransport(),
        payload,
        device_id=args.device,
        ready_timeout=args.ready_timeout,
        connect_timeout=args.connect_timeout,
        logger=_logger(args.log_file),
    )
    print(f"[OK] C8 sent: {result.c8_hex}")
    print(f"[OK] BC72 countdown: {len(result.countdown)} packets, 30..0")
    print(f"[{'OK' if result.d1_received else 'FAIL'}] D1 ready")
    print(f"[{'OK' if result.c8_response_matched else 'FAIL'}] C8 response matched")
    print(f"[OK] FF02 writes: {result.ff02_write_count}")
    print(f"[OK] C9 writes: {result.c9_write_count}")
    print(f"[OK] CA writes: {result.ca_write_count}")
    print(f"[{'OK' if result.disconnected else 'FAIL'}] disconnected")
    return 0 if result.disconnected else 1


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    try:
        if args.command == "inspect":
            return inspect_file(args.file)
        if args.command == "build":
            return build_packets(args.file, args.output, args.force)
        if args.command == "compare-capture":
            return compare(args.file, args.capture)
        if args.command == "scan":
            return asyncio.run(_scan_command(args))
        if args.command == "info":
            return asyncio.run(_info_command(args))
        if args.command == "listen":
            return asyncio.run(_listen_command(args))
        if args.command == "transport-self-test":
            return asyncio.run(_transport_self_test())
        return asyncio.run(_prepare_command(args))
    except KeyboardInterrupt:
        print("已取消；BLE 清理流程已执行。", file=sys.stderr)
        return 130
    except Ultra3UploaderError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
