"""Independent follow-up evidence verification detects forged accounting claims."""

import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "scripts/contact/verify_followup.py"
SPEC = importlib.util.spec_from_file_location("verify_contact_followup", PATH)
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class FollowupBundleTests(unittest.TestCase):
    def test_published_canary_is_exact_and_fully_attributed(self):
        result = VERIFIER.verify()
        self.assertTrue(result["exact_canary"])
        self.assertEqual(result["attributed_requests"], 2)
        self.assertFalse(result["full_followup_budget_fits"])

    def test_rehashed_false_accounting_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "evidence"
            shutil.copytree(VERIFIER.BUNDLE, bundle)
            path = bundle / "accounting.json"
            data = json.loads(path.read_text())
            data["new_requests"][0]["retained_micro_usd"] = 1
            path.write_text(json.dumps(data))
            checksums = json.loads((bundle / "SHA256SUMS.json").read_text())
            checksums["accounting.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
            (bundle / "SHA256SUMS.json").write_text(json.dumps(checksums))
            with self.assertRaises(AssertionError):
                VERIFIER.verify(bundle)
