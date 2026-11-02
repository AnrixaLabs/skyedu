"""Non-destructive SkyED Course Hub source reconciliation and preview staging.

Never connects to production or writes to a captured Course Hub snapshot.
The first stage preserves every byte of the existing published website and
adds only an isolated /lobby-preview/ directory. Production promotion is NOT
implemented by design: the 11 unlinked lessons need verified mapping first.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import http.server
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
from urllib.parse import unquote, urlsplit

RELEASE = "2.3.1"
PREVIEW_DIR = "lobby-preview"
STATIC_SUFFIXES = {".html", ".htm", ".css", ".js", ".json", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".mp3", ".wav", ".ogg", ".m4a", ".txt", ".webmanifest", ".woff2"}
MEDIA_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp3", ".wav", ".ogg", ".m4a"}
REJECTED_FILENAMES = {".env", ".htpasswd", "id_rsa", "id_ed25519", "wp-config.php"}
REJECTED_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".sqlite", ".sqlite3", ".db", ".bak", ".php", ".py", ".ps1", ".sh"}
URL_PATTERN = re.compile(r'''(?:href|src)\s*=\s*["']([^"'<>]+)["']|(?:"(?:url|href|path|src)"\s*:\s*")([^"<>]+)"''', re.I)
MAX_FILES = 20000
MAX_TOTAL_BYTES = 8 * 1024**3


class GateError(Exception):
    """A deliberate release safety stop, not a recoverable success."""


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_tree(root: Path) -> list[tuple[str, Path, int, str]]:
    """Return (relative path, file, size, sha) with no symlinks or private data."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise GateError("Source must be a real directory")
    if not (root / "index.html").is_file():
        raise GateError("Existing Course Hub index.html missing: not a verified site snapshot")
    result = []
    seen = set()
    total = 0
    for parent, dirs, files in os.walk(root, followlinks=False):
        dirs.sort()
        files.sort()
        base = Path(parent)
        for dirname in dirs:
            directory = base / dirname
            if directory.is_symlink() or dirname.startswith("."):
                raise GateError(f"Unsafe directory in capture: {directory}")
        for filename in files:
            path = base / filename
            if path.is_symlink() or not path.is_file():
                raise GateError(f"Unsafe non-regular captured file: {path}")
            rel = path.relative_to(root).as_posix()
            parts = PurePosixPath(rel).parts
            if filename.lower() in REJECTED_FILENAMES or any(p.startswith(".") for p in parts):
                raise GateError(f"Potentially private file found in website capture: {rel}")
            if path.suffix.lower() in REJECTED_SUFFIXES or path.suffix.lower() not in STATIC_SUFFIXES:
                raise GateError(f"Unexpected executable/private or unknown file in capture: {rel}")
            key = rel.casefold()
            if key in seen:
                raise GateError(f"Case-insensitive filename collision: {rel}")
            seen.add(key)
            size = path.stat().st_size
            total += size
            if len(seen) > MAX_FILES or total > MAX_TOTAL_BYTES:
                raise GateError("Captured site exceeds bounded audit limits")
            result.append((rel, path, size, digest(path)))
    if not result:
        raise GateError("Captured site is empty")
    if PREVIEW_DIR in {x.split("/")[0] for x, *_ in result}:
        raise GateError("Captured site already contains lobby-preview; refuse ambiguous overlay")
    return result


def media_summary(files: list[tuple[str, Path, int, str]]) -> dict:
    summary = {"audio": 0, "images": 0, "total_media": 0}
    for rel, _, _, _ in files:
        ext = Path(rel).suffix.lower()
        if ext in {".mp3", ".wav", ".ogg", ".m4a"}:
            summary["audio"] += 1
        if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            summary["images"] += 1
    summary["total_media"] = summary["audio"] + summary["images"]
    return summary


def discover_links(files: list[tuple[str, Path, int, str]]) -> list[dict]:
    """Evidence-based candidate links only; no automatic lesson matching."""
    paths = {r for r, *_ in files}
    found: dict[tuple[str, str], dict] = {}
    for rel, path, size, _ in files:
        if path.suffix.lower() not in {".html", ".htm", ".json"} or size > 4 * 1024 * 1024:
            continue
        raw = path.read_text(encoding="utf-8-sig", errors="replace")
        for match in URL_PATTERN.finditer(raw):
            candidate = (match.group(1) or match.group(2) or "").strip()
            if not candidate or candidate.startswith(("#", "//", "data:", "javascript:", "mailto:")):
                continue
            parsed = urlsplit(candidate)
            if parsed.scheme:
                if parsed.scheme != "https" or parsed.hostname not in {"skyed.org", "course.skyed.org"}:
                    continue
                dest = parsed.path.lstrip("/")
            else:
                from posixpath import normpath, dirname, join
                dest = normpath(join(dirname(rel), unquote(parsed.path).lstrip("/")))
            if not dest or dest == ".":
                continue
            if dest not in paths and dest + "/index.html" not in paths:
                continue
            if not dest.endswith((".html", ".htm")) and not parsed.fragment:
                continue
            key = (candidate, rel)
            found[key] = {"candidate": candidate, "found_in": rel, "file_target_exists": True, "approved": False}
    return [found[k] for k in sorted(found)]


