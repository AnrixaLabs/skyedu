"""UI smoke without network, backend credentials or opening the legacy app."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtWidgets
    from skyed_control_panel import ControlPanel
except ImportError:
    QtWidgets = None
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


if __name__ == "__main__":
    unittest.main()
