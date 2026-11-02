"""Real localhost HTTP, security, persistence and integration tests (stdlib)."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("private_lobby_server", HERE / "scripts" / "control_server.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LobbyContract(unittest.TestCase):
    def setUp(self):
        self.seed = json.loads((HERE / "site" / "content" / "lobby.json").read_text(encoding="utf8"))

    def test_base_content(self):
        module.validate_content(self.seed)
        self.assertEqual(len(self.seed["programs"]), 5)
        self.assertEqual(len(self.seed["lessons"]), 11)
        self.assertEqual(sum(p["placeholder"] for p in self.seed["programs"]), 4)
        self.assertTrue(all(not x["url"] and x["status"] == "needs-link" for x in self.seed["lessons"]))

    def test_block_bad_relationship(self):
        copy_doc = copy.deepcopy(self.seed)
        copy_doc["lessons"][0]["programId"] = "not-a-program"
        with self.assertRaisesRegex(ValueError, "relationships"):
            module.validate_content(copy_doc)

    def test_published_requires_approved_url(self):
        for address in ("", "http://skyed.org/page", "https://malicious.invalid/", "//skyed.org/page", "javascript:alert(1)", "/\\evil"):
            d = copy.deepcopy(self.seed)
            d["lessons"][0].update(status="published", url=address)
            with self.subTest(address=address), self.assertRaises(ValueError):
                module.validate_content(d)

    def test_no_unsafe_media(self):
        d = copy.deepcopy(self.seed)
        d["programs"][0]["image"] = "assets/media/../../private.env"
        with self.assertRaises(ValueError):
            module.validate_content(d)

    def test_content_file_atomic_and_backup(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            target = root / "site" / "content" / "lobby.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(self.seed), encoding="utf-8")
            original = target.read_bytes()
            updated = copy.deepcopy(self.seed)
            updated["site"]["title"] = "A localized design test"
            module.save_content(updated, root)
            self.assertEqual(json.loads(target.read_text(encoding="utf8"))["site"]["title"], "A localized design test")
            self.assertEqual((root / "backups" / "lobby.json.previous").read_bytes(), original)
            d = copy.deepcopy(updated)
            d["lessons"][0]["programId"] = "missing"
            with self.assertRaises(ValueError):
                module.save_content(d, root)
            self.assertEqual(json.loads(target.read_text(encoding="utf8"))["site"]["title"], "A localized design test")

    def test_public_tools_are_outside_site(self):
        self.assertFalse((HERE / "site" / "tools").exists())
        self.assertTrue((HERE / "tools" / "edit-lobby.html").is_file())


class LocalServerContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        shutil.copytree(HERE / "site", self.root / "site")
        shutil.copytree(HERE / "tools", self.root / "tools")
        self.token = "safe-test-token-" + "x" * 40
        self.server = module.Server(("127.0.0.1", 0), self.token, self.root)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def request(self, path, *, method="GET", doc=None, token=None, origin=None, host=None):
        body = None if doc is None else json.dumps(doc).encode()
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["X-SkyED-Editor-Token"] = token
        if origin:
            headers["Origin"] = origin
        if host:
            headers["Host"] = host
        req = Request(self.origin + path, data=body, method=method, headers=headers)
        return urlopen(req, timeout=4)

    def test_home_and_session(self):
        with self.request("/site/index.html") as result:
            self.assertEqual(result.status, 200)
            self.assertIn(b"Course Hub", result.read())
        with self.request("/api/session") as result:
            session = json.loads(result.read())
            self.assertEqual(session["editorToken"], self.token)
            self.assertTrue(session["canSave"])

    def test_save_requires_token(self):
        doc = json.loads((self.root / "site/content/lobby.json").read_text(encoding="utf-8"))
        old = (self.root / "site/content/lobby.json").read_bytes()
        with self.assertRaises(HTTPError) as err:
            self.request("/api/save-content", method="POST", doc=doc)
        self.assertEqual(err.exception.code, 403)
        self.assertEqual((self.root / "site/content/lobby.json").read_bytes(), old)

    def test_save_updates_only_local_draft(self):
        doc = json.loads((self.root / "site/content/lobby.json").read_text(encoding="utf-8"))
        doc["site"]["title"] = "Website design updated by Control Panel"
        with self.request("/api/save-content", method="POST", doc=doc, token=self.token, origin=self.origin) as response:
            self.assertTrue(json.loads(response.read())["saved"])
        self.assertEqual(json.loads((self.root / "site/content/lobby.json").read_text(encoding="utf-8"))["site"]["title"], doc["site"]["title"])
        self.assertTrue((self.root / "backups" / "lobby.json.previous").is_file())

    def test_bad_url_cannot_save(self):
        doc = json.loads((self.root / "site/content/lobby.json").read_text(encoding="utf-8"))
        doc["lessons"][0].update(status="published", url="https://evil.invalid/")
        with self.assertRaises(HTTPError) as err:
            self.request("/api/save-content", method="POST", doc=doc, token=self.token)
        self.assertEqual(err.exception.code, 400)

    def test_bad_origin_and_host(self):
        with self.assertRaises(HTTPError) as err:
            self.request("/api/session", origin="https://evil.invalid")
        self.assertEqual(err.exception.code, 403)
        with self.assertRaises(HTTPError) as err:
            self.request("/api/session", host="evil.invalid")
        self.assertEqual(err.exception.code, 403)

    def test_server_does_not_serve_python_or_backups(self):
        for endpoint in ("/scripts/control_server.py", "/backups/lobby.json.previous", "/site/../scripts/control_server.py", "/site/content/../../tools/editor.js"):
            with self.subTest(endpoint=endpoint), self.assertRaises(HTTPError) as err:
                self.request(endpoint)
            self.assertIn(err.exception.code, (403, 404))


if __name__ == "__main__":
    unittest.main()
