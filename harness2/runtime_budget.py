"""A loopback-only DeepSeek gateway with durable, conservative dollar reservations."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import secrets
import threading
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from decimal import ROUND_CEILING, Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def atomic_json(path, value):
    """Commit accounting state durably before admitting another request."""
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


# Twice the published Flash peak rates on 2026-10-20 ($/million tokens).
# Unknown liabilities retain their full reservations (ADR-0003).
INPUT_MICRO_USD_PER_TOKEN = Decimal("0.6")
OUTPUT_MICRO_USD_PER_TOKEN = Decimal("2.4")


class BudgetExhausted(RuntimeError):
    pass


def authorized_limit(root: Path) -> int:
    path = root / "budget-authorization.json"
    if not path.exists():
        return 5_000_000
    record = json.loads(path.read_text())
    original = (root / record["audit_file"]).read_bytes()
    if (
        record["decision"] != "ADR-0005 accepted 2026-10-20"
        or record["prior_limit_micro_usd"] != 5_000_000
        or record["limit_micro_usd"] != 10_000_000
        or hashlib.sha256(original).hexdigest() != record["prior_ledger_sha256"]
        or json.loads(original)["limit_micro_usd"] != 5_000_000
    ):
        raise ValueError("Invalid cumulative budget authorization")
    return record["limit_micro_usd"]


def authorize_ten_dollar_cap(root: Path) -> dict:
    """Operator-only ADR-0005 migration; never called by a model request handler."""
    with (root / "dollar-budget.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = root / "dollar-budget.json"
        data = json.loads(path.read_text())
        authorization = root / "budget-authorization.json"
        if authorization.exists():
            if authorized_limit(root) != 10_000_000:
                raise ValueError("Authorization changed")
            record = json.loads(authorization.read_text())
            if data["limit_micro_usd"] == 10_000_000:
                DollarBudget(root)._load(path)
                return record
            if hashlib.sha256(path.read_bytes()).hexdigest() != record["prior_ledger_sha256"]:
                raise ValueError("Interrupted authorization no longer matches the old ledger")
        else:
            DollarBudget(root, 5)._load(path)
            data = json.loads(path.read_text())
            original = path.read_bytes()
            checksum = hashlib.sha256(original).hexdigest()
            audit_name = "budget-before-adr0005-" + checksum + ".json"
            audit = root / audit_name
            if audit.exists() and audit.read_bytes() != original:
                raise ValueError("Budget migration audit changed")
            if not audit.exists():
                with audit.open("xb") as stream:
                    stream.write(original)
                    stream.flush()
                    os.fsync(stream.fileno())
            record = {
                "decision": "ADR-0005 accepted 2026-10-20",
                "prior_limit_micro_usd": 5_000_000,
                "limit_micro_usd": 10_000_000,
                "prior_ledger_sha256": checksum,
                "audit_file": audit_name,
            }
            atomic_json(authorization, record)
        data["limit_micro_usd"] = 10_000_000
        atomic_json(path, data)
        return record


class DollarBudget:
    def __init__(self, root: Path, limit_usd: float | None = None):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        authorized = authorized_limit(root)
        self.limit = authorized if limit_usd is None else round(limit_usd * 1_000_000)
        if not 0 < self.limit <= authorized:
            raise ValueError("Requested ceiling exceeds the authorized cumulative cap")

    def _retained(self, row):
        usage = row.get("usage")
        if row.get("http_status") != 200 or not isinstance(usage, dict):
            return row["reserved_micro_usd"]
        a, b = usage.get("prompt_tokens"), usage.get("completion_tokens")
        if type(a) is not int or type(b) is not int or a < 0 or b < 0:
            return row["reserved_micro_usd"]
        if a > row["input_token_bound"] or b > row["output_token_bound"]:
            raise ValueError("Reported usage exceeds reserved token bounds")
        if type(usage.get("total_tokens")) is not int or usage["total_tokens"] != a + b:
            return row["reserved_micro_usd"]
        return int(
            (a * INPUT_MICRO_USD_PER_TOKEN + b * OUTPUT_MICRO_USD_PER_TOKEN).to_integral_value(
                rounding=ROUND_CEILING
            )
        )

    def _load(self, path):
        if not path.exists():
            return {
                "accounting_version": 2,
                "limit_micro_usd": self.limit,
                "reserved_micro_usd": 0,
                "requests": [],
            }
        original = path.read_bytes()
        data = json.loads(original)
        if data["limit_micro_usd"] != self.limit:
            raise ValueError("Budget identity changed")
        authorization = self.root / "budget-authorization.json"
        if authorization.exists():
            record = json.loads(authorization.read_text())
            prior = json.loads((self.root / record["audit_file"]).read_text())
            if data["requests"][: len(prior["requests"])] != prior["requests"]:
                raise ValueError("Historical receipts changed after authorization")
        version = data.get("accounting_version", 1)
        if version not in (1, 2):
            raise ValueError("Unknown accounting version")
        total = 0
        for index, row in enumerate(data["requests"]):
            if row["receipt"] != index:
                raise ValueError("Receipt identity changed")
            total += row["reserved_micro_usd"] if version == 1 else row["retained_micro_usd"]
        if total != data["reserved_micro_usd"] or not 0 <= total <= self.limit:
            raise ValueError("Budget total is inconsistent")
        if version == 1:
            digest = hashlib.sha256(original).hexdigest()
            audit = self.root / ("accounting-v1-" + digest + ".json")
            if audit.exists() and audit.read_bytes() != original:
                raise ValueError("Migration audit changed")
            if not audit.exists():
                with audit.open("xb") as stream:
                    stream.write(original)
                    stream.flush()
                    os.fsync(stream.fileno())
            data["migration_source_sha256"] = digest
            data["accounting_version"] = 2
            for row in data["requests"]:
                row["retained_micro_usd"] = self._retained(row)
            data["reserved_micro_usd"] = sum(r["retained_micro_usd"] for r in data["requests"])
            data["exhausted"] = False
            atomic_json(path, data)
        for row in data["requests"]:
            if row["retained_micro_usd"] != self._retained(row):
                raise ValueError("Retained liability is inconsistent")
        return data

    def reserve(self, payload: dict, *, attribution: dict | None = None) -> int:
        if payload.get("model") != "deepseek-flash":
            raise ValueError("Only the approved Flash model may use this budget")
        maximum = payload.get("max_tokens")
        if type(maximum) is not int or not 1 <= maximum <= 2048:
            raise ValueError("Explicit output limit must be 1..2048")
        if any(t.get("type") != "function" for t in payload.get("tools", [])):
            raise ValueError("Server-side tools are outside the experiment budget")
        # Byte-level tokenization: serialized request bytes bound content tokens;
        # extra allowance covers chat framing and tool-description formatting.
        byte_bound = len(json.dumps(payload, ensure_ascii=True).encode()) + 4096
        reserved = int(
            (
                byte_bound * INPUT_MICRO_USD_PER_TOKEN + maximum * OUTPUT_MICRO_USD_PER_TOKEN
            ).to_integral_value(rounding=ROUND_CEILING)
        )
        with (self.root / "dollar-budget.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = self.root / "dollar-budget.json"
            data = self._load(path)
            if data.get("blocked"):
                raise BudgetExhausted("Accounting invariant requires review")
            if data["reserved_micro_usd"] + reserved > self.limit:
                data["exhausted"] = True
                atomic_json(path, data)
                raise BudgetExhausted("Dollar reservation ceiling reached")
            data["exhausted"] = False
            data["reserved_micro_usd"] += reserved
            receipt = len(data["requests"])
            data["requests"].append(
                {
                    "receipt": receipt,
                    "reserved_micro_usd": reserved,
                    "retained_micro_usd": reserved,
                    "input_token_bound": byte_bound,
                    "output_token_bound": maximum,
                    "request_sha256": hashlib.sha256(
                        json.dumps(payload, sort_keys=True).encode()
                    ).hexdigest(),
                }
            )
            if attribution is not None:
                data["requests"][-1]["attribution"] = dict(attribution)
            atomic_json(path, data)
        return receipt

    def complete(self, receipt, status, body, content_type):
        usages = []
        try:
            if "text/event-stream" in content_type:
                for line in body.decode().splitlines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        usage = json.loads(line[6:]).get("usage")
                        if isinstance(usage, dict):
                            usages.append(usage)
            else:
                usage = json.loads(body).get("usage")
                if isinstance(usage, dict):
                    usages.append(usage)
        except (ValueError, AttributeError, UnicodeError):
            pass
        with (self.root / "dollar-budget.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = self.root / "dollar-budget.json"
            data = self._load(path)
            row = data["requests"][receipt]
            usage = usages[-1] if usages else None
            if "http_status" in row:
                if row["http_status"] == status and row["usage"] == usage:
                    return
                data["blocked"] = "Contradictory completion"
                atomic_json(path, data)
                raise ValueError(data["blocked"])
            row["http_status"] = status
            row["usage"] = usage
            before = row["retained_micro_usd"]
            try:
                row["retained_micro_usd"] = self._retained(row)
            except ValueError:
                data["blocked"] = "Reported usage exceeds reserved token bounds"
                atomic_json(path, data)
                raise
            data["reserved_micro_usd"] += row["retained_micro_usd"] - before
            data["exhausted"] = False
            atomic_json(path, data)


class RequestAttribution:
    """Caller-owned scoped credentials; model/SDK headers cannot choose attribution."""

    def __init__(self, root: Path):
        self.root = root
        self.url = None
        self._contexts = {}
        self._lock = threading.RLock()

    @contextmanager
    def scope(self, *, role, session, phase, execution=None):
        if (
            role not in ("solver", "proposer", "selector")
            or not all(isinstance(v, str) and 0 < len(v) <= 512 for v in (session, phase))
            or (execution is not None and (not isinstance(execution, str) or not execution))
        ):
            raise ValueError("Invalid caller attribution")
        if self.url is None:
            raise RuntimeError("Attribution gateway is not running")
        token = secrets.token_urlsafe(32)
        context = {
            "role": role,
            "session": session,
            "phase": phase,
            "execution": execution,
            "auxiliary_subrole": "unknown",
        }
        with self._lock:
            self._contexts[token] = context
        try:
            yield self.url, token
        finally:
            with self._lock:
                self._contexts.pop(token, None)

    def resolve(self, token):
        with self._lock:
            return dict(self._contexts[token]) if token in self._contexts else None

    @contextmanager
    def _journal(self):
        with self._lock, (self.root / "gateway-requests.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = self.root / "gateway-requests.json"
            data = json.loads(path.read_text()) if path.exists() else {"requests": []}
            yield data
            atomic_json(path, data)

    def record(self, request_id, context, method, target, receipt):
        with self._journal() as data:
            if any(r["request_id"] == request_id for r in data["requests"]):
                raise ValueError("Duplicate gateway request identity")
            data["requests"].append(
                {
                    "request_id": request_id,
                    "context": context,
                    "method": method,
                    "target": target,
                    "accounting_receipt": receipt,
                    "state": "forwarding",
                }
            )

    def finish(self, request_id, status):
        with self._journal() as data:
            row = next(r for r in data["requests"] if r["request_id"] == request_id)
            row.update(http_status=status, state="unknown" if status is None else "responded")


class RequestLimits:
    """Bound every forward, including SDK auxiliaries and model-catalog readiness."""

    def __init__(self, *, posts, gets, payload_bytes, output_tokens):
        self.posts, self.gets = posts, gets
        self.payload_bytes, self.output_tokens = payload_bytes, output_tokens
        self._lock = threading.Lock()

    def admit(self, method, payload):
        with self._lock:
            if method == "GET":
                if self.gets <= 0:
                    raise BudgetExhausted("Readiness request limit reached")
                self.gets -= 1
            else:
                if (
                    len(json.dumps(payload, ensure_ascii=True).encode()) > self.payload_bytes
                    or payload["max_tokens"] > self.output_tokens
                ):
                    raise ValueError("Preregistered payload bound exceeded")
                if self.posts <= 0:
                    raise BudgetExhausted("Request limit reached")
                self.posts -= 1


@contextmanager
def gateway(
    root: Path,
    api_key: str,
    *,
    limit_usd: float = 5.0,
    attribution: RequestAttribution | None = None,
    limits: RequestLimits | None = None,
):
    """Agents receive a temporary gateway token, never the upstream API key."""
    budget = DollarBudget(root, limit_usd)
    upstream_url = os.getenv("HARNESS2_DEEPSEEK_UPSTREAM_URL", "https://api.deepseek.com").rstrip(
        "/"
    )
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, body, content_type="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def forward(self, payload=None):
            authorization = self.headers.get("Authorization", "")
            context = (
                attribution.resolve(authorization.removeprefix("Bearer ")) if attribution else None
            )
            if (
                not authorization.startswith("Bearer ")
                or (attribution is not None and context is None)
                or (attribution is None and authorization != "Bearer " + token)
            ):
                self.respond(401, b'{"error":"unauthorized"}')
                return
            request_id = uuid.uuid4().hex
            receipt = None
            if self.command == "GET":
                if self.path not in ("/models", "/v1/models"):
                    self.respond(404, b"{}")
                    return
                target = "/v1/models"
                if limits is not None:
                    try:
                        limits.admit("GET", None)
                    except BudgetExhausted:
                        self.respond(402, b'{"error":"Readiness request limit reached"}')
                        return
            else:
                if self.path not in ("/chat/completions", "/v1/chat/completions"):
                    self.respond(404, b"{}")
                    return
                target = "/v1/chat/completions"
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 2_000_000:
                        raise ValueError("Request too large")
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict):
                        raise ValueError("JSON object required")
                    maximum = payload.pop("max_completion_tokens", payload.get("max_tokens", 2048))
                    payload["max_tokens"] = maximum
                    payload["thinking"] = {"type": "disabled"}
                    payload["temperature"] = 0.0
                    if limits is not None:
                        limits.admit("POST", payload)
                    receipt = budget.reserve(
                        payload,
                        attribution={"request_id": request_id, **context} if context else None,
                    )
                except BudgetExhausted:
                    self.respond(402, b'{"error":{"message":"Campaign dollar budget exhausted"}}')
                    return
                except (ValueError, TypeError, AttributeError):
                    self.respond(400, b'{"error":{"message":"Unbudgeted request refused"}}')
                    return
            if attribution is not None:
                attribution.record(request_id, context, self.command, target, receipt)
            try:
                req = urllib.request.Request(
                    upstream_url + target,
                    headers={
                        "Authorization": "Bearer " + api_key,
                        "Content-Type": "application/json",
                    },
                    data=json.dumps(payload).encode() if payload is not None else None,
                )
                with urllib.request.urlopen(req, timeout=120) as response:
                    # Buffer the bounded output; retain SSE format for OpenCode.
                    body = response.read()
                    content_type = response.headers.get("Content-Type", "application/json")
                    if payload is not None:
                        budget.complete(receipt, response.status, body, content_type)
                    if attribution is not None:
                        attribution.finish(request_id, response.status)
                    self.respond(response.status, body, content_type)
            except urllib.error.HTTPError as exc:
                if payload is not None:
                    budget.complete(receipt, exc.code, b"{}", "application/json")
                if attribution is not None:
                    attribution.finish(request_id, exc.code)
                self.respond(exc.code, b'{"error":{"message":"Upstream rejected request"}}')
            except (urllib.error.URLError, TimeoutError):
                if attribution is not None:
                    attribution.finish(request_id, None)
                self.respond(
                    502, b'{"error":{"message":"Upstream unavailable; reservation retained"}}'
                )

        do_GET = forward
        do_POST = forward

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    if attribution is not None:
        attribution.url = f"http://127.0.0.1:{server.server_port}"
    try:
        yield f"http://127.0.0.1:{server.server_port}", token
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        if attribution is not None:
            attribution.url = None


def main():
    import argparse
    import signal

    from . import config

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--connection", type=Path, required=True)
    args = parser.parse_args()
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    with gateway(args.root, config.require("DEEPSEEK_API_KEY", needed_by="budget gateway")) as (
        url,
        token,
    ):
        args.connection.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(args.connection, {"url": url, "token": token})
        args.connection.chmod(0o600)
        print("Budget gateway started on loopback; connection file created", flush=True)
        stopped.wait()


if __name__ == "__main__":
    main()
