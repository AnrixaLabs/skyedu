"""Declarative, non-destructive navigation for the SkyED Windows control panel.

This module intentionally has no Qt, network or production side effects.
Legacy automation remains owned by pyside_gui.MainWindow.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Route = Literal["legacy", "folder", "website", "diagnostics", "settings", "lobby", "integration"]
_ALLOWED_HOSTS = frozenset({"course.skyed.org", "portal.skyed.org", "growth.skyed.org", "skyed.org"})


@dataclass(frozen=True)
class Task:
    key: str
    title: str
    section: str
    description: str
    route: Route
    legacy_tab: str = ""
    target: str = ""
    requires: str = ""


TASKS: tuple[Task, ...] = (
    Task("homework", "Homework Studio", "CREATE", "Edit lessons, generate homework and inspect the pipeline log.", "legacy", "Quick"),
    Task("audio", "Voice & TTS", "CREATE", "EN/ZH voices, playback tests and audio speed controls.", "legacy", "Audio"),
    Task("images", "Image Studio", "CREATE", "ComfyUI, image sources, prompts and card previews.", "legacy", "Images"),
    Task("batch", "Folder Batches", "CREATE", "Process lesson folders using the existing batch pipeline.", "legacy", "Batch"),
    Task("assets", "Asset Batcher", "CREATE", "Open the existing vocabulary and media batcher.", "legacy", "Quick", requires="skyed_asset_batcher"),
    Task("cutter", "Card Cutter", "CREATE", "Launch the existing card cutting tool.", "legacy", "Quick", requires="skyed_card_cutter"),
    Task("tags", "Interactive Games", "CREATE", "Build, preview and publish tag_s learning activities.", "legacy", "tag_s Creator"),
    Task("ng", "NG Lessons", "CREATE", "NG audio fields, games and lesson publishing workflow.", "legacy", "NG"),
    Task("reader", "Picture Reader", "CREATE", "Use the image-based Picture Reader workflow.", "legacy", "Picture Reader"),
    Task("publish", "WordPress Publishing", "OPERATE", "Open legacy publishing with existing safety checks.", "legacy", "Publish"),
    Task("lobby-designer", "Lobby Designer", "OPERATE", "Edit curricula, lesson cards, colors and local draft content with Save to workspace.", "lobby", target="editor"),
    Task("lobby-preview", "Lobby Live Preview", "OPERATE", "View the responsive Course Hub lobby using your locally saved content.", "lobby", target="preview"),
    Task("course-integration", "Course Hub Integration", "OPERATE", "Combine a captured live site with the new tile lobby in a verified, isolated local preview.", "integration"),
    Task("library", "Local Lesson Library", "OPERATE", "Browse existing generated lesson output without altering it.", "folder", target="output"),
    Task("assetlibrary", "Media Library", "OPERATE", "Browse the canonical local asset library, if present.", "folder", target="asset_library"),
    Task("course", "Course Hub", "WEBSITES", "Open the separate Course Hub application.", "website", target="https://course.skyed.org"),
    Task("portal", "ClassFlow Portal", "WEBSITES", "Open ClassFlow in the browser; its database stays independent.", "website", target="https://portal.skyed.org"),
    Task("growth", "GrowthBridge", "WEBSITES", "Open the independent GrowthBridge application.", "website", target="https://growth.skyed.org"),
    Task("diagnostics", "Health & Wiring", "SYSTEM", "Read-only local module, executable and folder checks.", "diagnostics"),
    Task("settings", "Settings", "SYSTEM", "Appearance and read-only legacy settings summary.", "settings"),
)
BY_KEY = {task.key: task for task in TASKS}


def validate_catalog() -> None:
    """Make miswired, ambiguous or unsafe navigation fail in CI."""
    assert len(BY_KEY) == len(TASKS), "Duplicate control-panel task key"
    from urllib.parse import urlsplit
    for task in TASKS:
        assert task.key and task.title and task.section and task.description
        if task.route == "legacy":
            assert task.legacy_tab in {"Quick", "Audio", "Images", "Batch", "tag_s Creator", "NG", "Publish", "Picture Reader"}
            assert not task.target
        elif task.route == "folder":
            assert task.target in {"output", "asset_library"}
        elif task.route == "lobby":
            assert task.target in {"editor", "preview"} and not task.legacy_tab
        elif task.route == "integration":
            assert not task.target and not task.legacy_tab
        elif task.route == "website":
            parsed = urlsplit(task.target)
            assert parsed.scheme == "https" and parsed.hostname in _ALLOWED_HOSTS
            assert not parsed.username and not parsed.password and not parsed.port
            assert not task.legacy_tab
        else:
            assert not task.target and not task.legacy_tab


def task_by_key(key: str) -> Task:
    return BY_KEY[key]


def searchable(query: str) -> list[Task]:
    words = query.casefold().split()
    return [
        task for task in TASKS
        if all(word in (task.title + " " + task.section + " " + task.description + " " + task.key).casefold() for word in words)
    ]


def local_diagnostics(root: Path) -> list[tuple[str, bool, str]]:
    """Read-only checks; NOT a claim that remote services or images/audio work."""
    import importlib.util
    import sys
    root = root.resolve()
    def module_ok(name: str) -> bool:
        try:
            return importlib.util.find_spec(name) is not None
        except (ImportError, ValueError, AttributeError):
            return False
    def check(label: str, ok: bool, value: object) -> tuple[str, bool, str]:
        return (label, bool(ok), str(value))

    return [
        check("Python executable", Path(sys.executable).is_file(), sys.executable),
        check("Project directory", root.is_dir(), root),
        check("Legacy control panel", (root / "pyside_gui.py").is_file(), root / "pyside_gui.py"),
        check("Homework generator", (root / "run_pipeline.py").is_file(), root / "run_pipeline.py"),
        check("Legacy configuration", (root / "gui_config.json").is_file(), "Present (credentials deliberately hidden)" if (root / "gui_config.json").exists() else "Not yet created"),
        check("Lesson input", (root / "homework.txt").is_file(), root / "homework.txt"),
        check("Lobby Designer", (root / "skyed_lobby" / "tools" / "edit-lobby.html").is_file(), root / "skyed_lobby" / "tools" / "edit-lobby.html"),
        check("Staging integration", (root / "scripts" / "course_hub_integration.py").is_file(), root / "scripts" / "course_hub_integration.py"),
        check("Lobby content", (root / "skyed_lobby" / "site" / "content" / "lobby.json").is_file(), root / "skyed_lobby" / "site" / "content" / "lobby.json"),
        check("Asset library", (root / "asset_library").is_dir(), root / "asset_library"),
        check("Comfy workflow", (root / "assets/comfy/workflow_api.json").is_file(), root / "assets/comfy/workflow_api.json"),
        check("Asset Batcher package", module_ok("skyed_asset_batcher"), "Importable" if module_ok("skyed_asset_batcher") else "Not installed in this Python environment"),
        check("Card Cutter package", module_ok("skyed_card_cutter"), "Importable" if module_ok("skyed_card_cutter") else "Not installed in this Python environment"),
    ]


validate_catalog()
