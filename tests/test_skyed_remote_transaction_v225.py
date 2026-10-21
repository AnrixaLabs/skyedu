"""Exercise the real remote Bash transaction against a fake, isolated WordPress tree."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@unittest.skipUnless(os.name == "posix", "POSIX-only Bash transaction simulation")
class RemoteTransactionTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="skyed-v225-sim-")
        self.addCleanup(self.scratch.cleanup)
        self.tmp = Path(self.scratch.name)
        self.root = self.tmp / "skyed.org"
        self.plugin = self.root / "wp-content/plugins/skyed-lesson-renderer"
        (self.plugin / "assets").mkdir(parents=True)
        (self.root / "wp-config.php").write_text("<?php // fake WP install\n")
        self.original = b"<?php // old renderer"
        self.new = b"<?php // corrected renderer"
        (self.plugin / "skyed-lesson-renderer.php").write_bytes(self.original)
        (self.plugin / "assets/skyed-lesson.css").write_text("/* working CSS */\n")
        os.chmod(self.plugin, 0o755)
        os.chmod(self.plugin / "assets", 0o755)
        for f in self.plugin.rglob("*"):
            if f.is_file():
                os.chmod(f, 0o644)
        self.base = self.tmp / ".skyed-release-v225"
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        stubs = {
            "wp": "#!/bin/sh\ncase \"$*\" in *'config get DB_NAME'*) echo skyed_org;; *'db prefix'*) echo wpml_;; *) exit 4;; esac\n",
            "runuser": "#!/bin/sh\nwhile [ \"$1\" != '--' ]; do shift; done\nshift\ncase \"$3\" in \"$SKYED_TEST_PRIVATE_BASE\"/*) exit 1;; esac\nif [ \"$SKYED_TEST_DENY_STAGED\" = 1 ]; then case \"$3\" in *'.skyed-renderer-stage-'*) exit 1;; esac; fi\nexec \"$@\"\n",
            "id": "#!/bin/sh\nif [ \"$1\" = -u ] && [ \"$2\" = www-data ]; then echo 33; else /usr/bin/id \"$@\"; fi\n",
            "curl": "#!/bin/sh\nprintf '<html><div class=\"skyed-lesson skyed-practice\"></div></html>'\n",
            "php": "#!/bin/sh\nexit 0\n",
        }
        for name, data in stubs.items():
            script = self.bin / name
            script.write_text(data)
            os.chmod(script, 0o755)
        self.env = dict(os.environ)
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env.get("PATH", "")
        self.env["SKYED_TEST_PRIVATE_BASE"] = str(self.base)
        self.env["SKYED_TEST_DENY_STAGED"] = "0"
        archive = self.tmp / "candidate.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("skyed-lesson-renderer/skyed-lesson-renderer.php", self.new)
            z.writestr("skyed-lesson-renderer/assets/skyed-lesson.css", "/* new css */")
            z.writestr("skyed-lesson-renderer/README.md", "candidate fixture")
        self.archive = archive
        source = Path(__file__).resolve().parents[1] / "scripts/skyed_renderer_remote_v225.sh"
        text = source.read_text()
        text = text.replace("ROOT=/var/www/skyed.org", "ROOT=" + str(self.root))
        text = text.replace("BASE=/var/www/.skyed-renderer-v225", "BASE=" + str(self.base))
        text = re.sub(r"(?m)^OLD=[a-f0-9]{64}$", "OLD=" + digest(self.original), text)
        text = re.sub(r"(?m)^NEW=[a-f0-9]{64}$", "NEW=" + digest(self.new), text)
        text = re.sub(r"(?m)^ZIPHASH=[a-f0-9]{64}$", "ZIPHASH=" + digest(archive.read_bytes()), text)
        text = text.replace("sleep 720", "sleep 30")
        text = text.replace('INPUT="/tmp/skyed-v225-$ID.zip"',
                            'INPUT="' + str(self.tmp) + '/skyed-v225-$ID.zip"')
        self.script = self.tmp / "simulated-release.sh"
        self.script.write_text(text)
        os.chmod(self.script, 0o700)
        self.run_id = uuid.uuid4().hex[:16]

    def call(self, mode: str, *, expected: int = 0) -> str:
        result = subprocess.run(["bash", str(self.script), mode, self.run_id],
                                env=self.env, capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, expected, result.stdout + "\n" + result.stderr)
        return result.stdout

    def deploy(self):
        target = self.tmp / f"skyed-v225-{self.run_id}.zip"
        target.write_bytes(self.archive.read_bytes())
        return self.call("deploy")

    def test_inspect_deploy_commit(self):
        self.assertIn("STATUS=INSTALLED_V047", self.call("inspect"))
        self.assertIn("STATUS=PENDING_BROWSER_COMMIT", self.deploy())
        self.assertIn("STATUS=INSTALLED_V048", self.call("inspect"))
        self.assertIn("STATUS=COMMITTED_V048", self.call("commit"))
        self.assertIn("STATUS=INSTALLED_V048", self.call("inspect"))
        self.assertEqual((self.plugin / "skyed-lesson-renderer.php").read_bytes(), self.new)

    def test_deploy_and_rollback(self):
        self.deploy()
        self.assertIn("STATUS=RESTORED_V047_VERIFIED", self.call("rollback"))
        self.assertIn("STATUS=INSTALLED_V047", self.call("inspect"))
        self.assertEqual((self.plugin / "skyed-lesson-renderer.php").read_bytes(), self.original)

    def test_candidate_access_is_checked_outside_private_transaction(self):
        # The mock denies web-worker access beneath the private backup root.
        self.assertIn("STATUS=PENDING_BROWSER_COMMIT", self.deploy())
        candidate = self.plugin / "skyed-lesson-renderer.php"
        self.assertEqual(candidate.read_bytes(), self.new)
        self.assertFalse((self.root / "wp-content" / (
            ".skyed-renderer-stage-" + self.run_id)).exists())

    def test_pre_swap_worker_access_block_preserves_original(self):
        self.env["SKYED_TEST_DENY_STAGED"] = "1"
        source = self.tmp / f"skyed-v225-{self.run_id}.zip"
        source.write_bytes(self.archive.read_bytes())
        result = subprocess.run(["bash", str(self.script), "deploy", self.run_id],
                                env=self.env, capture_output=True, text=True, timeout=25)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("STATUS=BLOCKED_STAGED_FPM_TRAVERSE", result.stdout)
        self.assertEqual((self.plugin / "skyed-lesson-renderer.php").read_bytes(),
                         self.original)
        self.assertIn("TRANSACTION_STATE=PRE_SWAP", self.call("inspect"))
        self.assertFalse((self.base / self.run_id / "PENDING").exists())

    def test_unknown_plugin_rejected_without_swap(self):
        (self.plugin / "skyed-lesson-renderer.php").write_bytes(b"unexpected administrator edit")
        result = subprocess.run(["bash", str(self.script), "deploy", self.run_id],
                                env=self.env, capture_output=True, text=True, timeout=25)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("STATUS=BLOCKED_NOT_ORIGINAL", result.stdout)
        self.assertFalse((self.base / self.run_id).exists())


if __name__ == "__main__":
    unittest.main()
