"""Authenticated API hardening contracts for the v2.3.1 candidate."""
from __future__ import annotations

import io
import sys
from email.message import Message
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "build" / "growthbridge" / "SkyED-GrowthBridge-v2.3.1" / "backend"))
# The source root may also be provided explicitly by CI, without modifying sys.path
if len(sys.argv) > 1:
    sys.path.insert(0, str(Path(sys.argv[1]).resolve() / "backend"))

from server import Handler  # type: ignore  # imported from verified candidate


def verify_proxy_ip() -> None:
    handler = object.__new__(Handler)
    handler.client_address = ("127.0.0.1", 10000)
    headers = Message()
    headers["X-Real-IP"] = "203.0.113.8"
    handler.headers = headers
    assert handler._client_ip() == "203.0.113.8"
    headers.replace_header("X-Real-IP", "spoofed, invalid")
    assert handler._client_ip() == "127.0.0.1"
    handler.client_address = ("198.51.100.9", 10000)
    headers.replace_header("X-Real-IP", "203.0.113.8")
    assert handler._client_ip() == "198.51.100.9"
    print("PROXY_TRUST_BOUNDARY=PASS")


def verify_api_headers() -> None:
    handler = object.__new__(Handler)
    handler.command = "GET"
    handler.wfile = io.BytesIO()
    result = []
    handler.send_response = lambda code: result.append(("status", str(code)))
    handler.send_header = lambda name, value: result.append((name, value))
    handler.end_headers = lambda: None
    handler._json(200, {"ok": True})
    headers = dict(result)
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert b'"ok": true' in handler.wfile.getvalue()
    print("API_PRIVACY_HEADERS=PASS")


if __name__ == "__main__":
    verify_proxy_ip()
    verify_api_headers()
