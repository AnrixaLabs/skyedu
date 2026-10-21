"""Safety regressions for real-media QA; no TTS requests are made."""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "qa_real_media.py"
_spec = importlib.util.spec_from_file_location("qa_real_media", SCRIPT)
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)


class RealMediaQASafetyTests(unittest.TestCase):
    def test_original_pycharm_root_protected(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            original = base / "skyed_automation"
            original.mkdir()
            out = base / "result"
            with self.assertRaisesRegex(ValueError, "PyCharm"):
                _m.generate(original, out, 5)
            self.assertFalse(out.exists())

    def test_existing_evidence_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            repo = base / "skyedu"
            repo.mkdir()
            (repo / "run_pipeline.py").write_text("# existing", encoding="utf-8")
            output = base / "already-exists"
            output.mkdir()
            sentinel = output / "evidence"
            sentinel.write_text("PRESERVE", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                _m.generate(repo, output, 5)
            self.assertEqual(sentinel.read_text(), "PRESERVE")

    def test_no_output_inside_source_checkout(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "skyedu"
            repo.mkdir()
            with self.assertRaises(ValueError):
                _m.generate(repo, repo / "media-output", 5)

    def test_sha256(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "data"
            f.write_bytes(b"example")
            self.assertEqual(_m.sha256(f), hashlib.sha256(b"example").hexdigest())


if __name__ == "__main__":
    unittest.main()
