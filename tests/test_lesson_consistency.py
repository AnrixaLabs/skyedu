import unittest
from skyed.lesson_consistency import unused_vocabulary, correct_consistency_report


class LessonConsistencyTests(unittest.TestCase):
    def test_family_house_lesson_181_and_182(self):
        words = ["bedroom", "bathroom", "kitchen", "living room", "house", "family",
                 "grandma", "grandpa", "daddy", "mommy", "brother", "sister", "baby"]
        sentences = [
            "This is my grandma.", "This is my mommy.",
            "This is my sister.", "This is my brother.", "This is a baby.",
            "The baby is in the living room.", "Grandpa is in the kitchen.",
            "Mommy is in the bathroom.",
        ]
        spec = {"vocab": [{"en": w} for w in words],
                "sentences": [{"en": s} for s in sentences]}
        self.assertEqual(unused_vocabulary(spec), ["bedroom", "house", "family", "daddy"])

    def test_preserve_extra_report_fields(self):
        spec = {"vocab": [{"en": "cat"}], "sentences": [{"en": "cat!"}]}
        self.assertEqual(correct_consistency_report(spec, {"ok": 3}),
                         {"ok": 3, "vocab_not_seen_in_sentences": []})

    def test_word_boundaries(self):
        spec = {"vocab": [{"en": "cat"}, {"en": "at"}], "sentences": [{"en": "Cats are cute."}]}
        self.assertEqual(unused_vocabulary(spec), ["cat", "at"])


if __name__ == "__main__":
    unittest.main()
