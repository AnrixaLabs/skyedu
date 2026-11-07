"""Release v2.4.0 installer/content preservation and binary artwork reproducibility."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('skyed_v240_package',ROOT/'scripts/package_control_panel_v240.py')
P=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(P)

class CompleteRelease(unittest.TestCase):
    def test_allowlisted_complete_successor(self):
        self.assertEqual(len(P.MEMBERS),55)
        self.assertEqual(len(P.ILLUSTRATIONS),18)
        # The on-disk application intentionally excludes release-only docs;
        # require every executable and visual asset both in CI and after install.
        runtime = (name for name in P.MEMBERS if not name.startswith('docs/'))
        self.assertTrue(all((ROOT / name).is_file() for name in runtime))
        self.assertTrue((ROOT/'scripts/Install-SkyED-ControlPanel-v2.3.3.ps1').is_file())
        self.assertTrue((ROOT/'tests/test_course_hub_integration.py').is_file())

    def test_windows_crlf_does_not_modify_binary_artwork(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); winroot=root/'windows-checkout'; winroot.mkdir()
            missing={name for name in P.MEMBERS if not (ROOT/name).is_file()}
            # The actual installed runtime intentionally excludes full release docs.
            release_only={'docs/CONTROL-PANEL-v2.3.3.md','docs/RELEASE-CHECKPOINT.json','docs/VISUAL-IDENTITY-v2.4.0.md'}
            if missing and missing.issubset(release_only):self.skipTest('ZIP-only release docs unavailable in installed runtime')
            self.assertFalse(missing,repr(missing))
            for name in P.MEMBERS:
                dest=winroot/name;dest.parent.mkdir(parents=True,exist_ok=True)
                b=(ROOT/name).read_bytes();dest.write_bytes(b if name.endswith('.webp') else b.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
            a=root/'canonical.zip';b=root/'windows.zip'
            P.build(ROOT,a);P.build(winroot,b)
            self.assertEqual(a.read_bytes(),b.read_bytes())

    def test_windows_installer_guards_draft_and_rolls_back(self):
        src=(ROOT/'scripts/Install-SkyED-ControlPanel-v2.4.0.ps1').read_text(encoding='utf-8')
        for value in ('SKYED_V240_MANIFEST=PASS','validate_lobby_content_v240.py','ROLLED_BACK','SKYED_V240_INSTALL=PASS','[switch]$SkipShortcuts'):
            self.assertIn(value,src)
        self.assertNotIn('& $py -c',src)

if __name__=='__main__':unittest.main()
