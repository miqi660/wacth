from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ultra3_editor import (
    BuildDeterminismStatus,
    GoldenBuildStatus,
    GreenLionStaticBuildInput,
    build_greenlion_static_diy,
)


EXPECTED = (
    (
        "photo01",
        "1.JPG",
        "44B4893ACF6244119DE655B32C1CE760048F3128A24489B49FF24F7BB60FA664",
    ),
    (
        "photo02",
        "2.png",
        "CBD34D9BE77B138481AB7AD590326CC7437EE55C45DBECB532A0DF1C4F8A2763",
    ),
    (
        "photo03",
        "3.png",
        "19CAF5303D780FD6C4F46DED3219AD41E839FD495A1A96C51FD40EAE296C23B6",
    ),
    (
        "photo04",
        "4.png",
        "7F1F531F94E6C312FFEF167B03B2988AAC44A42790ABA19A6EED9F03795344C9",
    ),
    (
        "photo05",
        "5.png",
        "62E2B481F62C270937E090AD69CC87A34A11B7DDBEFFCA1B70D31AE638CB4078",
    ),
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验证 Stage 8B-1 公共核心的五份黄金结果")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sample_passed(item: dict) -> bool:
    return bool(
        item["run1_run2_exact_match"]
        and item["historical_exact_match"]
        and item["run1_sha256"] == item["expected_sha256"]
        and item["run2_sha256"] == item["expected_sha256"]
        and item["golden_status_run1"] == GoldenBuildStatus.MATCH.value
        and item["golden_status_run2"] == GoldenBuildStatus.MATCH.value
        and item["exact_golden_match_run1"] is True
        and item["exact_golden_match_run2"] is True
        and item["output_size_run1"] == 351_617
        and item["output_size_run2"] == 351_617
        and item["template_offset_zero_run1"] == 2
        and item["template_offset_zero_run2"] == 2
        and item["output_revalidated_run1"] is True
        and item["output_revalidated_run2"] is True
        and item["image_unchanged_run1"] is True
        and item["image_unchanged_run2"] is True
        and item["historical_output_unchanged"] is True
        and item["determinism_status_run1"]
        == BuildDeterminismStatus.NOT_EVALUATED.value
        and item["determinism_status_run2"]
        == BuildDeterminismStatus.NOT_EVALUATED.value
        and item["repeated_build_sha256_run1"] is None
        and item["repeated_build_sha256_run2"] is None
    )


def verification_complete(summary: dict) -> bool:
    return bool(
        summary["template_unchanged"] is True
        and summary["passed_count"] == 5
        and summary["repeat_deterministic_count"] == 5
        and summary["historical_exact_match_count"] == 5
    )


def main() -> int:
    args = parse_args()
    baseline = args.baseline
    output_dir = args.output_dir
    if not baseline.is_dir():
        raise NotADirectoryError(baseline)
    if output_dir.exists():
        raise FileExistsError(f"输出目录已存在，拒绝覆盖: {output_dir}")

    template = baseline / "sample" / "official_calibration_351617.bin"
    photos = baseline / "evidence" / "local_additions" / "test_photos"
    historical = baseline / "evidence" / "local_additions" / "test_builds"
    template_before = sha256_file(template)
    output_dir.mkdir(parents=True)
    records = []

    for sample, filename, expected_sha256 in EXPECTED:
        image = photos / filename
        historical_output = historical / sample / "real_file_351617.bin"
        image_before = sha256_file(image)
        historical_before = sha256_file(historical_output)
        run1_path = output_dir / f"{sample}_run1.bin"
        run2_path = output_dir / f"{sample}_run2.bin"
        run1 = build_greenlion_static_diy(
            GreenLionStaticBuildInput(image, template, run1_path)
        )
        run2 = build_greenlion_static_diy(
            GreenLionStaticBuildInput(image, template, run2_path)
        )
        run1_bytes = run1_path.read_bytes()
        run2_bytes = run2_path.read_bytes()
        historical_bytes = historical_output.read_bytes()
        records.append(
            {
                "sample": sample,
                "image": f"$FROZEN_BASELINE/evidence/local_additions/test_photos/{filename}",
                "historical_output": (
                    "$FROZEN_BASELINE/evidence/local_additions/test_builds/"
                    f"{sample}/real_file_351617.bin"
                ),
                "run1_output": f"$OUTPUT/{run1_path.name}",
                "run2_output": f"$OUTPUT/{run2_path.name}",
                "expected_sha256": expected_sha256,
                "run1_sha256": run1.output_sha256,
                "run2_sha256": run2.output_sha256,
                "run1_run2_exact_match": run1_bytes == run2_bytes,
                "historical_exact_match": run1_bytes == historical_bytes,
                "golden_status_run1": run1.golden_status.value,
                "golden_status_run2": run2.golden_status.value,
                "exact_golden_match_run1": run1.exact_golden_match,
                "exact_golden_match_run2": run2.exact_golden_match,
                "output_size_run1": run1.output_size,
                "output_size_run2": run2.output_size,
                "template_offset_zero_run1": run1.template_offset_zero,
                "template_offset_zero_run2": run2.template_offset_zero,
                "output_revalidated_run1": run1.output_revalidated,
                "output_revalidated_run2": run2.output_revalidated,
                "image_unchanged_run1": run1.image_unchanged,
                "image_unchanged_run2": run2.image_unchanged,
                "historical_output_unchanged": (
                    sha256_file(historical_output) == historical_before
                ),
                "determinism_status_run1": run1.determinism_status.value,
                "determinism_status_run2": run2.determinism_status.value,
                "repeated_build_sha256_run1": run1.repeated_build_sha256,
                "repeated_build_sha256_run2": run2.repeated_build_sha256,
            }
        )

    passed = sum(sample_passed(item) for item in records)
    repeat_count = sum(item["run1_run2_exact_match"] for item in records)
    historical_count = sum(item["historical_exact_match"] for item in records)
    template_after = sha256_file(template)
    result = {
        "implementation": "ultra3_editor.build_greenlion_static_diy",
        "frozen_builder_called": False,
        "sample_count": len(EXPECTED),
        "passed_count": passed,
        "repeat_deterministic_count": repeat_count,
        "repeat_determinism_verified": repeat_count == len(EXPECTED),
        "historical_exact_match_count": historical_count,
        "template_sha256_before": template_before,
        "template_sha256_after": template_after,
        "template_unchanged": template_after == template_before,
        "external_usage": {
            "hardware_initializations": 0,
            "hardware_scans": 0,
            "hardware_connections": 0,
            "hardware_writes": 0,
            "external_processes": 0,
            "network_requests": 0,
            "real_uploads": 0,
        },
        "samples": records,
    }
    result["status"] = "COMPLETE" if verification_complete(result) else "FAILED"
    result_path = output_dir / "golden_results.json"
    with result_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"Public core golden matches: {passed}/{len(EXPECTED)}")
    print(f"Repeated deterministic: {result['repeat_deterministic_count']}/{len(EXPECTED)}")
    print(f"Saved: {result_path}")
    return 0 if result["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
