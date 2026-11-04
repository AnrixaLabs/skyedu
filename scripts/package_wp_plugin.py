"""Build the existing WordPress lesson renderer plugin ZIP from a complete checkout.

Requires PHP syntax validation and the checked-in CSS. Does not install or
activate the plugin. Deploy only after the release gates are satisfied.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--output", type=Path, default=Path("SkyED-Lesson-Renderer-v0.4.7.zip"))
    args = p.parse_args()
    plugin = args.repo.resolve() / "wp_plugin" / "skyed-lesson-renderer"
    mainfile = plugin / "skyed-lesson-renderer.php"
    css = plugin / "assets" / "skyed-lesson.css"
    if not mainfile.is_file() or not css.is_file():
        print("BLOCKED: plugin PHP/CSS source is incomplete", file=sys.stderr)
        return 2
    if "Version: 0.4.7" not in mainfile.read_text(encoding="utf-8"):
        print("BLOCKED: expected v0.4.7 not found", file=sys.stderr)
        return 2
    php = shutil.which("php")
    if not php:
        print("BLOCKED: PHP CLI unavailable for lint", file=sys.stderr)
        return 2
    check = subprocess.run([php, "-l", str(mainfile)], capture_output=True, text=True)
    if check.returncode:
        print(check.stdout + check.stderr, file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.output, "w", ZIP_DEFLATED) as z:
        for path in plugin.rglob("*"):
            if path.is_file() and not path.is_symlink():
                z.write(path, Path("skyed-lesson-renderer") / path.relative_to(plugin))
    print("READY_FOR_STAGING_REVIEW:", args.output.resolve())
    print("ZIP_SHA256:", hashlib.sha256(args.output.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
