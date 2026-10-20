"""Verify the released contact pilot using raw outputs and independent comparisons."""

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

FIELDS = ("name", "email", "phone")
BASE = "Extract the contact details from the text. Use null for anything not present."


def load(path):
    return json.loads(path.read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def schema(text):
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return False
    return (
        isinstance(value, dict)
        and set(value) == set(FIELDS)
        and all(v is None or isinstance(v, str) for v in value.values())
        and (
            value["email"] is None
            or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value["email"]) is not None
        )
    )


def grade(run, gold):
    actual = run["result"]["result"]
    completed = (
        run["result"]["status"] == "completed"
        and isinstance(actual, dict)
        and set(actual) == set(FIELDS)
    )
    actual = actual if isinstance(actual, dict) else {}
    correct = {f: bool(completed and actual[f] == gold[f]) for f in FIELDS}
    return {
        "exact_record": all(correct.values()),
        "fields": correct,
        "unsupported_non_null": sum(
            actual.get(f) is not None and actual.get(f) != gold[f] for f in FIELDS
        ),
        "missing_fields": sum(gold[f] is None for f in FIELDS),
        "correct_nulls": sum(completed and gold[f] is None and actual[f] is None for f in FIELDS),
        "first_schema_valid": bool(run["attempts"]) and schema(run["attempts"][0]["text"]),
        "status": run["result"]["status"],
        "attempts": len(run["attempts"]),
        "prompt_tokens": run["result"]["prompt_tokens"],
        "completion_tokens": run["result"]["completion_tokens"],
        "latency_ms": run["result"]["latency_ms"],
    }


