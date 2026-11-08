import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "discover_original_skyed.py"
_spec = importlib.util.spec_from_file_location("discover_original_skyed", _SCRIPT)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

class DiscoverOriginalsTests(unittest.TestCase):
    def make_original(self, root: Path, count=12):
        (root / "skyed").mkdir(parents=True)
        (root / "skyed/__init__.py").write_text("# Original\n")
        (root / "run_pipeline.py").write_text("# Original\n")
        for name in _module.MISSING_MODULES[:count]:
            (root / "skyed" / (name + ".py")).write_text("VALUE = 2\n", encoding="utf-8")

    def test_detect_exact_and_checksum_export(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            source = base / "work" / "SkyED-Original"
            self.make_original(source)
            candidate = _module.evaluate_workspace(source)
            self.assertEqual(candidate["found_count"], 12)
            self.assertEqual(candidate["missing_count"], 0)
            self.assertFalse(any(i["suspicious_secret_pattern"] for i in candidate["found"]))
            out = base / "SkyED-Originals.zip"
            answer = _module.export_originals(candidate, out)
            self.assertEqual(answer["files"], 12)
            with zipfile.ZipFile(out) as z:
                self.assertEqual(len(z.namelist()), 13)
                manifest = json.loads(z.read("recovery-manifest.json"))
                self.assertEqual(manifest["found_count"], 12)
                for file in manifest["files"]:
                    self.assertEqual(_module.sha256_bytes(z.read(file["relative_path"])), file["sha256"])
            with self.assertRaises(FileExistsError):
                _module.export_originals(candidate, out)

    def test_bounded_scan_and_partial(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            source = root / "deep" / "SkyED"
            self.make_original(source, count=5)
            results, stats = _module.discover([root], max_depth=3)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["found_count"], 5)
            self.assertEqual(results[0]["missing_count"], 7)
            self.assertFalse(stats["search_limit_reached"])

    def test_sensitive_literal_refuses_export(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            self.make_original(root, count=1)
            (root / "skyed" / "asset_library.py").write_text('OPENAI_API_KEY = "abcdefghijklmno"\n')
            candidate = _module.evaluate_workspace(root)
            self.assertTrue(candidate["found"][0]["suspicious_secret_pattern"])
            with self.assertRaisesRegex(ValueError, "(?:credential|secret)"):
                _module.export_originals(candidate, root / "bad.zip")

    def test_empty_candidate_not_selected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "skyed").mkdir()
            self.assertIsNone(_module.evaluate_workspace(root))

if __name__ == "__main__":
    unittest.main()
