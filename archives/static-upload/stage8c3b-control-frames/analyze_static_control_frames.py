from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


EXPECTED_LAYER = "android.bluetooth.IBluetoothGatt$Stub$Proxy.writeCharacteristic"
EXPECTED_OVERLOAD = "(int, java.lang.String, int, int, int, [B)"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 根值必须是 object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} 不是 JSON object")
        records.append(value)
    return records


def _write_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _ranges(offsets: list[int]) -> list[list[int]]:
    if not offsets:
        return []
    output: list[list[int]] = []
    start = previous = offsets[0]
    for offset in offsets[1:]:
        if offset != previous + 1:
            output.append([start, previous])
            start = offset
        previous = offset
    output.append([start, previous])
    return output


def _compare_hex(left: list[str], right: list[str]) -> dict[str, Any]:
    pairs: list[dict[str, Any]] = []
    for index in range(max(len(left), len(right))):
        if index >= len(left) or index >= len(right):
            pairs.append({"index": index, "status": "frame_missing"})
            continue
        first = bytes.fromhex(left[index])
        second = bytes.fromhex(right[index])
        limit = min(len(first), len(second))
        differences = [
            {"offset": offset, "a": first[offset], "b": second[offset]}
            for offset in range(limit)
            if first[offset] != second[offset]
        ]
        equal_offsets = [
            offset for offset in range(limit) if first[offset] == second[offset]
        ]
        pairs.append({
            "index": index,
            "status": "identical" if first == second else "different",
            "a_length": len(first),
            "b_length": len(second),
            "common_ranges": _ranges(equal_offsets),
            "difference_offsets": [item["offset"] for item in differences],
            "differences": differences,
        })
    return {
        "a_count": len(left),
        "b_count": len(right),
        "pairs": pairs,
    }


