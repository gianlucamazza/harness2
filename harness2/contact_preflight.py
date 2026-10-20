"""Offline cumulative-budget preflight; unknown calls retain their entire bounds."""

import hashlib
import json
from decimal import ROUND_CEILING
from pathlib import Path

from .contact_policy import ADOPTION_POLICY, SPEC_SHA256
from .runtime_budget import INPUT_MICRO_USD_PER_TOKEN, OUTPUT_MICRO_USD_PER_TOKEN, DollarBudget


def check_budget(root: Path, protocol: dict, phase: str) -> dict:
    if not (root / "dollar-budget.json").is_file():
        raise ValueError("Existing cumulative ledger is required")
    ledger = DollarBudget(root)._load(root / "dollar-budget.json")
    anchor = protocol["budget_anchor"]
    rows = ledger["requests"]
    prefix = json.dumps(rows[: anchor["requests"]], sort_keys=True).encode()
    if (
        len(rows) < anchor["requests"]
        or hashlib.sha256(prefix).hexdigest() != anchor["requests_sha256"]
        or ledger["limit_micro_usd"] != 5_000_000
        or protocol["monetary_cap_usd"] != 5
        or ledger.get("accounting_version") != 2
        or ledger.get("blocked")
    ):
        raise ValueError("Cumulative accounting identity changed; refusing a fresh allowance")
    retained = sum(row["retained_micro_usd"] for row in rows)
    if retained != ledger["reserved_micro_usd"] or not 0 <= retained <= 5_000_000:
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
    remaining = 5_000_000 - retained
    return {
        "phase": phase,
        "historical_requests": len(rows),
        "retained_micro_usd": retained,
        "remaining_micro_usd": remaining,
        "worst_case_micro_usd": worst,
        "fits": worst <= remaining,
        "limits": limits,
        "includes": "all posts including SDK auxiliaries, repairs and failures; catalog GETs are capped and unbilled",
        "invoice_verified": False,
    }
