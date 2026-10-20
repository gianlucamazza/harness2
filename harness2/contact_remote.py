"""Trusted host orchestration with scoped model execution over authenticated SSH."""

from __future__ import annotations

import base64
import json
import shlex
import subprocess
from contextlib import contextmanager
from pathlib import Path

from .benchmarks.agent_runtime import AgentRuntimeAdapter, atomic_json
from .cli.agent_runtime import BoundedProposer
from .core.proposer import _opencode_cost, _opencode_stdout


def safe_files(directory: Path) -> dict[str, str]:
    files = {}
    total = 0
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlinks are forbidden in remote workspaces")
        if path.is_file():
            content = path.read_bytes()
            total += len(content)
            if total > 2_000_000:
                raise ValueError("Remote workspace exceeds its bound")
            files[str(path.relative_to(directory))] = base64.b64encode(content).decode()
    return files


def restore_files(directory: Path, files: dict[str, str]) -> None:
    for name, encoded in files.items():
        if name not in ("context/harness/systemprompt.md", "output/answer.md"):
            raise ValueError("Remote session returned an unsupported artifact")
        data = base64.b64decode(encoded, validate=True)
        if len(data) > 100_000:
            raise ValueError("Remote artifact exceeds its bound")
        path = directory / name
        if path.is_symlink():
            raise ValueError("Remote artifact cannot replace a symlink")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


