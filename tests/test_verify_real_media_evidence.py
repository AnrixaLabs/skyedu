import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_real_media_evidence.py"
spec = importlib.util.spec_from_file_location("verify_real_media_evidence", SCRIPT)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class MediaEvidenceVerifierTests(unittest.TestCase):
    def make_archive(self, root, quality="BLOCKED_PLACEHOLDER_OR_FALLBACK", corrupted=False):
        path = root / "media.zip"
        entries = [
            (f"cards/{n}.png", b"\x89PNG\r\n\x1a\n" + bytes([i])*120)
            for i, n in enumerate(("cat", "dog", "apple", "ball"))
        ]
        entries.extend((f"audio/{lang}/{n}.mp3", b"ID3" + bytes([i])*150)
                       for i, (lang,n) in enumerate(
                           [(lang,n) for lang in ("en", "zh")
                            for n in ("cat", "dog", "apple", "ball", "sent_one", "sent_two")]))
        files = [
            {"path": rel, "status": "PASS", "bytes": len(b),
             "sha256": hashlib.sha256(b).hexdigest()}
            for rel, b in entries
        ]
        blockers = [{"word": "cat", "status": "local_asset_missing_placeholder"}] \
            if quality == "BLOCKED_PLACEHOLDER_OR_FALLBACK" else []
        info = {
            "result": {
                "generator_exit_code": 0,
                "source_commit": "a"*40,
                "wordpress_posts_created": 0,
                "production_publish_authorized": False,
                "status": "BLOCKED_VISUAL_CONTENT" if blockers else "TECHNICAL_MEDIA_PASS",
                "visual_quality_status": quality,
                "visual_quality_blockers": blockers,
            },
            "files": files,
        }
        with ZipFile(path, "w") as archive:
            archive.writestr("media-validation.json", json.dumps(info))
            archive.writestr("generation.log", "Generated")
            archive.writestr("lesson/quiz.json", "{}")
            archive.writestr("lesson/spec_debug.json", "{}")
            for i, (rel, data) in enumerate(entries):
                archive.writestr("lesson/" + rel, b"bad" if corrupted and i == 0 else data)
        return path

    def test_valid_media_with_placeholder_is_technical_pass_but_not_promotion(self):
        with tempfile.TemporaryDirectory() as d:
            result = verify.inspect(self.make_archive(Path(d)))
            self.assertEqual(result["status"], "TECHNICAL_MEDIA_PASS_VISUAL_BLOCKED")
            self.assertEqual(result["verified_mp3"], 12)
            self.assertEqual(result["production_approval"], "NOT_GRANTED")

    def test_valid_media_still_needs_teacher_review(self):
        with tempfile.TemporaryDirectory() as d:
            result = verify.inspect(self.make_archive(Path(d), "REVIEW_REQUIRED"))
            self.assertEqual(result["status"], "TECHNICAL_MEDIA_PASS_TEACHER_REVIEW_REQUIRED")

    def test_checksum_tampering_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            result = verify.inspect(self.make_archive(Path(d), corrupted=True))
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("hash/size", result["failure"])

    def test_old_incomplete_bundle_cannot_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"old.zip"
            with ZipFile(p,"w") as archive:
                archive.writestr("media-validation.json", json.dumps({"result":{
                    "generator_exit_code":0,
                    "source_commit":"a"*40,
                    "wordpress_posts_created":0,
                    "production_publish_authorized":False}, "files":[]}))
                archive.writestr("generation.log", "complete")
                archive.writestr("lesson/quiz.json", "{}")
                archive.writestr("lesson/spec_debug.json", "{}")
            result = verify.inspect(p)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("older validator crash", result["failure"])


if __name__ == "__main__":
    unittest.main()
