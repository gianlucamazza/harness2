import http.client
import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from harness2.core.proposer import Proposer, ProposerError
from harness2.core.spec import ChannelSpec
from harness2.runtime_budget import gateway


class ProviderEvidenceTests(unittest.TestCase):
    def test_gateway_enforces_registered_sampling(self):
        with tempfile.TemporaryDirectory() as directory:
            response = MagicMock()
            response.__enter__.return_value = response
            response.status = 200
            response.headers = {"Content-Type": "application/json"}
            response.read.return_value = json.dumps(
                {"usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}}
            ).encode()
            with gateway(Path(directory), "upstream-key") as (url, token):
                address = urllib.parse.urlsplit(url)
                with patch(
                    "harness2.runtime_budget.urllib.request.urlopen", return_value=response
                ) as upstream:
                    client = http.client.HTTPConnection(address.hostname, address.port)
                    client.request(
                        "POST",
                        "/v1/chat/completions",
                        body=json.dumps(
                            {
                                "model": "deepseek-flash",
                                "max_tokens": 16,
                                "temperature": 1,
                                "thinking": {"type": "enabled"},
                            }
                        ),
                        headers={"Authorization": "Bearer " + token},
                    )
                    reply = client.getresponse()
                    reply.read()
                    self.assertEqual(reply.status, 200)
                    sent = json.loads(upstream.call_args.args[0].data)
                    self.assertEqual(sent["temperature"], 0.0)
                    self.assertEqual(sent["thinking"], {"type": "disabled"})
                    client.close()

    def test_failed_proposer_preserves_redacted_events(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proposer = Proposer(
                ChannelSpec("opencode", "deepseek/deepseek-flash"),
                audit_dir=root / "audit",
                attempts=1,
            )
            with (
                patch("harness2.core.proposer._opencode_dir", return_value=root),
                patch.object(proposer, "env", return_value={"API_KEY": "redact-me-secret"}),
                patch(
                    "harness2.core.proposer.subprocess.run",
                    return_value=Mock(
                        stdout='{"type":"step_finish","part":{"reason":"length"}}',
                        stderr="redact-me-secret",
                        returncode=0,
                    ),
                ),
            ):
                with self.assertRaises(ProposerError):
                    proposer.call("Synthetic diagnostic", None, "failed")
            events = list((root / "audit/provider-events").glob("*.jsonl"))
            self.assertEqual(len(events), 1)
            self.assertIn("length", events[0].read_text())
            stderr = next((root / "audit/provider-events").glob("*.stderr.txt"))
            self.assertEqual(stderr.read_text(), "[REDACTED]")
            self.assertEqual(stderr.stat().st_mode & 0o777, 0o600)
