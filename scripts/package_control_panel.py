"""Build an immutable, integrity-checked Control Panel overlay ZIP.

This artifact deliberately does not bundle legacy source, credentials, font files,
existing asset libraries or production configuration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

SOURCE_FILES = (
    "skyed_control_panel.py",
    "skyed_control/__init__.py",
    "skyed_control/registry.py",
    "scripts/Install-SkyED-ControlPanel-v2.2.0.ps1",
    "docs/CONTROL-PANEL-v2.2.0.md",
)


def package(repo: Path, output: Path) -> dict:
    repo = repo.resolve()
    output = output.resolve()
    manifest = {"version": "2.2.0", "kind": "additive-control-panel-overlay", "files": {}}
    for name in SOURCE_FILES:
        path = repo / name
        if not path.is_file():
            raise FileNotFoundError(f"Required source missing: {path}")
        raw = path.read_bytes()
        if b"\x00" in raw:
            raise ValueError(f"Unexpected binary input: {name}")
        manifest["files"][name] = hashlib.sha256(raw).hexdigest()

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in SOURCE_FILES:
            z.write(repo / name, name)
        z.writestr("member-sha256.json", json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:
            raise ValueError("ZIP integrity failed")
        for name, expected in manifest["files"].items():
            if hashlib.sha256(z.read(name)).hexdigest() != expected:
                raise ValueError(f"ZIP SHA mismatch: {name}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = package(args.repo, args.out)
    print(f"CONTROL_PANEL_ZIP=PASS files={len(manifest['files'])} output={args.out}")
