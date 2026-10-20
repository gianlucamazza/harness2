"""Independently reproduce published follow-up canary and accounting checks."""

import hashlib
import json
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "docs/evals/contact-followup-2026-10-20"


def verify(bundle=BUNDLE):
    def load(name):
        return json.loads((bundle / name).read_text())

    if not __debug__:
        raise RuntimeError("Verification requires enabled assertions")
    for name, checksum in load("SHA256SUMS.json").items():
        assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == checksum, name
    result, attempts = load("result.json"), load("attempts.json")
    expected = {
        "name": "Casey Canary",
        "email": "casey.canary@example.com",
        "phone": "+1-202-555-0198",
    }
    assert result["status"] == "completed" and result["result"] == expected
    assert len(attempts) == 1 and json.loads(attempts[0]["text"]) == expected
    assert result["attempts"] == 1
    accounting = load("accounting.json")
    old = json.loads((ROOT / "docs/evals/contact-pilot-2026-10-20/dollar-budget.json").read_text())
    protocol_path = ROOT / "experiments/contact/protocol-v3.json"
    protocol = json.loads(protocol_path.read_text())
    assert (
        hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        == load("provenance.json")["protocol_sha256"]
    )
    assert (
        hashlib.sha256(json.dumps(old["requests"], sort_keys=True).encode()).hexdigest()
        == protocol["budget_anchor"]["requests_sha256"]
    )
    assert accounting["historical_requests"] == len(old["requests"]) == 1062
    assert accounting["historical_retained_micro_usd"] == old["reserved_micro_usd"]
    traces = load("gateway-requests.json")["requests"]
    by_id = {r["request_id"]: r for r in traces}
    assert len(by_id) == len(traces) == 2
    assert sum(r["method"] == "GET" and r["accounting_receipt"] is None for r in traces) == 1
    receipts = accounting["new_requests"]
    assert len(receipts) == 1 and receipts[0]["receipt"] == 1062
    for row in receipts:
        usage = row["usage"]
        assert row["http_status"] == 200
        assert (
            type(usage["prompt_tokens"]) is int
            and 0 <= usage["prompt_tokens"] <= row["input_token_bound"]
        )
        assert (
            type(usage["completion_tokens"]) is int
            and 0 <= usage["completion_tokens"] <= row["output_token_bound"]
        )
        assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
        retained = int(
            (
                usage["prompt_tokens"] * Decimal("0.6")
                + usage["completion_tokens"] * Decimal("2.4")
            ).to_integral_value(rounding=ROUND_CEILING)
        )
        assert retained == row["retained_micro_usd"]
        assert usage["prompt_tokens"] == attempts[0]["prompt_tokens"] == result["prompt_tokens"]
        assert (
            usage["completion_tokens"]
            == attempts[0]["completion_tokens"]
            == result["completion_tokens"]
        )
        trace = by_id[row["attribution"]["request_id"]]
        assert trace["method"] == "POST" and trace["accounting_receipt"] == row["receipt"]
        assert trace["context"] == {
            k: v for k, v in row["attribution"].items() if k != "request_id"
        }
    assert all(r["state"] == "responded" and r["http_status"] == 200 for r in traces)
    assert all(
        r["context"]["role"] == "solver" and r["context"]["execution"] == "followup-canary"
        for r in traces
    )
    total = old["reserved_micro_usd"] + sum(r["retained_micro_usd"] for r in receipts)
    assert accounting["retained_micro_usd"] == total == 3990737
    assert accounting["total_requests"] == 1063
    assert accounting["limit_micro_usd"] == 5000000
    full = load("followup-preflight.json")
    limits = protocol["phases"]["followup"]
    bound = (
        int(
            (
                (limits["payload_bytes"] + 4096) * Decimal("0.6")
                + limits["output_tokens"] * Decimal("2.4")
            ).to_integral_value(rounding=ROUND_CEILING)
        )
        * limits["posts"]
    )
    assert full["worst_case_micro_usd"] == bound == 130429952
    assert full["remaining_micro_usd"] == 5000000 - total and not full["fits"]
    assert load("campaign-identity.json")["adoption_policy"] == "contact-first-attempt-v1"
    assert load("adoption-eligibility.json")["qualified"]
    return {
        "exact_canary": True,
        "attributed_requests": len(traces),
        "cumulative_retained_micro_usd": total,
        "remaining_micro_usd": 5000000 - total,
        "full_followup_budget_fits": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