def audit(source: Path, min_media: int = 400) -> tuple[list, dict]:
    files = safe_tree(source)
    media = media_summary(files)
    if min_media < 0 or media["total_media"] < min_media:
        raise GateError(f"MEDIA_GATE=BLOCKED: found {media['total_media']} media, require at least {min_media}; check full remote capture")
    inventory = {
        "schema_version": 1,
        "release": RELEASE,
        "scope": "read-only source audit",
        "publication_authorized": False,
        "file_count": len(files),
        "total_bytes": sum(x[2] for x in files),
        "media": media,
        "files": {rel: {"size": size, "sha256": sha} for rel, _, size, sha in files},
        "candidate_links": discover_links(files),
    }
    return files, inventory


def _write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_existing(source: Path, stage: Path, report: dict) -> None:
    """Require exact file equality and that the live root was never overwritten."""
    legacy = report.get("legacy_files")
    if not isinstance(legacy, dict):
        raise GateError("Invalid stage manifest")
    for rel, expected in legacy.items():
        original = source / rel
        copied = stage / rel
        if not copied.is_file() or digest(copied) != expected or not original.is_file() or digest(original) != expected:
            raise GateError(f"Existing Course Hub file changed: {rel}")
    staged_paths = {p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()}
    if staged_paths - set(legacy) - {PREVIEW_DIR + "/" + rel for rel in report.get("lobby_files", {})}:
        raise GateError("Unexpected file appeared in integration staging")
    for rel, expected in report.get("lobby_files", {}).items():
        path = stage / PREVIEW_DIR / rel
        if not path.is_file() or digest(path) != expected:
            raise GateError(f"Staged lobby file missing or modified: {rel}")


def stage(source: Path, lobby: Path, output: Path, min_media: int = 400) -> dict:
    source, lobby, output = source.resolve(strict=True), lobby.resolve(strict=True), output.resolve()
    if not lobby.joinpath("index.html").is_file() or not lobby.joinpath("content/lobby.json").is_file():
        raise GateError("Lobby source missing index.html or lobby.json")
    if output.exists():
        raise GateError("Output already exists: never overwrite a previous staging attempt")
    for protected in (source, lobby):
        if output == protected or protected in output.parents or output in protected.parents:
            raise GateError("Output must be outside both original source trees")
    output.parent.mkdir(parents=True, exist_ok=True)
    old_files, inventory = audit(source, min_media)
    new_files = safe_tree_for_lobby(lobby)
    lobby_content = json.loads((lobby / "content" / "lobby.json").read_text(encoding="utf-8-sig"))
    # Published cards are not promoted merely because somebody edited a JSON field.
    published = [x.get("id") for x in lobby_content.get("lessons", []) if x.get("status") == "published"]
    if published:
        raise GateError(f"LOBBY_APPROVAL_GATE=BLOCKED: {len(published)} published cards require verified URL mapping; use unlinked draft placeholders")
    if len(lobby_content.get("lessons", [])) < 11:
        raise GateError("Missing original eleven pilot lesson placeholders")
    from shutil import copy2
    temp = Path(tempfile.mkdtemp(prefix="skyed-stage-", dir=str(output.parent)))
    try:
        for rel, src, _, _ in old_files:
            dst = temp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            copy2(src, dst)
        for rel, src, _, _ in new_files:
            dst = temp / PREVIEW_DIR / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            copy2(src, dst)
        report = {
            "schema_version": 1,
            "release": RELEASE,
            "status": "STAGED_NOT_DEPLOYED",
            "production_mutation": False,
            "production_promotion_authorized": False,
            "existing_entrypoint_unchanged": True,
            "all_media_bytes_preserved": True,
            "lesson_mapping_status": "UNVERIFIED_PLACEHOLDERS",
            "media": inventory["media"],
            "legacy_files": {rel: h for rel, _, _, h in old_files},
            "lobby_files": {rel: h for rel, _, _, h in new_files},
            "original_lesson_placeholder_count": len(lobby_content.get("lessons", [])),
            "candidate_links": inventory["candidate_links"],
        }
        verify_existing(source, temp, report)
        temp.rename(output)
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return report


