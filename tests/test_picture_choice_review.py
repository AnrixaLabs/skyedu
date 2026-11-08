"""Security/educational gate: picture-listening quizzes require label-free artwork review."""
from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from skyed.publish_gates import PublishGateError, validate_picture_choice_review


class PictureChoiceReviewTests(unittest.TestCase):
    def fixture(self, root: Path) -> None:
        (root / "cards").mkdir()
        (root / "cards/cat.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 250)
        (root / "cards/dog.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"y" * 250)
        (root / "quiz.json").write_text(json.dumps({
            "questions": [{"kind": "listen_to_picture",
                           "prompt_audio": "audio/en/cat.mp3",
                           "choices": [
                               {"img": "cards/cat.png"}, {"img": "cards/dog.png"},
                           ]}]
        }), encoding="utf-8")

    def review(self, root, *, label_free=True, stale=False):
        cards = ["cards/cat.png", "cards/dog.png"]
        payload = {
            "schema": "skyed.picture-choice-review.v1",
            "reviewer": "Teacher QA",
            "reviewed_date": date.today().isoformat(),
            "label_free_confirmed": label_free,
            "meaning_confirmed": True,
            "images": [{
                "path": name,
                "sha256": ("0" * 64 if stale and i == 1 else
                           hashlib.sha256((root / name).read_bytes()).hexdigest()),
                "label_free": True,
                "meaning_correct": True,
            } for i, name in enumerate(cards)]
        }
        (root / "picture_choice_review.json").write_text(
            json.dumps(payload), encoding="utf-8")

    def test_no_review_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            self.fixture(r)
            with self.assertRaisesRegex(PublishGateError, "provenance"):
                validate_picture_choice_review(r)

    def test_review_with_picture_labels_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d); self.fixture(r); self.review(r, label_free=False)
            with self.assertRaisesRegex(PublishGateError, "incomplete"):
                validate_picture_choice_review(r)

    def test_stale_sha_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d); self.fixture(r); self.review(r, stale=True)
            with self.assertRaisesRegex(PublishGateError, "stale"):
                validate_picture_choice_review(r)

    def test_matching_review_passes(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d); self.fixture(r); self.review(r)
            result = validate_picture_choice_review(r)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["images_checked"], 2)

    def test_interim_existing_library_allowed_without_extra_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            self.fixture(r)
            (r / "cards/image_report.json").write_text(json.dumps([
                {"word": "cat", "slug": "cat", "status": "local_asset_match"},
                {"word": "dog", "slug": "dog", "status": "local_asset_match"},
            ]), encoding="utf-8")
            with patch.dict("os.environ", {"SKYED_REQUIRE_LABEL_FREE_REVIEW": "0"}):
                result = validate_picture_choice_review(r)
            self.assertEqual(result["status"], "INTERIM_ASSET_LIBRARY")
            self.assertEqual(result["images_checked"], 2)
            self.assertEqual(result["teacher_visual_review"], "RECOMMENDED_INTERIM")

    def test_strict_opt_in_requires_explicit_review_even_for_library(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            self.fixture(r)
            (r / "cards/image_report.json").write_text(json.dumps([
                {"word": "cat", "slug": "cat", "status": "local_asset_match"},
                {"word": "dog", "slug": "dog", "status": "local_asset_match"},
            ]), encoding="utf-8")
            with patch.dict("os.environ", {"SKYED_REQUIRE_LABEL_FREE_REVIEW": "1"}):
                with self.assertRaisesRegex(PublishGateError, "teacher"):
                    validate_picture_choice_review(r)

    def test_interim_rejects_placeholder_and_generated_untested_picture(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            self.fixture(r)
            (r / "cards/image_report.json").write_text(json.dumps([
                {"word": "cat", "slug": "cat", "status": "local_asset_match"},
                {"word": "dog", "slug": "dog", "status": "clean_placeholder"},
            ]), encoding="utf-8")
            with patch.dict("os.environ", {"SKYED_REQUIRE_LABEL_FREE_REVIEW": "0"}):
                with self.assertRaisesRegex(PublishGateError, "local_asset_match"):
                    validate_picture_choice_review(r)

    def test_non_picture_quiz_does_not_require_review(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d)
            (r/"quiz.json").write_text(json.dumps({"questions":[
                {"kind":"sentence_cloze","choices":["cat","dog"]}]}),encoding="utf-8")
            self.assertEqual(validate_picture_choice_review(r)["status"],"NOT_REQUIRED")


if __name__ == "__main__":
    unittest.main()
