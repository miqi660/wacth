from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "docs" / "handoff" / "ultra3_handoff_v1.schema.json"
DESIGN_DIR = REPO / "editor" / "artifacts" / "stage8c0_handoff_design"
SHA256_RE = re.compile(r"[0-9A-F]{64}\Z")
HEADER_HEX = "02 00 00 FF FF FF 00 00 80 01 40 01 FC 00 D2 00 00"
TEMPLATE_SHA256 = "5D04DE76C94DA9D7F7069AF3E6038E1575D3B42E5E009EAD590CE4DD33F5E1CC"
ROOT_KEYS = {
    "schema",
    "artifact_type",
    "artifact_path",
    "artifact_size",
    "artifact_sha256",
    "container",
    "firmware_scope",
    "builder_version",
    "pillow_version",
    "template_sha256",
    "template_header_hex",
    "template_offset_zero",
    "layout",
    "main_resource",
    "thumbnail_resource",
    "build_validation",
    "device_evidence",
    "transfer",
}
LAYOUT = {
    "header": {"start": 0, "end": 17, "length": 17},
    "main": {"start": 17, "end": 245777, "length": 245760},
    "thumbnail": {"start": 245777, "end": 351617, "length": 105840},
}
MAIN_RESOURCE = {
    "width": 320,
    "height": 384,
    "encoding": "greenlion-next-high-rgb565",
}
THUMBNAIL_RESOURCE = {
    "width": 210,
    "height": 252,
    "encoding": "greenlion-next-high-rgb565",
    "source": "auto-from-main-image",
}
TRANSFER = {
    "status": "not_prepared",
    "payload_size": None,
    "chunk_count": None,
    "ble_frames_present": False,
}
SAMPLES = {
    "golden_match.handoff.json": (
        "editor/artifacts/stage8b2_gui_builder/golden_match.json",
        "editor/artifacts/stage8b2_gui_builder/golden_match.bin",
    ),
    "custom_not_applicable.handoff.json": (
        "editor/artifacts/stage8b2_gui_builder/custom_not_applicable.json",
        "editor/artifacts/stage8b2_gui_builder/custom_not_applicable.bin",
    ),
}
CANDIDATE_FILES = (
    SCHEMA_PATH,
    REPO / "docs" / "handoff" / "README.md",
    REPO / "editor" / "STAGE8C0_EDITOR_UPLOADER_HANDOFF_DESIGN_REPORT_2026-07-14.md",
    DESIGN_DIR / "README.md",
    DESIGN_DIR / "golden_match.handoff.json",
    DESIGN_DIR / "custom_not_applicable.handoff.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def serialized(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def manifest_from_builder_record(record_path: Path, artifact_path: str) -> dict:
    record = json.loads(record_path.read_text(encoding="utf-8"))
    return {
        "schema": "ultra3-handoff/v1",
        "artifact_type": "greenlion_static_diy_complete_bin",
        "artifact_path": artifact_path,
        "artifact_size": record["output_size"],
        "artifact_sha256": record["output_sha256"].upper(),
        "container": record["container"],
        "firmware_scope": [record["firmware_scope"]],
        "builder_version": record["builder_version"],
        "pillow_version": "10.4.0",
        "template_sha256": record["template_sha256_before"].upper(),
        "template_header_hex": record["template_header_hex"],
        "template_offset_zero": record["template_offset_zero"],
        "layout": LAYOUT,
        "main_resource": MAIN_RESOURCE,
        "thumbnail_resource": THUMBNAIL_RESOURCE,
        "build_validation": {
            "output_revalidated": record["output_revalidated"],
            "input_unchanged": record["image_unchanged"],
            "template_unchanged": record["template_unchanged"],
            "golden_status": record["golden_status"],
            "exact_golden_match": record["exact_golden_match"],
            "determinism_status": record["determinism_status"],
        },
        "device_evidence": {
            "level": "C",
            "note": "离线构建与归档上传文字证据存在；逐样本真机截图和抓包尚未归档。",
        },
        "transfer": TRANSFER,
    }


def expected_samples() -> dict[str, dict]:
    return {
        name: manifest_from_builder_record(REPO / record, artifact)
        for name, (record, artifact) in SAMPLES.items()
    }


def write_samples() -> None:
    DESIGN_DIR.mkdir(parents=True, exist_ok=True)
    for name, manifest in expected_samples().items():
        path = DESIGN_DIR / name
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized(manifest))


