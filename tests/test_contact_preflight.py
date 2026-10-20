"""Budget bounds include failures and SDK requests; a new ledger cannot reset spend."""

import json
import tempfile
import unittest
from pathlib import Path

from harness2 import config
from harness2.contact_preflight import check_budget
from harness2.runtime_budget import BudgetExhausted, RequestLimits


class PreflightTests(unittest.TestCase):
    def test_pinned_cumulative_budget_allows_canary_and_refuses_full_followup(self):
        protocol = json.loads((config.ROOT / "experiments/contact/protocol-v3.json").read_text())
        root = config.ROOT / "docs/evals/contact-pilot-2026-10-20"
        canary = check_budget(root, protocol, "canary")
        self.assertTrue(canary["fits"])
        self.assertEqual(canary["worst_case_micro_usd"], 45006)
        self.assertEqual(canary["remaining_micro_usd"], 1009400)
        full = check_budget(root, protocol, "followup")
        self.assertFalse(full["fits"])
        self.assertEqual(full["worst_case_micro_usd"], 130429952)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Existing cumulative ledger"):
                check_budget(Path(directory), protocol, "canary")
            (Path(directory) / "dollar-budget.json").write_text(
                json.dumps(
                    {
                        "accounting_version": 2,
                        "limit_micro_usd": 5000000,
                        "reserved_micro_usd": 0,
                        "requests": [],
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "fresh allowance"):
                check_budget(Path(directory), protocol, "canary")

    def test_limits_bound_auxiliary_calls_readiness_output_and_payload(self):
        limits = RequestLimits(posts=2, gets=1, payload_bytes=100, output_tokens=16)
        limits.admit("GET", None)
        with self.assertRaises(BudgetExhausted):
            limits.admit("GET", None)
        with self.assertRaises(ValueError):
            limits.admit("POST", {"max_tokens": 17})
        with self.assertRaises(ValueError):
            limits.admit("POST", {"max_tokens": 16, "messages": "x" * 101})
        limits.admit("POST", {"max_tokens": 16})
        limits.admit("POST", {"max_tokens": 16})
        with self.assertRaises(BudgetExhausted):
            limits.admit("POST", {"max_tokens": 16})
