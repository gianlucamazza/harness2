import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness2.contact_remote import SSHTransport, restore_files, safe_files


class RemoteBoundaryTests(unittest.TestCase):
    def test_only_declared_regular_files_cross_workspace_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input.md").write_text("synthetic input")
            files = safe_files(root)
            self.assertEqual(base64.b64decode(files["input.md"]), b"synthetic input")
            (root / "link").symlink_to("/etc/passwd")
            with self.assertRaises(ValueError):
                safe_files(root)
            with self.assertRaises(ValueError):
                restore_files(root, {"../../escape": "eA=="})
            restore_files(root, {"context/harness/systemprompt.md": "eA=="})
            self.assertEqual((root / "context/harness/systemprompt.md").read_text(), "x")

    def test_failed_remote_command_is_never_retried_or_echoed(self):
        transport = SSHTransport(key=Path("/key"), known_hosts=Path("/known"))
        with patch("harness2.contact_remote.subprocess.run") as run:
            run.return_value.returncode = 1
            run.return_value.stderr = "sensitive request"
            with self.assertRaisesRegex(RuntimeError, "not retried") as error:
                transport.run("code", {"token": "temporary"})
            self.assertNotIn("sensitive", str(error.exception))
            self.assertEqual(run.call_count, 1)
