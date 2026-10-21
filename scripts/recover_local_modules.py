"""Safely recover missing modules from the known-working Windows installation.

Default is preview. --apply only copies files absent from the repository; never
overwrites, and verifies SHA256. Does not push to GitHub or touch credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from verify_repo_integrity import missing_project_modules


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for buf in iter(lambda: f.read(1048576), b""):
            h.update(buf)
    return h.hexdigest()


def recover(source: Path, repo: Path, apply: bool = False) -> dict:
    source, repo = source.resolve(), repo.resolve()
    if source == repo or repo in source.parents or source in repo.parents:
        raise ValueError("Source and destination must be separate, unrelated folders")
    if not (source / "skyed" / "__init__.py").is_file():
        raise ValueError("Invalid source: missing skyed/__init__.py")
    if not (repo / "skyed" / "__init__.py").is_file():
        raise ValueError("Invalid checkout: missing skyed/__init__.py")
    recovered = []
    for item in missing_project_modules(repo):
        name = item["module"]
        if not name.startswith("skyed."):
            continue
        rel = Path(*name.split(".")).with_suffix(".py")
        src, dest = source / rel, repo / rel
        status = "NOT_FOUND_IN_SOURCE"
        digest = None
        if src.is_file() and not src.is_symlink() and src.resolve().is_relative_to(source):
            digest = sha256(src)
            status = "READY"
            if dest.exists():
                status = "REFUSED_OVERWRITE"
            elif apply:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                if sha256(dest) != digest:
                    raise RuntimeError(f"SHA256 mismatch: {rel}")
                status = "COPIED_AND_VERIFIED"
        recovered.append({"module": name, "path": rel.as_posix(),
                          "status": status, "source_sha256": digest})
    return {"mode": "APPLY" if apply else "PREVIEW", "files": recovered,
            "remaining_missing": missing_project_modules(repo)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        result = recover(args.source, args.repo, args.apply)
    except (ValueError, OSError) as exc:
        print(f"BLOCKED: {exc}")
        return 3
    out = json.dumps(result, ensure_ascii=False, indent=2)
    print(out)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(out + "\n", encoding="utf-8")
    return 2 if any(x["status"] == "NOT_FOUND_IN_SOURCE" for x in result["files"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
