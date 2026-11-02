"""SkyED Control Panel 2.3 — modern Windows shell over the proven legacy workflows.

No legacy module is replaced, no production action runs on startup, and no
credentials are copied into Qt settings or logs. Start with pythonw.exe.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from skyed_control.registry import TASKS, Task, local_diagnostics, searchable, task_by_key

ROOT = Path(__file__).resolve().parent
APP_VERSION = "2.3.0"
SECTIONS = ("CREATE", "OPERATE", "WEBSITES", "SYSTEM")


def _theme(dark: bool) -> str:
    background, surface, raised, text, muted, border, accent = (
        ("#0b1220", "#111d30", "#18283f", "#eff5ff", "#a5b6ce", "#2a3d58", "#6cb7ff")
        if dark else
        ("#f4f7fc", "#ffffff", "#eaf1fc", "#14253e", "#65778e", "#dce5f2", "#1764ce")
    )
    return f"""
    QWidget#Shell {{background:{background}; color:{text};}}
    QFrame#Sidebar, QFrame#Panel, QFrame#TaskCard {{
        background:{surface}; border:1px solid {border}; border-radius:16px;
    }}
    QFrame#Sidebar {{border-radius:0; border:0; border-right:1px solid {border};}}
    QLabel {{color:{text}; background:transparent;}}
    QLabel#Muted, QLabel#Description {{color:{muted};}}
    QLabel#Title {{font-size:27px; font-weight:750;}}
    QLabel#Brand {{font-size:22px; font-weight:800;}}
    QLabel#Section {{font-size:11px; font-weight:800; color:{muted};}}
    QLineEdit {{background:{surface};color:{text};border:1px solid {border};
               border-radius:12px;padding:11px;font-size:13px;}}
    QLineEdit:focus {{border:2px solid {accent};}}
    QPushButton {{background:{raised};color:{text};border:1px solid {border};
                  border-radius:11px;padding:10px 14px;text-align:left;font-weight:600;}}
    QPushButton:hover {{border-color:{accent};}}
    QPushButton#Primary {{background:{accent};color:#ffffff;border:0;text-align:center;}}
    QPushButton#Nav {{background:transparent;border:0;padding:13px 15px;}}
    QPushButton#Nav:checked {{background:{raised};border-left:4px solid {accent};}}
    QPushButton#CardAction {{background:{raised};border:0;}}
    QScrollArea, QScrollArea > QWidget > QWidget {{background:transparent;border:0;}}
    QDialog {{background:{background};}}
    QListWidget {{background:{surface};color:{text};border:1px solid {border};border-radius:10px;}}
    QListWidget::item {{padding:10px;}}
    QListWidget::item:selected {{background:{accent};color:white;}}
    QMessageBox {{background:{surface};}}
    """


class TaskCard(QtWidgets.QFrame):
    activated = QtCore.Signal(str)

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.setObjectName("TaskCard")
        self.setMinimumHeight(176)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        content = QtWidgets.QVBoxLayout(self)
        content.setContentsMargins(19, 18, 19, 18)
        content.setSpacing(8)
        caption = QtWidgets.QLabel(task.section)
        caption.setObjectName("Section")
        content.addWidget(caption)
        heading = QtWidgets.QLabel(task.title)
        heading.setWordWrap(True)
        heading.setStyleSheet("font-size:17px;font-weight:750;")
        content.addWidget(heading)
        summary = QtWidgets.QLabel(task.description)
        summary.setWordWrap(True)
        summary.setObjectName("Description")
        content.addWidget(summary, 1)
        button = QtWidgets.QPushButton("Open workspace  →")
        button.setObjectName("CardAction")
        button.setAccessibleName("Open " + task.title)
        button.clicked.connect(lambda _checked=False: self.activated.emit(task.key))
        content.addWidget(button)


class CommandPalette(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Go to workflow")
        self.setMinimumSize(520, 480)
        self.choice = ""
        layout = QtWidgets.QVBoxLayout(self)
        self.query = QtWidgets.QLineEdit()
        self.query.setPlaceholderText("Search workflows…")
        self.results = QtWidgets.QListWidget()
        layout.addWidget(self.query)
        layout.addWidget(self.results, 1)
        self.query.textChanged.connect(self._populate)
        self.results.itemActivated.connect(self._select)
        self._populate("")
        self.query.setFocus()

    def _populate(self, query: str):
        self.results.clear()
        for task in searchable(query):
            item = QtWidgets.QListWidgetItem(f"{task.title}    ·    {task.section}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, task.key)
            self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(0)

    def _select(self, item):
        self.choice = str(item.data(QtCore.Qt.ItemDataRole.UserRole))
        self.accept()

    def accept(self):
        if not self.choice and self.results.currentItem():
            self.choice = str(self.results.currentItem().data(QtCore.Qt.ItemDataRole.UserRole))
        super().accept()


class ControlPanel(QtWidgets.QMainWindow):
    def __init__(self, root: Path = ROOT):
        super().__init__()
        self.root = root.resolve()
        self.legacy = None
        self.lobby_workspace = None
        self.settings = QtCore.QSettings("SkyEducation", "SkyEdControlPanel")
        self.dark = self.settings.value("appearance/dark", False, bool)
        self.section = "HOME"
        self.setWindowTitle(f"SkyED Control Panel · {APP_VERSION}")
        self.setMinimumSize(1040, 690)
        self.resize(1400, 850)
        self._build()
        self._apply_theme()
        self.show_section("HOME")

    def _build(self):
        shell = QtWidgets.QWidget()
        shell.setObjectName("Shell")
        self.setCentralWidget(shell)
        main = QtWidgets.QHBoxLayout(shell)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        sidebar = QtWidgets.QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(242)
        nav_layout = QtWidgets.QVBoxLayout(sidebar)
        nav_layout.setContentsMargins(15, 25, 15, 20)
        nav_layout.setSpacing(7)
        brand = QtWidgets.QLabel("SKYED  /  STUDIO")
        brand.setObjectName("Brand")
        nav_layout.addWidget(brand)
        subtitle = QtWidgets.QLabel("Education workflow control")
        subtitle.setObjectName("Muted")
        nav_layout.addWidget(subtitle)
        nav_layout.addSpacing(29)
        self.nav = {}
        for label, key in (("Overview", "HOME"), ("Creation", "CREATE"), ("Operations", "OPERATE"), ("Websites", "WEBSITES"), ("System", "SYSTEM")):
            b = QtWidgets.QPushButton(label)
            b.setObjectName("Nav")
            b.setCheckable(True)
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _checked=False, section=key: self.show_section(section))
            self.nav[key] = b
            nav_layout.addWidget(b)
        nav_layout.addStretch()
        legacy_btn = QtWidgets.QPushButton("Open classic workroom")
        legacy_btn.clicked.connect(lambda: self._open_legacy("Quick"))
        nav_layout.addWidget(legacy_btn)
        version = QtWidgets.QLabel("Control Panel 2.3.0\nLocal-first · safe navigation")
        version.setObjectName("Muted")
        nav_layout.addWidget(version)
        main.addWidget(sidebar)

        center = QtWidgets.QWidget()
        center_layout = QtWidgets.QVBoxLayout(center)
        center_layout.setContentsMargins(34, 26, 34, 20)
        center_layout.setSpacing(15)
        header = QtWidgets.QHBoxLayout()
        titles = QtWidgets.QVBoxLayout()
        titles.setSpacing(3)
        self.heading = QtWidgets.QLabel()
        self.heading.setObjectName("Title")
        self.description = QtWidgets.QLabel()
        self.description.setObjectName("Muted")
        titles.addWidget(self.heading)
        titles.addWidget(self.description)
        header.addLayout(titles, 1)
        self.search = QtWidgets.QLineEdit()
        self.search.setFixedWidth(275)
        self.search.setPlaceholderText("Search  Ctrl+K")
        self.search.returnPressed.connect(self._search_open)
        header.addWidget(self.search)
        self.theme_button = QtWidgets.QPushButton("Appearance")
        self.theme_button.clicked.connect(self.toggle_theme)
        header.addWidget(self.theme_button)
        center_layout.addLayout(header)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        center_layout.addWidget(self.scroll, 1)
        self.footer = QtWidgets.QLabel()
        self.footer.setObjectName("Muted")
        center_layout.addWidget(self.footer)
        main.addWidget(center, 1)
        shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+K"), self)
        shortcut.activated.connect(self.open_palette)

    def _apply_theme(self):
        self.centralWidget().setStyleSheet(_theme(self.dark))
        self.settings.setValue("appearance/dark", self.dark)

    def toggle_theme(self):
        self.dark = not self.dark
        self._apply_theme()

    def _set_scroll_widget(self, content):
        old = self.scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self.scroll.setWidget(content)

    def show_section(self, section: str):
        if section not in ("HOME", *SECTIONS):
            raise ValueError(f"Unknown section: {section}")
        self.section = section
        for key, button in self.nav.items():
            button.setChecked(key == section)
        self.heading.setText("Control Center" if section == "HOME" else section.title())
        self.description.setText("Verified local routes to existing Sky Education tools · no background publishing")
        matches = TASKS if section == "HOME" else tuple(t for t in TASKS if t.section == section)
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 14, 0, 15)
        layout.setSpacing(18)

        if section in ("HOME", "SYSTEM"):
            checks = local_diagnostics(self.root)
            ready = sum(ok for _label, ok, _detail in checks)
            banner = QtWidgets.QFrame()
            banner.setObjectName("Panel")
            banner.setMinimumHeight(80)
            row = QtWidgets.QHBoxLayout(banner)
            count = QtWidgets.QLabel(f"Local wiring   {ready} / {len(checks)} checks")
            count.setStyleSheet("font-size:18px;font-weight:750;")
            row.addWidget(count, 1)
            note = QtWidgets.QLabel("Read-only status · not a production health claim")
            note.setObjectName("Muted")
            row.addWidget(note)
            layout.addWidget(banner)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(17)
        grid.setVerticalSpacing(17)
        for i, task in enumerate(matches):
            card = TaskCard(task)
            card.activated.connect(self.open_task)
            grid.addWidget(card, i // 3, i % 3)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        layout.addLayout(grid)
        layout.addStretch()
        self._set_scroll_widget(page)
        self.footer.setText(f"{len(matches)} routes available · {self.root}")

    def open_palette(self):
        dlg = CommandPalette(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted and dlg.choice:
            self.open_task(dlg.choice)

    def _search_open(self):
        hits = searchable(self.search.text())
        if len(hits) == 1:
            self.open_task(hits[0].key)
        else:
            dlg = CommandPalette(self)
            dlg.query.setText(self.search.text())
            if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted and dlg.choice:
                self.open_task(dlg.choice)

    def _open_legacy(self, tab: str):
        try:
            if self.legacy is None:
                from pyside_gui import MainWindow, load_config, load_dotenv, CONFIG_NAME
                load_dotenv(dotenv_path=str(self.root / ".env"), override=False)
                cfg_file = self.root / CONFIG_NAME
                cfg = load_config(cfg_file, root_dir=self.root)
                # Local interpreter path must be valid; do not silently redirect.
                if not Path(cfg.project_python).is_file():
                    cfg.project_python = str(Path(sys.executable).resolve())
                if not Path(cfg.project_workdir).is_dir():
                    cfg.project_workdir = str(self.root)
                self.legacy = MainWindow(self.root, cfg, cfg_file)
            for idx in range(self.legacy.right_tabs.count()):
                if self.legacy.right_tabs.tabText(idx) == tab:
                    self.legacy.right_tabs.setCurrentIndex(idx)
                    break
            else:
                raise RuntimeError(f"Legacy panel does not provide tab '{tab}'")
            self.legacy.showMaximized()
            self.legacy.raise_()
            self.legacy.activateWindow()
            return self.legacy
        except Exception as error:
            QtWidgets.QMessageBox.critical(
                self, "Workspace launch failed",
                f"Could not open {tab}.\n\n{type(error).__name__}: {error}\n\n"
                "The original control panel and its installed modules have not been modified.",
            )
            return None

    def open_task(self, key: str):
        task = task_by_key(key)
        if task.route == "lobby":
            self._open_lobby(task.target)
            return
        if task.route == "legacy":
            legacy = self._open_legacy(task.legacy_tab)
            if legacy and key == "assets":
                legacy.open_asset_batcher()
            elif legacy and key == "cutter":
                legacy.open_card_cutter()
            return

        if task.route == "folder":
            target = self.root / task.target
            if not target.is_dir():
                QtWidgets.QMessageBox.information(self, "Folder unavailable", f"Directory not found:\n{target}")
                return
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(target)))
            return
        if task.route == "website":
            message = f"Open {task.title} in your browser?\n\n{task.target}\n\nNo local data will be sent by this control panel."
            if QtWidgets.QMessageBox.question(self, "Open external website", message) == QtWidgets.QMessageBox.StandardButton.Yes:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl(task.target))
            return
        if task.route == "diagnostics":
            self._show_diagnostics()
            return
        if task.route == "settings":
            self._show_settings()
            return
        raise AssertionError(f"Unknown route: {task.route}")

    def _open_lobby(self, view: str):
        """Open the actual editor in an embedded native workspace.

        The server starts on an ephemeral loopback port only when requested.
        """
        from skyed_control.lobby_workspace import LobbyWorkspace
        if self.lobby_workspace is not None and self.lobby_workspace.isVisible():
            self.lobby_workspace._navigate(view)
            self.lobby_workspace.raise_()
            self.lobby_workspace.activateWindow()
            return
        self.lobby_workspace = LobbyWorkspace(self.root, self, initial_view=view)
        self.lobby_workspace.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.lobby_workspace.destroyed.connect(lambda *_: setattr(self, "lobby_workspace", None))
        self.lobby_workspace.showMaximized()

    def _show_diagnostics(self):
        rows = local_diagnostics(self.root)
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.addWidget(self._text_heading("Local diagnostics", "These checks do not connect to WordPress, SSH, Modal, Supabase or GitHub."))
        for label, ok, detail in rows:
            item = QtWidgets.QFrame()
            item.setObjectName("Panel")
            v = QtWidgets.QVBoxLayout(item)
            heading = QtWidgets.QLabel(("PASS  " if ok else "CHECK  ") + label)
            heading.setStyleSheet("font-weight:750;")
            v.addWidget(heading)
            note = QtWidgets.QLabel(detail)
            note.setWordWrap(True)
            note.setObjectName("Muted")
            v.addWidget(note)
            layout.addWidget(item)
        layout.addStretch()
        self._set_scroll_widget(content)
        self.heading.setText("Health & Wiring")

    def _show_settings(self):
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.addWidget(self._text_heading("Control Panel settings", "The legacy GUI remains the authority for backend credentials and pipeline settings."))
        path = self.root / "gui_config.json"
        summary = {}
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                for key in ("image_backend", "picture_cards_type", "lesson_theme", "voice_en", "voice_zh", "tts_rate_percent"):
                    if isinstance(data, dict) and key in data:
                        summary[key] = str(data[key])
            except (OSError, ValueError, UnicodeError) as exc:
                summary["Configuration read"] = f"{type(exc).__name__}: unable to parse"
        for key, value in (summary or {"Legacy configuration": "Not created yet"}).items():
            field = QtWidgets.QLabel(f"{key.replace('_', ' ').title()}:  {value}")
            field.setWordWrap(True)
            layout.addWidget(field)
        appearance = QtWidgets.QPushButton("Switch between light and dark appearance")
        appearance.clicked.connect(self.toggle_theme)
        layout.addWidget(appearance)
        classic = QtWidgets.QPushButton("Edit full workflow settings in classic workroom")
        classic.clicked.connect(lambda: self._open_legacy("Quick"))
        layout.addWidget(classic)
        layout.addStretch()
        self._set_scroll_widget(content)
        self.heading.setText("Settings")

    @staticmethod
    def _text_heading(title: str, description: str):
        panel = QtWidgets.QFrame()
        panel.setObjectName("Panel")
        l = QtWidgets.QVBoxLayout(panel)
        heading = QtWidgets.QLabel(title)
        heading.setStyleSheet("font-size:20px;font-weight:750;")
        l.addWidget(heading)
        note = QtWidgets.QLabel(description)
        note.setWordWrap(True)
        note.setObjectName("Muted")
        l.addWidget(note)
        return panel


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    smoke = "--smoke-test" in argv
    argv = [value for value in argv if value != "--smoke-test"]
    if smoke:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        # Only the offscreen test backend needs this font directory override.
        # The normal Windows platform plugin discovers Windows fonts itself.
        if sys.platform == "win32" and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            windows_root = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
            if windows_root:
                font_dir = Path(windows_root) / "Fonts"
                if font_dir.is_dir():
                    os.environ["QT_QPA_FONTDIR"] = str(font_dir)
    os.chdir(ROOT)
    app = QtWidgets.QApplication(argv)
    app.setApplicationName("SkyED Control Panel")
    app.setStyle("Fusion")
    win = ControlPanel(ROOT)
    if smoke:
        win.show()
        app.processEvents()
        assert win.section == "HOME"
        assert len(TASKS) >= 15
        win.show_section("SYSTEM")
        app.processEvents()
        win.open_task("diagnostics")
        app.processEvents()
        win.close()
        print("SKYED_CONTROL_PANEL_QT_SMOKE=PASS")
        return 0
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
