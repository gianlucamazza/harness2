"""Run one bounded synthetic extraction in an existing VM through a host gateway.

The upstream API key stays on the host. Only a scoped, revoked-after-use gateway
credential crosses authenticated SSH stdin. This script does not boot a VM.
"""

import argparse
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

from harness2 import config
from harness2.benchmarks.agent_runtime import AgentRuntimeAdapter, atomic_json
from harness2.cli.agent_runtime import require_preregistered
from harness2.contact_policy import ADOPTION_POLICY, assert_runtime_compatible
from harness2.contact_preflight import check_budget
from harness2.core.spec import RunView
from harness2.runtime_budget import RequestAttribution, RequestLimits, gateway

INVENTORY = """
import hashlib,json,subprocess
from pathlib import Path
from agent_runtime.contracts import get_contract
if subprocess.run(['systemd-detect-virt','--vm'],capture_output=True).returncode:
    raise RuntimeError('Dedicated VM required')
c=get_contract('extract_contact')
files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('src').rglob('*.py')}
print(json.dumps({'files':files,'schema':c.output_model.model_json_schema(),'format':c.reply_format,
                 'kernel':subprocess.check_output(['uname','-r'],text=True).strip()}))
"""
EXECUTE = """
import asyncio,json,os,sys
from pathlib import Path
from agent_runtime.experiment import execute
from agent_runtime.models import RunRequest
p=json.load(sys.stdin)
os.environ['DEEPSEEK_API_KEY']=p['token']
os.environ['DEEPSEEK_EXPERIMENT_BASE_URL']=p['url']
directory=Path(p['directory'])
asyncio.run(execute(RunRequest.model_validate(p['request']),directory,'deepseek-flash',p['catalog']))
print(json.dumps({name:json.loads((directory/(name+'.json')).read_text())
                 for name in ['result','attempts','identity']}))
"""


def source_files(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root / "src").rglob("*.py")
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--budget-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ssh-key", type=Path, required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--ssh-port", type=int, default=22982)
    parser.add_argument("--ssh-target", default="harness@127.0.0.1")
    parser.add_argument("--guest-runtime", default="/home/harness/agent-runtime")
    args = parser.parse_args()
    protocol = require_preregistered()
    preflight = check_budget(args.budget_root, protocol, "canary")
    if not preflight["fits"]:
        raise RuntimeError("Canary does not fit the existing cumulative allowance")
    if args.output.exists():
        raise ValueError("Canary output must be new; never replay an uncertain request")
    args.output.mkdir(parents=True)
    atomic_json(args.output / "preflight.json", preflight)
    ssh = [
        "ssh",
        "-i",
        str(args.ssh_key),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "UserKnownHostsFile=" + str(args.known_hosts),
        "-p",
        str(args.ssh_port),
    ]

    def remote(script, *, data=None, forward=None):
        options = ["-o", "ExitOnForwardFailure=yes", "-R", forward] if forward else []
        command = (
            "cd "
            + shlex.quote(args.guest_runtime)
            + " && .venv/bin/python -c "
            + shlex.quote(script)
        )
        result = subprocess.run(
            ssh + options + [args.ssh_target, command],
            input=json.dumps(data) if data is not None else None,
            text=True,
            capture_output=True,
            timeout=180,
        )
        if result.returncode:
            # Never echo SSH stdin or provider error bodies.
            raise RuntimeError("Isolated command failed; no automatic retry")
        return json.loads(result.stdout)

    inventory = remote(INVENTORY)
    if inventory["files"] != source_files(args.runtime):
        raise ValueError("Guest/runtime source mismatch")
    assert_runtime_compatible(inventory["schema"], inventory["format"])
    atomic_json(args.output / "runtime-source-parity.json", inventory)
    catalog = json.loads(
        (config.ROOT / "docs/evals/contact-pilot-2026-10-20/provenance.json").read_text()
    )["catalog"]

    class IsolatedAdapter(AgentRuntimeAdapter):
        def _launch(self, directory, timeout):
            env = self._runtime_env()
            url = env["DEEPSEEK_EXPERIMENT_BASE_URL"]
            port = int(url.rsplit(":", 1)[1])
            payload = remote(
                EXECUTE,
                data={
                    "request": json.loads((directory / "request.json").read_text()),
                    "url": url,
                    "token": env["DEEPSEEK_API_KEY"],
                    "catalog": catalog,
                    "directory": "runs/contact-followup-canary/" + directory.name,
                },
                forward=f"127.0.0.1:{port}:127.0.0.1:{port}",
            )
            (directory / "runtime").mkdir()
            for name, value in payload.items():
                atomic_json(directory / "runtime" / (name + ".json"), value)
            return subprocess.CompletedProcess(
                [], 0 if payload["result"]["status"] == "completed" else 1
            )

    attribution = RequestAttribution(args.budget_root)
    with gateway(
        args.budget_root,
        config.require("DEEPSEEK_API_KEY", needed_by="isolated canary"),
        attribution=attribution,
        limits=RequestLimits(**preflight["limits"]),
    ) as (url, token):
        adapter = IsolatedAdapter(
            args.output / "campaign",
            args.runtime,
            [
                {
                    "id": "followup-canary",
                    "cluster": "canary",
                    "input": {
                        "text": "Name: Casey Canary. Email: casey.canary@example.com. Phone: +1-202-555-0198."
                    },
                }
            ],
            adoption_policy=ADOPTION_POLICY,
            request_context=attribution.scope,
            base_url=url,
            api_key=token,
        )
        directory = adapter.execute("followup-canary", None, "followup-canary")
        rv = RunView(
            label="canary",
            run_id="followup-canary",
            run_dir=directory,
            ok=True,
            delivered=adapter.delivered(directory),
        )
        eligible = bool(adapter.adoption_pool({"canary": rv}, [], work_dir=args.output))
        result = json.loads((directory / "runtime/result.json").read_text())
        exact = result.get("result") == {
            "name": "Casey Canary",
            "email": "casey.canary@example.com",
            "phone": "+1-202-555-0198",
        }
    after = remote(INVENTORY)
    if after != inventory:
        raise ValueError("Guest runtime or kernel changed during the canary")
    summary = {
        "eligible": eligible,
        "exact": exact,
        "source_parity": True,
        "catalog_unchanged": True,
        "gateway_stopped": True,
        "ledger": check_budget(args.budget_root, protocol, "canary"),
    }
    atomic_json(args.output / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if eligible and exact else 1


if __name__ == "__main__":
    raise SystemExit(main())
