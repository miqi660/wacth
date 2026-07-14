from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

from PIL import Image, __version__ as pillow_version


EXPECTED_ZIP_SHA256 = (
    "3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231"
)
BUILDER_RELATIVE = Path("builder/ultra3_builder_v0.2.4-greenlion-exact.py")
TEMPLATE_RELATIVE = Path("sample/official_calibration_351617.bin")
CHECKSUM_RELATIVE = Path("CHECKSUMS.sha256")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def logical_path(
    path: Path,
    *,
    baseline: Path,
    temp_root: Path | None = None,
    zip_path: Path | None = None,
) -> str:
    resolved = path.resolve()
    if zip_path is not None and resolved == zip_path.resolve():
        return "$FROZEN_ZIP"
    roots = [
        (baseline.resolve(), "$FROZEN_BASELINE"),
        (REPO_ROOT.resolve(), "$REPO"),
    ]
    if temp_root is not None:
        roots.insert(1, (temp_root.resolve(), "$TEMP_AUDIT"))
    for root, label in roots:
        if is_relative_to(resolved, root):
            relative = resolved.relative_to(root).as_posix()
            return label if not relative else f"{label}/{relative}"
    raise ValueError(f"Path is outside known logical roots: {path}")


def normalize_text(text: str, *, baseline: Path, temp_root: Path) -> str:
    replacements = {
        str(baseline): "$FROZEN_BASELINE",
        str(baseline.resolve()): "$FROZEN_BASELINE",
        str(temp_root): "$TEMP_AUDIT",
        str(temp_root.resolve()): "$TEMP_AUDIT",
        sys.executable: "<PYTHON>",
    }
    for source, replacement in sorted(replacements.items(), key=lambda item: -len(item[0])):
        text = text.replace(source, replacement)
    return text


def role_for(relative: str) -> str:
    lowered = relative.lower()
    name = PurePosixPath(relative.replace("\\", "/")).name.lower()
    if "/builder/" in f"/{lowered}" and name.endswith(".py"):
        return "builder_source"
    if "test_photos/" in lowered or name == "ultra3_calibration_320x384.png":
        return "input_image"
    if name == "official_calibration_351617.bin":
        return "template_and_golden"
    if "test_builds/" in lowered or "/sample/" in f"/{lowered}":
        return "sample_or_output"
    if name.endswith((".md", ".txt")):
        return "report_or_evidence"
    if name.endswith((".json", ".sha256", ".lock")):
        return "metadata_or_integrity"
    if "/tools/" in f"/{lowered}":
        return "research_tool"
    return "supporting_file"


