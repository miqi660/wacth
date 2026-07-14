from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ultra3_uploader import HandoffValidationStatus, validate_handoff


FIRMWARE = "NJ-LEJ-2.1.7"
SAMPLES = (
    "golden_match.handoff.json",
    "custom_not_applicable.handoff.json",
)


def record(repo_root: Path, name: str, target_firmware: str | None) -> dict:
    relative = Path("editor/artifacts/stage8c0_handoff_design") / name
    result = validate_handoff(
        repo_root / relative,
        bundle_root=repo_root,
        target_firmware=target_firmware,
    )
    expected_safe = target_firmware == FIRMWARE
    if result.status is not HandoffValidationStatus.VALID:
        raise RuntimeError(f"{name} 离线验证失败: {[issue.error_code for issue in result.errors]}")
    if result.safe_to_prepare_transfer is not expected_safe:
        raise RuntimeError(f"{name} safe_to_prepare_transfer 不符合预期")
    return {
        "sample": name,
        "manifest": relative.as_posix(),
        "target_firmware": target_firmware,
        "status": result.status.value,
        "firmware_compatible": result.firmware_compatible,
        "safe_to_prepare_transfer": result.safe_to_prepare_transfer,
        "actual_artifact_sha256": result.actual_artifact_sha256,
        "actual_artifact_size": result.actual_artifact_size,
        "header_valid": result.header_valid,
        "offset_zero_valid": result.offset_zero_valid,
        "layout_valid": result.layout_valid,
        "artifact_unchanged": result.artifact_unchanged,
        "transfer_unprepared": result.transfer_unprepared,
        "golden_status": result.golden_status,
        "device_evidence_level": result.device_evidence_level,
        "warnings": [issue.error_code for issue in result.warnings],
        "errors": [issue.error_code for issue in result.errors],
        "external_usage": asdict(result.external_usage),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 8C-1 真实 Handoff 样例离线验证")
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve(strict=True)
    records = [
        record(repo_root, name, target)
        for name in SAMPLES
        for target in (None, FIRMWARE)
    ]
    report = {
        "status": "COMPLETE",
        "schema": "ultra3-handoff/v1",
        "sample_count": len(SAMPLES),
        "validation_count": len(records),
        "validations": records,
        "boundary": "safe_to_prepare_transfer=true 仅表示离线前置条件通过，不表示允许真实上传",
    }
    output = repo_root / "uploader/artifacts/stage8c1_handoff_validation/sample_validation_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