def _find_all(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while needle:
        offset = data.find(needle, start)
        if offset < 0:
            break
        offsets.append(offset)
        start = offset + 1
    return offsets


def _observations(sample: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = sample["metadata"]
    layers = {
        name: metadata[name]
        for name in ("input_image", "static_container", "region_stream", "c9_frame_stream")
    }
    facts = {"c9_count_le16": int(sample["c9_count"]).to_bytes(2, "little")}
    for name, layer in layers.items():
        facts[f"{name}_size_le32"] = int(layer["size"]).to_bytes(4, "little")
        if layer.get("sha256"):
            facts[f"{name}_sha256_bytes"] = bytes.fromhex(layer["sha256"])
    output: list[dict[str, Any]] = []
    for command in ("C8", "CA"):
        for frame_index, value in enumerate(sample[f"{command.lower()}_hex"]):
            frame = bytes.fromhex(value)
            for fact, encoded in facts.items():
                offsets = _find_all(frame, encoded)
                if offsets:
                    output.append({
                        "command": command,
                        "frame_index": frame_index,
                        "observation": fact,
                        "offsets": offsets,
                        "claim_level": "byte_match_only",
                    })
    return output


def analyze_sample(name: str, jsonl_path: Path) -> dict[str, Any]:
    metadata_path = jsonl_path.parent / "session_metadata.json"
    metadata = _read_json(metadata_path)
    records = _read_jsonl(jsonl_path)
    frames = [record for record in records if record.get("kind") == "frame"]
    summaries = [record for record in records if record.get("kind") == "summary"]
    ordinals = [record.get("ordinal") for record in frames]
    errors: list[str] = []
    if ordinals != list(range(1, len(frames) + 1)):
        errors.append("ordinal 不是从 1 开始的连续原始顺序")
    binder_ordinals = [record.get("binder_invocation_ordinal") for record in frames]
    if any(
        not isinstance(current, int) or current <= previous
        for previous, current in zip([0, *binder_ordinals], binder_ordinals)
    ):
        errors.append("Binder invocation ordinal 不是严格递增")
    for record in frames:
        if record.get("overload") != EXPECTED_OVERLOAD:
            errors.append("Binder overload 不匹配")
        if record.get("address") != "<redacted>":
            errors.append("address 未脱敏")
        redacted_strings = record.get("string_args_redacted")
        if isinstance(redacted_strings, list):
            redacted_strings = len([
                item for item in redacted_strings
                if isinstance(item, dict) and item.get("value") == "<redacted>"
            ])
        if redacted_strings != 1:
            errors.append("string 参数脱敏计数不匹配")

    by_command = {
        command: [record for record in frames if record.get("command") == command]
        for command in ("C8", "C9", "CA")
    }
    c9_sequences = [record.get("sequence") for record in by_command["C9"]]
    counts = Counter(c9_sequences)
    expected_count = int(metadata["expected_c9_count"])
    missing = [sequence for sequence in range(expected_count) if counts[sequence] == 0]
    duplicates = sorted(sequence for sequence, count in counts.items() if count > 1)
    out_of_order = c9_sequences != list(range(expected_count))
    first_c9_ordinal = by_command["C9"][0]["ordinal"] if by_command["C9"] else None
    last_c9_ordinal = by_command["C9"][-1]["ordinal"] if by_command["C9"] else None
    controls = sorted(by_command["C8"] + by_command["CA"], key=lambda item: item["ordinal"])
    before = [record for record in controls if first_c9_ordinal and record["ordinal"] < first_c9_ordinal]
    after = [record for record in controls if last_c9_ordinal and record["ordinal"] > last_c9_ordinal]
    c8_hex = [record["frame_hex"] for record in by_command["C8"]]
    ca_hex = [record["frame_hex"] for record in by_command["CA"]]
    checksum_failures = [
        record["sequence"] for record in by_command["C9"]
        if record.get("checksum_valid") is not True
    ]
    malformed = [
        record["sequence"] for record in by_command["C9"]
        if record.get("validation_errors")
    ]
    bad_regions = [
        record["sequence"] for record in by_command["C9"]
        if record.get("c9_region_length") != record.get("value_length", 0) - 6
    ]
    bad_full_hex = [
        record["sequence"] for record in by_command["C9"]
        if (record.get("frame_hex") is not None) != (record.get("sequence") in {0, 1528})
    ]
    handle_histogram = {
        str(handle): count
        for handle, count in sorted(Counter(
            record.get("observed_handle") for record in frames
        ).items())
    }

    if not c8_hex:
        errors.append("未捕获 C8")
    if not ca_hex:
        errors.append("未捕获 CA")
    if len(by_command["C9"]) != expected_count:
        errors.append("C9 count 与 metadata 不匹配")
    if missing:
        errors.append("存在缺失 C9 sequence")
    if duplicates:
        errors.append("存在重复 C9 sequence")
    if out_of_order:
        errors.append("C9 sequence 原始顺序不连续")
    if checksum_failures:
        errors.append("存在 C9 checksum 失败")
    if malformed:
        errors.append("存在 malformed C9")
    if bad_regions:
        errors.append("C9 region length 不匹配")
    if bad_full_hex:
        errors.append("C9 compact HEX 策略不匹配")
    if len(summaries) != 1 or not records or records[-1].get("kind") != "summary":
        errors.append("JSONL 末尾没有唯一 summary")
    else:
        summary = summaries[0]
        summary_duplicates = summary.get("duplicates")
        if isinstance(summary_duplicates, list):
            summary_duplicates = summary.get("duplicate_count", len(summary_duplicates))
        if summary.get("c8_count") != len(by_command["C8"]) or summary.get("c9_count") != len(by_command["C9"]) or summary.get("ca_count") != len(by_command["CA"]):
            errors.append("summary 协议计数不匹配")
        if summary.get("unique_sequences") != expected_count or summary.get("sequence_range") != f"0..{expected_count - 1}":
            errors.append("summary sequence 不匹配")
        if summary.get("missing_count") != len(missing) or summary_duplicates != len(duplicates):
            errors.append("summary missing/duplicates 不匹配")
        if summary.get("malformed_c9") != len(malformed) or summary.get("out_of_range_sequences"):
            errors.append("summary malformed/out-of-range 不匹配")
        if summary.get("handle_histogram") != handle_histogram:
            errors.append("summary handle histogram 不匹配")
    if not before:
        errors.append("第一个 C9 前没有控制帧")
    if not after:
        errors.append("最后一个 C9 后没有控制帧")
    if not metadata.get("greenlion_reported_success"):
        errors.append("GreenLion 成功未确认")
    if not metadata.get("watch_display_confirmed"):
        errors.append("手表显示成功未确认")

    result = {
        "sample": name,
        "status": "PASS" if not errors else "FAIL",
        "capture_layer": EXPECTED_LAYER,
        "binder_overload": EXPECTED_OVERLOAD,
        "input_image": metadata["input_image"],
        "static_container": metadata["static_container"],
        "region_stream": metadata["region_stream"],
        "c9_frame_stream": metadata["c9_frame_stream"],
        "total_target_writes": len(frames),
        "c8_count": len(by_command["C8"]),
        "c9_count": len(by_command["C9"]),
        "ca_count": len(by_command["CA"]),
        "first_c9_ordinal": first_c9_ordinal,
        "last_c9_ordinal": last_c9_ordinal,
        "sequence_range": (
            f"{min(c9_sequences)}..{max(c9_sequences)}" if c9_sequences else None
        ),
        "missing": missing,
        "duplicates": duplicates,
        "out_of_order": out_of_order,
        "checksum_failures": checksum_failures,
        "malformed_c9": malformed,
        "observed_handle_histogram": handle_histogram,
        "before_first_c9_frames": [
            {"ordinal": item["ordinal"], "command": item["command"], "length": item["value_length"], "hex": item["frame_hex"]}
            for item in before
        ],
        "after_last_c9_frames": [
            {"ordinal": item["ordinal"], "command": item["command"], "length": item["value_length"], "hex": item["frame_hex"]}
            for item in after
        ],
        "c8_hex": c8_hex,
        "ca_hex": ca_hex,
        "c8_lengths": [item["value_length"] for item in by_command["C8"]],
        "ca_lengths": [item["value_length"] for item in by_command["CA"]],
        "greenlion_reported_success": bool(metadata.get("greenlion_reported_success")),
        "watch_display_confirmed": bool(metadata.get("watch_display_confirmed")),
        "capture_summary": summaries[0] if len(summaries) == 1 else None,
        "errors": sorted(set(errors)),
        "metadata": metadata,
    }
    result["observations"] = _observations(result)
    result.pop("metadata")
    return result


def parse_sample(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--sample 必须为 NAME=JSONL")
    name, path = value.split("=", 1)
    if not name or not path:
        raise argparse.ArgumentTypeError("--sample 必须为 NAME=JSONL")
    return name, Path(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="append", type=parse_sample, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if len(args.sample) < 2:
        parser.error("至少需要两个 --sample")

    samples = [analyze_sample(name, path) for name, path in args.sample]
    comparisons: dict[str, Any] = {}
    for index in range(1, len(samples)):
        key = f"{samples[0]['sample']}_vs_{samples[index]['sample']}"
        comparisons[key] = {
            "c8": _compare_hex(samples[0]["c8_hex"], samples[index]["c8_hex"]),
            "ca": _compare_hex(samples[0]["ca_hex"], samples[index]["ca_hex"]),
        }
    document = {
        "status": "PASS" if all(sample["status"] == "PASS" for sample in samples) else "FAIL",
        "sample_count": len(samples),
        "terminology": {
            "input_image": "原始 JPG/PNG",
            "static_container": "351617 字节 BIN / C9 DATA concat",
            "region_stream": "353146 字节 DATA+checksum 区域流",
            "c9_frame_stream": "362320 字节完整 C9 帧流",
        },
        "samples": samples,
        "comparisons": comparisons,
        "interpretation_boundary": "仅报告原始差异和字节匹配；两个样本不足以永久命名字段。",
    }
    _write_exclusive(args.output, document)
    for (name, path), sample in zip(args.sample, samples):
        _write_exclusive(path.parent.parent / "result.json", sample)
        print(f"{name}: {sample['status']}")
    print(f"overall: {document['status']}")
    return 0 if document["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
