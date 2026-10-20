"""Grade recorded extraction regressions without inference or runtime validators.

Each input row is {"task": <fixture id>, "result": <runtime result>,
"attempts": <recorded raw attempts>}. All 44 IDs must occur exactly once.
"""

import argparse
import hashlib
import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "docs/evals/contact-regressions-v1"


def load_fixtures():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    for name, checksum in manifest["sha256"].items():
        if hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() != checksum:
            raise ValueError("Regression fixture checksum changed")
    inputs = json.loads((FIXTURES / "inputs.json").read_text())
    gold = json.loads((FIXTURES / "gold.json").read_text())
    ids = [c["id"] for c in inputs]
    if len(ids) != manifest["cases"] or len(set(ids)) != len(ids) or set(ids) != set(gold):
        raise ValueError("Regression fixture identity mismatch")
    return inputs, gold


def grade(rows):
    _, gold = load_fixtures()
    ids = [r["task"] for r in rows]
    if len(set(ids)) != len(ids) or set(ids) != set(gold):
        raise ValueError("Every regression case must be recorded exactly once")
    records = []
    for row in rows:
        result, attempts = row["result"], row["attempts"]
        actual = result.get("result")
        exact = result["status"] == "completed" and actual == gold[row["task"]]
        try:
            raw = json.loads(attempts[0]["text"])
            first_structure = (
                isinstance(raw, dict)
                and set(raw) == {"name", "email", "phone"}
                and all(v is None or isinstance(v, str) for v in raw.values())
            )
        except (ValueError, TypeError, KeyError, IndexError):
            first_structure = False
        records.append(
            {
                "task": row["task"],
                "exact": exact,
                "first_object_structure": first_structure,
                "repairs": max(0, len(attempts) - 1),
                "status": result["status"],
            }
        )
    return {
        "cases": len(records),
        "exact": sum(r["exact"] for r in records),
        "first_object_structure": sum(r["first_object_structure"] for r in records),
        "repairs": sum(r["repairs"] for r in records),
        "records": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executions", type=Path)
    args = parser.parse_args()
    if args.executions is None:
        inputs, _ = load_fixtures()
        print(json.dumps({"fixtures_verified": len(inputs), "model_calls": 0}))
        return 0
    report = grade(json.loads(args.executions.read_text()))
    print(json.dumps(report, indent=2))
    return 0 if report["exact"] == report["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
