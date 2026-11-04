import json
import tempfile
import unittest
from pathlib import Path

from skyed.publish_gates import PublishGateError, validate_image_source_quality


class ImagePublicationGateTests(unittest.TestCase):
    SPEC = {"vocab": [{"en": "cat"}, {"en": "dog"}], "sentences": []}

    def write_report(self, root, rows):
        cards = root / "cards"
        cards.mkdir(exist_ok=True)
        (cards / "image_report.json").write_text(
            json.dumps(rows, ensure_ascii=False), encoding="utf-8"
        )

    def test_missing_report_blocks_publication(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(PublishGateError, "report unavailable"):
                validate_image_source_quality(Path(d), self.SPEC)

    def test_placeholders_and_deterministic_fallback_block(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.write_report(root, [
                {"word": "cat", "status": "local_asset_missing_placeholder"},
                {"word": "dog", "status": "local_asset_missing_deterministic_fallback"},
            ])
            with self.assertRaisesRegex(PublishGateError, "cat: local_asset_missing_placeholder"):
                validate_image_source_quality(root, self.SPEC)

    def test_normal_assets_pass_machine_gate_but_require_teacher(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.write_report(root, [
                {"word": "cat", "status": "local_asset_match"},
                {"word": "dog", "status": "accepted"},
            ])
            result = validate_image_source_quality(root, self.SPEC)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["checked"], 2)
            self.assertEqual(result["teacher_visual_review"], "REQUIRED")

    def test_missing_vocab_image_row_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.write_report(root, [{"word": "cat", "status": "accepted"}])
            with self.assertRaisesRegex(PublishGateError, "dog: missing"):
                validate_image_source_quality(root, self.SPEC)

    def test_picture_reader_does_not_use_vocab_gate(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(
                validate_image_source_quality(Path(d), self.SPEC,
                                              page_kind="picture_reader")["status"],
                "PASS",
            )

if __name__ == "__main__":
    unittest.main()
