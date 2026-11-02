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
        valid = {"legacy", "folder", "website", "diagnostics", "settings", "lobby"}
        self.assertEqual({item.route for item in TASKS}, valid)
        self.assertEqual(task_by_key("lobby-designer").target, "editor")
        self.assertEqual(task_by_key("lobby-preview").target, "preview")
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


    def test_legacy_ui_tab_names_and_methods_are_still_wired(self):
        """Guard against accidentally breaking a tile by renaming the classic UI."""
        import re
        source = Path(__file__).resolve().parents[1] / "pyside_gui.py"
        raw = source.read_text(encoding="utf-8")
        existing_tabs = set(re.findall(r'self\.right_tabs\.addTab\([^\n]+,\s*"([^"]+)"\)', raw))
        expected_tabs = {task.legacy_tab for task in TASKS if task.route == "legacy"}
        self.assertTrue(expected_tabs <= existing_tabs, sorted(expected_tabs - existing_tabs))
        self.assertRegex(raw, r"(?m)^    def open_asset_batcher\(self\)")
        self.assertRegex(raw, r"(?m)^    def open_card_cutter\(self\)")
        self.assertRegex(raw, r"(?m)^    def run_pipeline\(self,\s*mode:")
        self.assertRegex(raw, r"(?m)^    def run_ng_pipeline\(self,\s*mode:")


if __name__ == "__main__":
    unittest.main()
