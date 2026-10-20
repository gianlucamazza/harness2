"""Independent contact v4 evidence verifier: no runtime, adapter or network imports."""

import argparse
import hashlib
import json
import statistics
from decimal import ROUND_CEILING, Decimal
from pathlib import Path


def load(p):
    return json.loads(Path(p).read_text())


def exact(result, expected):
    return result.get("status") == "completed" and result.get("result") == expected


def valid(text):
    import re

    try:
        x = json.loads(text)
    except (ValueError, TypeError):
        return False
    return (
        isinstance(x, dict)
        and set(x) == {"name", "email", "phone"}
        and all(v is None or isinstance(v, str) for v in x.values())
        and (
            x["email"] is None or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", x["email"]) is not None
        )
    )


def metrics(executions, expected):
    rows = []
    for execution, gold in zip(executions, expected):
        result, attempts = execution["result"], execution["attempts"]
        actual = result.get("result") or {}
        complete = result["status"] == "completed"
        rows.append(
            {
                "exact": exact(result, gold),
                "fields": {f: complete and actual.get(f) == gold[f] for f in gold},
                "unsupported": sum(
                    actual.get(f) is not None and actual.get(f) != gold[f] for f in gold
                ),
                "first_schema": bool(attempts) and valid(attempts[0]["text"]),
                "repairs": max(0, len(attempts) - 1),
                "status": result["status"],
                "latency_ms": result.get("latency_ms"),
                "input": sum(a.get("prompt_tokens") or 0 for a in attempts),
                "output": sum(a.get("completion_tokens") or 0 for a in attempts),
            }
        )
    return {
        "cases": len(rows),
        "exact": sum(r["exact"] for r in rows),
        "fields": {f: sum(r["fields"][f] for r in rows) for f in ["name", "email", "phone"]},
        "unsupported_non_null": sum(r["unsupported"] for r in rows),
        "first_schema": sum(r["first_schema"] for r in rows),
        "repairs": sum(r["repairs"] for r in rows),
        "rejected": sum(r["status"] == "rejected" for r in rows),
        "input": sum(r["input"] for r in rows),
        "output": sum(r["output"] for r in rows),
        "mean_latency_ms": statistics.mean(r["latency_ms"] for r in rows),
        "rows": rows,
    }


def grade_legacy(check, output):
    import re

    if not output.strip():
        return False
    kind = check["type"]
    if kind == "contains":
        return any(s.lower() in output.lower() for s in check["any_of"])
    if kind == "regex":
        return re.search(check["pattern"], output) is not None
    if kind == "number":
        numbers = re.findall(r"-?\d[\d,]*(?:\.\d+)?", output)
        return bool(numbers) and abs(
            float(numbers[-1].replace(",", "")) - check["value"]
        ) <= check.get("tolerance", 0)
    try:
        text = output.strip()
        if text.startswith("```"):
            text = "\n".join(text.splitlines()[1:-1])
        value = json.loads(text)
    except ValueError:
        return False
    if not isinstance(value, dict):
        return False
    sentinel = object()

    def lookup(path):
        current = value
        for key in path.split("."):
            if not isinstance(current, dict) or key not in current:
                return sentinel
            current = current[key]
        return current

    return all(lookup(key) is not sentinel for key in check.get("keys", [])) and all(
        str(lookup(key)).strip().casefold() == str(expected).strip().casefold()
        for key, expected in check.get("equals", {}).items()
    )


