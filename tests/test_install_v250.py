"""Complete v2.5.0 Windows overlay, installer, and deterministic archive contract."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from package_control_panel_v250 import MEMBERS,ADDED,build

class CompleteV250Release(unittest.TestCase):
    def test_full_additive_member_list(self):
        self.assertEqual(len(MEMBERS),len(set(MEMBERS)))
        self.assertGreaterEqual(len(MEMBERS),65)
        for rel in MEMBERS:
            if rel.startswith('docs/') and not (ROOT/rel).is_file():continue
            self.assertTrue((ROOT/rel).is_file(),rel)
        self.assertIn('skyed_lobby/site/assets/illustrations/topic-11.webp',MEMBERS)
        self.assertIn('scripts/course_hub_deploy.py',MEMBERS)

    def test_package_reproducible_across_windows_line_endings(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);native=root/'win';native.mkdir()
            missing=[x for x in MEMBERS if not (ROOT/x).is_file()]
            if missing and all(x.startswith('docs/') for x in missing):
                self.skipTest('Installed workspace legitimately omits ZIP-only docs')
            self.assertFalse(missing)
            for rel in MEMBERS:
                d=native/rel;d.parent.mkdir(parents=True,exist_ok=True)
                data=(ROOT/rel).read_bytes()
                d.write_bytes(data if rel.endswith('.webp') else data.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
            a=root/'a.zip';b=root/'b.zip'
            build(ROOT,a);build(native,b)
            self.assertEqual(a.read_bytes(),b.read_bytes())

    def test_installer_preserves_drafts_and_checks_before_shortcuts(self):
        script=(ROOT/'scripts/Install-SkyED-ControlPanel-v2.5.0.ps1').read_text(encoding='utf-8')
        for item in ('SKYED_V250_MANIFEST=PASS','SKYED_V250_INSTALL=PASS','SKYED_EXISTING_LOBBY_CONTENT_INVALID_NO_OVERWRITE','SKYED_V250_ROOT_RELEASE_TESTS_FAILED','SKYED_V250_IMAGE_UPLOAD_TESTS_FAILED','ROLLED_BACK'):
            self.assertIn(item,script)
        self.assertNotIn('& $py -c',script)
        self.assertLess(script.index('SKYED_V250_LOCAL_QA=PASS'),script.index('CreateShortcut'))

    def test_root_release_stays_local_until_human_approval(self):
        code=(ROOT/'scripts/course_hub_deploy.py').read_text(encoding='utf-8')
        for marker in ('StrictHostKeyChecking=yes','check_approval','candidate_tree_sha256','HTTP_SMOKE_FAILED_ROLLBACK_COMPLETED','CURRENT_NOT_SYMLINK'):
            self.assertIn(marker,code)
        self.assertNotIn('StrictHostKeyChecking=no',code)

if __name__=='__main__':unittest.main()
