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
ROOT_READY = re.compile(r"^SKYED_V250_ROOT_PREVIEW=(http://127\.0\.0\.1:\d+/)$")


class IntegrationWorkspace(QtWidgets.QDialog):
    def __init__(self, project_root: Path, parent=None):
        super().__init__(parent)
        self.root = project_root.resolve()
        self.engine = self.root / "scripts" / "course_hub_integration.py"
        self.release_engine = self.root / "scripts" / "course_hub_release.py"
        self.release_stage_path = ""
        self.release_report_path = ""
        self._build_kind = "stage"
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
        self.setWindowTitle("SkyED · Course Hub Studio & Release Pipeline v2.5.0")
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(15)
        title = QtWidgets.QLabel("Course Hub · Integration workspace")
        title.setStyleSheet("font-size:23px;font-weight:750;")
        layout.addWidget(title)
        description = QtWidgets.QLabel(
            "Edit the Bright Course Hub, preview its real courses, and build a versioned release candidate. "
            "The captured website remains immutable; production deployment requires separate teacher review and explicit authorization."
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
        # Preselect the newest existing captured snapshot so ordinary local editing
        # doesn't require hunting through timestamped directories.
        snapshots = Path.home() / "Documents" / "SkyED-CourseHub-Integration"
        if snapshots.is_dir():
            options = [f for f in snapshots.glob("snapshot-*") if (f / "index.html").is_file()]
            if options:
                self.source_input.setText(str(max(options, key=lambda d: d.stat().st_mtime)))
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
        new_line = QtWidgets.QHBoxLayout()
        self.release_button = QtWidgets.QPushButton("Build full Bright root candidate")
        self.release_button.setObjectName("build-bright-root")
        self.release_button.setToolTip("Safe local release with Bright homepage at /; original available at /classic.html")
        self.release_button.clicked.connect(self._run_release)
        new_line.addWidget(self.release_button)
        self.root_preview_button = QtWidgets.QPushButton("Preview full Bright website")
        self.root_preview_button.clicked.connect(self._open_root_preview)
        self.root_preview_button.setEnabled(False)
        new_line.addWidget(self.root_preview_button)
        content.addLayout(new_line)
        self.status = QtWidgets.QLabel("Waiting for a verified current-site source directory")
        self.status.setWordWrap(True)
        content.addWidget(self.status)
        layout.addWidget(stage_box)
        warn = QtWidgets.QLabel("Release gate: 400+ original media, 11 authentic lesson links, source hash parity, "
            "teacher review and fresh server preflight. Root preview is safe locally; publishing is never automatic.")
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
        preflight = QtWidgets.QPushButton("Copy production preflight")
        preflight.clicked.connect(self._copy_preflight_command)
        footer.addWidget(preflight)
        publish = QtWidgets.QPushButton("Copy gated publish command")
        publish.clicked.connect(self._copy_publish_command)
        footer.addWidget(publish)
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
        self._build_kind = "stage"
        self.stage_path = str(base / ("staged-" + ident))
        self.report_path = str(base / ("report-" + ident))
        self.source_path = str(source.resolve())
        self.preview_button.setEnabled(False)
        self.stage_button.setEnabled(False)
        self.release_button.setEnabled(False)
        self.status.setText("Copying and verifying original site files into an isolated new staging directory…")
        args = [str(self.engine), "stage", "--source", self.source_path,
                "--lobby", str(self.root / "skyed_lobby" / "site"),
                "--output", self.stage_path, "--report", self.report_path]
        self.builder.setWorkingDirectory(str(self.root))
        self.builder.start(console_python(), args)
        if not self.builder.waitForStarted(3500):
            self.stage_button.setEnabled(True)
            self.status.setText("Could not start local staging; no production changes were attempted.")

    def _run_release(self):
        source = Path(self.source_input.text().strip())
        if not source.is_dir() or not (source / "index.html").is_file():
            QtWidgets.QMessageBox.warning(self, "Invalid capture", "Select the original captured Course Hub folder containing index.html.")
            return
        if not self.release_engine.is_file():
            QtWidgets.QMessageBox.critical(self, "Missing Bright release builder", str(self.release_engine))
            return
        if self.builder.state() != QtCore.QProcess.ProcessState.NotRunning:
            return
        base = Path.home() / "Documents" / "SkyED-CourseHub-Integration"
        base.mkdir(parents=True, exist_ok=True)
        ident = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self.release_stage_path = str(base / ("bright-candidate-" + ident))
        self.release_report_path = str(base / ("bright-report-" + ident))
        self.source_path = str(source.resolve())
        self._build_kind = "release"
        self.root_preview_button.setEnabled(False)
        self.release_button.setEnabled(False)
        self.stage_button.setEnabled(False)
        self.status.setText("Building a verified Bright homepage and preserving classic.html + all original media…")
        args = [str(self.release_engine), "build", "--source", self.source_path,
                "--lobby", str(self.root / "skyed_lobby" / "site"),
                "--output", self.release_stage_path, "--report", self.release_report_path]
        self.builder.setWorkingDirectory(str(self.root))
        self.builder.start(console_python(), args)
        if not self.builder.waitForStarted(3500):
            self.stage_button.setEnabled(True)
            self.release_button.setEnabled(True)
            self.status.setText("Could not start Bright candidate builder; production is unchanged.")

    def _read_builder(self):
        self.log.appendPlainText(bytes(self.builder.readAllStandardOutput()).decode("utf-8", "replace"))

    def _on_build_finished(self, code, status):
        self.stage_button.setEnabled(True)
        self.release_button.setEnabled(True)
        success = code == 0 and status == QtCore.QProcess.ExitStatus.NormalExit
        if self._build_kind == "release":
            self.root_preview_button.setEnabled(success)
            self.status.setText("Bright root candidate verified. Original homepage stored at /classic.html; production unchanged." if success else "Bright release blocked; inspect log. Production unchanged.")
            if success:
                self.log.appendPlainText(f"BRIGHT_REPORT={self.release_report_path}\nBRIGHT_CANDIDATE={self.release_stage_path}")
        else:
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

    def _open_root_preview(self):
        candidate = Path(self.release_stage_path) if self.release_stage_path else None
        if candidate is None or not (candidate / "assets" / "bright" / "app.js").is_file():
            return
        if self.preview_process.state() != QtCore.QProcess.ProcessState.NotRunning:
            self.preview_process.terminate()
            if not self.preview_process.waitForFinished(2000):
                self.preview_process.kill()
                self.preview_process.waitForFinished(1500)
        self.preview_process.setWorkingDirectory(str(self.root))
        self.preview_process.start(console_python(), [str(self.release_engine), "preview", "--candidate", str(candidate)])

    def _copy_preflight_command(self):
        if not self.release_stage_path or not self.release_report_path:
            self.status.setText("Build a Bright root candidate first.")
            return
        command = (f'"{console_python()}" "{self.root / "scripts" / "course_hub_deploy.py"}" '
                   f'--mode preflight --server-ip 8.210.9.172 '
                   f'--source "{self.source_path}" --candidate "{self.release_stage_path}" '
                   f'--report "{self.release_report_path}"')
        QtWidgets.QApplication.clipboard().setText(command)
        self.status.setText("Read-only preflight copied. Verify server identity before connecting; no server changes performed.")

    def _copy_publish_command(self):
        if not self.release_stage_path or not self.release_report_path:
            self.status.setText("Build and review a Bright root candidate first.")
            return
        self.status.setText("Publication requires a fully signed teacher-review file and a successful remote preflight; no action performed.")
        receipt = str(Path(self.release_report_path) / "deployment-receipt.json")
        approval = str(Path(self.release_report_path) / "teacher-review-template.json")
        command = (f'"{console_python()}" "{self.root / "scripts" / "course_hub_deploy.py"}" '
                   f'--mode deploy --server-ip 8.210.9.172 '
                   f'--source "{self.source_path}" --candidate "{self.release_stage_path}" '
                   f'--report "{self.release_report_path}" --approval "{approval}" '
                   f'--receipt "{receipt}" --confirm "PUBLISH SKYED BRIGHT 2.5.0"')
        QtWidgets.QApplication.clipboard().setText(command)

    def _read_preview(self):
        for line in bytes(self.preview_process.readAllStandardOutput()).decode("utf-8", "replace").splitlines():
            match = PREVIEW_READY.fullmatch(line.strip()) or ROOT_READY.fullmatch(line.strip())
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