def verify_bundle(bundle):
    if not __debug__:
        raise RuntimeError("Assertions must be enabled")
    bundle = Path(bundle)

    def read(name):
        return load(bundle / name)

    for name, checksum in read("SHA256SUMS.json").items():
        assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == checksum, name
    ledger = read("dollar-budget.json")
    auth = read("budget-authorization.json")
    prior = read(auth["audit_file"])
    assert (
        hashlib.sha256((bundle / auth["audit_file"]).read_bytes()).hexdigest()
        == auth["prior_ledger_sha256"]
    )
    assert (
        prior["limit_micro_usd"] == 5000000
        and len(prior["requests"]) == 1063
        and prior["reserved_micro_usd"] == 3990737
    )
    assert ledger["limit_micro_usd"] == 10000000 and ledger["requests"][:1063] == prior["requests"]
    total = 0
    for i, row in enumerate(ledger["requests"]):
        assert row["receipt"] == i
        usage = row.get("usage")
        retained = row["reserved_micro_usd"]
        if row.get("http_status") == 200 and isinstance(usage, dict):
            a, b = usage.get("prompt_tokens"), usage.get("completion_tokens")
            assert (
                type(a) is int
                and type(b) is int
                and 0 <= a <= row["input_token_bound"]
                and 0 <= b <= row["output_token_bound"]
            )
            if usage.get("total_tokens") == a + b:
                retained = int(
                    (Decimal(a) * Decimal(".6") + Decimal(b) * Decimal("2.4")).to_integral_value(
                        rounding=ROUND_CEILING
                    )
                )
        assert row["retained_micro_usd"] == retained
        total += retained
    assert total == ledger["reserved_micro_usd"] <= 10000000
    traces = read("gateway-requests.json")["requests"]
    by_id = {r["request_id"]: r for r in traces}
    assert len(by_id) == len(traces)
    new = ledger["requests"][1063:]
    for row in new:
        meta = row["attribution"]
        trace = by_id[meta["request_id"]]
        assert trace["accounting_receipt"] == row["receipt"] and trace["method"] == "POST"
        assert trace["context"] == {k: v for k, v in meta.items() if k != "request_id"}
        assert row["http_status"] == trace["http_status"] == 200 and trace["state"] == "responded"
    executions = read("executions.json")
    runs = {r["key"]: r for r in executions}
    assert len(runs) == len(executions)
    for row in executions:
        for name, field in [
            ("request.json", "request"),
            ("runtime/result.json", "result"),
            ("runtime/attempts.json", "attempts"),
            ("runtime/identity.json", "runtime_identity"),
        ]:
            raw = (json.dumps(row[field], indent=2) + "\n").encode()
            assert hashlib.sha256(raw).hexdigest() == row["record"]["checksums"][name]
        assert row["request"] == row["record"]["identity"]["request"]
        calls = [
            r
            for r in new
            if r["attribution"]["role"] == "solver"
            and r["attribution"]["execution"] == row["record"]["identity"]["run_id"]
        ]
        assert [(r["usage"]["prompt_tokens"], r["usage"]["completion_tokens"]) for r in calls] == [
            (a["prompt_tokens"], a["completion_tokens"]) for a in row["attempts"]
        ]
    freeze = read("freeze.json")
    text = (bundle / "systemprompt.md").read_text()
    manifest = read("heldout-manifest.json")
    inputs = read("heldout-inputs.json")
    gold = read("heldout-gold.json")
    from datetime import datetime

    assert (
        hashlib.sha256(text.encode()).hexdigest()
        == freeze["instruction_sha256"]
        == manifest["instruction_sha256"]
    )
    assert datetime.fromisoformat(manifest["generated_at"]) > datetime.fromisoformat(
        freeze["frozen_at"]
    )
    assert (
        hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
        == manifest["inputs_sha256"]
    )
    assert len(inputs) == len(gold) == 36 and all(
        sum(c["cluster"] == group for c in inputs) == 9
        for group in ["complete", "missing", "ambiguity", "injection"]
    )
    assert (
        hashlib.sha256((bundle / "protocol-v4.json").read_bytes()).hexdigest()
        == freeze["protocol_sha256"]
    )
    excluded = set(read("released-input-hashes.json")) | {
        hashlib.sha256(c["input"]["text"].encode()).hexdigest() for c in read("dev-inputs.json")
    }
    assert all(
        hashlib.sha256(c["input"]["text"].encode()).hexdigest() not in excluded for c in inputs
    )
    assert {c["id"] for c in inputs} == set(gold)
    assert all(
        set(v) == {"name", "email", "phone"}
        and all(x is None or isinstance(x, str) for x in v.values())
        for v in gold.values()
    )
    index = read("heldout-index.json")
    assert len(index) == 36
    calculated = {
        arm: metrics([runs[r[arm]] for r in index], [gold[r["task"]] for r in index])
        for arm in ["base", "frozen", "matched"]
    }
    for row in index:
        candidates = [
            (json.dumps(runs[p]["result"].get("result"), ensure_ascii=False), i, p)
            for i, p in enumerate(row["samples"])
            if runs[p]["result"]["status"] == "completed"
        ]
        counts = {text: sum(c[0] == text for c in candidates) for text, _, _ in candidates}
        assert min(candidates, key=lambda c: (-counts[c[0]], c[0], c[1]))[2] == row["matched"]
        assert (
            len(row["samples"]) == 4
            and runs[row["frozen"]]["request"]["instruction"] == text.rstrip()
        )
    quality = read("quality.json")
    for arm, score in calculated.items():
        reported = quality["heldout"][arm]
        assert (
            score["exact"] == reported["exact_records"]
            and score["first_schema"] == reported["first_schema_valid"]
            and score["repairs"] == reported["repair_attempts"]
            and score["unsupported_non_null"] == reported["unsupported_non_null"]
            and score["fields"] == reported["field_correct"]
        )
    selection = read("selections.json")
    assert len(selection) == 12
    for row in selection:
        assert row["status"] == "ok" and not row["stages"] and row["eligibility"]["qualified"]
        selected = row["selection"]
        assert row["eligibility"]["decisions"][selected["chosen_label"]]["eligible"]
        chosen = runs[selected["chosen_run_dir"]]
        assert len(chosen["attempts"]) == 1 and valid(chosen["attempts"][0]["text"])
    dev = read("development-index.json")
    assert len(dev) == 12 and runs[dev[-1]["adapted"]]["request"]["instruction"] == text.rstrip()
    original = read("original-regression-executions.json")
    cases = read("original-regression-cases.json")
    assert len(cases) == 87 and len(original) == 174
    by_key = {(r["arm"], r["task"]): r for r in original}
    unchanged = 0
    for case in cases:
        if case["request"].get("task") != "extract_contact":
            a = by_key["base", case["id"]]["attempts"][0]
            b = by_key["frozen", case["id"]]["attempts"][0]
            assert a["messages"] == b["messages"] and a["max_tokens"] == b["max_tokens"]
            unchanged += 1
    for arm in ["base", "frozen"]:
        passed = 0
        for case in cases:
            row = by_key[arm, case["id"]]
            result = row["result"]
            output = result["output"] if result["result"] is None else json.dumps(result["result"])
            passed += result["status"] == "completed" and grade_legacy(case["check"], output)
            calls = [
                r
                for r in new
                if r["attribution"]["role"] == "solver"
                and r["attribution"]["execution"] == f"original/{arm}/{case['id']}"
            ]
            assert [
                (r["usage"]["prompt_tokens"], r["usage"]["completion_tokens"]) for r in calls
            ] == [(a["prompt_tokens"], a["completion_tokens"]) for a in row["attempts"]]
        assert quality["original_regressions"][arm] == {"cases": 87, "passed": passed}
    assert unchanged == 84
    extraction = read("extraction-regression-index.json")
    assert len(extraction) == 88
    extraction_gold = read("extraction-regression-gold.json")
    for arm in ["base", "frozen"]:
        values = [r for r in extraction if r["arm"] == arm]
        score = metrics(
            [runs[r["run_dir"]] for r in values], [extraction_gold[r["task"]] for r in values]
        )
        assert (
            score["cases"] == 44
            and score["exact"] == quality["extraction_regressions"][arm]["exact_records"]
        )
    assert (
        read("complete.json")["status"] == "completed"
        and read("complete.json")["promotion"] == "none"
    )
    return {
        "heldout_exact": {arm: calculated[arm]["exact"] for arm in calculated},
        "original_regressions": quality["original_regressions"],
        "extraction_regressions": {
            arm: quality["extraction_regressions"][arm]["exact_records"]
            for arm in ["base", "frozen"]
        },
        "typed_executions": len(executions),
        "new_paid_requests": len(new),
        "cumulative_retained_micro_usd": total,
        "original_non_extraction_requests_unchanged": unchanged,
        "adopted_base_tasks": sum(r["selection"]["chosen_tree_is_base"] for r in selection),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "docs/evals/contact-campaign-v4-2026-10-20",
    )
    args = parser.parse_args()
    print(json.dumps(verify_bundle(args.bundle), indent=2))
