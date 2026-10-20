import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from harness2 import config
from harness2.contact_metrics import grade_run, raw_schema_valid


class ProtocolTests(unittest.TestCase):
    def test_preregistered_protocol_and_public_inputs(self):
        root = config.ROOT / "experiments/contact"
        protocol = json.loads((root / "protocol.json").read_text())
        inputs = json.loads((root / "dev-inputs.json").read_text())
        self.assertEqual(protocol["k"], 1)
        self.assertEqual(protocol["monetary_cap_usd"], 5)
        self.assertEqual(protocol["max_contract_attempts"], 2)
        self.assertEqual(protocol["heldout_cases"], 36)
        self.assertEqual(len(inputs), protocol["dev_cases"])
        self.assertEqual(
            hashlib.sha256((root / "dev-inputs.json").read_bytes()).hexdigest(),
            protocol["dev_inputs_sha256"],
        )
        for case in inputs:
            self.assertEqual(set(case), {"id", "input", "cluster"})
        self.assertEqual(
            {c: sum(i["cluster"] == c for i in inputs) for c in {i["cluster"] for i in inputs}},
            {"complete": 3, "missing": 3, "ambiguity": 3, "injection": 3},
        )

    def test_valid_json_does_not_imply_correct_facts(self):
        invented = '{"name":"Invented Person","email":"fake@example.com","phone":null}'
        self.assertTrue(raw_schema_valid(invented))
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            (directory / "runtime").mkdir()
            (directory / "runtime/result.json").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "result": json.loads(invented),
                    }
                )
            )
            (directory / "runtime/attempts.json").write_text(json.dumps([{"text": invented}]))
            row = grade_run(directory, {"name": None, "email": None, "phone": None})
            self.assertFalse(row["exact_record"])
            self.assertEqual(row["unsupported_non_null"], 2)
            self.assertTrue(row["first_schema_valid"])

    def test_rejected_empty_result_is_not_a_correct_all_null_answer(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            (directory / "runtime").mkdir()
            (directory / "runtime/result.json").write_text(
                json.dumps({"status": "rejected", "result": None})
            )
            (directory / "runtime/attempts.json").write_text('[{"text":"{}"},{"text":"{}"}]')
            row = grade_run(directory, {"name": None, "email": None, "phone": None})
            self.assertFalse(row["exact_record"])
            self.assertFalse(row["first_schema_valid"])
            self.assertEqual(row["correct_nulls"], 0)


if __name__ == "__main__":
    unittest.main()
