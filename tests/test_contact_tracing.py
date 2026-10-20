"""Real local HTTP attribution checks; no paid inference."""

import http.client
import json
import tempfile
import unittest
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

from harness2 import config
from harness2.cli.agent_runtime import BoundedProposer
from harness2.core.proposer import Proposer, Reply
from harness2.core.spec import ChannelSpec
from harness2.runtime_budget import RequestAttribution, gateway


def request(url, token, method="POST"):
    address = urllib.parse.urlsplit(url)
    client = http.client.HTTPConnection(address.hostname, address.port)
    path = "/v1/models" if method == "GET" else "/v1/chat/completions"
    body = None if method == "GET" else json.dumps({"model": "deepseek-flash", "max_tokens": 16})
    client.request(
        method,
        path,
        body=body,
        headers={"Authorization": "Bearer " + token, "X-Session": "model-controlled-value"},
    )
    response = client.getresponse()
    response.read()
    client.close()
    return response.status


class TracingTests(unittest.TestCase):
    def test_proposer_environment_uses_scoped_credentials_for_sdk_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / "deepseek-sdk/node_modules/@ai-sdk/deepseek/dist/index.js"
            sdk.parent.mkdir(parents=True)
            sdk.touch()
            attribution = RequestAttribution(root)
            with gateway(root, "upstream", attribution=attribution) as (url, token):
                prop = BoundedProposer(
                    ChannelSpec("opencode", "deepseek/deepseek-flash"),
                    gateway_url=url,
                    gateway_token=token,
                    campaign=root,
                    request_context=attribution.scope,
                )

                def sdk_call(*args, **kwargs):
                    env = prop.env()
                    self.assertNotEqual(env["DEEPSEEK_API_KEY"], token)
                    self.assertEqual(request(url, env["DEEPSEEK_API_KEY"]), 200)
                    return Reply(label="inv1", text="<notes>done</notes>", ok=True)

                with (
                    patch.object(config, "DEPENDENCIES", root),
                    patch.object(Proposer, "call", side_effect=sdk_call),
                    patch(
                        "harness2.runtime_budget.urllib.request.urlopen",
                        return_value=self.response(),
                    ),
                ):
                    prop.call("mission", root / "context", "inv1")
            row = json.loads((root / "dollar-budget.json").read_text())["requests"][0]
            self.assertEqual(row["attribution"]["phase"], "inv1")
            self.assertEqual(row["attribution"]["role"], "proposer")

    def test_multiple_registry_instances_do_not_lose_journal_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registries = [RequestAttribution(root), RequestAttribution(root)]

            def write(i):
                registry = registries[i % 2]
                registry.record(str(i), {"session": str(i)}, "GET", "/v1/models", None)
                registry.finish(str(i), 200)

            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(write, range(20)))
            rows = json.loads((root / "gateway-requests.json").read_text())["requests"]
            self.assertEqual(len(rows), 20)
            self.assertEqual({r["request_id"] for r in rows}, {str(i) for i in range(20)})
            self.assertTrue(all(r["state"] == "responded" for r in rows))

    def response(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.headers = {"Content-Type": "application/json"}
        response.read.return_value = (
            b'{"usage":{"prompt_tokens":10,"completion_tokens":1,"total_tokens":11}}'
        )
        return response

    def test_concurrent_scopes_auxiliary_readiness_and_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attribution = RequestAttribution(root)
            with gateway(root, "real-upstream-secret", attribution=attribution) as (url, master):
                with patch(
                    "harness2.runtime_budget.urllib.request.urlopen", return_value=self.response()
                ) as upstream:
                    self.assertEqual(request(url, master), 401)

                    def session(role):
                        with attribution.scope(
                            role=role, session=role + "-session", phase="probe"
                        ) as (scoped_url, token):
                            self.assertEqual(request(scoped_url, token, "GET"), 200)
                            self.assertEqual(request(scoped_url, token), 200)
                            self.assertEqual(request(scoped_url, token), 200)
                        self.assertEqual(request(scoped_url, token), 401)

                    with ThreadPoolExecutor(max_workers=2) as pool:
                        list(pool.map(session, ("proposer", "solver")))
                    self.assertEqual(upstream.call_count, 6)
                    for call in upstream.call_args_list:
                        headers = dict(call.args[0].header_items())
                        self.assertEqual(headers["Authorization"], "Bearer real-upstream-secret")
                        self.assertNotIn("X-session", headers)
                        self.assertNotIn("session", str(headers).lower())
            traces = json.loads((root / "gateway-requests.json").read_text())["requests"]
            ledger = json.loads((root / "dollar-budget.json").read_text())["requests"]
            self.assertEqual(len(traces), 6)
            self.assertEqual(len({r["request_id"] for r in traces}), 6)
            self.assertEqual(len(ledger), 4)
            by_id = {r["request_id"]: r for r in traces}
            for receipt in ledger:
                context = receipt["attribution"]
                trace = by_id[context["request_id"]]
                self.assertEqual(trace["accounting_receipt"], receipt["receipt"])
                self.assertEqual(trace["context"]["session"], context["role"] + "-session")
                self.assertEqual(context["auxiliary_subrole"], "unknown")
            for file in (root / "gateway-requests.json", root / "dollar-budget.json"):
                self.assertNotIn("real-upstream-secret", file.read_text())

    def test_unknown_outcomes_retain_liability_and_retries_have_new_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attribution = RequestAttribution(root)
            with gateway(root, "secret", attribution=attribution):
                with attribution.scope(
                    role="solver", session="one", phase="canary", execution="run-1"
                ) as (url, token):
                    with patch(
                        "harness2.runtime_budget.urllib.request.urlopen",
                        side_effect=urllib.error.URLError("lost connection"),
                    ):
                        self.assertEqual(request(url, token), 502)
                    with patch(
                        "harness2.runtime_budget.urllib.request.urlopen",
                        return_value=self.response(),
                    ):
                        self.assertEqual(request(url, token), 200)
            traces = json.loads((root / "gateway-requests.json").read_text())["requests"]
            receipts = json.loads((root / "dollar-budget.json").read_text())["requests"]
            self.assertEqual([r["state"] for r in traces], ["unknown", "responded"])
            self.assertEqual(len({r["request_id"] for r in traces}), 2)
            self.assertEqual(receipts[0]["retained_micro_usd"], receipts[0]["reserved_micro_usd"])
            self.assertEqual(receipts[1]["attribution"]["execution"], "run-1")

    def test_invalid_context_fails_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            attribution = RequestAttribution(Path(directory))
            with gateway(Path(directory), "secret", attribution=attribution) as (url, _):
                with patch("harness2.runtime_budget.urllib.request.urlopen") as upstream:
                    self.assertEqual(request(url, "unregistered"), 401)
                    with self.assertRaises(ValueError):
                        with attribution.scope(role="invented", session="s", phase="p"):
                            pass
                    upstream.assert_not_called()
