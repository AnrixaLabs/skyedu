import unittest
from skyed.kids_homework import generate_kids_homework, required_media


class KidsHomeworkTests(unittest.TestCase):
    def test_deterministic_audio_first(self):
        spec = {"title": "Animals", "vocab": [
            {"en": "cat", "zh": "猫"}, {"en": "dog", "zh": "狗"},
            {"en": "bird", "zh": "鸟"}], "sentences": [{"en": "It's a cat!"}]}
        a = generate_kids_homework(spec)
        self.assertEqual(a, generate_kids_homework(spec))
        self.assertEqual([x["type"] for x in a["activities"]],
                         ["listen", "repeat", "listen_and_choose", "speak_with_parent"])
        self.assertIn("audio/en/cat.mp3", required_media(a))

    def test_short_lesson_no_fake_choices(self):
        a = generate_kids_homework({"vocab": [{"en": "hello"}]})
        self.assertEqual([x["type"] for x in a["activities"]], ["listen", "repeat"])

    def test_empty_lesson_rejected(self):
        with self.assertRaises(ValueError):
            generate_kids_homework({"vocab": []})


if __name__ == "__main__":
    unittest.main()
