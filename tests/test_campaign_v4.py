import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness2 import contact_campaign

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "docs/evals/contact-campaign-v4-2026-10-20"
spec = importlib.util.spec_from_file_location(
    "verify_v4", ROOT / "scripts/contact/verify_campaign_v4.py"
)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class CampaignTests(unittest.TestCase):
    def test_published_evidence_recomputes_scores_and_receipts(self):
        result = verifier.verify_bundle(BUNDLE)
        self.assertEqual(result["heldout_exact"], {"base": 35, "frozen": 36, "matched": 35})
        self.assertEqual(result["new_paid_requests"], 885)

    def test_completed_output_is_never_modified_on_replay_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "completed"
            output.mkdir()
            marker = output / "complete.json"
            marker.write_text('{"status":"completed"}\n')
            before = marker.read_bytes()
            with patch.object(contact_campaign, "SSHTransport") as ssh:
                with self.assertRaisesRegex(ValueError, "must be new"):
                    contact_campaign.main(
                        [
                            "--runtime",
                            directory,
                            "--budget-root",
                            directory,
                            "--output",
                            str(output),
                        ]
                    )
                ssh.assert_not_called()
            self.assertEqual(marker.read_bytes(), before)
            self.assertEqual(list(output.iterdir()), [marker])

    def test_plan_has_no_transport_or_output_side_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "unused"
            with (
                patch.object(contact_campaign, "SSHTransport") as ssh,
                contextlib.redirect_stdout(io.StringIO()) as out,
            ):
                contact_campaign.main(
                    [
                        "--plan",
                        "--runtime",
                        directory,
                        "--budget-root",
                        str(BUNDLE),
                        "--output",
                        str(output),
                    ]
                )
                ssh.assert_not_called()
            self.assertFalse(json.loads(out.getvalue())["launches_models"])
            self.assertFalse(output.exists())

    def test_newly_published_inputs_are_excluded_from_future_cohorts(self):
        released = set(
            json.loads((ROOT / "experiments/contact/released-input-hashes.json").read_text())
        )
        for case in json.loads((BUNDLE / "heldout-inputs.json").read_text()):
            self.assertIn(hashlib.sha256(case["input"]["text"].encode()).hexdigest(), released)

    def test_rehashed_false_score_is_rejected_by_independent_oracle(self):
        import shutil

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "bundle"
            shutil.copytree(BUNDLE, target)
            quality = target / "quality.json"
            data = json.loads(quality.read_text())
            data["heldout"]["base"]["exact_records"] = 36
            quality.write_text(json.dumps(data, indent=2) + "\n")
            sums = target / "SHA256SUMS.json"
            checksums = json.loads(sums.read_text())
            checksums["quality.json"] = hashlib.sha256(quality.read_bytes()).hexdigest()
            sums.write_text(json.dumps(checksums))
            with self.assertRaises(AssertionError):
                verifier.verify_bundle(target)
