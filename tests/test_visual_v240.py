"""SkyED v2.4.0 real-source visual layer and non-destructive staging gates."""
from __future__ import annotations
import importlib.util
import json
import re
from pathlib import Path
import tempfile
import unittest
from shutil import copytree

ROOT = Path(__file__).resolve().parents[1]
LOBBY = ROOT / "skyed_lobby/site"
ENGINE = ROOT / "scripts/course_hub_integration.py"
spec = importlib.util.spec_from_file_location('skyed_visual_stage_engine', ENGINE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class VisualSourceContract(unittest.TestCase):
    def test_exact_artwork_assets(self):
        arts = list((LOBBY / 'assets/illustrations').glob('*.webp'))
        self.assertIn(len(arts),(18,19))
        for art in arts:
            self.assertGreater(art.stat().st_size, 3000, art.name)
            self.assertEqual(art.read_bytes()[:4], b'RIFF', art.name)
            self.assertEqual(art.read_bytes()[8:12], b'WEBP', art.name)

    def test_all_original_local_editing_and_staging_contracts_remain(self):
        draft = json.loads((LOBBY / 'content/lobby.json').read_text(encoding='utf-8'))
        self.assertEqual(len(draft['lessons']), 11)
        self.assertEqual(len(draft['programs']), 5)
        self.assertEqual(sum(bool(x['placeholder']) for x in draft['programs']), 4)
        safe = mod.safe_tree_for_lobby(LOBBY)
        self.assertEqual(len(safe), 5+len(list((LOBBY / 'assets/illustrations').glob('*.webp'))))
        self.assertFalse(any('tools/' in item[0] or 'control_server.py' in item[0] for item in safe))

    def test_legacy_lobby_without_bright_artwork_still_stages(self):
        """Existing v2.3.x packages retain their original staging contract."""
        with tempfile.TemporaryDirectory() as temp:
            clone = Path(temp) / 'legacy-lobby'
            copytree(LOBBY, clone)
            for path in (clone / 'assets/illustrations').glob('*.webp'):
                path.unlink()
            self.assertEqual(len(mod.safe_tree_for_lobby(clone)), 5)

    def test_incomplete_bright_artwork_blocks_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            clone = Path(temp) / 'partial-lobby'
            copytree(LOBBY, clone)
            (clone / 'assets/illustrations/topic-01.webp').unlink()
            with self.assertRaisesRegex(mod.GateError, 'Bright lobby illustrations missing'):
                mod.safe_tree_for_lobby(clone)

    def test_secure_local_app_contract(self):
        app = (LOBBY/'assets/app.js').read_text(encoding='utf-8')
        index = (LOBBY/'index.html').read_text(encoding='utf-8')
        for needed in ("data/catalog.v1.json", "data/content.v1.json", "answer_index", "pathAsset", "localStorage", "quizFinished", "playAudio", "window.addEventListener('hashchange'", "state.lang", "state.saved"):
            self.assertIn(needed, app)
        for needed in ("script-src 'self'", "media-src 'self'", "object-src 'none'", "form-action 'none'", '<main id="main"', 'id="menu-toggle"'):
            self.assertIn(needed, index)
        self.assertNotIn('https://fonts.googleapis.com', index)
        self.assertNotIn('innerHTML = data', app)
        self.assertNotIn('navigator.mediaDevices.getUserMedia', app)
        self.assertNotIn('published:true', app)
        self.assertNotIn('3 / 5', app)

    def test_visual_does_not_change_source_publishing_rights(self):
        app = (LOBBY/'assets/app.js').read_text(encoding='utf-8')
        self.assertIn('catalog.published===false', app)
        self.assertIn('teacher', app.lower())
        self.assertIn('source only' if False else 'No accounts or remote sync.', app)
        self.assertTrue((ROOT/'skyed_lobby/tools/edit-lobby.html').is_file())

    def test_staging_is_read_only_and_rejects_unknown_illustration(self):
        with tempfile.TemporaryDirectory() as temp:
            clone=Path(temp)/'lobby'
            copytree(LOBBY,clone)
            extra=clone/'assets/illustrations/private.txt'
            extra.write_text('secret',encoding='utf-8')
            with self.assertRaisesRegex(mod.GateError,'Unexpected lobby file'):
                mod.safe_tree_for_lobby(clone)


if __name__ == '__main__':
    unittest.main()
