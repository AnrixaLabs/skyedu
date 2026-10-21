"""Regression coverage for WordPress quiz media paths and sentence-cloze rounds."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from skyed.pipeline_helpers import sentence_audio_stem
from skyed.quizgen import _blank_word, _build_entries, _sentence_audio_stem, generate_quiz
from skyed.utils import slugify_file


class QuizMediaParityTests(unittest.TestCase):
    def setUp(self):
        self.spec = {
            "title": "My Family Rooms",
            "vocab": [
                {"en": "living room", "zh": "客厅", "pos": "noun"},
                {"en": "baby", "zh": "婴儿", "pos": "noun"},
                {"en": "bathroom", "zh": "卫生间", "pos": "noun"},
                {"en": "grandma", "zh": "奶奶", "pos": "noun"},
                {"en": "kitchen", "zh": "厨房", "pos": "noun"},
                {"en": "bedroom", "zh": "卧室", "pos": "noun"},
            ],
            "sentences": [
                {"en": "The baby is in the living room.", "zh": "宝宝在客厅里。"},
                {"en": "Grandma is in the kitchen.", "zh": "奶奶在厨房里。"},
                {"en": "The bathroom is clean.", "zh": "卫生间很干净。"},
            ],
        }

    def test_word_media_matches_generated_filename_stem(self):
        entries = _build_entries(self.spec)
        target = next(e for e in entries if e.en == "living room")
        self.assertEqual(target.image, "cards/living_room.png")
        self.assertEqual(target.audio_en, "audio/en/living_room.mp3")
        self.assertEqual(target.audio_zh, "audio/zh/living_room.mp3")
        for e in entries:
            stem = slugify_file(e.en)
            self.assertEqual(e.image, f"cards/{stem}.png")
            self.assertEqual(e.audio_en, f"audio/en/{stem}.mp3")

    def test_sentence_audio_stem_matches_main_pipeline(self):
        for raw in [s["en"] for s in self.spec["sentences"]]:
            self.assertEqual(_sentence_audio_stem(raw), sentence_audio_stem(raw))
        self.assertIn("_", _sentence_audio_stem("The baby is in the living room."))

    def test_word_boundaries_and_blank_generation(self):
        self.assertEqual(_blank_word("A baby is sleeping.", "baby"), "A ____ is sleeping.")
        self.assertEqual(_blank_word("The baby is in the living room.", "living room"),
                         "The baby is in the ____.")
        self.assertIsNone(_blank_word("A baby is sleeping.", "bab"))
        self.assertIsNone(_blank_word("Cats are sleeping.", "cat"))

    def test_cloze_questions_present_and_media_references_consistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            for theme in ("sky", "fun_mission", "strict_dark", "sky_tiles"):
                path = generate_quiz(self.spec, Path(tmp) / theme, theme_variant=theme)
                quiz = json.loads(path.read_text(encoding="utf-8"))
                self.assertTrue(quiz["questions"])
                for q in quiz["questions"]:
                    for choice in q["choices"]:
                        if isinstance(choice, dict):
                            if choice.get("img"):
                                self.assertNotIn("living-room.", choice["img"])
                            if choice.get("audio"):
                                self.assertNotIn("living-room.", choice["audio"])
                if theme in {"sky", "fun_mission", "strict_dark"}:
                    cloze = [q for q in quiz["questions"] if q["kind"] == "sentence_cloze"]
                    self.assertTrue(cloze, f"Missing cloze practice in {theme}")
                    for q in cloze:
                        self.assertIn("____", q["q"])
                        self.assertTrue(q["prompt_audio"].startswith("audio/en/sent_"))
                if theme == "sky_tiles":
                    self.assertLessEqual(len(quiz["questions"]), 5)
                    self.assertTrue(all(q["kind"] == "listen_to_picture" for q in quiz["questions"]))


if __name__ == "__main__":
    unittest.main()
