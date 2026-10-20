"""Static compatibility checks for reviewed SkyED responsive homework UI."""
from __future__ import annotations
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StageDDesignContracts(unittest.TestCase):
    def test_standalone_picture_quiz_grid_and_all_round_scoring(self):
        html = (ROOT / "templates/quiz_index.html").read_text(encoding="utf-8")
        self.assertIn(".skyed-picture-grid .choice-grid", html)
        self.assertIn("repeat(2,minmax(0,1fr))", html)
        self.assertIn("questions.reduce", html)
        self.assertIn("delete answers[idx]", html)
        self.assertIn("Complete all rounds to see your score", html)
        self.assertIn("Picture option ", html)

    def test_renderer_review_version_and_child_choice_grid(self):
        php = (ROOT / "wp_plugin/skyed-lesson-renderer/skyed-lesson-renderer.php").read_text(encoding="utf-8")
        css = (ROOT / "wp_plugin/skyed-lesson-renderer/assets/skyed-lesson.css").read_text(encoding="utf-8")
        self.assertIn("Version: 0.4.7", php)
        self.assertIn("delete answers[idx]", php)
        self.assertIn("Finish all rounds to see your score", php)
        self.assertIn("Picture option ", php)
        self.assertIn(".skyed-qcard--kid .skyed-choices{ grid-template-columns:repeat(2,minmax(0,1fr))", css)

    def test_bilingual_flashcard_text_separate_from_art(self):
        src = (ROOT / "skyed/cards.py").read_text(encoding="utf-8")
        # Both zones are maintained in the original make_flashcard, not in a
        # forked replacement generator.
        start, end = src.index("def make_flashcard("), src.index("def _normalize_vocab(")
        func = src[start:end]
        self.assertIn('"SKYED / WORDS"', func)
        self.assertIn("max_text_width = 262", func)
        self.assertIn("x1, y1, x2, y2 = 353, 82, 963, 646", func)
        self.assertIn("_contain_fit(art, panel_w, panel_h", func)
        self.assertNotIn('"Say it 2 times + make 1 full sentence."', func)

    def test_sky_tiles_audio_is_not_described_as_optional(self):
        src = (ROOT / "skyed/pipeline_helpers.py").read_text(encoding="utf-8")
        self.assertIn("This is a listening task: play the sound before choosing each picture.", src)
        self.assertIn('normalize_theme_variant(theme) == "sky_tiles"', src)


if __name__ == "__main__":
    unittest.main()