def validate_schema_document(schema: dict) -> list[str]:
    errors: list[str] = []
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("JSON Schema draft 不是 2020-12")
    if schema.get("additionalProperties") is not False:
        errors.append("根 additionalProperties 必须为 false")
    properties = schema.get("properties", {})
    expected_consts = {
        "schema": "ultra3-handoff/v1",
        "artifact_type": "greenlion_static_diy_complete_bin",
        "artifact_size": 351617,
        "template_offset_zero": 2,
    }
    for name, expected in expected_consts.items():
        if properties.get(name, {}).get("const") != expected:
            errors.append(f"Schema const 错误: {name}")
    transfer = properties.get("transfer", {}).get("properties", {})
    if transfer.get("status", {}).get("const") != "not_prepared":
        errors.append("Schema transfer.status 错误")
    if transfer.get("payload_size", {}).get("type") != "null":
        errors.append("Schema payload_size 必须为 null")
    if transfer.get("chunk_count", {}).get("type") != "null":
        errors.append("Schema chunk_count 必须为 null")
    if transfer.get("ble_frames_present", {}).get("const") is not False:
        errors.append("Schema ble_frames_present 必须为 false")
    return errors


def validate_artifact_path(value: object) -> list[str]:
    if not isinstance(value, str) or not value:
        return ["artifact_path 必须为非空字符串"]
    errors = []
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        errors.append("artifact_path 不得为绝对路径")
    if "\\" in value:
        errors.append("artifact_path 必须使用 POSIX 分隔符")
    if "\0" in value:
        errors.append("artifact_path 不得包含 NUL")
    if ":" in value:
        errors.append("artifact_path 不得包含冒号")
    parts = value.split("/")
    if "" in parts:
        errors.append("artifact_path 不得包含空路径段")
    if "." in parts:
        errors.append("artifact_path 不得包含 .")
    if ".." in parts:
        errors.append("artifact_path 不得包含 ..")
    return errors


def validate_sha256(value: object) -> list[str]:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        return ["SHA-256 必须为 64 位大写十六进制"]
    return []


