"""Review snapshot packaging never includes fonts or secrets."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/package_source_review.py"
_spec = importlib.util.spec_from_file_location("package_source_review", _SCRIPT)
_pkg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pkg)


class SourceReviewArchiveTests(unittest.TestCase):
    def test_snapshot_retains_code_but_never_fonts_or_dotenv(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            repo = base / "skyedu"
            repo.mkdir()
            for filename, body in [
                ("skyed/cards.py", b"print('ok')"),
                ("assets/fonts/secret.ttf", b"NO_SIR"),
                (".env", b"WP_SECRET=this-must-not-leak"),
                ("wp_plugin/skyed-lesson-renderer/main.php", b"<?php"),
            ]:
                p = repo / filename
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(body)
            subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(repo), "add", "-f", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.email=test@example.com",
                            "-c", "user.name=QA", "commit", "-qm", "Fixture"], check=True)
            out = base / "source.zip"
            result = _pkg.package(repo, out)
            self.assertGreaterEqual(result["included_files"], 2)
            with zipfile.ZipFile(out) as z:
                names = z.namelist()
                self.assertIn("skyedu/skyed/cards.py", names)
                self.assertIn("skyedu/wp_plugin/skyed-lesson-renderer/main.php", names)
                self.assertFalse(any(name.endswith(".ttf") or name.endswith("/.env")
                                     for name in names))
                metadata = json.loads(z.read("skyedu/REVIEW-SNAPSHOT-MANIFEST.json"))
                excluded = {x["path"] for x in metadata["excluded_files"]}
                self.assertIn("assets/fonts/secret.ttf", excluded)
                self.assertIn(".env", excluded)


if __name__ == "__main__":
    unittest.main()
