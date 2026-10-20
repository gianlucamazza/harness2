"""Contract visibility and real adoption-path checks with an independent fake runtime."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

import test_agent_runtime_adapter as fixtures

from harness2.benchmarks.agent_runtime import BASE_INSTRUCTION, AgentRuntimeAdapter
from harness2.contact_policy import (
    ADOPTION_POLICY,
    PUBLIC_SPEC,
    SPEC_SHA256,
    assert_runtime_compatible,
)
from harness2.core.proposer import Reply
from harness2.core.schedule import Namespace, run_domain


class ContactFollowupTests(unittest.TestCase):
    setUp = fixtures.AdapterTests.setUp

    def test_runtime_structural_drift_is_refused(self):
        from harness2 import config

        inventory = json.loads(
            (
                config.ROOT / "docs/evals/contact-followup-2026-10-20/runtime-source-parity.json"
            ).read_text()
        )
        assert_runtime_compatible(inventory["schema"], inventory["format"])
        for changed in (
            {**inventory["schema"], "additionalProperties": True},
            {**inventory["schema"], "required": ["email"]},
            {**inventory["schema"], "type": "array"},
        ):
            with self.assertRaises(ValueError):
                assert_runtime_compatible(changed, inventory["format"])

    def test_public_contract_and_resume_identity(self):
        self.assertIn(PUBLIC_SPEC, self.adapter.task_prompt("contact-1"))
        self.assertIn(PUBLIC_SPEC, self.adapter.spec.prompts.work)
        self.assertEqual(self.adapter.identity["public_spec_sha256"], SPEC_SHA256)
        self.assertEqual(
            (self.adapter.base_harness() / "systemprompt.md").read_text(), BASE_INSTRUCTION + "\n"
        )
        with self.assertRaisesRegex(ValueError, "identity changed"):
            AgentRuntimeAdapter(
                self.adapter.root, self.runtime, fixtures.CASES, adoption_policy=ADOPTION_POLICY
            )

    def launch(self, directory, timeout):
        fixtures.AdapterTests.launch(self, directory, timeout)
        runtime = directory / "runtime"
        result = json.loads((runtime / "result.json").read_text())
        attempts = [{"text": json.dumps(result["result"])}]
        edited = (
            json.loads((directory / "request.json").read_text())["instruction"] != BASE_INSTRUCTION
        )
        if (edited and self.reject_candidates) or (not edited and self.reject_base):
            attempts.insert(0, {"text": "[]"})
        (runtime / "attempts.json").write_text(json.dumps(attempts))
        import subprocess

        return subprocess.CompletedProcess([], 0)

    def exercise_adoption(self, *, reject_base=False, reject_candidates=True, modes=("agg",), k=1):
        self.adapter.adoption_policy = ADOPTION_POLICY
        self.reject_base = reject_base
        self.reject_candidates = reject_candidates

        class Editor:
            spec = self.adapter.spec.channels["proposer"]
            audit_dir = None
            attempts = 1

            def call(editor, mission, context_dir, label, **kwargs):
                if label.startswith("select."):
                    return Reply(label=label, text="```choice\nA\n```", ok=True)
                if label.startswith("experience."):
                    return Reply(label=label, text="NO_ENTRY", ok=True)
                artifact = Path(context_dir) / "harness"
                path = artifact / "systemprompt.md"
                path.write_text(path.read_text() + "\nNever invent contact details.")
                return Reply(
                    label=label,
                    text="<notes>Use explicit evidence.</notes>",
                    ok=True,
                    workspace=artifact,
                )

        with patch.object(self.adapter, "_launch", side_effect=self.launch):
            return run_domain(
                "contact",
                self.adapter.tasks(),
                k,
                adapter=self.adapter,
                prop=Editor(),
                runs_root=self.adapter.spec.runs_root,
                library_root=self.adapter.root / "library",
                modes=modes,
                stop_on_fallback=True,
            )

    def test_k1_retains_eligible_incumbent_after_candidate_repair_and_resumes(self):
        result = self.exercise_adoption()
        self.assertEqual(result["failed"], 0)
        task = Namespace("contact", "ar", "agg", 1).task_dir(
            self.adapter.spec.runs_root, "contact-1"
        )
        summary = json.loads((task / "summary.json").read_text())
        selected = summary["selections"]["agg"]
        self.assertEqual(selected["chosen_label"], "base1")

        self.assertFalse(selected["fallback"])
        self.assertTrue(selected["chosen_tree_is_base"])
        policy = json.loads((task / "adoption-eligibility.json").read_text())
        self.assertEqual(policy["outcome"], "incumbent-retained")
        self.assertFalse(policy["decisions"]["agg1"]["eligible"])
        result = self.exercise_adoption()
        self.assertEqual(result["failed"], 0)

    def test_k2_selector_cannot_choose_repaired_candidates(self):
        result = self.exercise_adoption(k=2)
        self.assertEqual(result["failed"], 0)
        task = Namespace("contact", "ar", "agg", 2).task_dir(
            self.adapter.spec.runs_root, "contact-1"
        )
        selected = json.loads((task / "summary.json").read_text())["selections"]["agg"]
        self.assertEqual(selected["chosen_label"], "base1")
        self.assertEqual(selected["id_map"], {"A": "base1"})

    def test_eligible_candidate_is_adopted_even_when_incumbent_needs_repair(self):
        result = self.exercise_adoption(reject_base=True, reject_candidates=False)
        self.assertEqual(result["failed"], 0)
        task = Namespace("contact", "ar", "agg", 1).task_dir(
            self.adapter.spec.runs_root, "contact-1"
        )
        summary = json.loads((task / "summary.json").read_text())
        self.assertEqual(summary["selections"]["agg"]["chosen_label"], "agg1")

    def test_no_eligible_instruction_fails_qualification(self):
        result = self.exercise_adoption(reject_base=True)
        self.assertEqual(result["failed"], 1)
        task = Namespace("contact", "ar", "agg", 1).task_dir(
            self.adapter.spec.runs_root, "contact-1"
        )
        policy = json.loads((task / "adoption-eligibility.json").read_text())
        self.assertEqual(policy["outcome"], "no-eligible-instruction")
        self.assertFalse(policy["qualified"])

    def test_sequential_adoption_has_same_eligibility_policy(self):
        result = self.exercise_adoption(modes=("seq",))
        self.assertEqual(result["failed"], 0)
        task = Namespace("contact", "ar", "agg", 1).task_dir(
            self.adapter.spec.runs_root, "contact-1"
        )
        selected = json.loads((task / "summary.json").read_text())["selections"]["seq"]
        self.assertEqual(selected["chosen_label"], "base1")