def git_diff(path: str) -> str:
    return subprocess.run(
        ["git", "diff", "--", path],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def scan_candidate_files() -> dict[str, int]:
    text = "\n".join(path.read_text(encoding="utf-8") for path in CANDIDATE_FILES)
    folded = text.casefold()
    private_hits = sum(
        folded.count(token)
        for token in ("c:\\users\\", "administrator", "\\desktop\\", "\\appdata\\")
    )
    private_hits += len(re.findall(r"python\d+\\python\.exe", text, re.IGNORECASE))
    manifests = "\n".join(
        (DESIGN_DIR / name).read_text(encoding="utf-8") for name in SAMPLES
    )
    return {
        "private_path_hits": private_hits,
        "device_address_hits": len(re.findall(r'"device_address"\s*:', manifests, re.IGNORECASE))
        + len(re.findall(r"\b(?:[0-9A-F]{2}:){5}[0-9A-F]{2}\b", manifests, re.IGNORECASE)),
        "top_bottom_hits": len(re.findall(r'"(?:top|bottom)"\s*:', manifests, re.IGNORECASE)),
    }


def validate_manifest(manifest: dict, repo_root: Path = REPO) -> list[str]:
    errors: list[str] = []

    def exact(name: str, expected: object) -> None:
        if manifest.get(name) != expected:
            errors.append(f"{name} 不匹配: {manifest.get(name)!r} != {expected!r}")

    if set(manifest) != ROOT_KEYS:
        errors.append(f"根字段不匹配: {sorted(set(manifest) ^ ROOT_KEYS)}")
    exact("schema", "ultra3-handoff/v1")
    exact("artifact_type", "greenlion_static_diy_complete_bin")
    exact("artifact_size", 351617)
    exact("container", "greenlion-static")
    exact("firmware_scope", ["NJ-LEJ-2.1.7"])
    exact("builder_version", "0.2.4-greenlion-exact")
    exact("pillow_version", "10.4.0")
    exact("template_sha256", TEMPLATE_SHA256)
    exact("template_header_hex", HEADER_HEX)
    exact("template_offset_zero", 2)
    exact("layout", LAYOUT)
    exact("main_resource", MAIN_RESOURCE)
    exact("thumbnail_resource", THUMBNAIL_RESOURCE)
    exact("transfer", TRANSFER)

    artifact_sha = manifest.get("artifact_sha256")
    errors.extend(validate_sha256(artifact_sha))

    validation = manifest.get("build_validation")
    expected_validation_keys = {
        "output_revalidated",
        "input_unchanged",
        "template_unchanged",
        "golden_status",
        "exact_golden_match",
        "determinism_status",
    }
    if not isinstance(validation, dict) or set(validation) != expected_validation_keys:
        errors.append("build_validation 字段不匹配")
    else:
        for field in ("output_revalidated", "input_unchanged", "template_unchanged"):
            if validation[field] is not True:
                errors.append(f"build_validation.{field} 必须为 true")
        golden = validation["golden_status"]
        exact_match = validation["exact_golden_match"]
        if golden not in {"match", "not_applicable"}:
            errors.append("golden_status 不受支持")
        if (golden == "match" and exact_match is not True) or (
            golden == "not_applicable" and exact_match is not None
        ):
            errors.append("golden_status 与 exact_golden_match 不一致")
        if validation["determinism_status"] != "not_evaluated":
            errors.append("determinism_status 必须为 not_evaluated")

    evidence = manifest.get("device_evidence")
    if not isinstance(evidence, dict) or set(evidence) != {"level", "note"}:
        errors.append("device_evidence 字段不匹配")
    elif evidence["level"] != "C" or not isinstance(evidence["note"], str) or not evidence["note"]:
        errors.append("device_evidence 必须为非空 Level C")

    path_errors = validate_artifact_path(manifest.get("artifact_path"))
    errors.extend(path_errors)
    if not path_errors:
        artifact = (repo_root / manifest["artifact_path"]).resolve()
        if not artifact.is_relative_to(repo_root.resolve()):
            errors.append("artifact 解析后超出 bundle root")
        elif artifact.is_symlink():
            errors.append("artifact 不得为符号链接")
        elif not artifact.is_file():
            errors.append("artifact 不是普通文件")
        else:
            data = artifact.read_bytes()
            if len(data) != 351617:
                errors.append("实际 artifact 大小不是 351617")
            if isinstance(artifact_sha, str) and sha256_file(artifact) != artifact_sha.upper():
                errors.append("实际 artifact SHA-256 与 Manifest 不匹配")
            if data[:17].hex(" ").upper() != HEADER_HEX:
                errors.append("实际 artifact 17 字节头不匹配")
            if not data or data[0] != 2:
                errors.append("实际 artifact offset 0 不是 02")

    serialized_manifest = json.dumps(manifest, ensure_ascii=False).casefold()
    for forbidden in ("c:\\\\users\\", "appdata", "administrator", "device_address"):
        if forbidden in serialized_manifest:
            errors.append(f"Manifest 包含私人或设备字段: {forbidden}")
    return errors


def run_self_tests(samples: dict[str, dict], schema: dict) -> list[dict]:
    golden = samples["golden_match.handoff.json"]
    custom = samples["custom_not_applicable.handoff.json"]
    results: list[dict] = []
    artifact_path_pattern = schema["properties"]["artifact_path"]["pattern"]
    artifact_sha_pattern = schema["properties"]["artifact_sha256"]["pattern"]

    def passed(name: str, condition: bool, category: str = "original_contract") -> None:
        results.append({"name": name, "category": category, "passed": bool(condition)})

    def rejected(name: str, mutator) -> None:
        value = copy.deepcopy(golden)
        mutator(value)
        passed(name, bool(validate_manifest(value)))

    passed("golden_sample_valid", not validate_manifest(golden))
    passed("not_applicable_sample_valid", not validate_manifest(custom))
    rejected("wrong_schema_rejected", lambda v: v.__setitem__("schema", "ultra3-handoff/v2"))
    rejected("absolute_path_rejected", lambda v: v.__setitem__("artifact_path", "C:/watchface.bin"))
    rejected("parent_traversal_rejected", lambda v: v.__setitem__("artifact_path", "../watchface.bin"))
    rejected("wrong_size_rejected", lambda v: v.__setitem__("artifact_size", 1))
    rejected("wrong_sha_format_rejected", lambda v: v.__setitem__("artifact_sha256", "bad"))
    rejected("offset_zero_not_two_rejected", lambda v: v.__setitem__("template_offset_zero", 0))
    rejected("wrong_header_rejected", lambda v: v.__setitem__("template_header_hex", "00"))
    rejected("wrong_main_region_rejected", lambda v: v["layout"]["main"].__setitem__("end", 1))
    rejected("wrong_thumbnail_region_rejected", lambda v: v["layout"]["thumbnail"].__setitem__("start", 1))
    rejected("prepared_status_rejected", lambda v: v["transfer"].__setitem__("status", "prepared"))
    rejected("payload_size_rejected", lambda v: v["transfer"].__setitem__("payload_size", 353146))
    rejected("chunk_count_rejected", lambda v: v["transfer"].__setitem__("chunk_count", 1529))
    rejected("ble_frames_rejected", lambda v: v["transfer"].__setitem__("ble_frames_present", True))
    rejected("top_bottom_field_rejected", lambda v: v.__setitem__("top", True))
    rejected("device_address_field_rejected", lambda v: v.__setitem__("device_address", "00:00"))
    passed(
        "private_absolute_path_scan_zero",
        all(
            token not in json.dumps(samples, ensure_ascii=False).casefold()
            for token in ("c:\\\\users\\", "appdata", "administrator")
        ),
    )
    passed(
        "artifact_sha_matches_real_bin",
        all(
            sha256_file(REPO / item["artifact_path"]) == item["artifact_sha256"]
            for item in samples.values()
        ),
    )
    expected = expected_samples()
    passed(
        "schema_and_samples_reproducible",
        all(serialized(samples[name]) == serialized(expected[name]) for name in expected),
    )

    accepted_paths = (
        "watchface.bin",
        "artifacts/watchface.bin",
        "stage8b2_gui_builder/golden_match.bin",
        "editor/artifacts/stage8b2_gui_builder/golden_match.bin",
    )
    for index, value in enumerate(accepted_paths, start=1):
        passed(
            f"canonical_path_accepted_{index}",
            not validate_artifact_path(value)
            and re.fullmatch(artifact_path_pattern, value) is not None,
            "path_acceptance",
        )

    rejected_paths = (
        ".",
        "./watchface.bin",
        "foo/./watchface.bin",
        "foo//bar.bin",
        "foo/",
        "../watchface.bin",
        "foo/../watchface.bin",
        "/absolute.bin",
        "C:/absolute.bin",
        "C:\\absolute.bin",
        "\\\\server\\share\\watchface.bin",
        "foo\\bar.bin",
        "http://example",
        "https://example/watchface.bin",
        "file://watchface.bin",
        "foo:bar.bin",
        "watchface.bin:stream",
        "",
        "watchface\0.bin",
    )
    for index, value in enumerate(rejected_paths, start=1):
        passed(
            f"noncanonical_path_rejected_{index}",
            bool(validate_artifact_path(value))
            and re.fullmatch(artifact_path_pattern, value) is None,
            "path_rejection",
        )

    sha_cases = (
        ("uppercase_sha_accepted", "A" * 64, True),
        ("lowercase_sha_rejected", "a" * 64, False),
        ("mixed_case_sha_rejected", "A" * 63 + "a", False),
        ("short_sha_rejected", "A" * 63, False),
        ("long_sha_rejected", "A" * 65, False),
        ("non_hex_sha_rejected", "G" * 64, False),
        ("leading_space_sha_rejected", " " + "A" * 64, False),
        ("trailing_space_sha_rejected", "A" * 64 + " ", False),
    )
    for name, value, valid in sha_cases:
        passed(
            name,
            ((not validate_sha256(value)) and re.fullmatch(artifact_sha_pattern, value) is not None)
            is valid,
            "sha_format",
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 8C-0 Handoff v1 离线契约审计")
    parser.add_argument("--write-samples", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.write_samples:
        write_samples()

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_errors = validate_schema_document(schema)
    samples = {
        name: json.loads((DESIGN_DIR / name).read_text(encoding="utf-8"))
        for name in SAMPLES
    }
    sample_errors = {name: validate_manifest(value) for name, value in samples.items()}
    tests = run_self_tests(samples, schema)
    categories = Counter(item["category"] for item in tests)
    content_scans = scan_candidate_files()
    source_diffs = {
        "editor/src": git_diff("editor/src"),
        "uploader/src": git_diff("uploader/src"),
    }
    actual_artifact_sha256 = {
        name: sha256_file(REPO / manifest["artifact_path"])
        for name, manifest in samples.items()
    }
    failed = sum(not item["passed"] for item in tests)
    complete = (
        not schema_errors
        and not any(sample_errors.values())
        and failed == 0
        and not any(content_scans.values())
        and not any(source_diffs.values())
    )
    report = {
        "status": "COMPLETE" if complete else "FAILED",
        "schema": "ultra3-handoff/v1",
        "schema_draft": schema.get("$schema"),
        "schema_sha256": sha256_file(SCHEMA_PATH),
        "schema_errors": schema_errors,
        "sample_errors": sample_errors,
        "sample_count": len(samples),
        "samples_passed": sum(not errors for errors in sample_errors.values()),
        "path_acceptance_tests": categories["path_acceptance"],
        "path_rejection_tests": categories["path_rejection"],
        "sha_format_tests": categories["sha_format"],
        "original_contract_tests": categories["original_contract"],
        "tests_passed": sum(item["passed"] for item in tests),
        "tests_total": len(tests),
        "tests_failed": failed,
        "tests": tests,
        "actual_artifact_sha256": actual_artifact_sha256,
        "content_scans": content_scans,
        "production_source_diff": source_diffs,
        "external_usage": {
            "bleak_initializations": 0,
            "ble_scans": 0,
            "ble_connections": 0,
            "ff02_writes": 0,
            "ff03_notifications": 0,
            "adb": 0,
            "frida": 0,
            "uploader_runtime_calls": 0,
            "network_requests": 0,
            "real_uploads": 0
        }
    }
    if args.output is not None:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized(report))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
