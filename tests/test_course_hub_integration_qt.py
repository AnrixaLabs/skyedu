"""Native Qt wiring test: staging UI remains non-mutating until clicked."""
from pathlib import Path
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

try:
    from PySide6 import QtWidgets
except ModuleNotFoundError as exc:
    if exc.name != 'PySide6':
        raise
    QtWidgets = None

if QtWidgets is not None:
    from skyed_control.integration_workspace import IntegrationWorkspace, console_python
    from skyed_control.registry import task_by_key
else:
    IntegrationWorkspace = None
    console_python = None


@unittest.skipIf(QtWidgets is None, 'PySide6 unavailable: dedicated desktop CI installs it')
class IntegrationNativeUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_registry_and_ui_do_not_connect_on_load(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(task_by_key('course-integration').route, 'integration')
        view = IntegrationWorkspace(root)
        try:
            view.show()
            self.app.processEvents()
            self.assertFalse(view.preview_button.isEnabled())
            self.assertEqual(view.builder.state(), view.builder.ProcessState.NotRunning)
            self.assertEqual(view.preview_process.state(), view.preview_process.ProcessState.NotRunning)
            self.assertTrue(console_python().lower().endswith(('python.exe', '/python', '/python3')) or 'python' in console_python().lower())
        finally:
            view.close()
            self.app.processEvents()


if __name__ == '__main__':
    unittest.main()
