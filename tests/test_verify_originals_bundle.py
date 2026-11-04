import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import discover_original_skyed
import verify_originals_bundle

class BundleTests(unittest.TestCase):
    def test_no_overwrite_and_verified_restore(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, repo = root / "original", root / "git"
            for p in (src, repo):
                (p / "skyed").mkdir(parents=True)
                (p / "skyed/__init__.py").write_text("# Original package\n")
            (src / "skyed/asset_library.py").write_text("VALUE=123\n")
            candidate = discover_original_skyed.evaluate_workspace(src)
            archive = root / "originals.zip"
            discover_original_skyed.export_originals(candidate, archive)
            result = verify_originals_bundle.restore_bundle(archive, repo)
            self.assertEqual(result["verified_originals"], 1)
            self.assertFalse((repo / "skyed/asset_library.py").exists())
            result = verify_originals_bundle.restore_bundle(archive, repo, apply=True)
            self.assertEqual(result["files"][0]["status"], "COPIED_AND_VERIFIED")
            self.assertEqual((repo / "skyed/asset_library.py").read_text(), "VALUE=123\n")
            with self.assertRaisesRegex(ValueError, "overwrite"):
                verify_originals_bundle.restore_bundle(archive, repo, apply=True)

    def test_reject_modified_member(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            file = root / "fake.zip"
            manifest = {"found_count": 1, "files": [{"module": "skyed.tag_creator",
                        "relative_path": "skyed/tag_creator.py", "sha256": "0" * 64}]}
            with zipfile.ZipFile(file, "w") as z:
                z.writestr("recovery-manifest.json", json.dumps(manifest))
                z.writestr("skyed/tag_creator.py", "VALUE=1\n")
            with self.assertRaisesRegex(ValueError, "SHA256"):
                verify_originals_bundle.inspect_bundle(file)

if __name__ == "__main__":
    unittest.main()