def verify_external_baseline_integrity(baseline: Path) -> dict:
    checksum_path = baseline / CHECKSUM_RELATIVE
    declarations: dict[str, str] = {}
    for line_number, line in enumerate(
        checksum_path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]) is None:
            raise ValueError(f"Invalid checksum declaration at line {line_number}")
        digest, relative = parts[0].upper(), parts[1].strip()
        pure = PurePosixPath(relative)
        if (
            not relative
            or "\\" in relative
            or pure.is_absolute()
            or ".." in pure.parts
            or re.match(r"^[A-Za-z]:", relative)
        ):
            raise ValueError(f"Unsafe checksum path at line {line_number}: {relative}")
        canonical = pure.as_posix()
        if canonical in declarations:
            raise ValueError(f"Duplicate checksum declaration: {canonical}")
        declarations[canonical] = digest

    verified: dict[str, dict] = {}
    missing: list[str] = []
    non_regular: list[str] = []
    mismatches: list[dict] = []
    baseline_root = baseline.resolve()
    for relative, declared_digest in declarations.items():
        path = baseline.joinpath(*PurePosixPath(relative).parts)
        resolved = path.resolve()
        if not is_relative_to(resolved, baseline_root):
            raise ValueError(f"Checksum path escapes baseline: {relative}")
        if not path.exists():
            missing.append(relative)
            continue
        if not path.is_file() or path.is_symlink():
            non_regular.append(relative)
            continue
        actual_digest = sha256_file(path)
        if actual_digest != declared_digest:
            mismatches.append(
                {
                    "path": relative,
                    "declared_sha256": declared_digest,
                    "actual_sha256": actual_digest,
                }
            )
            continue
        verified[relative] = {
            "size": path.stat().st_size,
            "sha256": actual_digest,
        }

    checksum_relative = CHECKSUM_RELATIVE.as_posix()
    physical_files = {
        path.relative_to(baseline).as_posix()
        for path in baseline.rglob("*")
        if path.is_file()
    }
    checksum_self_declared = checksum_relative in declarations
    undeclared = sorted(
        physical_files - set(declarations) - {checksum_relative}
    )
    canonical_text = "".join(
        f"{relative}\t{verified[relative]['size']}\t{verified[relative]['sha256']}\n"
        for relative in sorted(verified)
    )

    input_paths = [
        "evidence/local_additions/test_photos/1.JPG",
        *(f"evidence/local_additions/test_photos/{index}.png" for index in range(2, 6)),
    ]
    real_paths = [
        f"evidence/local_additions/test_builds/photo{index:02d}/real_file_351617.bin"
        for index in range(1, 6)
    ]
    payload_paths = [
        f"evidence/local_additions/test_builds/photo{index:02d}/payload_353146.bin"
        for index in range(1, 6)
    ]

    local_freeze_path = baseline / "LOCAL_FREEZE.json"
    local_freeze_exists = local_freeze_path.is_file()
    try:
        local_freeze = json.loads(local_freeze_path.read_text(encoding="utf-8-sig"))
        local_freeze_parseable = True
    except (OSError, json.JSONDecodeError):
        local_freeze = {}
        local_freeze_parseable = False
    hash_fields = sorted(key for key in local_freeze if "hash" in key.lower() or "sha" in key.lower())
    expected_fields = {
        "baseline_name",
        "frozen_at",
        "source_package",
        "destination",
        "archive_mode",
        "original_files_moved",
        "file_count",
        "status",
    }
    local_freeze_relative = "LOCAL_FREEZE.json"
    local_freeze_summary = {
        "parseable": local_freeze_parseable,
        "fields": sorted(local_freeze),
        "expected_fields_present": expected_fields.issubset(local_freeze),
        "freeze_information_present": all(
            field in local_freeze
            for field in ("frozen_at", "archive_mode", "original_files_moved", "status")
        ),
        "archive_mode": local_freeze.get("archive_mode"),
        "original_files_moved": local_freeze.get("original_files_moved"),
        "recorded_file_count": local_freeze.get("file_count"),
        "recorded_file_count_matches_declared": local_freeze.get("file_count") == len(declarations),
        "path_fields_present_but_values_redacted": [
            field for field in ("source_package", "destination") if field in local_freeze
        ],
        "hash_fields": hash_fields,
        "recorded_hash_verification": (
            "UNKNOWN_NO_HASH_FIELDS" if not hash_fields else "UNKNOWN_UNMAPPED_HASH_FIELDS"
        ),
        "exists": local_freeze_exists,
        "size": local_freeze_path.stat().st_size if local_freeze_exists else None,
        "sha256": sha256_file(local_freeze_path) if local_freeze_exists else None,
        "covered": local_freeze_relative in verified,
    }

    frozen_lock_path = baseline / "FROZEN.lock"
    frozen_lock_relative = "FROZEN.lock"
    frozen_lock_exists = frozen_lock_path.is_file()
    frozen_lock_lines = (
        frozen_lock_path.read_text(encoding="utf-8-sig").splitlines()
        if frozen_lock_exists
        else []
    )
    frozen_lock_summary = {
        "exists": frozen_lock_exists,
        "size": frozen_lock_path.stat().st_size if frozen_lock_exists else None,
        "sha256": sha256_file(frozen_lock_path) if frozen_lock_exists else None,
        "content_summary": frozen_lock_lines,
        "covered": frozen_lock_relative in verified,
        "trust_basis": "CHECKSUM_COVERED" if frozen_lock_relative in verified else "NAME_ONLY_UNTRUSTED",
    }

    def all_covered(paths: list[str]) -> bool:
        return len(paths) == 5 and all(path in verified for path in paths)

    five_inputs_covered = all_covered(input_paths)
    five_real_covered = all_covered(real_paths)
    five_payloads_covered = all_covered(payload_paths)
    builder_covered = BUILDER_RELATIVE.as_posix() in verified
    template_covered = TEMPLATE_RELATIVE.as_posix() in verified
    historical_verified = five_inputs_covered and five_real_covered and five_payloads_covered
    integrity_verified = (
        len(verified) == len(declarations)
        and not missing
        and not non_regular
        and not mismatches
        and not undeclared
        and not checksum_self_declared
    )

    return {
        "checksum_file_relative_path": checksum_relative,
        "checksum_file_sha256": sha256_file(checksum_path),
        "checksum_file_self_declared": checksum_self_declared,
        "checksum_file_self_excluded_by_design": not checksum_self_declared,
        "declared_count": len(declarations),
        "verified_count": len(verified),
        "mismatch_count": len(mismatches),
        "missing_count": len(missing),
        "non_regular_count": len(non_regular),
        "undeclared_count": len(undeclared),
        "mismatches": mismatches,
        "missing_files": missing,
        "non_regular_files": non_regular,
        "undeclared_files": undeclared,
        "canonical_manifest_format": "<relative_path>\\t<size>\\t<SHA256>\\n",
        "canonical_manifest_entry_count": len(verified),
        "canonical_manifest_sha256": hashlib.sha256(
            canonical_text.encode("utf-8")
        ).hexdigest().upper(),
        "builder_covered": builder_covered,
        "template_covered": template_covered,
        "five_inputs_covered": five_inputs_covered,
        "five_historical_real_bins_covered": five_real_covered,
        "five_historical_payloads_covered": five_payloads_covered,
        "frozen_lock_covered": frozen_lock_relative in verified,
        "local_freeze_covered": local_freeze_relative in verified,
        "local_freeze": local_freeze_summary,
        "frozen_lock": frozen_lock_summary,
        "integrity_status": "VERIFIED" if integrity_verified else "PARTIAL",
        "historical_oracle_integrity": "VERIFIED" if historical_verified else "PARTIAL",
    }


