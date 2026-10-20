"""Post-selection contact metrics, independent of runtime rendering and validators."""

from __future__ import annotations

import json
import re
from pathlib import Path

FIELDS = ("name", "email", "phone")


def raw_schema_valid(text: str) -> bool:
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return False
    if not isinstance(value, dict) or set(value) != set(FIELDS):
        return False
    if any(v is not None and not isinstance(v, str) for v in value.values()):
        return False
    email = value["email"]
    return email is None or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is not None


def grade_run(directory: Path, expected: dict) -> dict:
    if set(expected) != set(FIELDS):
        raise ValueError("Gold must explicitly define all three nullable fields")
    runtime = directory / "runtime"
    result = json.loads((runtime / "result.json").read_text())
    attempts = json.loads((runtime / "attempts.json").read_text())
    actual = result.get("result") or {}
    completed = result["status"] == "completed" and set(actual) == set(FIELDS)
    correct = {field: completed and actual[field] == expected[field] for field in FIELDS}
    return {
        "exact_record": all(correct.values()),
        "fields": correct,
        "unsupported_non_null": sum(
            actual.get(f) is not None and actual.get(f) != expected[f] for f in FIELDS
        ),
        "missing_fields": sum(expected[f] is None for f in FIELDS),
        "correct_nulls": sum(
            completed and expected[f] is None and actual[f] is None for f in FIELDS
        ),
        "first_schema_valid": bool(attempts) and raw_schema_valid(attempts[0]["text"]),
        "status": result["status"],
        "attempts": len(attempts),
        "prompt_tokens": result.get("prompt_tokens"),
        "completion_tokens": result.get("completion_tokens"),
        "latency_ms": result.get("latency_ms"),
    }


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "n": n,
        "exact_records": sum(r["exact_record"] for r in rows),
        "exact_record_accuracy": sum(r["exact_record"] for r in rows) / n if n else None,
        "field_correct": {f: sum(r["fields"][f] for r in rows) for f in FIELDS},
        "unsupported_non_null": sum(r["unsupported_non_null"] for r in rows),
        "first_schema_valid": sum(r["first_schema_valid"] for r in rows),
        "rejected": sum(r["status"] == "rejected" for r in rows),
        "repair_attempts": sum(max(0, r["attempts"] - 1) for r in rows),
        "prompt_tokens": sum(r["prompt_tokens"] or 0 for r in rows),
        "completion_tokens": sum(r["completion_tokens"] or 0 for r in rows),
    }
