"""Static guardrails for the PowerShell wrapper, complementing live Windows CI."""
from pathlib import Path
import unittest


FILE = Path(__file__).resolve().parents[1] / "Verify-Captured-Stage.ps1"


class PowerShellContractTests(unittest.TestCase):
    def test_no_python_inline_eval_or_shell_escape(self):
        s = FILE.read_text(encoding="utf-8")
        self.assertNotIn("python -c", s.lower())
        self.assertNotIn("Invoke-Expression", s)
        self.assertNotIn("StrictHostKeyChecking=no", s)
        self.assertNotIn("ssh.exe", s)
        self.assertNotIn("scp.exe", s)
        self.assertIn("@pythonArgs", s)

    def test_archive_miss_can_discover_matched_timestamp(self):
        s = FILE.read_text(encoding="utf-8")
        self.assertIn("--workspace", s)
        self.assertIn("--stamp", s)
        self.assertIn("report-([0-9]{8}-[0-9]{6})", s)
        self.assertIn("SKYED_ARCHIVE_NOT_LOCAL=USING_MATCHED_STAGE_DIRECTORIES", s)

    def test_explicit_pair_and_receipt(self):
        s = FILE.read_text(encoding="utf-8")
        self.assertIn("--report-dir", s)
        self.assertIn("--stage-dir", s)
        self.assertIn("--output", s)
        self.assertIn("SKYED_V235_TEACHER_REVIEW=PENDING", s)
        self.assertIn("SKYED_V235_PRODUCTION_APPROVAL=false", s)


if __name__ == "__main__":
    unittest.main()