class SSHTransport:
    def __init__(self, *, key: Path, known_hosts: Path, port=22982, target="harness@127.0.0.1"):
        self.arguments = [
            "ssh",
            "-i",
            str(key),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "UserKnownHostsFile=" + str(known_hosts),
            "-o",
            "ConnectTimeout=10",
            "-p",
            str(port),
        ]
        self.target = target

    def run(self, script, payload=None, *, timeout=210):
        result = subprocess.run(
            self.arguments
            + [
                self.target,
                "cd /home/harness && /home/harness/agent-runtime/.venv/bin/python -c "
                + shlex.quote(script),
            ],
            input=json.dumps(payload) if payload is not None else None,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        if result.returncode:
            raise RuntimeError("Remote execution failed; uncertain work is not retried")
        return json.loads(result.stdout)

    @contextmanager
    def tunnel(self, url):
        port = int(url.rsplit(":", 1)[1])
        import tempfile

        with tempfile.TemporaryDirectory(prefix="h2-ssh-") as directory:
            control = str(Path(directory) / "socket")
            command = self.arguments + [
                "-M",
                "-S",
                control,
                "-f",
                "-N",
                "-o",
                "ExitOnForwardFailure=yes",
                "-R",
                f"127.0.0.1:{port}:127.0.0.1:{port}",
                self.target,
            ]
            subprocess.run(command, check=True, capture_output=True, timeout=20)
            try:
                yield
            finally:
                subprocess.run(
                    self.arguments + ["-S", control, "-O", "exit", self.target],
                    capture_output=True,
                    timeout=15,
                    check=True,
                )


INVENTORY = r"""
import hashlib,json,subprocess,os
from pathlib import Path
from agent_runtime.contracts import get_contract
os.chdir('/home/harness/agent-runtime')
if subprocess.run(['systemd-detect-virt','--vm'],capture_output=True).returncode:
    raise RuntimeError('VM required')
c=get_contract('extract_contact')
print(json.dumps({'files':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('src').rglob('*.py')},
 'schema':c.output_model.model_json_schema(),'format':c.reply_format,
 'kernel':subprocess.check_output(['uname','-r'],text=True).strip(),
 'provider_lock_sha256':hashlib.sha256(Path('/home/harness/harness2/dependencies/deepseek-sdk/package-lock.json').read_bytes()).hexdigest(),
 'opencode_commit':subprocess.check_output(['git','-C','/home/harness/harness2/dependencies/opencode','rev-parse','HEAD'],text=True).strip()}))
"""

RUNTIME = r"""
import asyncio,hashlib,json,os,sys
from pathlib import Path
import httpx
from agent_runtime.core import Conductor
from agent_runtime.experiment import RecordedDeepSeek,atomic_json
from agent_runtime.models import RunRequest
from agent_runtime.store import RunStore
p=json.load(sys.stdin)
os.chdir('/home/harness/agent-runtime')
def sources():return {str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in Path('src').rglob('*.py')}
if sources()!=p['source_files']:raise RuntimeError('Runtime source drift')
directory=Path(p['directory']);directory.mkdir(parents=True,exist_ok=False)
async def main():
 store=RunStore(str(directory/'runs.db'))
 try:
  async with httpx.AsyncClient(timeout=60) as client:
   backend=RecordedDeepSeek(client,p['token'],'deepseek-flash',directory,base_url=p['url'])
   ready,detail=await backend.health(timeout=15)
   if not ready or backend.catalog!=p['catalog']:raise RuntimeError('Catalog mismatch')
   conductor=Conductor(backend,store,approvals=not p.get('proposal_only',False),allow_instruction_overrides=True)
   result=await conductor.run(RunRequest.model_validate(p['request']),'single-run')
   identity={'model':'deepseek-flash','catalog':backend.catalog,'temperature':0.0,'thinking':'disabled'}
   return {'result':result.model_dump(mode='json'),'attempts':backend.completions,'identity':identity}
 finally:store.close()
result=asyncio.run(main())
if sources()!=p['source_files']:raise RuntimeError('Runtime changed during execution')
for name,value in result.items():atomic_json(directory/(name+'.json'),value)
print(json.dumps(result))
"""

PROPOSER = r"""
import base64,json,os,signal,subprocess,sys,tempfile
from pathlib import Path,PurePosixPath
p=json.load(sys.stdin)
with tempfile.TemporaryDirectory(prefix='h2-campaign-session-') as temporary:
 root=Path(temporary)
 total=0
 for name,encoded in p['files'].items():
  parts=PurePosixPath(name)
  if parts.is_absolute() or '..' in parts.parts:raise ValueError('Unsafe input path')
  content=base64.b64decode(encoded,validate=True);total+=len(content)
  if total>2000000:raise ValueError('Workspace too large')
  path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
 env={'HOME':'/home/harness','PATH':'/home/harness/bin:/usr/local/bin:/usr/bin:/bin','LANG':'C.UTF-8'}
 env.update(p['env'])
 config=json.loads(env['OPENCODE_CONFIG_CONTENT'])
 config['provider']['deepseek']['npm']='file:///home/harness/harness2/dependencies/deepseek-sdk/node_modules/@ai-sdk/deepseek/dist/index.js'
 env['OPENCODE_CONFIG_CONTENT']=json.dumps(config)
 env['OPENCODE_PERMISSION']=json.dumps({'external_directory':{'*':'deny',str(root):'allow',str(root)+'/**':'allow'}})
 env['XDG_DATA_HOME']=str(root/'.ocdata');env['XDG_STATE_HOME']=str(root/'.ocstate')
 command=['/home/harness/harness2/dependencies/tools/node_modules/.bin/bun','run','--cwd','/home/harness/harness2/dependencies/opencode/packages/opencode','--conditions=browser','src/index.ts','run',
 'Read MISSION.md first. Follow it. Save the complete requested response to output/answer.md and return it as your final message.','--dir',str(root),'--model','deepseek/deepseek-flash','--format','json']
 process=subprocess.Popen(command,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
 try:stdout,stderr=process.communicate(timeout=p['timeout'])
 except subprocess.TimeoutExpired:
  os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate()
  stdout='';stderr='session timeout'
 files={}
 for name in ['context/harness/systemprompt.md','output/answer.md']:
  path=root/name
  if path.is_symlink():raise ValueError('Symlink artifact refused')
  if path.is_file():
   if path.stat().st_size>100000:raise ValueError('Artifact too large')
   files[name]=base64.b64encode(path.read_bytes()).decode()
 print(json.dumps({'files':files,'stdout':stdout,'stderr':stderr,'returncode':process.returncode}))
"""


class RemoteProposer(BoundedProposer):
    def __init__(self, *args, transport, **kwargs):
        super().__init__(*args, **kwargs)
        self.transport = transport

    def _opencode(self, cwd, mission, system, wall):
        (cwd / "MISSION.md").write_text((system + "\n\n" if system else "") + mission)
        (cwd / "output").mkdir(exist_ok=True)
        atomic_json(cwd / "opencode.json", {"agent": {"build": {"steps": self.spec.steps}}})
        env = {
            k: v
            for k, v in self.env().items()
            if k
            in (
                "DEEPSEEK_API_KEY",
                "OPENCODE_CONFIG_CONTENT",
                "OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX",
            )
        }
        result = self.transport.run(
            PROPOSER, {"files": safe_files(cwd), "env": env, "timeout": wall}, timeout=wall + 30
        )
        restore_files(cwd, result["files"])
        for name in ("stdout", "stderr"):
            result[name] = result[name].replace(env["DEEPSEEK_API_KEY"], "[REDACTED]")
        if self.audit_dir:
            audit = Path(self.audit_dir) / "provider-events"
            audit.mkdir(parents=True, exist_ok=True)
            for suffix, value in (("jsonl", result["stdout"]), ("stderr.txt", result["stderr"])):
                path = audit / (cwd.name + "." + suffix)
                path.write_text(value)
                path.chmod(0o600)
        answer = cwd / "output/answer.md"
        cost = _opencode_cost(result["stdout"])
        if answer.is_file() and answer.read_text().strip():
            return answer.read_text(), cost, ""
        text, error = _opencode_stdout(result["stdout"])
        return text, cost, error or result["stderr"][-200:]


class RemoteRuntimeAdapter(AgentRuntimeAdapter):
    def __init__(self, *args, transport, inventory, catalog, **kwargs):
        super().__init__(*args, **kwargs)
        self.transport, self.inventory, self.expected_catalog = transport, inventory, catalog

    def _launch(self, directory, timeout):
        env = self._runtime_env()
        payload = self.transport.run(
            RUNTIME,
            {
                "request": json.loads((directory / "request.json").read_text()),
                "url": env["DEEPSEEK_EXPERIMENT_BASE_URL"],
                "token": env["DEEPSEEK_API_KEY"],
                "directory": "runs/contact-v4/"
                + self.root.parent.name
                + "/"
                + self.root.name
                + "/"
                + directory.name,
                "source_files": self.inventory["files"],
                "catalog": self.expected_catalog,
            },
        )
        (directory / "runtime").mkdir()
        for name, value in payload.items():
            atomic_json(directory / "runtime" / (name + ".json"), value)
        return subprocess.CompletedProcess(
            [], 0 if payload["result"]["status"] == "completed" else 1
        )
