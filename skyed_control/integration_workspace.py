"""Local-only Course Hub integration cockpit for SkyED Control Panel.

This window never deploys, connects over SSH, edits a captured production file,
or promotes unverified lesson content. The user can select a known site snapshot,
build a verifiable stage, review the report and preview the result on localhost.
"""
from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import re
import sys

from PySide6 import QtCore, QtGui, QtWidgets

def console_python() -> str:
    """pythonw.exe has no stdout: use the matched venv python.exe for QProcess."""
    exe = Path(sys.executable)
    if exe.name.casefold() == "pythonw.exe":
        exe = exe.with_name("python.exe")
    if not exe.is_file():
        raise FileNotFoundError("Expected console Python missing: " + str(exe))
    return str(exe)


PREVIEW_READY = re.compile(r"^SKYED_STAGE_PREVIEW=(http://127\.0\.0\.1:\d+/lobby-preview/)$")


class IntegrationWorkspace(QtWidgets.QDialog):
    def __init__(self, project_root: Path, parent=None):
        super().__init__(parent)
        self.root = project_root.resolve()
        self.engine = self.root / "scripts" / "course_hub_integration.py"
        self.source_path = ""
        self.stage_path = ""
        self.report_path = ""
        self.builder = QtCore.QProcess(self)
        self.preview_process = QtCore.QProcess(self)
        self.builder.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        self.preview_process.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        self.builder.readyReadStandardOutput.connect(self._read_builder)
        self.builder.finished.connect(self._on_build_finished)
        self.preview_process.readyReadStandardOutput.connect(self._read_preview)
        self.setMinimumSize(850, 590)
        self.resize(1050, 750)
        self.setWindowTitle("SkyED · Course Hub Integration — Staged only")
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(15)
        title = QtWidgets.QLabel("Course Hub · Integration workspace")
        title.setStyleSheet("font-size:23px;font-weight:750;")
        layout.addWidget(title)
        description = QtWidgets.QLabel(
            "Safely combine a verified copy of the current Course Hub with the new tile lobby. "
            "The current homepage and all media stay byte-for-byte unchanged. Nothing is deployed."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        source_box = QtWidgets.QGroupBox("1 · Existing Course Hub export (read-only)")
        row = QtWidgets.QHBoxLayout(source_box)
        self.source_input = QtWidgets.QLineEdit()
        self.source_input.setPlaceholderText("Select the original deployed public folder containing index.html and media")
        self.source_input.setAccessibleName("Current Course Hub source folder")
        row.addWidget(self.source_input, 1)
        select = QtWidgets.QPushButton("Browse…")
        select.clicked.connect(self._choose_source)
        row.addWidget(select)
        layout.addWidget(source_box)
        stage_box = QtWidgets.QGroupBox("2 · Build versioned local preview")
        content = QtWidgets.QVBoxLayout(stage_box)
        line = QtWidgets.QHBoxLayout()
        self.stage_button = QtWidgets.QPushButton("Build and verify safe staging")
        self.stage_button.clicked.connect(self._run_stage)
        line.addWidget(self.stage_button)
        self.preview_button = QtWidgets.QPushButton("Preview new lobby")
        self.preview_button.clicked.connect(self._open_preview)
        self.preview_button.setEnabled(False)
        line.addWidget(self.preview_button)
        report_button = QtWidgets.QPushButton("Open review report")
        report_button.clicked.connect(self._open_report)
        line.addWidget(report_button)
        content.addLayout(line)
        self.status = QtWidgets.QLabel("Waiting for a verified current-site source directory")
        self.status.setWordWrap(True)
        content.addWidget(self.status)
        layout.addWidget(stage_box)
        warn = QtWidgets.QLabel("Release gate: 400+ existing media files, 11 source-backed pilot lesson links, no original file changes. "
            "Publication remains disabled until lesson links and live routes are verified.")
        warn.setWordWrap(True)
        warn.setStyleSheet("color:#ad6a00;font-weight:650;")
        layout.addWidget(warn)
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setAccessibleName("Staging and verification log")
        layout.addWidget(self.log, 1)
        footer = QtWidgets.QHBoxLayout()
        instructions = QtWidgets.QPushButton("Copy read-only server capture command")
        instructions.clicked.connect(self._copy_capture_command)
        footer.addWidget(instructions)
        footer.addStretch()
        exit_button = QtWidgets.QPushButton("Close")
        exit_button.clicked.connect(self.close)
        footer.addWidget(exit_button)
        layout.addLayout(footer)

    def _choose_source(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select current Course Hub export")
        if folder:
            self.source_input.setText(folder)

    def _run_stage(self):
        source = Path(self.source_input.text().strip())
        if not source.is_dir() or not (source / "index.html").is_file():
            QtWidgets.QMessageBox.warning(self, "Invalid source", "Select a captured current Course Hub directory containing index.html.")
            return
        if not self.engine.is_file():
            QtWidgets.QMessageBox.critical(self, "Missing integration engine", str(self.engine))
            return
        if self.builder.state() != QtCore.QProcess.ProcessState.NotRunning:
            return
        base = Path.home() / "Documents" / "SkyED-CourseHub-Integration"
        base.mkdir(parents=True, exist_ok=True)
        ident = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self.stage_path = str(base / ("staged-" + ident))
        self.report_path = str(base / ("report-" + ident))
        self.source_path = str(source.resolve())
        self.preview_button.setEnabled(False)
        self.stage_button.setEnabled(False)
        self.status.setText("Copying and verifying original site files into an isolated new staging directory…")
        args = [str(self.engine), "stage", "--source", self.source_path,
                "--lobby", str(self.root / "skyed_lobby" / "site"),
                "--output", self.stage_path, "--report", self.report_path]
        self.builder.setWorkingDirectory(str(self.root))
        self.builder.start(console_python(), args)
        if not self.builder.waitForStarted(3500):
            self.stage_button.setEnabled(True)
            self.status.setText("Could not start local staging; no production changes were attempted.")

    def _read_builder(self):
        self.log.appendPlainText(bytes(self.builder.readAllStandardOutput()).decode("utf-8", "replace"))

    def _on_build_finished(self, code, status):
        self.stage_button.setEnabled(True)
        success = code == 0 and status == QtCore.QProcess.ExitStatus.NormalExit
        self.preview_button.setEnabled(success)
        self.status.setText("Local stage verified — original site files preserved." if success else "Staging blocked; inspect the log. No production changes were made.")
        if success:
            self.log.appendPlainText(f"REPORT={self.report_path}\nSTAGE={self.stage_path}")

    def _open_preview(self):
        if not self.stage_path or not (Path(self.stage_path) / "lobby-preview" / "index.html").is_file():
            return
        if self.preview_process.state() == QtCore.QProcess.ProcessState.NotRunning:
            self.preview_process.setWorkingDirectory(str(self.root))
            self.preview_process.start(console_python(), [str(self.engine), "preview", "--stage", self.stage_path])
        else:
            self.status.setText("Existing local preview is running; open the URL in the log.")

    def _read_preview(self):
        for line in bytes(self.preview_process.readAllStandardOutput()).decode("utf-8", "replace").splitlines():
            match = PREVIEW_READY.fullmatch(line.strip())
            if match:
                url = match.group(1)
                self.log.appendPlainText("READ_ONLY_PREVIEW=" + url)
                QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
            elif line.strip():
                self.log.appendPlainText(line.strip())

    def _open_report(self):
        report = Path(self.report_path) / "integration-report.json" if self.report_path else None
        if report is None or not report.is_file():
            QtWidgets.QMessageBox.information(self,"No report", "Build a verified local stage first.")
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(report)))

    def _copy_capture_command(self):
        cmd = (
            'powershell.exe -NoProfile -ExecutionPolicy Bypass '
            f'-File "{self.root / "scripts" / "Start-SkyED-CourseHub-Integration-v2.4.0.ps1"}" '
            f'-ProjectRoot "{self.root}" -Mode CaptureAndStage'
        )
        QtWidgets.QApplication.clipboard().setText(cmd)
        self.status.setText("Read-only SSH capture command copied. Run in PowerShell to receive the SSH password prompt.")

    def closeEvent(self, event):
        for process in (self.builder,self.preview_process):
            if process.state() != QtCore.QProcess.ProcessState.NotRunning:
                process.terminate()
                if not process.waitForFinished(1500):
                    process.kill()
                    process.waitForFinished(1800)
        super().closeEvent(event)
