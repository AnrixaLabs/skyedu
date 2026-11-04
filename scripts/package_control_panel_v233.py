"""Reproducibly package the full SkyED Control Panel v2.3.3 overlay.

The packaged overlay is additive: no existing classic GUI, .env, user draft,
media assets, database, or server credentials are collected or modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

VERSION = "2.3.3"
DIRECTORY = "SkyED-ControlPanel-Lobby-v" + VERSION
KIND = "additive-control-panel-and-private-lobby-integration"
# This list MUST stay explicit; never recurse blindly into source or secrets.
MEMBERS = (
    "docs/CONTROL-PANEL-v2.3.3.md",
    "docs/RELEASE-CHECKPOINT.json",
    "scripts/Install-SkyED-ControlPanel-v2.3.3.ps1",
    "scripts/Start-SkyED-CourseHub-Integration-v2.3.3.ps1",
    "scripts/course_hub_integration.py",
    "scripts/package_control_panel_v233.py",
    "scripts/validate_lobby_content_v233.py",
    "skyed_control/__init__.py",
    "skyed_control/integration_workspace.py",
    "skyed_control/lobby_workspace.py",
    "skyed_control/registry.py",
    "skyed_control_panel.py",
    "skyed_lobby/scripts/control_server.py",
    "skyed_lobby/scripts/preview.py",
    "skyed_lobby/site/assets/app.js",
    "skyed_lobby/site/assets/favicon.svg",
    "skyed_lobby/site/assets/media/README.txt",
    "skyed_lobby/site/assets/styles.css",
    "skyed_lobby/site/content/lobby.json",
    "skyed_lobby/site/index.html",
    "skyed_lobby/tests/test_browser_lobby.py",
    "skyed_lobby/tests/test_control_lobby.py",
    "skyed_lobby/tools/edit-lobby.html",
    "skyed_lobby/tools/editor.css",
    "skyed_lobby/tools/editor.js",
    "tests/test_course_hub_integration.py",
    "tests/test_course_hub_integration_qt.py",
    "tests/test_install_v233.py",
    "tests/test_pilot_route_reconciliation.py",
)


def build(repo: Path, target: Path) -> str:
    repo = repo.resolve(strict=True)
    target = target.resolve()
    if len(set(MEMBERS)) != 29:
        raise RuntimeError("Duplicate or missing allowlisted members")
    contents: dict[str, bytes] = {}
    manifest: dict[str, object] = {"version": VERSION, "kind": KIND, "files": {}}
    for member in MEMBERS:
        if ".." in Path(member).parts or member.startswith("/") or "\\" in member:
            raise ValueError("Unsafe release path")
        path = repo / member
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError("Release input missing/unsafe: " + member)
        data = path.read_bytes()
        if b"\x00" in data:
            raise ValueError("Release inputs must be text, never binaries")
        # Git on Windows may checkout text sources as CRLF even when the Git
        # blob and Linux checkout use LF. Normalize package members WITHOUT
        # writing back to the checkout, so Windows/Linux archives are identical.
        data = data.replace(b"\r\n", b"\n")
        contents[member] = data
        manifest["files"][member] = hashlib.sha256(data).hexdigest()
    contents["member-sha256.json"] = (json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name in sorted(contents):
            info = zipfile.ZipInfo(f"{DIRECTORY}/{name}", (2026, 11, 3, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            output.writestr(info, contents[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(target) as check:
        if check.testzip() is not None:
            raise RuntimeError("Release archive CRC failed")
        for member, expected in manifest["files"].items():
            assert hashlib.sha256(check.read(f"{DIRECTORY}/{member}")).hexdigest() == expected
    sha = hashlib.sha256(target.read_bytes()).hexdigest()
    print(f"SKYED_V233_PACKAGE=PASS members={len(MEMBERS)} sha256={sha} bytes={target.stat().st_size}")
    return sha


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    cli.add_argument("--out", type=Path, required=True)
    args = cli.parse_args()
    build(args.repo, args.out)
