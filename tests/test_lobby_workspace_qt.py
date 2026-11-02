"""Qt wiring acceptance: launch the actual private server from the control panel.

The web renderer is independently exercised in the real Chromium browser gate.
This test checks Qt signals, QProcess boot, app routing and teardown without
starting the heavier QtWebEngine GPU process in headless CI.
"""
from __future__ import annotations

import os
from pathlib import Path
import time
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets
from skyed_control.registry import task_by_key
from skyed_control.lobby_workspace import LobbyWorkspace, verify_bundle

PROJECT = Path(__file__).resolve().parents[1]


class NativeLobbyWiringTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_integration_bundle_and_registry(self):
        self.assertEqual(verify_bundle(PROJECT), [])
        self.assertEqual(task_by_key("lobby-designer").route, "lobby")
        self.assertEqual(task_by_key("lobby-preview").target, "preview")

    def test_qprocess_handshake_and_teardown(self):
        with patch.object(LobbyWorkspace, "_setup_view", autospec=True) as embed:
            dialog = LobbyWorkspace(PROJECT, initial_view="editor")
            dialog.show()
            try:
                deadline = time.monotonic() + 8
                while not dialog.origin and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.02)
                self.assertTrue(dialog.origin.startswith("http://127.0.0.1:"), dialog._error)
                self.assertTrue(embed.called)
                self.assertTrue(dialog.process is not None and dialog.process.state())
                dialog._navigate("preview")
                self.assertEqual(dialog.initial_view, "preview")
            finally:
                dialog.close()
                self.app.processEvents()
            self.assertEqual(dialog.process.state(), dialog.process.ProcessState.NotRunning)
