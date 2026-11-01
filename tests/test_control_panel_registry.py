"""Pure tests for every desktop navigation target (no Qt dependencies)."""
from pathlib import Path
import tempfile
import unittest

from skyed_control.registry import TASKS, task_by_key, searchable, validate_catalog, local_diagnostics


class ControlPanelRegistryTest(unittest.TestCase):
    def test_catalog_is_valid_and_unique(self):
        validate_catalog()
        self.assertEqual(len(TASKS), len({task.key for task in TASKS}))
        self.assertGreaterEqual(len(TASKS), 15)

    def test_every_route_is_real(self):
        valid = {"legacy", "folder", "website", "diagnostics", "settings"}
        self.assertEqual({item.route for item in TASKS}, valid)
        self.assertEqual(task_by_key("tags").legacy_tab, "tag_s Creator")
        self.assertEqual(task_by_key("ng").legacy_tab, "NG")
        self.assertEqual(task_by_key("reader").legacy_tab, "Picture Reader")

    def test_search_filters_all_words(self):
        self.assertEqual([x.key for x in searchable("card cutter")], ["cutter"])
        self.assertIn("audio", [x.key for x in searchable("voice")])
        self.assertEqual(searchable("impossible phrase 773299"), [])

    def test_no_unapproved_external_hosts(self):
        for item in TASKS:
            if item.route == "website":
                self.assertTrue(item.target.startswith("https://"))
                self.assertIn(item.target.split("/")[2], {
                    "course.skyed.org", "portal.skyed.org",
                    "growth.skyed.org", "skyed.org",
                })

    def test_diagnostics_are_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = tuple(root.iterdir())
            checks = local_diagnostics(root)
            self.assertTrue(checks)
            self.assertEqual(tuple(root.iterdir()), before)
            self.assertFalse(next(ok for title, ok, _ in checks if title == "Homework generator"))
            self.assertFalse(next(ok for title, ok, _ in checks if title == "Legacy control panel"))


if __name__ == "__main__":
    unittest.main()
