import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_repo_integrity.py"
spec = importlib.util.spec_from_file_location("verify_repo_integrity", SCRIPT)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class RepoIntegrityTests(unittest.TestCase):
    def test_detect_and_resolve_missing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "skyed").mkdir()
            (root / "skyed/__init__.py").write_text("")
            (root / "run.py").write_text("from skyed.extra import foo\n")
            self.assertEqual([x["module"] for x in verifier.missing_project_modules(root)], ["skyed.extra"])
            (root / "skyed/extra.py").write_text("foo=1\n")
            self.assertEqual(verifier.missing_project_modules(root), [])

    def test_detect_relative_import(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "skyed").mkdir()
            (root / "skyed/__init__.py").write_text("")
            (root / "skyed/mod.py").write_text("from .gone import bar\n")
            self.assertEqual(verifier.missing_project_modules(root)[0]["module"], "skyed.gone")


if __name__ == "__main__":
    unittest.main()
