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


class DollarBudget:
    def __init__(self, root: Path, limit_usd: float = 5.0):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.limit = round(limit_usd * 1_000_000)
        if not 0 < self.limit <= 5_000_000:
            raise ValueError("Approved campaign ceiling is 5 USD")

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

    def reserve(self, payload: dict) -> int:
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


@contextmanager
def gateway(root: Path, api_key: str, *, limit_usd: float = 5.0):
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
            if self.headers.get("Authorization") != "Bearer " + token:
                self.respond(401, b'{"error":"unauthorized"}')
                return
            if self.command == "GET":
                if self.path not in ("/models", "/v1/models"):
                    self.respond(404, b"{}")
                    return
                target = "/v1/models"
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
                    receipt = budget.reserve(payload)
                except BudgetExhausted:
                    self.respond(402, b'{"error":{"message":"Campaign dollar budget exhausted"}}')
                    return
                except (ValueError, TypeError, AttributeError):
                    self.respond(400, b'{"error":{"message":"Unbudgeted request refused"}}')
                    return
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
                    self.respond(response.status, body, content_type)
            except urllib.error.HTTPError as exc:
                if payload is not None:
                    budget.complete(receipt, exc.code, b"{}", "application/json")
                self.respond(exc.code, b'{"error":{"message":"Upstream rejected request"}}')
            except (urllib.error.URLError, TimeoutError):
                self.respond(
                    502, b'{"error":{"message":"Upstream unavailable; reservation retained"}}'
                )

        do_GET = forward
        do_POST = forward

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", token
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


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
