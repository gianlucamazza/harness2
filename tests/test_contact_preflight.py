"""Budget bounds include failures and SDK requests; a new ledger cannot reset spend."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from harness2 import config
from harness2.contact_preflight import check_budget, check_heldout
from harness2.runtime_budget import BudgetExhausted, RequestLimits


class PreflightTests(unittest.TestCase):
    def test_heldout_requires_post_freeze_commitment_and_excludes_released_cases(self):
        cases = [{"id": "fresh-1", "input": {"text": "New synthetic input."}, "cluster": "missing"}]
        frozen = {"frozen_at": "2026-10-20T12:00:00+00:00", "instruction_sha256": "abc"}
        manifest = {
            "generated_at": "2026-10-20T12:01:00+00:00",
            "instruction_sha256": "abc",
            "inputs_sha256": hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
        }
        check_heldout(cases, [], frozen, manifest, [])
        for changed in (
            {**manifest, "generated_at": frozen["frozen_at"]},
            {**manifest, "instruction_sha256": "wrong"},
            {**manifest, "inputs_sha256": "wrong"},
            {**manifest, "expected": "gold must stay outside"},
        ):
            with self.assertRaises(ValueError):
                check_heldout(cases, [], frozen, changed, [])
        with self.assertRaisesRegex(ValueError, "released"):
            check_heldout(
                cases,
                [],
                frozen,
                manifest,
                [hashlib.sha256(cases[0]["input"]["text"].encode()).hexdigest()],
            )
        with self.assertRaisesRegex(ValueError, "development"):
            check_heldout(cases, cases, frozen, manifest, [])

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
