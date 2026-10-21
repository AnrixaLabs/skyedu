"""Isolated read-only Stage C evidence diagnosis regressions."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "inspect_media_qa_evidence.py"
spec = importlib.util.spec_from_file_location("skyed_stage_c_inspector", SCRIPT)
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)

def fixture(root: Path, status: str = "BLOCKED_VISUAL_CONTENT", corrupt: bool = False) -> Path:
    archive = root / "evidence.zip"
    mp3 = b"ID3" + b"x" * 1100
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 180
    words = ["cat", "dog", "apple", "ball"]
    items = [(f"cards/{w}.png", png) for w in words]
    items += [(f"audio/{lang}/{w}.mp3", mp3) for lang in ("en", "zh")
              for w in words + ["sent_one", "sent_two"]]
    manifest = [{"path": name, "bytes": len(data),
                 "sha256": hashlib.sha256(data).hexdigest(), "status": "PASS"}
                for name, data in items]
    body = {"result": {
        "status": status, "generator_exit_code": 0, "source_commit": "a" * 40,
        "wordpress_posts_created": 0, "production_publish_authorized": False,
        "visual_quality_blockers": [{"word":"cat","status":"local_asset_missing_placeholder"}]
            if status == "BLOCKED_VISUAL_CONTENT" else [],
        "image_count": 4, "mp3_count": 12,
    }, "files": manifest}
    with ZipFile(archive, "w") as z:
        z.writestr("media-validation.json", json.dumps(body))
        for i, (name, data) in enumerate(items):
            z.writestr("lesson/" + name, b"tampered" if corrupt and i == 0 else data)
    return archive

class MediaEvidenceInspectionTests(unittest.TestCase):
    def test_expected_placeholder_blocks_but_audio_and_png_hashes_verified(self):
        with tempfile.TemporaryDirectory() as d:
            result = inspector.analyze(fixture(Path(d)))
            self.assertEqual(result["status"], "BLOCKED_VISUAL_CONTENT")
            self.assertEqual(result["verified_media_files"], 16)
            self.assertEqual(result["verified_mp3"], 12)
            self.assertEqual(result["verified_png"], 4)
            self.assertFalse(result["production_publish_authorized"])

    def test_technical_pass_always_requires_manual_review(self):
        with tempfile.TemporaryDirectory() as d:
            result = inspector.analyze(fixture(Path(d), "TECHNICAL_MEDIA_PASS"))
            self.assertEqual(result["status"], "TECHNICAL_MEDIA_PASS_TEACHER_REVIEW_REQUIRED")

    def test_corrupt_member_never_passes(self):
        with tempfile.TemporaryDirectory() as d:
            result = inspector.analyze(fixture(Path(d), corrupt=True))
            self.assertEqual(result["status"], "BLOCKED_MEDIA_EVIDENCE")
            self.assertIn("cards/cat.png", result["bad_media_members"])

    def test_sha256_pin_rejects_wrong_uploaded_archive(self):
        with tempfile.TemporaryDirectory() as d:
            result = inspector.analyze(fixture(Path(d)), "0" * 64)
            self.assertEqual(result["status"], "UNVERIFIED_EVIDENCE")
            self.assertIn("SHA256_MISMATCH", result["reason"])

    def test_missing_zip_is_not_a_product_failure(self):
        with tempfile.TemporaryDirectory() as d:
            result = inspector.analyze(Path(d) / "absent.zip")
            self.assertEqual(result["status"], "UNVERIFIED_EVIDENCE")

if __name__ == "__main__":
    unittest.main()
