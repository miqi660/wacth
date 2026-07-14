from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_stage8b1_golden.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("stage8b1_golden_verifier", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _complete_record() -> dict:
    return {
        "run1_run2_exact_match": True,
        "historical_exact_match": True,
        "run1_sha256": "A",
        "run2_sha256": "A",
        "expected_sha256": "A",
        "golden_status_run1": "match",
        "golden_status_run2": "match",
        "exact_golden_match_run1": True,
        "exact_golden_match_run2": True,
        "output_size_run1": 351_617,
        "output_size_run2": 351_617,
        "template_offset_zero_run1": 2,
        "template_offset_zero_run2": 2,
        "output_revalidated_run1": True,
        "output_revalidated_run2": True,
        "image_unchanged_run1": True,
        "image_unchanged_run2": True,
        "historical_output_unchanged": True,
        "determinism_status_run1": "not_evaluated",
        "determinism_status_run2": "not_evaluated",
        "repeated_build_sha256_run1": None,
        "repeated_build_sha256_run2": None,
    }


def test_golden_verifier_requires_every_sample_safety_condition() -> None:
    verifier = _load_verifier()
    record = _complete_record()
    assert verifier.sample_passed(record) is True

    for key, value in record.items():
        broken = dict(record)
        if isinstance(value, bool):
            broken[key] = False
        elif value is None:
            broken[key] = "unexpected"
        elif isinstance(value, int):
            broken[key] = value + 1
        else:
            broken[key] = "unexpected"
        assert verifier.sample_passed(broken) is False, key


@pytest.mark.parametrize(
    "field",
    (
        "template_unchanged",
        "passed_count",
        "repeat_deterministic_count",
        "historical_exact_match_count",
    ),
)
def test_top_level_complete_requires_all_five_and_unchanged_template(field: str) -> None:
    verifier = _load_verifier()
    summary = {
        "template_unchanged": True,
        "passed_count": 5,
        "repeat_deterministic_count": 5,
        "historical_exact_match_count": 5,
    }
    assert verifier.verification_complete(summary) is True
    summary[field] = False if field == "template_unchanged" else 4
    assert verifier.verification_complete(summary) is False
