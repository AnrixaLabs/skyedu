"""Acceptance tests for the Windows v2.3.2 lobby-content preflight."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_lobby_content_v232.py"
INSTALLER = ROOT / "scripts" / "Install-SkyED-ControlPanel-v2.3.2.ps1"
APPROVED_DRAFT = ROOT / "skyed_lobby" / "site" / "content" / "lobby.json"


class ExistingDraftPreflight(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "lobby.json"
        self.path.write_bytes(APPROVED_DRAFT.read_bytes())

    def run_validator(self):
        before = self.path.read_bytes()
        cmd = [sys.executable, str(VALIDATOR), str(self.path)]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(self.path.read_bytes(), before, "Preflight must never mutate a user's draft")
        return r

    def test_existing_unicode_json_passes_unchanged(self):
        r = self.run_validator()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("SKYED_PREVIOUS_LOBBY_CONTENT=PRESERVED", r.stdout)

    def test_existing_bom_is_accepted_and_preserved(self):
        self.path.write_bytes(b"\xef\xbb\xbf" + self.path.read_bytes())
        self.assertEqual(self.run_validator().returncode, 0)

    def test_invalid_json_blocks_without_overwrite(self):
        self.path.write_text('{"schemaVersion": 1,', encoding="utf-8")
        self.assertNotEqual(self.run_validator().returncode, 0)

    def test_missing_schema_blocks_without_overwrite(self):
        doc = json.loads(APPROVED_DRAFT.read_text(encoding="utf-8"))
        doc["schemaVersion"] = 999
        self.path.write_text(json.dumps(doc), encoding="utf-8")
        self.assertNotEqual(self.run_validator().returncode, 0)

    def test_invalid_url_blocks_without_overwrite(self):
        doc = json.loads(APPROVED_DRAFT.read_text(encoding="utf-8"))
        doc["lessons"][0]["url"] = "javascript:alert(1)"
        self.path.write_text(json.dumps(doc), encoding="utf-8")
        self.assertNotEqual(self.run_validator().returncode, 0)

    def test_oversized_draft_blocks(self):
        self.path.write_bytes(b' ' * (1024 * 1024 + 1))
        self.assertNotEqual(self.run_validator().returncode, 0)

    def test_missing_draft_blocks(self):
        self.path.unlink()
        r = subprocess.run([sys.executable, str(VALIDATOR), str(self.path)], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)

    def test_symlink_draft_blocks(self):
        target = Path(self._tmp.name) / "target.json"
        target.write_bytes(APPROVED_DRAFT.read_bytes())
        self.path.unlink()
        try:
            self.path.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not available on this host")
        self.assertNotEqual(self.run_validator().returncode, 0)
        self.assertEqual(target.read_bytes(), APPROVED_DRAFT.read_bytes())

    def test_windows_crlf_checkout_produces_identical_archive(self):
        """Git may translate text to CRLF on Windows; the release must not drift."""
        from importlib.util import module_from_spec, spec_from_file_location
        spec = spec_from_file_location("skyed_v232_packager", ROOT / "scripts/package_control_panel_v232.py")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            canonical, winroot = work / "linux.zip", work / "windows-clone"
            winroot.mkdir()
            for name in module.MEMBERS:
                source = ROOT / name
                output = winroot / name
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(source.read_bytes().replace(b"\n", b"\r\n"))
            module.build(ROOT, canonical)
            windows = work / "windows.zip"
            module.build(winroot, windows)
            self.assertEqual(canonical.read_bytes(), windows.read_bytes())

    def test_windows_installer_uses_file_instead_of_inline_code(self):
        s = INSTALLER.read_text(encoding="utf-8")
        self.assertNotIn("& $py -c", s)
        self.assertIn("& $py $validator $existingContent", s)
        self.assertIn("SKYED_PREVIOUS_LOBBY_CONTENT", VALIDATOR.read_text(encoding="utf-8"))
        self.assertIn("SKYED_V232_MANIFEST=PASS", s)
        self.assertIn("if ($properties.Count -ne 28)", s)


if __name__ == "__main__":
    unittest.main()