def safe_tree_for_lobby(root: Path):
    allowed = {"index.html", "assets/app.js", "assets/styles.css", "assets/favicon.svg", "content/lobby.json"}
    items=[]
    for file in sorted(root.rglob("*")):
        if file.is_dir():
            if file.is_symlink():
                raise GateError("Lobby symlink not allowed")
            continue
        rel = file.relative_to(root).as_posix()
        if file.is_symlink() or rel.startswith(".") or not file.is_file() or ".." in PurePosixPath(rel).parts:
            raise GateError("Unsafe lobby member")
        if rel == "assets/media/README.txt":
            continue  # Internal design guidance, not a website asset.
        if rel not in allowed and not (rel.startswith("assets/media/") and file.suffix.lower() in MEDIA_SUFFIXES):
            raise GateError("Unexpected lobby file in public stage: " + rel)
        items.append((rel,file,file.stat().st_size,digest(file)))
    if not allowed.issubset({r for r,*_ in items}):
        raise GateError("Required lobby frontend member missing")
    return items


def write_reports(report: dict, report_dir: Path):
    if report_dir.exists():
        raise GateError("Report output already exists; refuses overwrite")
    report_dir.mkdir(parents=True)
    _write_json(report_dir / "integration-report.json", report)
    with (report_dir / "legacy-link-candidates.csv").open("w",encoding="utf-8-sig",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=("candidate","found_in","file_target_exists","approved"))
        writer.writeheader()
        writer.writerows(report["candidate_links"])
    with (report_dir / "lesson-linking-review.csv").open("w",encoding="utf-8-sig",newline="") as file:
        writer=csv.writer(file)
        writer.writerow(["lesson_id","lesson_title","verified_existing_route","source_file_sha256","review_status"])
        for i in range(report["original_lesson_placeholder_count"]):
            writer.writerow([f"pilot-{i+1:02d}","EDIT VERIFIED TITLE","","","HUMAN_REVIEW_REQUIRED"])


def preview(root: Path, port: int):
    """Read-only loopback browser preview for staged current site + new lobby."""
    root=root.resolve(strict=True)
    if not (root / PREVIEW_DIR / "index.html").is_file():
        raise GateError("Not a complete staged site")
    if not 0 <= port <= 65535:
        raise GateError("Invalid port")
    class ReadOnly(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)
        def do_POST(self):
            self.send_error(405, "Read-only preview")
        def list_directory(self, path):
            self.send_error(404)
            return None
        def end_headers(self):
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            super().end_headers()
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), ReadOnly) as server:
        print(f"SKYED_STAGE_PREVIEW=http://127.0.0.1:{server.server_address[1]}/{PREVIEW_DIR}/",flush=True)
        server.serve_forever()


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest="mode",required=True)
    scan=subs.add_parser("audit");scan.add_argument("--source",type=Path,required=True);scan.add_argument("--out",type=Path,required=True);scan.add_argument("--min-media",type=int,default=400)
    build=subs.add_parser("stage");build.add_argument("--source",type=Path,required=True);build.add_argument("--lobby",type=Path,required=True);build.add_argument("--output",type=Path,required=True);build.add_argument("--report",type=Path,required=True);build.add_argument("--min-media",type=int,default=400)
    check=subs.add_parser("verify");check.add_argument("--source",type=Path,required=True);check.add_argument("--stage",type=Path,required=True);check.add_argument("--report",type=Path,required=True)
    serve=subs.add_parser("preview");serve.add_argument("--stage",type=Path,required=True);serve.add_argument("--port",type=int,default=0)
    args=parser.parse_args(argv)
    try:
        if args.mode == "audit":
            _,info=audit(args.source,args.min_media)
            if args.out.exists():raise GateError("Refusing to overwrite existing audit report")
            _write_json(args.out,info)
            print(f"SKYED_SITE_AUDIT=PASS files={info['file_count']} media={info['media']['total_media']}")
        elif args.mode == "stage":
            if args.report.exists():raise GateError("Refusing to overwrite report directory")
            report=stage(args.source,args.lobby,args.output,args.min_media)
            write_reports(report,args.report)
            print(f"SKYED_COURSE_HUB_STAGE=PASS legacy={len(report['legacy_files'])} media={report['media']['total_media']} preview_files={len(report['lobby_files'])}")
            print("SKYED_COURSE_HUB_PRODUCTION_WRITE=false")
        elif args.mode == "verify":
            report=json.loads((args.report / "integration-report.json").read_text(encoding="utf-8"))
            verify_existing(args.source,args.stage,report)
            print("SKYED_STAGE_VERIFY=PASS CURRENT_SITE_BYTES_PRESERVED=true")
        else:
            preview(args.stage,args.port)
    except (GateError,OSError,ValueError,KeyError) as exc:
        print(f"SKYED_COURSE_HUB_INTEGRATION=BLOCKED {type(exc).__name__}: {exc}",file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
