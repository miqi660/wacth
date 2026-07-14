from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ultra3_uploader.bc_frames import iter_c9
from ultra3_uploader.handoff import EXPECTED_HEADER, EXPECTED_LAYOUT, EXPECTED_SIZE


FIRMWARE = "NJ-LEJ-2.1.7"


def make_static_bundle(root: Path) -> tuple[Path, Path, str]:
    source = EXPECTED_HEADER + bytes(EXPECTED_SIZE - len(EXPECTED_HEADER))
    source_path = root / "watchface.bin"
    source_path.write_bytes(source)
    source_sha256 = hashlib.sha256(source).hexdigest().upper()
    document = {
        "schema": "ultra3-handoff/v1",
        "artifact_type": "greenlion_static_diy_complete_bin",
        "artifact_path": "watchface.bin",
        "artifact_size": EXPECTED_SIZE,
        "artifact_sha256": source_sha256,
        "container": "greenlion-static",
        "firmware_scope": [FIRMWARE],
        "builder_version": "0.2.4-greenlion-exact",
        "pillow_version": "10.4.0",
        "template_sha256": "5D04DE76C94DA9D7F7069AF3E6038E1575D3B42E5E009EAD590CE4DD33F5E1CC",
        "template_header_hex": "02 00 00 FF FF FF 00 00 80 01 40 01 FC 00 D2 00 00",
        "template_offset_zero": 2,
        "layout": EXPECTED_LAYOUT,
        "main_resource": {
            "width": 320,
            "height": 384,
            "encoding": "greenlion-next-high-rgb565",
        },
        "thumbnail_resource": {
            "width": 210,
            "height": 252,
            "encoding": "greenlion-next-high-rgb565",
            "source": "auto-from-main-image",
        },
        "build_validation": {
            "output_revalidated": True,
            "input_unchanged": True,
            "template_unchanged": True,
            "golden_status": "not_applicable",
            "exact_golden_match": None,
            "determinism_status": "not_evaluated",
        },
        "device_evidence": {"level": "C", "note": "offline fixture"},
        "transfer": {
            "status": "not_prepared",
            "payload_size": None,
            "chunk_count": None,
            "ble_frames_present": False,
        },
    }
    manifest_path = root / "watchface.handoff.json"
    manifest_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    payload = b"".join(frame[6:] for frame in iter_c9(source))
    payload_path = root / "payload.bin"
    payload_path.write_bytes(payload)
    return manifest_path, payload_path, hashlib.sha256(payload).hexdigest()
