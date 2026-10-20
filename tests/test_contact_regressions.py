"""Independent expected values catch facts that structural eligibility cannot."""

import importlib.util
import json
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "scripts/contact/check_regressions.py"
SPEC = importlib.util.spec_from_file_location("contact_regression_checker", PATH)
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class RegressionTests(unittest.TestCase):
    def rows(self):
        inputs, gold = CHECKER.load_fixtures()
        self.assertEqual(len(inputs), 44)
        self.assertEqual(sum(c["cluster"] == "ambiguity" for c in inputs), 13)
        return [
            {
                "task": c["id"],
                "result": {"status": "completed", "result": gold[c["id"]]},
                "attempts": [{"text": json.dumps(gold[c["id"]])}],
            }
            for c in inputs
        ]

    def test_oracle_detects_wrong_contact_arrays_extra_keys_and_invention(self):
        rows = self.rows()
        self.assertEqual(CHECKER.grade(rows)["exact"], 44)
        by_id = {r["task"]: r for r in rows}
        for ident, actual in (
            (
                "edge-primary-second",
                {"name": "Noor Ash", "email": "noor.ash@example.net", "phone": None},
            ),
            ("edge-no-primary", []),
            ("edge-empty-details", {"name": None, "email": None, "phone": None, "extra": "bad"}),
            ("edge-source-invent", {"name": "Emil Vale", "email": None, "phone": "+1-555-9999"}),
        ):
            by_id[ident]["result"]["result"] = actual
            by_id[ident]["attempts"][0]["text"] = json.dumps(actual)
        report = CHECKER.grade(rows)
        self.assertEqual(report["exact"], 40)
        self.assertEqual(report["first_object_structure"], 42)

    def test_missing_duplicate_and_rejected_cases_cannot_pass(self):
        rows = self.rows()
        for changed in (rows[:-1], rows + [rows[0]]):
            with self.assertRaises(ValueError):
                CHECKER.grade(changed)
        rows[0]["result"]["status"] = "rejected"
        self.assertEqual(CHECKER.grade(rows)["exact"], 43)
