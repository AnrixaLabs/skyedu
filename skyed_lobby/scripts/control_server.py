"""Private loopback-only preview and draft editor for the SkyED Control Panel.

Only site/ and tools/ are served. POST writes exactly one JSON content file after
per-process CSRF, same-origin, size, schema and URL checks. No network publish.
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "site" / "content" / "lobby.json"
ALLOWED_URL_HOSTS = frozenset({"skyed.org", "course.skyed.org"})
SAFE_MEDIA = re.compile(r"^assets/media/[a-zA-Z0-9_/-]+\.(?:png|jpe?g|webp|svg)$")
SAFE_ID = re.compile(r"^[a-z0-9-]+$")
MAX_CONTENT = 1024 * 1024


def validate_content(doc: object) -> dict:
    """Reject broken references, unknown URLs and malformed content pre-write."""
    if not isinstance(doc, dict) or doc.get("schemaVersion") != 1:
        raise ValueError("Invalid lobby schemaVersion")
    if not isinstance(doc.get("site"), dict) or not isinstance(doc.get("navigation"), list) or not isinstance(doc.get("filters"), dict):
        raise ValueError("Missing site/navigation/filters")
    for kind in ("programs", "groups", "lessons"):
        items = doc.get(kind)
        if not isinstance(items, list) or len(items) > 5000:
            raise ValueError("Invalid " + kind)
        ids = [item.get("id") for item in items if isinstance(item, dict)]
        if len(ids) != len(items) or len(set(ids)) != len(ids) or not all(isinstance(x, str) and SAFE_ID.fullmatch(x) for x in ids):
            raise ValueError("Invalid or duplicate " + kind + " IDs")
    programs = {item["id"] for item in doc["programs"]}
    groups = {item["id"] for item in doc["groups"]}

    def media(value: object) -> bool:
        return value in ("", None) or (isinstance(value, str) and ".." not in value and bool(SAFE_MEDIA.fullmatch(value)))

    def url(value: object) -> bool:
        if not isinstance(value, str) or not value or value.startswith("//") or "\\" in value or any(ord(c) < 32 for c in value):
            return False
        if value.startswith("/") and not value.startswith("//"):
            return True
        parsed = urlsplit(value)
        try:
            return parsed.scheme == "https" and parsed.hostname in ALLOWED_URL_HOSTS and not parsed.username and not parsed.password and parsed.port is None
        except ValueError:
            return False

    if not media(doc["site"].get("heroImage")):
        raise ValueError("Unsafe hero image")
    for item in doc["programs"]:
        if not media(item.get("image")):
            raise ValueError("Unsafe program image")
    for item in doc["lessons"]:
        if item.get("programId") not in programs or item.get("groupId") not in groups:
            raise ValueError("Broken lesson relationships")
        if not media(item.get("media")):
            raise ValueError("Unsafe lesson media")
        if item.get("status") == "published" and not url(item.get("url")):
            raise ValueError("Published lesson requires approved URL")
        if item.get("url") and not url(item["url"]):
            raise ValueError("Unsafe lesson URL")
    if doc["site"].get("backToCurrentSiteUrl") and not url(doc["site"]["backToCurrentSiteUrl"]):
        raise ValueError("Unsafe back URL")
    return doc


def encode_content(doc: object) -> bytes:
    validated = validate_content(doc)
    raw = (json.dumps(validated, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(raw) > MAX_CONTENT:
        raise ValueError("Content exceeds 1 MB")
    return raw


def save_content(doc: object, root: Path = ROOT) -> Path:
    """Write to project-local drafts with an atomic replace and recoverable backup."""
    target = root / "site" / "content" / "lobby.json"
    if not target.is_file() or target.is_symlink() or target.resolve().parent != (root / "site" / "content").resolve():
        raise ValueError("Invalid content destination")
    raw = encode_content(doc)
    previous = target.read_bytes()
    if hashlib.sha256(raw).digest() == hashlib.sha256(previous).digest():
        return target
    backup = root / "backups" / "lobby.json.previous"
    backup.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=backup.parent, delete=False) as stream:
        temp = Path(stream.name)
        stream.write(previous)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, backup)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        temp = Path(stream.name)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink()
    return target


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, token: str, root: Path = ROOT):
        self.editor_token = token
        self.root = root.resolve()
        super().__init__(address, Handler)


class Handler(http.server.SimpleHTTPRequestHandler):
    server: Server

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args):
        # A local editor's query strings and credentials must not appear in logs.
        pass

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        super().end_headers()

    def _allowed_origin(self) -> bool:
        port = self.server.server_address[1]
        allowed_host = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = self.headers.get("Host", "")
        if host not in allowed_host:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin in {"http://" + x for x in allowed_host}

    def _json(self, status: int, payload: dict):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not self._allowed_origin():
            self.send_error(403, "Invalid request host/origin")
            return
        path = urlsplit(self.path).path
        if path == "/api/session":
            self._json(200, {"editorToken": self.server.editor_token, "canSave": True})
            return
        if path in ("", "/"):
            self.send_response(302)
            self.send_header("Location", "/site/")
            self.end_headers()
            return
        # Explicit static roots; exclude scripts, backups, private files, etc.
        if not path.startswith(("/site/", "/tools/")):
            self.send_error(404)
            return
        raw = unquote(path)
        if "\\" in raw or "\x00" in raw:
            self.send_error(404)
            return
        parts = Path(raw.lstrip("/")).parts
        if ".." in parts or any(p.startswith(".") for p in parts):
            self.send_error(404)
            return
        candidate = (self.server.root / raw.lstrip("/")).resolve()
        allowed_root = (self.server.root / parts[0]).resolve()
        if not candidate.is_relative_to(allowed_root) or not candidate.is_file() and not candidate.is_dir():
            self.send_error(404)
            return
        if candidate.is_dir():
            if candidate == (self.server.root / "site").resolve():
                self.path = "/site/index.html"
            else:
                self.send_error(404)
                return
        return super().do_GET()

    def do_POST(self):
        if not self._allowed_origin() or urlsplit(self.path).path != "/api/save-content":
            self.send_error(403)
            return
        if self.headers.get("X-SkyED-Editor-Token", "") != self.server.editor_token:
            self._json(403, {"error": "Editor session is invalid"})
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            self._json(415, {"error": "Expected application/json"})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._json(411, {"error": "Missing Content-Length"})
            return
        if length <= 0 or length > MAX_CONTENT:
            self._json(413, {"error": "Invalid content length"})
            return
        try:
            doc = json.loads(self.rfile.read(length))
            target = save_content(doc, self.server.root)
        except (ValueError, TypeError, UnicodeError) as error:
            self._json(400, {"error": str(error)[:180]})
            return
        except OSError:
            self._json(500, {"error": "Local write failed; original content not changed"})
            return
        self._json(200, {"saved": True, "file": "site/content/lobby.json", "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        raise SystemExit("Invalid port")
    token = os.environ.get("SKYED_LOBBY_EDITOR_TOKEN", "")
    if len(token) < 32:
        raise SystemExit("No authorized editor token; server not started")
    with Server(("127.0.0.1", args.port), token) as srv:
        print(f"SKYED_LOBBY_READY=http://127.0.0.1:{srv.server_address[1]}", flush=True)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
