"""Loopback-only preview and private content editor. Python standard library only."""
from __future__ import annotations
import argparse
import http.server
from pathlib import Path
import socketserver
import webbrowser
ROOT = Path(__file__).resolve().parents[1]
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)
    def do_GET(self):
        if self.path in {"/", ""}:
            self.send_response(302); self.send_header("Location", "/site/"); self.end_headers(); return
        if self.path.startswith(("/.git", "/.env", "/scripts/", "/tests/", "/docs/")):
            self.send_error(404, "Not found"); return
        return super().do_GET()
    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        super().end_headers()
class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--no-browser",action="store_true")
    parser.add_argument("--open-editor",action="store_true")
    args=parser.parse_args()
    if not 1024 <= args.port <= 65535:raise SystemExit("Only unprivileged ports 1024..65535 allowed")
    with Server(("127.0.0.1",args.port),Handler) as server:
        print(f"SKYED_LOBBY_PREVIEW=http://127.0.0.1:{args.port}/site/",flush=True)
        print(f"SKYED_LOBBY_EDITOR=http://127.0.0.1:{args.port}/tools/edit-lobby.html",flush=True)
        if not args.no_browser:
            webbrowser.open(f"http://127.0.0.1:{args.port}/site/")
            if args.open_editor:webbrowser.open(f"http://127.0.0.1:{args.port}/tools/edit-lobby.html")
        try:server.serve_forever()
        except KeyboardInterrupt:print("SKYED_LOBBY_PREVIEW=STOPPED",flush=True)
if __name__=="__main__":main()
