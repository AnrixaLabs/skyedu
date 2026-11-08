"""Integrated Course Hub Lobby Designer and Preview for the existing PySide6 app.

Launches a private, ephemeral localhost server only while the workspace is
open. Embeds the actual editing website when Qt WebEngine is installed;
otherwise uses the default browser without changing the draft workflow.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import secrets
import sys
from urllib.parse import urlsplit

from PySide6 import QtCore, QtGui, QtWidgets

ALLOWED_EXTERNAL_HOSTS = frozenset({"skyed.org", "course.skyed.org"})
READY_PATTERN = re.compile(r"^SKYED_LOBBY_READY=(http://127\.0\.0\.1:\d+)$")


def bundle_root(project_root: Path) -> Path:
    return project_root.resolve() / "skyed_lobby"


def verify_bundle(project_root: Path) -> list[str]:
    """Fail explicitly on partial install; do not run an arbitrary script path."""
    root = bundle_root(project_root)
    required = (
        "scripts/control_server.py", "site/index.html", "site/assets/app.js",
        "site/assets/styles.css", "site/content/lobby.json",
        "tools/edit-lobby.html", "tools/editor.js", "tools/editor.css",
    )
    missing = []
    for filename in required:
        target = root / filename
        if not target.is_file() or target.is_symlink() or not target.resolve().is_relative_to(root):
            missing.append(filename)
    return missing


def approved_navigation(url: str, local_origin: str) -> str:
    """Classify a navigation as local, external-approved, or denied."""
    if url == "about:blank":
        return "local"
    parsed = urlsplit(url)
    if (parsed.scheme == "http" and f"{parsed.scheme}://{parsed.netloc}" == local_origin
            and parsed.hostname == "127.0.0.1" and not parsed.username and not parsed.password):
        return "local"
    if parsed.scheme == "https" and parsed.hostname in ALLOWED_EXTERNAL_HOSTS and not parsed.username and not parsed.password:
        return "external"
    return "deny"


class LobbyWorkspace(QtWidgets.QDialog):
    """A first-class app workspace, not just an untracked website shortcut."""
    def __init__(self, project_root: Path, parent=None, initial_view: str = "editor"):
        super().__init__(parent)
        if initial_view not in {"editor", "preview"}:
            raise ValueError("Invalid initial lobby view")
        self.project_root = Path(project_root).resolve()
        self.initial_view = initial_view
        self.origin = ""
        self.buffer = ""
        self._error = ""
        self.process: QtCore.QProcess | None = None
        self.browser = None
        self._startup_timer = QtCore.QTimer(self)
        self._startup_timer.setSingleShot(True)
        self._startup_timer.setInterval(12000)
        self._startup_timer.timeout.connect(self._startup_failed)
        self.setWindowTitle("SkyED · Course Hub Lobby Designer")
        self.setMinimumSize(900, 620)
        self.resize(1420, 920)
        self._create_ui()
        self._start()

    def _create_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        top = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("COURSE HUB  /  DESIGN STUDIO")
        title.setStyleSheet("font-size:17px;font-weight:750;")
        top.addWidget(title, 1)
        self.editor_button = QtWidgets.QPushButton("Edit content")
        self.preview_button = QtWidgets.QPushButton("Live preview")
        self.browser_button = QtWidgets.QPushButton("Open in browser")
        self.folder_button = QtWidgets.QPushButton("Open draft folder")
        for widget in (self.editor_button, self.preview_button, self.browser_button, self.folder_button):
            widget.setMinimumHeight(38)
            top.addWidget(widget)
        self.editor_button.clicked.connect(lambda: self._navigate("editor"))
        self.preview_button.clicked.connect(lambda: self._navigate("preview"))
        self.browser_button.clicked.connect(self._open_browser)
        self.folder_button.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(str(bundle_root(self.project_root) / "site" / "content"))))
        layout.addLayout(top)
        self.status = QtWidgets.QLabel("Starting local preview server…")
        self.status.setStyleSheet("color:#62738a;font-size:12px;")
        layout.addWidget(self.status)
        self.frame = QtWidgets.QStackedWidget()
        layout.addWidget(self.frame, 1)
        self.loading = QtWidgets.QLabel("Preparing the private lobby preview…")
        self.loading.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.loading.setWordWrap(True)
        self.frame.addWidget(self.loading)
        self.footer = QtWidgets.QLabel("LOCAL DRAFT ONLY  ·  Changes are not published to course.skyed.org")
        self.footer.setStyleSheet("color:#617089;font-size:11px;")
        layout.addWidget(self.footer)

    def _start(self):
        missing = verify_bundle(self.project_root)
        if missing:
            self._failed("The Lobby Designer installation is incomplete: " + ", ".join(missing))
            return
        script = bundle_root(self.project_root) / "scripts" / "control_server.py"
        self.process = QtCore.QProcess(self)
        self.process.setWorkingDirectory(str(self.project_root))
        self.process.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        env = QtCore.QProcessEnvironment.systemEnvironment()
        env.insert("SKYED_LOBBY_EDITOR_TOKEN", secrets.token_urlsafe(40))
        env.insert("PYTHONUNBUFFERED", "1")
        self.process.setProcessEnvironment(env)
        self.process.readyReadStandardOutput.connect(self._read_process)
        self.process.errorOccurred.connect(self._process_error)
        self.process.finished.connect(self._process_finished)
        # Desktop shortcuts use pythonw.exe, which has no usable stdout pipe.
        # The private server must use the matching console interpreter so QProcess
        # receives its ready handshake. Never use a different Python environment.
        interpreter = Path(sys.executable)
        if interpreter.name.casefold() == "pythonw.exe":
            interpreter = interpreter.with_name("python.exe")
        if not interpreter.is_file():
            self._failed("Matching Python interpreter is unavailable: " + str(interpreter))
            return
        self.process.start(str(interpreter), ["-u", str(script), "--port", "0"])
        self._startup_timer.start()

    def _read_process(self):
        if self.process is None:
            return
        self.buffer += bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        if len(self.buffer) > 8192:
            self.buffer = self.buffer[-8192:]
        for line in self.buffer.splitlines():
            match = READY_PATTERN.fullmatch(line.strip())
            if match and not self.origin:
                self.origin = match.group(1)
                self._startup_timer.stop()
                self.status.setText("Workspace connected  ·  Editing a private local draft")
                self._setup_view()
                self._navigate(self.initial_view)
                break

    def _setup_view(self):
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            from PySide6.QtWebEngineCore import QWebEnginePage
        except (ImportError, RuntimeError):
            self.loading.setText("The private editor is ready. Qt WebEngine is unavailable in this Python environment.\nUse Open in browser to edit or preview.")
            self.frame.setCurrentWidget(self.loading)
            self._open_browser()
            return
        workspace = self

        class RestrictedPage(QWebEnginePage):
            def acceptNavigationRequest(self, url, nav_type, is_main_frame):
                classification = approved_navigation(url.toString(), workspace.origin)
                if classification == "local":
                    return True
                if classification == "external" and nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
                    QtGui.QDesktopServices.openUrl(url)
                return False

            def createWindow(self, _type):
                # Open new-window requests in a controlled external browser only
                # through explicit user actions in the main workspace.
                return None

        self.browser = QWebEngineView(self.frame)
        self.browser.setPage(RestrictedPage(self.browser))
        self.frame.addWidget(self.browser)
        self.frame.setCurrentWidget(self.browser)
        self.browser.loadFinished.connect(self._page_loaded)

    def _page_loaded(self, ok: bool):
        if not ok:
            self.status.setText("Preview page failed to load. Open in browser to check local access.")

    def _navigate(self, view: str):
        if not self.origin:
            return
        if view not in {"editor", "preview"}:
            return
        self.initial_view = view
        self.editor_button.setEnabled(view != "editor")
        self.preview_button.setEnabled(view != "preview")
        url = self.origin + ("/tools/edit-lobby.html" if view == "editor" else "/site/")
        if self.browser is not None:
            self.browser.setUrl(QtCore.QUrl(url))
        else:
            self.status.setText("Ready  ·  use Open in browser (Qt WebEngine not installed)")

    def _open_browser(self):
        if not self.origin:
            return
        url = self.origin + ("/tools/edit-lobby.html" if self.initial_view == "editor" else "/site/")
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def _process_error(self, _):
        if self.isVisible():
            self._failed("The private preview server failed to start. Verify your Python installation and the bundled editor files.")

    def _process_finished(self, exit_code: int, _status):
        if self.isVisible() and not self._error:
            self._failed(f"The local preview process stopped unexpectedly (exit {exit_code}).")

    def _startup_failed(self):
        if not self.origin:
            self._failed("The local preview server did not signal readiness. Verify the installed source tree.")

    def _failed(self, message: str):
        self._error = message
        self._startup_timer.stop()
        self.loading.setText(message)
        self.frame.setCurrentWidget(self.loading)
        self.status.setText("Lobby Designer unavailable")
        self.editor_button.setEnabled(False)
        self.preview_button.setEnabled(False)

    def closeEvent(self, event):
        self._startup_timer.stop()
        if self.browser is not None:
            self.browser.setUrl(QtCore.QUrl("about:blank"))
        if self.process is not None:
            self.process.readyReadStandardOutput.disconnect(self._read_process)
            if self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
                self.process.terminate()
                if not self.process.waitForFinished(1700):
                    self.process.kill()
                    self.process.waitForFinished(1500)
        super().closeEvent(event)
