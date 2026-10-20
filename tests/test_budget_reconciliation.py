import concurrent.futures
import json
import tempfile
import unittest
from pathlib import Path

from harness2.runtime_budget import DollarBudget

PAYLOAD = {"model": "deepseek-flash", "max_tokens": 160}
USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


class ReconciliationTests(unittest.TestCase):
    def test_completed_usage_and_duplicate_are_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            budget = DollarBudget(root)
            receipt = budget.reserve(PAYLOAD)
            body = json.dumps({"usage": USAGE}).encode()
            budget.complete(receipt, 200, body, "application/json")
            budget.complete(receipt, 200, body, "application/json")
            self.assertEqual(
                json.loads((root / "dollar-budget.json").read_text())["reserved_micro_usd"], 18
            )
            with self.assertRaises(ValueError):
                budget.complete(receipt, 500, b"{}", "application/json")
            with self.assertRaises(Exception):
                budget.reserve(PAYLOAD)

    def test_unknown_and_invalid_usage_keep_full_liability(self):
        for status, usage in [
            (500, USAGE),
            (200, None),
            (200, {**USAGE, "total_tokens": 99}),
            (200, {**USAGE, "prompt_tokens": True}),
        ]:
            with (
                self.subTest(status=status, usage=usage),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                budget = DollarBudget(root)
                receipt = budget.reserve(PAYLOAD)
                before = (root / "dollar-budget.json").read_text()
                budget.complete(
                    receipt, status, json.dumps({"usage": usage}).encode(), "application/json"
                )
                after = json.loads((root / "dollar-budget.json").read_text())
                self.assertEqual(
                    after["reserved_micro_usd"], json.loads(before)["reserved_micro_usd"]
                )

    def test_bound_violation_blocks_future_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            budget = DollarBudget(Path(directory))
            receipt = budget.reserve(PAYLOAD)
            with self.assertRaises(ValueError):
                budget.complete(
                    receipt,
                    200,
                    json.dumps(
                        {"usage": {**USAGE, "completion_tokens": 161, "total_tokens": 171}}
                    ).encode(),
                    "application/json",
                )
            with self.assertRaises(ValueError):
                budget.reserve(PAYLOAD)

    def test_concurrent_requests_preserve_unknown_liabilities(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            budget = DollarBudget(root)

            def run(index):
                receipt = budget.reserve(PAYLOAD)
                if index % 2:
                    budget.complete(
                        receipt, 200, json.dumps({"usage": USAGE}).encode(), "application/json"
                    )

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(run, range(32)))
            data = json.loads((root / "dollar-budget.json").read_text())
            self.assertEqual(len(data["requests"]), 32)
            self.assertEqual(
                data["reserved_micro_usd"], sum(r["retained_micro_usd"] for r in data["requests"])
            )
            self.assertEqual(sum("http_status" not in r for r in data["requests"]), 16)

    def test_legacy_migration_preserves_audit_and_totals(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            budget = DollarBudget(root)
            budget.reserve(PAYLOAD)
            data = json.loads((root / "dollar-budget.json").read_text())
            del data["accounting_version"]
            row = data["requests"][0]
            del row["retained_micro_usd"]
            row.update(http_status=200, usage=USAGE)
            original = json.dumps(data).encode()
            (root / "dollar-budget.json").write_bytes(original)
            budget.reserve(PAYLOAD)
            self.assertEqual(next(root.glob("accounting-v1-*.json")).read_bytes(), original)
            migrated = json.loads((root / "dollar-budget.json").read_text())
            self.assertEqual(migrated["requests"][0]["retained_micro_usd"], 18)
            migrated["reserved_micro_usd"] = 0
            (root / "dollar-budget.json").write_text(json.dumps(migrated))
            with self.assertRaises(ValueError):
                budget.reserve(PAYLOAD)