def file_record(path: Path, root: Path, *, tracked: bool) -> dict:
    relative = path.relative_to(root).as_posix()
    role = role_for(relative)
    logical_root = "$REPO" if root.resolve() == REPO_ROOT.resolve() else "$FROZEN_BASELINE"
    return {
        "path": f"{logical_root}/{relative}",
        "relative_path": relative,
        "name": path.name,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "git_tracked": tracked,
        "role_assessment": role,
        "historical_frozen_content": root != REPO_ROOT,
        "executable_source": role == "builder_source",
        "sample": role in {"input_image", "sample_or_output"},
        "report": role == "report_or_evidence",
        "template": role == "template_and_golden",
        "output": "test_builds/" in relative or name_is_output(path.name),
    }


def name_is_output(name: str) -> bool:
    return name in {"real_file_351617.bin", "payload_353146.bin"}


def zip_manifest(zip_path: Path) -> dict:
    archive_sha = sha256_file(zip_path)
    if archive_sha != EXPECTED_ZIP_SHA256:
        raise RuntimeError(
            f"Frozen ZIP SHA-256 mismatch: {archive_sha} != {EXPECTED_ZIP_SHA256}"
        )

    entries = []
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            safe = not pure.is_absolute() and ".." not in pure.parts
            if not safe:
                raise RuntimeError(f"ZIP path traversal entry: {info.filename}")
            data = archive.read(info) if not info.is_dir() else b""
            entries.append(
                {
                    "path": info.filename,
                    "size": info.file_size,
                    "compressed_size": info.compress_size,
                    "crc32": f"{info.CRC:08X}",
                    "sha256": hashlib.sha256(data).hexdigest().upper(),
                    "is_directory": info.is_dir(),
                    "path_safe": safe,
                    "role_assessment": role_for(info.filename),
                }
            )
        checksum_name = next(
            name for name in archive.namelist() if name.endswith("/PACKAGE_CHECKSUMS.sha256")
        )
        declared_checksums = {}
        for line in archive.read(checksum_name).decode("utf-8").splitlines():
            digest, relative = line.split(maxsplit=1)
            declared_checksums[relative] = digest.upper()

    package_root = checksum_name.rsplit("/", 1)[0] + "/"
    actual_checksums = {
        item["path"].removeprefix(package_root): item["sha256"]
        for item in entries
        if item["path"] != checksum_name and not item["is_directory"]
    }
    checksum_mismatches = [
        {
            "path": relative,
            "declared": digest,
            "actual": actual_checksums.get(relative),
        }
        for relative, digest in declared_checksums.items()
        if actual_checksums.get(relative) != digest
    ]
    undeclared_entries = sorted(set(actual_checksums) - set(declared_checksums))
    missing_entries = sorted(set(declared_checksums) - set(actual_checksums))

    return {
        "status": "COMPLETE",
        "zip_path": "$FROZEN_ZIP",
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": archive_sha,
        "expected_zip_sha256": EXPECTED_ZIP_SHA256,
        "hash_matches": True,
        "entry_count": len(entries),
        "path_traversal_entries": [],
        "declared_checksum_count": len(declared_checksums),
        "internal_checksums_match": not checksum_mismatches and not undeclared_entries and not missing_entries,
        "checksum_mismatches": checksum_mismatches,
        "undeclared_entries": undeclared_entries,
        "missing_entries": missing_entries,
        "entries": entries,
    }


