"""Real Chromium end-to-end editor/save/preview workflow.

Enabled in browser CI with SKYED_RUN_BROWSER_TESTS=1; skipped in the Windows
installer unless Chromium is explicitly configured on the workstation.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get('SKYED_RUN_BROWSER_TESTS') == '1', 'Browser gate is run by explicit CI')
@unittest.skipUnless(sync_playwright is not None and shutil.which('chromium'), 'Chromium + playwright required')
class RealBrowserTests(unittest.TestCase):
    def test_editor_to_local_save_to_live_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            shadow = Path(tmp) / 'skyed_lobby'
            shutil.copytree(ROOT / 'site', shadow / 'site')
            shutil.copytree(ROOT / 'tools', shadow / 'tools')
            (shadow / 'scripts').mkdir()
            shutil.copy2(ROOT / 'scripts' / 'control_server.py', shadow / 'scripts' / 'control_server.py')
            env = dict(os.environ, SKYED_LOBBY_EDITOR_TOKEN='z'*48, PYTHONUNBUFFERED='1')
            process = subprocess.Popen([sys.executable, '-u', str(shadow / 'scripts' / 'control_server.py'), '--port', '0'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
            try:
                line = process.stdout.readline().strip()
                self.assertTrue(line.startswith('SKYED_LOBBY_READY='), line)
                origin = line.split('=',1)[1]
                with sync_playwright() as p:
                    browser = p.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
                    page = browser.new_page(viewport={'width':1420,'height':900})
                    errors=[]
                    page.on('pageerror', lambda x: errors.append(str(x)))
                    page.goto(origin + '/tools/edit-lobby.html',wait_until='domcontentloaded')
                    page.wait_for_selector('#field-title')
                    self.assertTrue(page.locator('#save-button').is_visible())
                    new_title='Integrated Lobby Design E2E'
                    page.locator('#field-title').fill(new_title)
                    page.locator('#save-button').click()
                    page.get_by_text('Saved locally to site/content/lobby.json.').wait_for(timeout=7000)
                    saved=json.loads((shadow / 'site/content/lobby.json').read_text(encoding='utf8'))
                    self.assertEqual(saved['site']['title'],new_title)
                    self.assertTrue((shadow/'backups/lobby.json.previous').exists())
                    page.goto(origin + '/site/', wait_until='domcontentloaded')
                    page.wait_for_function('(title)=>document.body.innerText.includes(title)',new_title)
                    self.assertEqual(errors, [])
                    browser.close()
            finally:
                process.terminate()
                try:process.wait(timeout=4)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=4)


if __name__ == '__main__':
    unittest.main()
