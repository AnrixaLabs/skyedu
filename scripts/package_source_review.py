"""Package the genuine SkyED development source, excluding bundled font binaries.

The reviewed project remains the existing GitHub feature branch; this is not
a production deployment. Never distribute the bundled Noto/other font files.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

DENY_SUFFIXES = {".ttf", ".ttc", ".otf", ".woff", ".woff2", ".eot", ".pem",
                 ".key", ".p12", ".pfx", ".pyc"}
DENY_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519",
              ".ds_store"}
MAX_BYTES = 15 * 1024 * 1024


def package(repo: Path, output: Path) -> dict:
    repo = repo.resolve()
    if output.exists():
        raise ValueError(f"Refusing overwrite: {output}")
    git = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"],
                         capture_output=True, check=True)
    paths = sorted(set(x for x in git.stdout.split(b"\0") if x))
    included, skipped = [], []
    for raw in paths:
        name = raw.decode("utf-8")
        path = PurePosixPath(name)
        if (path.is_absolute() or ".." in path.parts or
            any(x in {".git", "__pycache__"} for x in path.parts)):
            raise ValueError(f"Unsafe tracked path: {name}")
        actual = (repo / name).resolve()
        if not actual.is_relative_to(repo) or not actual.is_file():
            skipped.append({"path": name, "reason": "unavailable_or_symlink"})
            continue
        if (path.suffix.lower() in DENY_SUFFIXES or
            path.name.lower() in DENY_NAMES or "fonts" in {x.lower() for x in path.parts}):
            skipped.append({"path": name, "reason": "font_or_secret_file"})
            continue
        if actual.stat().st_size > MAX_BYTES:
            skipped.append({"path": name, "reason": "size_limit"})
            continue
        included.append((name, actual))
    sha = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                  text=True).strip()
    actual_branch = subprocess.check_output(
        ["git", "-C", str(repo), "branch", "--show-current"], text=True).strip()
    if actual_branch != "feature/homework-automation-v2":
        raise ValueError(
            f"Review snapshot must come from feature/homework-automation-v2, not {actual_branch or 'detached HEAD'}"
        )
    metadata = {
        "schema": "skyed.review.source.v2.1.7",
        "origin": "AnrixaLabs/skyedu",
        "branch": "feature/homework-automation-v2",
        "commit": sha,
        "scope": "Tracked development source and non-font assets, no credentials",
        "production_ready": False,
        "excluded_files": skipped,
        "file_hashes": {
            name: hashlib.sha256(actual.read_bytes()).hexdigest()
            for name, actual in included
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("skyedu/REVIEW-SNAPSHOT-MANIFEST.json",
                   json.dumps(metadata, indent=2, ensure_ascii=False))
        for name, actual in included:
            z.write(actual, "skyedu/" + name)
    return {"commit": sha, "included_files": len(included),
            "excluded_files": len(skipped),
            "output": str(output),
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    try:
        print(json.dumps(package(args.repo, args.output), indent=2))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"SOURCE_PACKAGE_BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
