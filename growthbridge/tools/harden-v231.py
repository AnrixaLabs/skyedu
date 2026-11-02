#!/usr/bin/env python3
"""Construct a v2.3.1 candidate from the pinned and verified v2.3.0 archive.

This script performs no network calls or production writes.
"""
from pathlib import Path
import hashlib
import shutil
import sys

ORIGINAL_SHA = "6be8aba9c1d63c502483e993e23f61978c2de3c3ae0d779c75f90e41fc866b79"


def change(path, old, new):
    data = path.read_text(encoding="utf-8")
    if data.count(old) != 1:
        raise RuntimeError("Unexpected source in " + str(path) + ": " + repr(old[:40]))
    path.write_text(data.replace(old, new), encoding="utf-8")


def manifest(root):
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "SOURCE_MANIFEST.txt"
                   and not ({"node_modules", "dist", "__pycache__", ".git"} & set(p.parts))
                   and p.suffix != ".pyc")
    lines = ["SKYED_GROWTHBRIDGE_SOURCE_MANIFEST=v2.3.1",
             "PROVENANCE_SHA256=" + ORIGINAL_SHA, "FILE_COUNT=" + str(len(files)), ""]
    lines += [hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.relative_to(root).as_posix()
              for p in files]
    (root / "SOURCE_MANIFEST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def construct(root):
    if root.name != "SkyED-GrowthBridge-v2.3.0":
        raise RuntimeError("WRONG_ORIGINAL_SOURCE_ROOT")
    server = root / "backend/server.py"
    change(server, "import hashlib\n", "import hashlib\nimport ipaddress\n")
    change(server, 'APP_VERSION = "2.3.0"', 'APP_VERSION = "2.3.1"')
    change(server, "    def _user_agent(self) -> str:\n", '''    def _client_ip(self) -> str:
        """Trust forwarded client IP only when the peer is the local Nginx proxy."""
        peer = self.client_address[0]
        if peer not in {"127.0.0.1", "::1"}:
            return peer
        value = self.headers.get("X-Real-IP", "").strip()
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            return peer

    def _user_agent(self) -> str:
''')
    change(server, "                check_mutation_rate(self.client_address[0])",
           "                check_mutation_rate(self._client_ip())")
    s = server.read_text(encoding="utf-8")
    before = "self.client_address[0], self._user_agent(),"
    if s.count(before) != 2:
        raise RuntimeError("EXPECTED_TWO_ACCOUNT_IP_CALLS")
    server.write_text(s.replace(before, "self._client_ip(), self._user_agent(),"),
                      encoding="utf-8")
    change(server, '        self.send_header("X-Content-Type-Options", "nosniff")\n',
           '''        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'; object-src 'none'; base-uri 'none'")
''')
    (root / "public/sw.js").write_text("""// Public immutable asset cache only. Never cache parent/teacher navigation or API data.
const CACHE = 'skyed-growthbridge-public-v2.3.1';
const OLD_PREFIX = 'skyed-growthbridge-shell-';
const PUBLIC = new Set(['/icon.svg', '/parent-manifest.webmanifest', '/teacher-manifest.webmanifest']);
self.addEventListener('install', e => e.waitUntil(self.skipWaiting()));
self.addEventListener('activate', e => e.waitUntil((async () => {
  const keys = await caches.keys();
  await Promise.all(keys.filter(k => k.startsWith(OLD_PREFIX)).map(k => caches.delete(k)));
  await self.clients.claim();
})()));
self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET' || request.mode === 'navigate') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
  const safe = PUBLIC.has(url.pathname) || /^\/assets\/[^/]+\.[a-f0-9]{8,}\.(?:js|css)$/.test(url.pathname);
  if (!safe) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(request);
    if (cached) return cached;
    const response = await fetch(request);
    if (response.ok && response.type === 'basic' && !response.headers.has('set-cookie')) {
      await cache.put(request, response.clone()).catch(() => undefined);
    }
    return response;
  })());
});
""", encoding="utf-8")
    for name in ("test_multitenant.py", "test_operational.py"):
        change(root / "backend" / name,
               'health["appVersion"] == "2.3.0"', 'health["appVersion"] == "2.3.1"')
    change(root / "backend/test_operational.py",
           'f"/api/v1/parent/child/{student_id}/report?period=month"',
           'f"/api/v1/parent/child/{student_id}/report?period=all"')
    change(root / "backend/test_operational.py",
           'f"/api/v1/teacher/student/{student_id}/report?institutionId={institution_id}&period=month"',
           'f"/api/v1/teacher/student/{student_id}/report?institutionId={institution_id}&period=all"')
    change(root / "src/App.tsx", "status.appVersion !== '2.3.0'",
           "status.appVersion !== '2.3.1'")
    change(root / "src/App.tsx", "Expected GrowthBridge 2.3.0",
           "Expected GrowthBridge 2.3.1")
    change(root / "package.json", '"version": "2.3.0"', '"version": "2.3.1"')
    change(root / "README.md", "**Release:** 2.3.0 — Operational Product Release",
           "**Release:** 2.3.1 — Security Hardened Candidate")
    shutil.rmtree(root / "backend/__pycache__", ignore_errors=True)
    new = root.with_name("SkyED-GrowthBridge-v2.3.1")
    root.rename(new)
    manifest(new)
    print("GROWTHBRIDGE_V231_RECONSTRUCTION=PASS")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--manifest":
        manifest(Path(sys.argv[2]))
    elif len(sys.argv) == 2:
        construct(Path(sys.argv[1]))
    else:
        raise SystemExit("Usage: harden-v231.py V230_SOURCE | --manifest V231_SOURCE")
