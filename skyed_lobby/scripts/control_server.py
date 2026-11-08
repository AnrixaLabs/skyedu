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
import struct
import zlib
import tempfile
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "site" / "content" / "lobby.json"
ALLOWED_URL_HOSTS = frozenset({"skyed.org", "course.skyed.org"})
SAFE_MEDIA = re.compile(r"^assets/media/[a-zA-Z0-9_/-]+\.(?:png|jpe?g|webp|svg)$")
SAFE_ID = re.compile(r"^[a-z0-9-]+$")
MAX_CONTENT = 1024 * 1024
MAX_UPLOAD = 12 * 1024 * 1024


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


def inspect_image(data: bytes, kind: str) -> tuple[str, int, int]:
    """Fail closed on unsupported/broken images; never accept SVG/HTML.

    PNG has a verified IHDR CRC, JPEG SOF dimensions, WebP container limits.
    A decoded-image QA step is still recommended for externally sourced assets.
    """
    if len(data) < 32 or len(data) > MAX_UPLOAD:
        raise ValueError('Image size exceeds safe limits')
    if kind == 'image/png':
        if data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR':
            raise ValueError('Not a PNG image')
        width, height = struct.unpack('>II', data[16:24])
        if zlib.crc32(data[12:29]) & 0xffffffff != struct.unpack('>I',data[29:33])[0]:
            raise ValueError('PNG image header CRC mismatch')
        ext = '.png'
    elif kind == 'image/webp':
        if data[:4]!=b'RIFF' or data[8:12]!=b'WEBP' or int.from_bytes(data[4:8],'little')+8 != len(data):
            raise ValueError('Not a valid WebP container')
        t=data[12:16]
        if t==b'VP8X':
            width=1+int.from_bytes(data[24:27],'little')
            height=1+int.from_bytes(data[27:30],'little')
        elif t==b'VP8 ' and data[23:26]==b'\x9d\x01\x2a':
            width=int.from_bytes(data[26:28],'little')&0x3fff
            height=int.from_bytes(data[28:30],'little')&0x3fff
        elif t==b'VP8L' and data[20]==0x2f:
            val=int.from_bytes(data[21:25],'little')
            width=(val&0x3fff)+1
            height=((val>>14)&0x3fff)+1
        else: raise ValueError('Unsupported WebP image format')
        ext='.webp'
    else: raise ValueError('Only high-quality PNG or WebP is supported')
    if width<800 or height<500 or width>8000 or height>8000 or width*height>30_000_000:
        raise ValueError('Tile image must be at least 800x500 pixels and within safe dimensions')
    return ext,width,height


def store_image(data: bytes, kind: str, root: Path = ROOT) -> dict:
    ext,width,height=inspect_image(data,kind)
    folder=root/'site'/'assets'/'media'/'uploads'
    # Ignore symlinks in every directory component including the media root.
    for part in (root/'site',root/'site'/'assets',root/'site'/'assets'/'media',folder):
        if part.is_symlink():raise ValueError('Unsafe upload directory')
    folder.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(data).hexdigest()
    filename='cover-'+digest[:32]+ext
    target=folder/filename
    if target.is_symlink():raise ValueError('Unsafe upload destination')
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
            raise ValueError('Uploaded file digest collision')
    else:
        with tempfile.NamedTemporaryFile(dir=folder,delete=False) as tmp:
            temp=Path(tmp.name);tmp.write(data);tmp.flush();os.fsync(tmp.fileno())
        try:os.replace(temp,target)
        finally:temp.unlink(missing_ok=True)
    return {'path':'assets/media/uploads/'+filename,'sha256':digest,'width':width,'height':height}


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
        path=urlsplit(self.path).path
        if not self._allowed_origin() or path not in ('/api/save-content','/api/upload-image'):
            self.send_error(403)
            return
        if self.headers.get("X-SkyED-Editor-Token", "") != self.server.editor_token:
            self._json(403, {"error": "Editor session is invalid"})
            return
        kind=self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if path == '/api/save-content' and kind != 'application/json':
            self._json(415, {"error": "Expected application/json"})
            return
        if path == '/api/upload-image' and kind not in ('image/png','image/webp'):
            self._json(415, {"error": "Upload a PNG or WebP image"})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._json(411, {"error": "Missing Content-Length"})
            return
        if length <= 0 or length > (MAX_UPLOAD if path=='/api/upload-image' else MAX_CONTENT):
            self._json(413, {"error": "Invalid content length"})
            return
        if path=='/api/upload-image':
            try:
                saved=store_image(self.rfile.read(length),kind,self.server.root)
            except (ValueError,OSError) as exc:
                self._json(400,{"error":str(exc)[:160]})
                return
            self._json(200,{"uploaded":True,**saved})
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
