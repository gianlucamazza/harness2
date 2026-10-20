"""Prepare, canary, or optimize the isolated contact extraction experiment."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
from pathlib import Path

from .. import config
from ..benchmarks.agent_runtime import AgentRuntimeAdapter, atomic_json, digest, load_inputs
from ..core.proposer import Proposer, ProposerError
from ..core.schedule import Namespace, run_domain
from ..runtime_budget import gateway

PROTOCOL = config.ROOT / "experiments/contact/protocol-v2.json"


class BoundedProposer(Proposer):
    def __init__(self, *args, gateway_url, gateway_token, campaign, **kwargs):
        super().__init__(*args, **kwargs)
        self.gateway_url = gateway_url
        self.gateway_token = gateway_token
        self.campaign = campaign

    def env(self):
        env = {
            k: os.environ[k]
            for k in ("HOME", "PATH", "LANG", "SSL_CERT_FILE", "SSL_CERT_DIR")
            if k in os.environ
        }
        env["DEEPSEEK_API_KEY"] = self.gateway_token
        env["OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX"] = "2048"
        sdk = config.DEPENDENCIES / "deepseek-sdk/node_modules/@ai-sdk/deepseek/dist/index.js"
        if not sdk.is_file():
            raise ValueError("Run python scripts/setup_contact_provider.py before optimization")
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps(
            {
                "agent": {
                    "build": {
                        "temperature": 0.0,
                        "prompt": (
                            "You optimize a single instruction artifact offline. Follow MISSION.md. "
                            "You have only eight model turns, including reading the mission. "
                            "Batch evidence inspection into one or two tool calls. "
                            "Do not spend turns inspecting configuration or directory metadata. "
                            "Only edit context/harness/systemprompt.md and output/answer.md. "
                            "Write the requested complete response to output/answer.md in the SAME "
                            "tool call as any instruction edit, by turn five at the latest. "
                            "If no edit is warranted, still write the requested response. "
                            "A file edit alone is not a completed mission. Finish with that response."
                        ),
                    }
                },
                "provider": {
                    "deepseek": {
                        "npm": sdk.as_uri(),
                        "options": {
                            "baseURL": self.gateway_url + "/v1",
                            "apiKey": "{env:DEEPSEEK_API_KEY}",
                        },
                        "models": {
                            "deepseek-flash": {
                                "name": "DeepSeek Flash experiment",
                                "limit": {"context": 1048576, "output": 2048},
                                "tool_call": True,
                            }
                        },
                    }
                },
            }
        )
        return env

    def call(self, *args, **kwargs):
        path = self.campaign / "optimizer-sessions.json"
        with (self.campaign / "optimizer-sessions.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = json.loads(path.read_text()) if path.exists() else {"reserved": 0}
            if data["reserved"] >= 64:
                raise ProposerError("Optimizer session budget exhausted")
            data["reserved"] += 1
            atomic_json(path, data)
        kwargs["max_attempts"] = 1
        return super().call(*args, **kwargs)


def require_preregistered():
    rel = str(PROTOCOL.relative_to(config.ROOT))
    committed = subprocess.check_output(["git", "-C", str(config.ROOT), "show", f"HEAD:{rel}"])
    if committed != PROTOCOL.read_bytes():
        raise ValueError("Commit the protocol separately before experimental inference")
    protocol = json.loads(committed)
    if protocol["monetary_cap_usd"] != 5 or protocol["k"] != 1:
        raise ValueError("Protocol differs from the accepted campaign")
    return protocol


def require_vm():
    result = subprocess.run(["systemd-detect-virt", "--vm"], capture_output=True, text=True)
    if result.returncode:
        raise ValueError("Optimization requires the dedicated VM specified in ADR-0001")


def frozen_instruction(adapter, task_id):
    task_dir = Namespace("contact", "ar", "agg", 1).task_dir(adapter.spec.runs_root, task_id)
    summary = json.loads((task_dir / "summary.json").read_text())
    if summary["status"] != "ok":
        raise ValueError("Final development task was not successful; cannot freeze")
    selected = summary["selections"]["agg"]["chosen_label"]
    path = task_dir / "harnesses" / selected / "systemprompt.md"
    text = path.read_text()
    adapter.validate_tree({"systemprompt.md": text})
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "canary", "optimize", "baseline", "evaluate"))
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inputs", type=Path)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if args.command == "canary":
        cases = [
            {
                "id": "canary",
                "cluster": "canary",
                "input": {
                    "text": "Name: Casey Canary. Email: casey.canary@example.com. Phone: +1-202-555-0198."
                },
            }
        ]
    elif args.inputs is not None:
        cases = load_inputs(args.inputs)
    else:
        parser.error("--inputs is required except for canary")
    output.mkdir(parents=True, exist_ok=True)
    if args.command == "plan":
        print(
            json.dumps(
                {
                    "protocol": json.loads(PROTOCOL.read_text()),
                    "input_count": len(cases),
                    "inputs_sha256": digest(cases),
                    "runtime": str(args.runtime.resolve()),
                    "launches_models": False,
                },
                indent=2,
            )
        )
        return 0
    protocol = require_preregistered()
    if args.command != "canary":
        require_vm()
    if args.command in ("optimize", "baseline"):
        if len(cases) != protocol["dev_cases"]:
            raise ValueError("Development case count differs from the protocol")
        pinned = config.ROOT / "experiments/contact/dev-inputs.json"
        if cases != load_inputs(pinned):
            raise ValueError("Development inputs differ from preregistration")
    if args.command == "evaluate" and len(cases) != protocol["heldout_cases"]:
        raise ValueError("Held-out case count differs from the protocol")
    key = config.require("DEEPSEEK_API_KEY", needed_by="hosted experiment")
    with gateway(output, key, limit_usd=5) as (url, token):
        adapter = AgentRuntimeAdapter(
            output / args.command, args.runtime, cases, base_url=url, api_key=token
        )
        if args.command == "canary":
            run = adapter.execute("canary", None, "canary")
            print(json.dumps({"run_dir": str(run), "delivered": adapter.delivered(run)}))
            return 0 if adapter.delivered(run) else 1
        if args.command == "optimize":
            prop = BoundedProposer(
                adapter.spec.channels["proposer"],
                audit_dir=output / "optimizer-audit",
                attempts=1,
                gateway_url=url,
                gateway_token=token,
                campaign=output,
            )
            result = run_domain(
                "contact",
                adapter.tasks(),
                1,
                adapter=adapter,
                prop=prop,
                runs_root=adapter.spec.runs_root,
                library_root=adapter.root / "library",
                modes=("agg",),
                stop_on_fallback=True,
            )
            atomic_json(output / "optimization.json", result)
            fallbacks = []
            for task in adapter.tasks():
                path = (
                    Namespace("contact", "ar", "agg", 1).task_dir(adapter.spec.runs_root, task)
                    / "summary.json"
                )
                if path.exists():
                    row = json.loads(path.read_text())
                    fallbacks += row.get("modes", {}).get("agg", {}).get("fell_back", [])
            budget = json.loads((output / "dollar-budget.json").read_text())
            if result["failed"] or fallbacks or budget.get("exhausted"):
                atomic_json(
                    output / "campaign-incomplete.json",
                    {
                        "failed_tasks": result["failed"],
                        "fallback_stages": fallbacks,
                        "budget_exhausted": budget.get("exhausted", False),
                    },
                )
                return 1
            instruction = frozen_instruction(adapter, adapter.tasks()[-1])
            frozen = output / "frozen"
            frozen.mkdir(exist_ok=True)
            (frozen / "systemprompt.md").write_text(instruction)
            atomic_json(
                frozen / "identity.json",
                {
                    "instruction_sha256": hashlib.sha256(instruction.encode()).hexdigest(),
                    "development_inputs_sha256": digest(cases),
                    "protocol_sha256": hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
                },
            )
            return 0
        if args.command == "baseline":
            rows = []
            for task in adapter.tasks():
                samples = [adapter.execute(task, None, f"matched/{task}/{i}") for i in range(4)]
                candidates = [
                    (adapter.deliverable_text(p), i, p)
                    for i, p in enumerate(samples)
                    if adapter.delivered(p)
                ]
                if not candidates:
                    rows.append({"task": task, "selected": None})
                    continue
                counts = {text: sum(c[0] == text for c in candidates) for text, _, _ in candidates}
                chosen = min(candidates, key=lambda c: (-counts[c[0]], c[0], c[1]))
                rows.append(
                    {"task": task, "selected": str(chosen[2]), "samples": [str(p) for p in samples]}
                )
            atomic_json(output / "matched-baseline.json", rows)
            return 0
        frozen = output / "frozen"
        identity = json.loads((frozen / "identity.json").read_text())
        text = (frozen / "systemprompt.md").read_text()
        if hashlib.sha256(text.encode()).hexdigest() != identity["instruction_sha256"]:
            raise ValueError("Frozen instruction changed")
        dev = load_inputs(config.ROOT / "experiments/contact/dev-inputs.json")
        dev_texts = {c["input"]["text"] for c in dev}
        if any(c["input"]["text"] in dev_texts or c["id"] in {d["id"] for d in dev} for c in cases):
            raise ValueError("Held-out inputs overlap development inputs")
        rows = []
        for task in adapter.tasks():
            for arm, harness in (("base", None), ("frozen", frozen)):
                # Identity JSON is outside the editable tree.
                candidate = None
                if harness:
                    candidate = adapter.root / "frozen-instruction"
                    candidate.mkdir(exist_ok=True)
                    (candidate / "systemprompt.md").write_text(text)
                run = adapter.execute(task, candidate, f"heldout/{task}/{arm}")
                rows.append({"task": task, "arm": arm, "run_dir": str(run)})
            base_run = next(
                Path(r["run_dir"]) for r in rows if r["task"] == task and r["arm"] == "base"
            )
            samples = [base_run] + [
                adapter.execute(task, None, f"heldout/{task}/repeat{i}") for i in range(1, 4)
            ]
            candidates = [
                (adapter.deliverable_text(p), i, p)
                for i, p in enumerate(samples)
                if adapter.delivered(p)
            ]
            counts = {t: sum(c[0] == t for c in candidates) for t, _, _ in candidates}
            selected = (
                min(candidates, key=lambda c: (-counts[c[0]], c[0], c[1]))[2]
                if candidates
                else samples[0]
            )
            rows.append(
                {
                    "task": task,
                    "arm": "matched",
                    "run_dir": str(selected),
                    "samples": [str(p) for p in samples],
                }
            )
        atomic_json(output / "heldout-executions.json", rows)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
