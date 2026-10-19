import tempfile
import unittest
from pathlib import Path

from skyed.publish_gates import (
    PublishGateError, validate_destination, validate_local_media,
    validate_remote_payload,
)


class PublishGateTests(unittest.TestCase):
    def test_only_expected_https_domain(self):
        self.assertEqual(validate_destination("https://skyed.org/"), "skyed.org")
        for host in ("https://skyedu.fun", "http://skyed.org",
                     "https://skyed.org.attacker.invalid", "https://skyed.org/evil",
                     "https://user:pass@skyed.org", "https://skyed.org:8443"):
            with self.subTest(host=host), self.assertRaises(PublishGateError):
                validate_destination(host)

    def test_media_missing_blocks_before_publication(self):
        spec = {"vocab": [{"en": "cat", "zh": "猫"}],
                "sentences": [{"en": "Hi.", "zh": "你好。"}]}
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            kwargs = {"card_stem": lambda s: "cat",
                      "sentence_stem": lambda s: "hi"}
            with self.assertRaisesRegex(PublishGateError, "Missing"):
                validate_local_media(root, spec, **kwargs)
            for rel in ("cards/cat.png", "audio/en/cat.mp3", "audio/zh/cat.mp3",
                        "audio/en/sent_hi.mp3", "audio/zh/sent_hi.mp3"):
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes((b"\x89PNG\r\n\x1a\n" + b"x" * 64) if p.suffix == ".png" else (b"ID3" + b"x" * 1200))
            self.assertEqual(validate_local_media(root, spec, **kwargs)["status"], "PASS")
            (root / "audio" / "en" / "cat.mp3").write_bytes(b"bad")
            with self.assertRaisesRegex(PublishGateError, "Too-small"):
                validate_local_media(root, spec, **kwargs)

    def test_quiz_remote_urls_must_be_rewritten(self):
        original = {"questions": [{"prompt_audio": "audio/en/cat.mp3",
                                   "choices": [{"img": "cards/cat.png"}]}]}
        base = {"vocab": [{"en": "cat", "img": "https://skyed.org/cat.png",
                            "audio_en": "https://skyed.org/cat.mp3",
                            "audio_zh": "https://skyed.org/cat-zh.mp3"}],
                "sentences": [], "practice": {"questions": [
                    {"prompt_audio": "https://skyed.org/cat.mp3",
                     "choices": [{"img": "https://skyed.org/cat.png"}]}]}}
        self.assertEqual(validate_remote_payload(base, original)["status"], "PASS")
        base["practice"]["questions"][0]["prompt_audio"] = ""
        with self.assertRaises(PublishGateError):
            validate_remote_payload(base, original)


if __name__ == "__main__":
    unittest.main()