def verify_bundle(directory, project):
    if not __debug__:
        raise RuntimeError("Verification requires assertions; run without -O or PYTHONOPTIMIZE")
    for name, digest in load(directory / "SHA256SUMS.json").items():
        assert sha((directory / name).read_bytes()) == digest, name
    freeze = load(directory / "freeze.json")
    protocol = load(project / "experiments/contact/protocol-v2.json")
    assert sha((directory / "systemprompt.md").read_bytes()) == freeze["instruction_sha256"]
    assert (
        sha((project / "experiments/contact/protocol-v2.json").read_bytes())
        == freeze["protocol_sha256"]
    )
    assert sha((directory / "dev-gold.json").read_bytes()) == protocol["dev_gold_sha256"]
    manifest = load(directory / "heldout-manifest.json")
    assert (
        manifest["generated_after_freeze"]
        and manifest["frozen_instruction_sha256"] == freeze["instruction_sha256"]
    )
    for name in ["inputs", "gold"]:
        assert sha((directory / f"heldout-{name}.json").read_bytes()) == manifest[name + "_sha256"]
    development = {r["id"]: r for r in load(project / "experiments/contact/dev-inputs.json")}
    heldout = {r["id"]: r for r in load(directory / "heldout-inputs.json")}
    assert len(development) == 12 and len(heldout) == 36 and not development.keys() & heldout.keys()
    assert Counter(c["cluster"] for c in heldout.values()) == dict.fromkeys(
        ["complete", "missing", "ambiguity", "injection"], 9
    )
    assert not {c["input"]["text"] for c in development.values()} & {
        c["input"]["text"] for c in heldout.values()
    }
    data = load(directory / "executions.json")
    runs = {r["key"]: r for r in data}
    assert len(runs) == len(data) == 276
    assert Counter(r["phase"] for r in data) == {"optimize": 48, "baseline": 48, "evaluate": 180}
    for run in data:
        assert (
            run["result"]["model"] == "deepseek-flash"
            and 1 <= len(run["attempts"]) <= 2
            and run["max_tokens"] == 160
        )
        assert all(a["max_tokens"] == 160 for a in run["attempts"])
    index = load(directory / "selection-index.json")
    quality = load(directory / "quality.json")
    expected_rows = {"dev": [], "heldout": []}
    all_samples = {"dev": [], "heldout": []}
    for phase, cases, gold in [
        ("dev", development, load(directory / "dev-gold.json")),
        ("heldout", heldout, load(directory / "heldout-gold.json")),
    ]:
        if phase == "dev":
            refs = [
                {
                    "task": r["task"],
                    "arm": a,
                    "key": r[a],
                    **({"samples": r["matched_samples"]} if a == "matched" else {}),
                }
                for r in index["dev"]
                for a in ["base", "adapted", "matched"]
            ]
        else:
            refs = index["heldout"]
        assert len(refs) == len(cases) * 3
        assert len({(r["task"], r["arm"]) for r in refs}) == len(refs)
        for ref in refs:
            task = ref["task"]
            run = runs[ref["key"]]
            assert run["input"] == cases[task]["input"]
            expected_rows[phase].append(
                {
                    "task": task,
                    "cluster": cases[task]["cluster"],
                    "arm": ref["arm"],
                    **grade(run, gold[task]),
                }
            )
            if ref["arm"] in ["base", "matched"]:
                assert run["instruction_sha256"] == sha(BASE.encode())
            if ref["arm"] == "frozen":
                assert run["instruction_sha256"] == sha(
                    (directory / "systemprompt.md").read_text().rstrip().encode()
                )
            if ref["arm"] == "matched":
                samples = [runs[k] for k in ref["samples"]]
                assert len(samples) == 4 and all(s["input"] == run["input"] for s in samples)
                candidates = [
                    (json.dumps(s["result"]["result"], ensure_ascii=False), i, s["key"])
                    for i, s in enumerate(samples)
                    if s["result"]["status"] == "completed"
                ]
                counts = Counter(c[0] for c in candidates)
                assert min(candidates, key=lambda c: (-counts[c[0]], c[0], c[1]))[2] == run["key"]
                all_samples[phase].extend(grade(s, gold[task]) for s in samples)
        observed = {(r["task"], r["arm"]): r for r in quality[phase]["rows"]}
        for r in expected_rows[phase]:
            assert observed[r["task"], r["arm"]] == r, (phase, r["task"], r["arm"])
        for arm, summary in quality[phase]["arms"].items():
            rows = [r for r in expected_rows[phase] if r["arm"] == arm]
            assert summary["n"] == len(rows) and summary["exact_records"] == sum(
                r["exact_record"] for r in rows
            )
            assert math.isclose(
                summary["exact_record_accuracy"], summary["exact_records"] / len(rows)
            )
            assert summary["field_correct"] == {
                f: sum(r["fields"][f] for r in rows) for f in FIELDS
            }
            for field in [
                "unsupported_non_null",
                "first_schema_valid",
                "missing_fields",
                "correct_nulls",
                "prompt_tokens",
                "completion_tokens",
            ]:
                assert summary[field] == sum(r[field] or 0 for r in rows), (phase, arm, field)
            assert summary["repair_attempts"] == sum(r["attempts"] - 1 for r in rows)
            assert summary["rejected"] == sum(r["status"] == "rejected" for r in rows)
        for pair in quality[phase]["paired"]:
            arm = pair["comparison"].split(" minus ")[0]
            changes = []
            for t in cases:
                a = next(r for r in expected_rows[phase] if r["task"] == t and r["arm"] == "base")
                b = next(r for r in expected_rows[phase] if r["task"] == t and r["arm"] == arm)
                changes.append(int(b["exact_record"]) - int(a["exact_record"]))
            assert pair["improved"] == changes.count(1) and pair["regressed"] == changes.count(-1)
    regression = load(directory / "regression.json")
    first = load(directory / "regression-first-requests.json")
    assert first["base"].keys() == first["frozen"].keys()
    nonextract = [key for key, r in first["base"].items() if r["task"] != "extract_contact"]
    assert len(nonextract) == regression["non_extraction_cases_checked"] == 84
    for key in nonextract:
        assert first["base"][key] == first["frozen"][key], key
    for arm in ["base", "frozen"]:
        r = load(directory / f"regression-{arm}.json")
        assert len(r["cases"]) == r["summary"]["total"] == 87
        assert (
            sum(c["passed"] for c in r["cases"])
            == r["summary"]["passed"]
            == regression[arm]["passed"]
            == 87
        )
    ledger = load(directory / "dollar-budget.json")
    assert (
        sha((directory / "original-budget.json").read_bytes()) == ledger["migration_source_sha256"]
    )
    assert len(ledger["requests"]) == 1062
    for index, row in enumerate(ledger["requests"]):
        assert row["receipt"] == index and row["http_status"] == 200
        usage = row["usage"]
        a, b = usage["prompt_tokens"], usage["completion_tokens"]
        assert type(a) is int and type(b) is int
        assert 0 <= a <= row["input_token_bound"] and 0 <= b <= row["output_token_bound"]
        assert usage["total_tokens"] == a + b
        cost = int(
            (Decimal("0.6") * a + Decimal("2.4") * b).to_integral_value(rounding=ROUND_CEILING)
        )
        bound = int(
            (
                Decimal("0.6") * row["input_token_bound"]
                + Decimal("2.4") * row["output_token_bound"]
            ).to_integral_value(rounding=ROUND_CEILING)
        )
        assert row["retained_micro_usd"] == cost <= row["reserved_micro_usd"] == bound
    assert (
        sum(r["retained_micro_usd"] for r in ledger["requests"])
        == ledger["reserved_micro_usd"]
        <= ledger["limit_micro_usd"]
        == 5000000
    )
    accounting = load(directory / "accounting.json")
    assert ledger["reserved_micro_usd"] == accounting["retained_micro_usd"]
    assert (
        accounting["retained_micro_usd"] <= accounting["approved_cap_micro_usd"] == 5000000
        and accounting["forwarded_requests"] == 1062
    )
    assert accounting["all_requests_have_successful_usage"]
    return {
        "physical_executions": len(runs),
        "heldout_base_correct": quality["heldout"]["arms"]["base"]["exact_records"],
        "heldout_frozen_correct": quality["heldout"]["arms"]["frozen"]["exact_records"],
        "regression_cases_per_arm": 87,
        "non_extraction_requests_unchanged": len(nonextract),
    }


def main():
    project = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle", type=Path, default=project / "docs/evals/contact-pilot-2026-10-20"
    )
    args = parser.parse_args()
    print(json.dumps(verify_bundle(args.bundle, project), indent=2))


if __name__ == "__main__":
    main()
