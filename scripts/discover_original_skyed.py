"""Read-only discovery and optional export of original SkyED Python modules.

Source workspace is never modified. Export is explicitly opt-in and confined
to the twelve missing, known module names; refuses embedded-secret patterns.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import zipfile
from collections import deque
from pathlib import Path

MISSING_MODULES = (
    "asset_library", "fallback_cards", "image_semantics", "lesson_metadata",
    "picture_reader", "pipeline_helpers", "scene_fallbacks", "tag_creator",
    "tag_game_profiles", "tag_registry", "tag_s_env", "thematic_backgrounds",
)
PRUNE_NAMES = frozenset({
    "$recycle.bin", "system volume information", "appdata", ".git", ".venv", "venv",
    "node_modules", "__pycache__", "dist", "build", "output", ".next", ".cache",
    ".npm", ".gradle", "site-packages", "windows", "program files",
    "program files (x86)", "programdata", "wp-content", "media", "uploads",
})
SECRET_PATTERNS = (
    re.compile(rb"(?i)\b(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{20,}|AIza[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b"),
    re.compile(rb'''(?i)\b(?:WP_APP_PASSWORD|CF_API_TOKEN|HF_TOKEN|OPENAI_API_KEY|AWS_SECRET_ACCESS_KEY|AZURE_API_KEY)\s*=\s*['"][^'"\r\n]{8,}['"]'''),
)

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sensible_roots() -> list[Path]:
    home = Path.home()
    likely = [home / s for s in ("Documents", "Desktop", "Downloads", "source", "projects", "repos")]
    if os.name == "nt":
        for letter in range(ord("C"), ord("Z") + 1):
            base = Path(f"{chr(letter)}:\\")
            for s in ("SkyED", "SkyEdu", "skyedu", "SkyEDAutomation",
                      "SkyED-Automation", "Projects", "Repositories", "git", "source"):
                likely.append(base / s)
    result, seen = [], set()
    for p in likely:
        key = str(p).casefold()
        if key not in seen and p.is_dir() and not p.is_symlink():
            result.append(p)
            seen.add(key)
    return result

def evaluate_workspace(path: Path) -> dict | None:
    path = Path(path)
    package = path / "skyed"
    if not package.is_dir() or package.is_symlink():
        return None
    try:
        root = path.resolve()
        found, missing = [], []
        for name in MISSING_MODULES:
            p = package / (name + ".py")
            if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(root):
                missing.append(name)
                continue
            raw = p.read_bytes()
            found.append({
                "module": "skyed." + name,
                "relative_path": "skyed/" + name + ".py",
                "bytes": len(raw),
                "sha256": sha256_bytes(raw),
                "suspicious_secret_pattern": any(rx.search(raw) for rx in SECRET_PATTERNS),
            })
        if not found:
            return None
        return {
            "source_root": str(root), "found_count": len(found),
            "missing_count": len(missing), "missing_module_names": missing,
            "markers": {n: (root / n).is_file() for n in
                        ("run_pipeline.py", "pyside_gui.py", "requirements.txt", "homework.txt")},
            "found": found,
        }
    except (OSError, PermissionError):
        return None

def discover(roots: list[Path], *, max_depth: int = 6,
             max_directories: int = 50000) -> tuple[list[dict], dict]:
    if max_depth < 0 or max_directories < 1:
        raise ValueError("Invalid discovery bounds")
    queue = deque((p, 0) for p in roots if p.is_dir() and not p.is_symlink())
    visited, candidates, errors = set(), {}, []
    count = 0
    while queue and count < max_directories:
        path, depth = queue.popleft()
        key = os.path.normcase(str(path.resolve()))
        if key in visited:
            continue
        visited.add(key)
        count += 1
        candidate = evaluate_workspace(path)
        if candidate:
            candidates[key] = candidate
        if depth >= max_depth:
            continue
        try:
            with os.scandir(path) as listing:
                for entry in listing:
                    if entry.name.casefold() in PRUNE_NAMES or entry.name.startswith("."):
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            queue.append((Path(entry.path), depth + 1))
                    except OSError:
                        pass
        except OSError as exc:
            if len(errors) < 20:
                errors.append(f"{path}: {type(exc).__name__}")
    items = sorted(candidates.values(), key=lambda x: (-x["found_count"],
               -sum(x["markers"].values()), x["source_root"].casefold()))
    return items, {
        "directories_examined": count, "search_limit_reached": bool(queue),
        "searched_roots": [str(p.resolve()) for p in roots], "io_error_examples": errors,
    }

def export_originals(candidate: dict, out: Path) -> dict:
    if not candidate["found"]:
        raise ValueError("No modules available to export")
    if any(i["suspicious_secret_pattern"] for i in candidate["found"]):
        raise ValueError("Possible embedded credentials; manual review required, export BLOCKED")
    root = Path(candidate["source_root"]).resolve()
    files = []
    for item in candidate["found"]:
        rel = item["relative_path"]
        path = root / rel
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"Unsafe source path: {rel}")
        data = path.read_bytes()
        if sha256_bytes(data) != item["sha256"]:
            raise ValueError(f"Source changed during export: {rel}")
        try:
            compile(data, str(path), "exec", dont_inherit=True)
        except SyntaxError as exc:
            raise ValueError(f"Original has invalid Python syntax: {rel}: {exc}") from exc
        files.append((rel, data))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite archive: {out}")
    manifest = {
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_root": str(root), "found_count": len(files),
        "missing_count": candidate["missing_count"], "files": candidate["found"],
        "warning": "REVIEW ONLY. Manually inspect original source for secrets before sharing.",
    }
    with zipfile.ZipFile(out, "x", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("recovery-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for rel, data in files:
            z.writestr(rel, data)
    return {"archive": str(out.resolve()), "zip_sha256": sha256_bytes(out.read_bytes()),
            "files": len(files), "missing_count": candidate["missing_count"]}

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", type=Path)
    ap.add_argument("--scan-root", type=Path, action="append")
    ap.add_argument("--max-depth", type=int, default=6)
    ap.add_argument("--max-directories", type=int, default=50000)
    ap.add_argument("--report", type=Path, default=Path("skyed-original-source-inventory.json"))
    ap.add_argument("--export-zip", type=Path)
    args = ap.parse_args(argv)
    try:
        if args.export_zip and not args.source_root:
            raise ValueError("--export-zip requires --source-root; refusing automatic source selection")
        if args.source_root:
            source = args.source_root.expanduser().resolve()
            candidate = evaluate_workspace(source)
            candidates = [candidate] if candidate else []
            stats = {"searched_roots": [str(source)], "directories_examined": 1,
                     "search_limit_reached": False, "io_error_examples": []}
        else:
            roots = [p.expanduser() for p in args.scan_root] if args.scan_root else sensible_roots()
            candidates, stats = discover(roots, max_depth=args.max_depth,
                                         max_directories=args.max_directories)
        result = {
            "status": "FOUND" if candidates else "NO_CANDIDATE_FOUND",
            "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "candidate_count": len(candidates), "search": stats, "candidates": candidates,
            "github_missing_expected": ["skyed." + n for n in MISSING_MODULES],
            "note": "Read-only discovery; nothing copied to GitHub or WordPress.",
        }
        if args.export_zip:
            if not candidates:
                raise ValueError("Source folder has no relevant missing modules")
            result["export"] = export_originals(candidates[0], args.export_zip)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        if args.report.exists():
            raise FileExistsError(f"Refusing to overwrite report: {args.report}")
        args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if candidates else 2
    except (OSError, ValueError, FileExistsError) as exc:
        print(f"RECOVERY_BLOCKED: {exc}", file=sys.stderr)
        return 3

if __name__ == "__main__":
    raise SystemExit(main())
