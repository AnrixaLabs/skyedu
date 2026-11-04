"""UI smoke without network, backend credentials or opening the legacy app."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtWidgets
except ModuleNotFoundError as exc:
    if exc.name != "PySide6":
        raise
    QtWidgets = None

if QtWidgets is not None:
    from skyed_control_panel import ControlPanel
else:
    ControlPanel = None


@unittest.skipIf(QtWidgets is None, "Requires PySide6; the dedicated desktop CI installs it")
class ControlPanelQtTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.window = ControlPanel()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_every_section_draws(self):
        for section in ("HOME", "CREATE", "OPERATE", "WEBSITES", "SYSTEM"):
            self.window.show_section(section)
            self.app.processEvents()
            self.assertEqual(self.window.section, section)

    def test_appearance_and_local_status(self):
        initial = self.window.dark
        self.window.toggle_theme()
        self.assertNotEqual(initial, self.window.dark)
        self.window.toggle_theme()
        self.assertEqual(initial, self.window.dark)
        self.window.open_task("diagnostics")
        self.window.open_task("settings")
        self.app.processEvents()

    def test_dashboard_does_not_launch_old_app(self):
        self.window.show()
        self.app.processEvents()
        self.assertIsNone(self.window.legacy)


    def test_legacy_routes_use_existing_workroom_without_executing_publish(self):
        """Mock just the heavyweight legacy GUI; verify actual new GUI delegation."""
        import sys
        import types
        from pathlib import Path
        from unittest.mock import patch

        class FakeLegacyWindow:
            def __init__(self, *_args):
                self.right_tabs = QtWidgets.QTabWidget()
                for label in ("Quick", "Audio", "Images", "Batch", "tag_s Creator",
                              "NG", "Publish", "Picture Reader"):
                    self.right_tabs.addTab(QtWidgets.QWidget(), label)
                self.batcher_launches = 0
                self.cutter_launches = 0
                self.publish_runs = 0

            def showMaximized(self): pass
            def raise_(self): pass
            def activateWindow(self): pass

            def open_asset_batcher(self):
                self.batcher_launches += 1

            def open_card_cutter(self):
                self.cutter_launches += 1

        module = types.ModuleType("pyside_gui")
        module.CONFIG_NAME = "gui_config.json"
        module.load_dotenv = lambda **_kw: None
        module.load_config = lambda _path, root_dir: types.SimpleNamespace(
            project_python=sys.executable, project_workdir=str(root_dir)
        )
        module.MainWindow = FakeLegacyWindow
        with patch.dict(sys.modules, {"pyside_gui": module}):
            self.window.open_task("assets")
            self.assertEqual(self.window.legacy.batcher_launches, 1)
            self.window.open_task("cutter")
            self.assertEqual(self.window.legacy.cutter_launches, 1)
            self.window.open_task("publish")
            tab = self.window.legacy.right_tabs
            self.assertEqual(tab.tabText(tab.currentIndex()), "Publish")
            self.assertEqual(self.window.legacy.publish_runs, 0)


if __name__ == "__main__":
    unittest.main()
