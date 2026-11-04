"""Regression tests for UTF-8 subprocess capture used by Windows PowerShell."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "qa_capture.py"
_spec = importlib.util.spec_from_file_location("qa_capture", _SCRIPT)
_adapter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_adapter)


class QACaptureTests(unittest.TestCase):
    def test_native_stderr_is_plain_text(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "combined.log"
            code = _adapter.run(["--log", str(path), "--", "-c",
                                 "import sys;print('out');print('warning',file=sys.stderr)"])
            self.assertEqual(code, 0)
            body = path.read_text(encoding="utf-8")
            self.assertIn("out", body)
            self.assertIn("warning", body)
            self.assertNotIn("NativeCommandError", body)

    def test_nonzero_exit_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "failure.log"
            code = _adapter.run(["--log", str(path), "--", "-c",
                                 "import sys;print('failure');sys.exit(7)"])
            self.assertEqual(code, 7)
            self.assertIn("failure", path.read_text(encoding="utf-8"))

    def test_refuses_log_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "existing.log"
            path.write_text("preserved", encoding="utf-8")
            self.assertEqual(_adapter.run(["--log", str(path), "--", "-V"]), 3)
            self.assertEqual(path.read_text(encoding="utf-8"), "preserved")


if __name__ == "__main__":
    unittest.main()