def git_tracked_candidates() -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    terms = ("builder", "greenlion", "rgb565", "thumbnail", "thumb", "watchface", "static", "frozen")
    return [
        REPO_ROOT / item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item and any(term in item.decode("utf-8").lower() for term in terms)
    ]


def builder_file_manifest(baseline: Path) -> dict:
    frozen_files = sorted(path for path in baseline.rglob("*") if path.is_file())
    tracked_files = git_tracked_candidates()
    return {
        "status": "COMPLETE",
        "frozen_baseline": "$FROZEN_BASELINE",
        "frozen_file_count": len(frozen_files),
        "repository_candidate_count": len(tracked_files),
        "files": [
            *(file_record(path, baseline, tracked=False) for path in frozen_files),
            *(file_record(path, REPO_ROOT, tracked=True) for path in tracked_files),
        ],
    }


def load_builder(builder_path: Path):
    spec = importlib.util.spec_from_file_location("frozen_ultra3_builder", builder_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load builder: {builder_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pixel_vector_results(builder) -> dict:
    vectors = [
        ("black", (0, 0, 0)),
        ("white", (255, 255, 255)),
        ("red", (255, 0, 0)),
        ("green", (0, 255, 0)),
        ("blue", (0, 0, 255)),
        ("middle_gray", (128, 128, 128)),
        ("asymmetric", (18, 165, 124)),
    ]
    image = Image.new("RGB", (len(vectors), 1))
    image.putdata([rgb for _, rgb in vectors])
    normal = builder.image_to_normal_rgb565_le(image, quantize="truncate")
    wire = builder.apply_greenlion_next_high(normal)
    return {
        "function_source": "frozen Builder functions called directly",
        "quantize": "truncate",
        "vectors": [
            {
                "name": name,
                "rgb": list(rgb),
                "normal_rgb565_le": normal[index * 2 : index * 2 + 2].hex().upper(),
                "greenlion_wire": wire[index * 2 : index * 2 + 2].hex().upper(),
            }
            for index, (name, rgb) in enumerate(vectors)
        ],
        "normal_buffer_hex": normal.hex().upper(),
        "wire_buffer_hex": wire.hex().upper(),
        "last_high_byte": wire[-1],
    }


def image_metadata(path: Path, *, baseline: Path) -> dict:
    with Image.open(path) as image:
        exif = image.getexif()
        return {
            "path": logical_path(path, baseline=baseline),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
            "format": image.format,
            "mode": image.mode,
            "dimensions": list(image.size),
            "exif_orientation": exif.get(274),
            "icc_profile_present": "icc_profile" in image.info,
            "transparency_present": "transparency" in image.info or "A" in image.getbands(),
        }


def changed_ranges(before: bytes, after: bytes) -> tuple[int, list[list[int]]]:
    changed = [index for index, pair in enumerate(zip(before, after)) if pair[0] != pair[1]]
    changed.extend(range(min(len(before), len(after)), max(len(before), len(after))))
    if not changed:
        return 0, []
    ranges: list[list[int]] = []
    start = previous = changed[0]
    for offset in changed[1:]:
        if offset != previous + 1:
            ranges.append([start, previous])
            start = offset
        previous = offset
    ranges.append([start, previous])
    return len(changed), ranges


def run_builder(
    builder_path: Path,
    source: Path,
    template: Path,
    output: Path,
    *,
    baseline: Path,
    temp_root: Path,
) -> dict:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite reproduction output: {output}")
    actual_command = [
        sys.executable,
        str(builder_path),
        "--image",
        str(source),
        "--template",
        str(template),
        "--out",
        str(output),
    ]
    completed = subprocess.run(actual_command, check=True, capture_output=True, text=True)
    real = output / "real_file_351617.bin"
    payload = output / "payload_353146.bin"
    return {
        "command": [
            "<PYTHON>",
            logical_path(builder_path, baseline=baseline, temp_root=temp_root),
            "--image",
            logical_path(source, baseline=baseline, temp_root=temp_root),
            "--template",
            logical_path(template, baseline=baseline, temp_root=temp_root),
            "--out",
            logical_path(output, baseline=baseline, temp_root=temp_root),
        ],
        "returncode": completed.returncode,
        "stdout": normalize_text(completed.stdout, baseline=baseline, temp_root=temp_root),
        "stderr": normalize_text(completed.stderr, baseline=baseline, temp_root=temp_root),
        "real_path": logical_path(real, baseline=baseline, temp_root=temp_root),
        "real_size": real.stat().st_size,
        "real_sha256": sha256_file(real),
        "payload_path": logical_path(payload, baseline=baseline, temp_root=temp_root),
        "payload_size": payload.stat().st_size,
        "payload_sha256": sha256_file(payload),
    }


def reproduction_results(baseline: Path, temp_root: Path, zip_path: Path) -> dict:
    if is_relative_to(temp_root.resolve(), REPO_ROOT.resolve()):
        raise RuntimeError(f"Temporary directory must be outside repository: {temp_root}")
    if temp_root.exists():
        raise FileExistsError(f"Temporary audit directory already exists: {temp_root}")
    temp_root.mkdir(parents=True)

    builder_path = baseline / BUILDER_RELATIVE
    template_path = baseline / TEMPLATE_RELATIVE
    photos_root = baseline / "evidence/local_additions/test_photos"
    historical_root = baseline / "evidence/local_additions/test_builds"
    builder = load_builder(builder_path)
    template_before = sha256_file(template_path)
    zip_before = sha256_file(zip_path)
    records = []

    photos = sorted(path for path in photos_root.iterdir() if path.is_file())
    for index, source in enumerate(photos, start=1):
        historical_dir = historical_root / f"photo{index:02d}"
        historical_real = historical_dir / "real_file_351617.bin"
        historical_payload = historical_dir / "payload_353146.bin"
        source_before = sha256_file(source)
        historical_real_before = sha256_file(historical_real)
        historical_payload_before = sha256_file(historical_payload)
        run1_output = temp_root / f"photo{index:02d}_run1"
        run2_output = temp_root / f"photo{index:02d}_run2"
        run1 = run_builder(
            builder_path,
            source,
            template_path,
            run1_output,
            baseline=baseline,
            temp_root=temp_root,
        )
        run2 = run_builder(
            builder_path,
            source,
            template_path,
            run2_output,
            baseline=baseline,
            temp_root=temp_root,
        )
        historical_bytes = historical_real.read_bytes()
        run1_bytes = (run1_output / "real_file_351617.bin").read_bytes()
        difference_count, ranges = changed_ranges(historical_bytes, run1_bytes)
        records.append(
            {
                "sample": f"photo{index:02d}",
                "input": image_metadata(source, baseline=baseline),
                "settings": {
                    "mode": "full",
                    "fit": "cover",
                    "resample": "bilinear",
                    "quantize": "truncate",
                    "wire_profile": "greenlion-next-high",
                    "preblur": 0.0,
                },
                "historical_real_sha256": historical_real_before,
                "historical_payload_sha256": historical_payload_before,
                "run1": run1,
                "run2": run2,
                "run1_run2_exact_match": run1["real_sha256"] == run2["real_sha256"],
                "historical_exact_match": difference_count == 0,
                "changed_bytes": difference_count,
                "changed_ranges": ranges,
                "input_unchanged": sha256_file(source) == source_before,
                "historical_outputs_unchanged": (
                    sha256_file(historical_real) == historical_real_before
                    and sha256_file(historical_payload) == historical_payload_before
                ),
                "device_evidence_level": "C",
                "device_evidence_note": (
                    "输入、Builder 输出和文字/上传日志存在；真机截图与逐样本抓包未归档"
                ),
            }
        )

    sample_dir = baseline / "sample"
    main_normal = (sample_dir / "main_normal_rgb565_le.bin").read_bytes()
    main_wire = (sample_dir / "main_greenlion_wire.bin").read_bytes()
    thumb_normal = (sample_dir / "thumb_normal_rgb565_le.bin").read_bytes()
    thumb_wire = (sample_dir / "thumb_greenlion_wire.bin").read_bytes()

    return {
        "status": "COMPLETE",
        "temporary_directory": "$TEMP_AUDIT",
        "temporary_directory_outside_repository": True,
        "builder_path": logical_path(builder_path, baseline=baseline, temp_root=temp_root),
        "builder_sha256": sha256_file(builder_path),
        "python_version": sys.version,
        "pillow_version": pillow_version,
        "template_path": logical_path(template_path, baseline=baseline, temp_root=temp_root),
        "template_size": template_path.stat().st_size,
        "template_sha256": template_before,
        "template_header_hex": template_path.read_bytes()[:17].hex(" ").upper(),
        "template_offset_0": template_path.read_bytes()[0],
        "pixel_vectors": pixel_vector_results(builder),
        "wire_artifact_verification": {
            "main_exact": builder.apply_greenlion_next_high(main_normal) == main_wire,
            "thumbnail_exact": builder.apply_greenlion_next_high(thumb_normal) == thumb_wire,
            "main_last_high": main_wire[-1],
            "thumbnail_last_high": thumb_wire[-1],
            "main_length": len(main_wire),
            "thumbnail_length": len(thumb_wire),
            "linear_across_main_row_boundary": main_wire[639] == main_normal[641],
            "resources_encoded_separately": main_wire[-1] == 0 and thumb_wire[-1] == 0,
        },
        "samples": records,
        "sample_count": len(records),
        "repeat_deterministic_count": sum(item["run1_run2_exact_match"] for item in records),
        "historical_exact_match_count": sum(item["historical_exact_match"] for item in records),
        "template_unchanged": sha256_file(template_path) == template_before,
        "frozen_zip_sha256_before": zip_before,
        "frozen_zip_sha256_after": sha256_file(zip_path),
        "frozen_zip_unchanged": sha256_file(zip_path) == zip_before,
        "external_baseline_integrity": verify_external_baseline_integrity(baseline),
        "external_usage": {
            "bleak_initialization": 0,
            "ble_scan": 0,
            "ble_connect": 0,
            "ff02_writes": 0,
            "adb": 0,
            "frida": 0,
            "uploader_calls": 0,
            "network_requests": 0,
            "real_uploads": 0,
        },
    }


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def write_json_exclusive(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the frozen Ultra3 v0.2.4 Builder")
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--temp-dir", type=Path, required=True)
    return parser.parse_args()


REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    args = parse_args()
    if not args.zip.is_file():
        raise FileNotFoundError(args.zip)
    if not args.baseline.is_dir():
        raise NotADirectoryError(args.baseline)
    if args.output_dir.exists():
        raise FileExistsError(f"Audit output directory already exists: {args.output_dir}")

    frozen = zip_manifest(args.zip)
    files = builder_file_manifest(args.baseline)
    reproduction = reproduction_results(args.baseline, args.temp_dir, args.zip)
    write_json_exclusive(args.output_dir / "frozen_zip_manifest.json", frozen)
    write_json_exclusive(args.output_dir / "builder_file_manifest.json", files)
    write_json_exclusive(args.output_dir / "reproduction_results.json", reproduction)
    print(f"Frozen ZIP entries: {frozen['entry_count']}")
    print(f"Builder files: {files['frozen_file_count']}")
    print(f"Repeated deterministic: {reproduction['repeat_deterministic_count']}/5")
    print(f"Historical exact matches: {reproduction['historical_exact_match_count']}/5")
    print(f"Saved: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
