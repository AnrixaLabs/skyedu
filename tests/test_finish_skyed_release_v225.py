"""Offline release-controller contract tests (no production access)."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from scripts.finish_skyed_renderer_v225 import (
    EXPECTED_ZIP, OLD_PHP, NEW_PHP, check_images,
    parse_fields, sha256, ReleaseFailure,
)


class ReleaseContractTests(unittest.TestCase):
    def test_pinned_candidate(self):
        self.assertEqual(len(EXPECTED_ZIP), 64)
        self.assertEqual(len(OLD_PHP), 64)
        self.assertEqual(len(NEW_PHP), 64)
        self.assertNotEqual(OLD_PHP, NEW_PHP)

    def test_machine_readable_status(self):
        self.assertEqual(parse_fields("STATUS=INSTALLED_V048\nFPM=PASS\n"),
                         {"STATUS": "INSTALLED_V048", "FPM": "PASS"})
        self.assertEqual(parse_fields("warning: harmless\n"), {})

    def test_hash_calculation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.bin"
            path.write_bytes(b"safe")
            self.assertEqual(sha256(path), hashlib.sha256(b"safe").hexdigest())

    def fixture(self, defects=(), *, count=20, practice=6):
        return {"lesson181-390": {"images": {"count": count,
                "practice_count": practice, "defects": list(defects)}}}

    def test_preexisting_broken_image_accepted(self):
        original = {"id": "source-hash", "inside": True, "pending": False}
        check_images(self.fixture([original]), self.fixture([original]))

    def test_repaired_image_accepted(self):
        original = {"id": "source-hash", "inside": True, "pending": False}
        check_images(self.fixture([original]), self.fixture([]))

    def test_new_image_fault_blocks(self):
        original = {"id": "source-hash", "inside": True, "pending": False}
        new = {"id": "different", "inside": True, "pending": False}
        with self.assertRaises(ReleaseFailure):
            check_images(self.fixture([original]), self.fixture([original, new]))

    def test_duplicate_of_existing_broken_image_blocks(self):
        old = {"id": "same", "inside": True, "pending": False}
        with self.assertRaises(ReleaseFailure):
            check_images(self.fixture([old]), self.fixture([old, old]))

    def test_moved_fault_into_practice_blocks(self):
        old = {"id": "same", "inside": False, "pending": False}
        new = {"id": "same", "inside": True, "pending": False}
        with self.assertRaises(ReleaseFailure):
            check_images(self.fixture([old]), self.fixture([new]))

    def test_missing_images_blocks(self):
        with self.assertRaises(ReleaseFailure):
            check_images(self.fixture(count=20), self.fixture(count=19))
        with self.assertRaises(ReleaseFailure):
            check_images(self.fixture(practice=6), self.fixture(practice=5))

    def test_remote_release_is_pinned_and_narrow(self):
        remote = Path(__file__).resolve().parents[1] / "scripts" / "skyed_renderer_remote_v225.sh"
        text = remote.read_text(encoding="utf-8")
        for required in ("set -Eeuo pipefail", "watchdog", "skyed_org", "wpml_",
                         "runuser -u www-data", "COMMITTED", "ROLLED_BACK",
                         "rollback", "skyed-lesson-renderer", NEW_PHP, OLD_PHP,
                         EXPECTED_ZIP):
            if required == "rollback":
                # The Bash implementation uses restore(), a synonym for rollback.
                required = "restore()"
            self.assertIn(required, text)
        self.assertNotIn("wp post update", text)
        self.assertNotIn("wp db import", text)


if __name__ == "__main__":
    unittest.main()
