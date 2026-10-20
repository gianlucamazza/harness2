"""Offline cumulative-budget preflight; unknown calls retain their entire bounds."""

import hashlib
import json
from datetime import datetime
from decimal import ROUND_CEILING
from pathlib import Path

from .contact_policy import ADOPTION_POLICY, SPEC_SHA256
from .runtime_budget import INPUT_MICRO_USD_PER_TOKEN, OUTPUT_MICRO_USD_PER_TOKEN, DollarBudget


def check_heldout(cases, development, frozen, manifest, released_hashes):
    """Reject released data and require an input commitment made after freezing."""
    if set(manifest) != {"generated_at", "inputs_sha256", "instruction_sha256"}:
        raise ValueError("Held-out manifest contains unexpected fields")
    generated, frozen_at = (
        datetime.fromisoformat(manifest["generated_at"]),
        datetime.fromisoformat(frozen["frozen_at"]),
    )
    if (
        generated.tzinfo is None
        or frozen_at.tzinfo is None
        or generated <= frozen_at
        or manifest["instruction_sha256"] != frozen["instruction_sha256"]
        or manifest["inputs_sha256"]
        != hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest()
    ):
        raise ValueError("Held-out manifest does not bind new inputs after freezing")
    excluded = set(released_hashes) | {
        hashlib.sha256(c["input"]["text"].encode()).hexdigest() for c in development
    }
    dev_ids = {c["id"] for c in development}
    if any(
        c["id"] in dev_ids or hashlib.sha256(c["input"]["text"].encode()).hexdigest() in excluded
        for c in cases
    ):
        raise ValueError("Held-out inputs overlap development or released regression data")


def check_budget(root: Path, protocol: dict, phase: str) -> dict:
    if not (root / "dollar-budget.json").is_file():
        raise ValueError("Existing cumulative ledger is required")
    if json.loads((root / "dollar-budget.json").read_text()).get("accounting_version") != 2:
        raise ValueError("Preflight requires an explicitly migrated v2 ledger")
    ledger = DollarBudget(root)._load(root / "dollar-budget.json")
    anchor = protocol["budget_anchor"]
    rows = ledger["requests"]
    prefix = json.dumps(rows[: anchor["requests"]], sort_keys=True).encode()
    if (
        len(rows) < anchor["requests"]
        or hashlib.sha256(prefix).hexdigest() != anchor["requests_sha256"]
        or ledger["limit_micro_usd"] != protocol["monetary_cap_usd"] * 1_000_000
        or ledger.get("accounting_version") != 2
        or ledger.get("blocked")
    ):
        raise ValueError("Cumulative accounting identity changed; refusing a fresh allowance")
    retained = sum(row["retained_micro_usd"] for row in rows)
    cap = ledger["limit_micro_usd"]
    if retained != ledger["reserved_micro_usd"] or not 0 <= retained <= cap:
        raise ValueError("Cumulative accounting total is inconsistent")
    if (
        protocol["public_spec_sha256"] != SPEC_SHA256
        or protocol["adoption_policy"] != ADOPTION_POLICY
    ):
        raise ValueError("Follow-up specification/policy differs from preregistration")
    limits = protocol["phases"][phase]
    one = int(
        (
            (limits["payload_bytes"] + 4096) * INPUT_MICRO_USD_PER_TOKEN
            + limits["output_tokens"] * OUTPUT_MICRO_USD_PER_TOKEN
        ).to_integral_value(rounding=ROUND_CEILING)
    )
    worst = one * limits["posts"]
    remaining = cap - retained
    rolling = protocol.get("admission_policy") == "cumulative-per-request-adr0005"
    if rolling and (protocol["version"] != 4 or cap != 10_000_000):
        raise ValueError("Unrecognized request-admission authorization")
    return {
        "phase": phase,
        "historical_requests": len(rows),
        "retained_micro_usd": retained,
        "remaining_micro_usd": remaining,
        "worst_case_micro_usd": worst,
        "fits": (one if rolling else worst) <= remaining,
        "admission_policy": "per-request" if rolling else "aggregate",
        "single_request_bound_micro_usd": one,
        "limits": limits,
        "includes": "all posts including SDK auxiliaries, repairs and failures; catalog GETs are capped and unbilled",
        "invoice_verified": False,
    }
