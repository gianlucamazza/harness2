import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from harness2 import config
from scripts.contact.verify_results import verify_bundle


class ReleasedResultTests(unittest.TestCase):
    def test_real_bundle_independently_reproduces_negative_result(self):
        result = verify_bundle(config.ROOT / "docs/evals/contact-pilot-2026-10-20", config.ROOT)
        self.assertEqual(result["physical_executions"], 276)
        self.assertEqual(result["heldout_base_correct"], 36)
        self.assertEqual(result["heldout_frozen_correct"], 28)
        self.assertEqual(result["non_extraction_requests_unchanged"], 84)

    def test_self_consistent_hashes_do_not_hide_a_false_quality_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bundle"
            shutil.copytree(config.ROOT / "docs/evals/contact-pilot-2026-10-20", bundle)
            quality = json.loads((bundle / "quality.json").read_text())
            row = next(
                r
                for r in quality["heldout"]["rows"]
                if r["arm"] == "frozen" and not r["exact_record"]
            )
            row["exact_record"] = True
            quality["heldout"]["arms"]["frozen"]["exact_records"] += 1
            (bundle / "quality.json").write_text(json.dumps(quality))
            checks = json.loads((bundle / "SHA256SUMS.json").read_text())
            checks["quality.json"] = hashlib.sha256(
                (bundle / "quality.json").read_bytes()
            ).hexdigest()
            (bundle / "SHA256SUMS.json").write_text(json.dumps(checks))
            with self.assertRaises(AssertionError):
                verify_bundle(bundle, config.ROOT)
