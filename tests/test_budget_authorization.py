import json
import tempfile
import unittest
from pathlib import Path

from harness2.runtime_budget import DollarBudget, authorize_ten_dollar_cap


class AuthorizationTests(unittest.TestCase):
    def test_increase_requires_preserved_authorization_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            budget = DollarBudget(root)
            budget.reserve({"model": "deepseek-flash", "max_tokens": 160})
            before = (root / "dollar-budget.json").read_bytes()
            with self.assertRaises(ValueError):
                DollarBudget(root, 10)
            authorization = authorize_ten_dollar_cap(root)
            self.assertEqual((root / authorization["audit_file"]).read_bytes(), before)
            self.assertEqual(authorize_ten_dollar_cap(root), authorization)
            current = json.loads((root / "dollar-budget.json").read_text())
            self.assertEqual(current["requests"], json.loads(before)["requests"])
            self.assertEqual(current["limit_micro_usd"], 10_000_000)
            DollarBudget(root).reserve({"model": "deepseek-flash", "max_tokens": 160})
            (root / authorization["audit_file"]).write_text("{}")
            with self.assertRaises(ValueError):
                DollarBudget(root, 10)

    def test_old_receipts_cannot_be_modified_after_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            DollarBudget(root).reserve({"model": "deepseek-flash", "max_tokens": 160})
            authorize_ten_dollar_cap(root)
            path = root / "dollar-budget.json"
            data = json.loads(path.read_text())
            data["requests"][0]["request_sha256"] = "changed"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "Historical receipts"):
                DollarBudget(root).reserve({"model": "deepseek-flash", "max_tokens": 160})
