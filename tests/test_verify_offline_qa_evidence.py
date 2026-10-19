import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify_offline_qa_evidence.py"
_spec = importlib.util.spec_from_file_location("verify_offline_qa_evidence", SCRIPT)
_v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_v)


class OfflineQAArchiveVerificationTests(unittest.TestCase):
    def _write(self, root, *, result_status="OFFLINE_QA_PASS", omit=()):
        destination = root / "qa.zip"
        statuses = {x: "PASS" for x in _v.CHECKS}
        statuses["php_lint"] = "UNVERIFIED_PHP_CLI_MISSING"
        results = {
            "status": result_status,
            "read_only_production": True,
            "original_windows_project_untouched": True,
            "commit": "a" * 40,
            "checks": statuses,
        }
        smoke = {
            "result": "PASS", "publish_performed": False,
            "themes": [
                {"theme": x, "status": "PASS", "media_generated": False,
                 "wp_calls": 0, "questions": 5, "vocabulary": 7, "sentences": 4}
                for x in sorted(_v.EXPECTED_THEMES)
            ],
        }
        files = {
            "results.json": json.dumps(results),
            "integrity.json": json.dumps({"status": "PASS", "missing_count": 0}),
            "smoke-report.json": json.dumps(smoke),
            "unit-tests.log": "Ran 20 tests in 0.021s\n\nOK\n",
        }
        with zipfile.ZipFile(destination, "w") as z:
            for name, body in files.items():
                if name not in omit:
                    z.writestr(name, body)
        return destination

    def test_complete_qa_pass(self):
        with tempfile.TemporaryDirectory() as d:
            report = _v.verify(self._write(Path(d)))
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["theme_count"], 4)
            self.assertEqual(report["php_lint"], "UNVERIFIED")

    def test_blocked_early_windows_qa_not_masked(self):
        with tempfile.TemporaryDirectory() as d:
            report = _v.verify(self._write(Path(d), result_status="BLOCKED"))
            self.assertEqual(report["status"], "BLOCKED")
            self.assertIn("not PASS", report["failure_reason"])

    def test_missing_smoke_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            report = _v.verify(self._write(Path(d), omit=("smoke-report.json",)))
            self.assertEqual(report["status"], "BLOCKED")
            self.assertIn("smoke-report", report["failure_reason"])


if __name__ == "__main__":
    unittest.main()
