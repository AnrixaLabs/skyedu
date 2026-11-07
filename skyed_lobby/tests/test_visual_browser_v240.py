"""Actual Chromium HTTP+interaction gate for SkyED v2.4.0.

Uses synthetic files only in GitHub CI. Real captured catalog, content and media
are checked offline by the stage verifier, and never committed to GitHub.
"""
from __future__ import annotations
import base64
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import threading
import unittest
import wave

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

LOBBY = Path(__file__).resolve().parents[1] / 'site'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==')


@unittest.skipUnless(os.getenv('SKYED_VISUAL_BROWSER') == '1', 'Execute on GitHub Chromium browser runner')
@unittest.skipUnless(sync_playwright is not None, 'Playwright is required')
class BrightLearningBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        shutil.copytree(LOBBY, cls.root / 'lobby-preview')
        (cls.root/'data').mkdir()
        groups=['source-unit-1']*2+['source-unit-2']*2+['source-unit-3']+['lesson-series']*5+['topic-sessions']
        catalog=[]
        content={}
        for i, group in enumerate(groups):
            slug=f'hw-visual-synthetic-lesson-{i+1:02d}'
            prefix=f'assets/media/v1/test-lesson-{i+1:02d}'
            image=f'{prefix}/cards/word.png'
            audio=f'{prefix}/audio/en/word.wav'
            media=cls.root/image
            media.parent.mkdir(parents=True,exist_ok=True)
            media.write_bytes(PNG)
            voice=cls.root/audio
            voice.parent.mkdir(parents=True,exist_ok=True)
            with wave.open(str(voice),'wb') as wav:
                wav.setnchannels(1); wav.setsampwidth(2);wav.setframerate(11025)
                wav.writeframes(b''.join(struct.pack('<h',int(1500)) for _ in range(2205)))
            catalog.append({'slug':slug,'title':f'Visual lesson {i+1}','unitId':group,'cover':image})
            content[slug]={
                'vocab':[{'en':'flower','zh':'花','image':image,'audioEn':audio,'audioZh':audio}],
                'sentences':[{'en':'A flower.','zh':'一朵花','audioEn':audio,'audioZh':audio}],
                'quiz':{'questions':[{'q':'Which is flower?','choices':[{'text':'tree'},{'text':'flower'}],'answer_index':1}, {'q':'Choose the flower','prompt_image':image,'choices':[{'text':'flower'},{'text':'stone'}],'answer_index':0}]}
            }
        (cls.root/'data/catalog.v1.json').write_text(json.dumps({'schema':'skyed.course-hub.catalog.v1','site':'course.skyed.org','published':False,'lessons':catalog}),encoding='utf-8')
        (cls.root/'data/content.v1.json').write_text(json.dumps({'schema':'skyed.course-hub.content.v1','lessons':content}),encoding='utf-8')
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self,*a,**kw):super().__init__(*a,directory=str(cls.root),**kw)
            def log_message(self,*a):pass
            def do_POST(self):self.send_error(405)
            def list_directory(self,path):self.send_error(404);return None
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.origin=f'http://127.0.0.1:{cls.server.server_address[1]}/lobby-preview/'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=3);cls.temp.cleanup()

    def test_desktop_and_mobile_functional_paths(self):
        with sync_playwright() as p:
            kwargs={}
            executable=shutil.which('chromium') or shutil.which('chromium-browser')
            if executable:kwargs['executable_path']=executable
            browser=p.chromium.launch(headless=True,args=['--no-sandbox'],**kwargs)
            for width,height in [(1440,900),(390,844)]:
                with self.subTest(viewport=width):
                    context=browser.new_context(viewport={'width':width,'height':height})
                    page=context.new_page()
                    errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(self.origin+'#/discover',wait_until='networkidle')
                    page.wait_for_selector('.lesson-card')
                    self.assertEqual(page.locator('.lesson-card').count(),11)
                    self.assertEqual(page.locator('.program-card').count(),5)
                    self.assertFalse(page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                    page.locator('.program-card').first.click()
                    page.wait_for_selector('.unit-card')
                    self.assertEqual(page.locator('.unit-card').count(),5)
                    self.assertEqual(page.locator('.unit-lesson').count(),11)
                    page.locator('.unit-lesson').first.click()
                    page.wait_for_selector('.word-display img')
                    self.assertTrue(page.locator('.word-display img').evaluate('(e)=>e.complete && e.naturalWidth>0'))
                    page.get_by_role('button', name='Play English audio').click()
                    page.locator('.mode-button[data-mode="practice"]').click()
                    page.locator('.choice[data-index="1"]').click()
                    page.locator('[data-action="check-answer"]').click()
                    self.assertIn('Correct',page.locator('.answer-feedback').inner_text())
                    page.locator('[data-action="next-question"]').click()
                    page.locator('.choice[data-index="0"]').click()
                    page.locator('[data-action="check-answer"]').click()
                    page.locator('[data-action="next-question"]').click()
                    self.assertIn('2/2',page.locator('.quiz-finish').inner_text())
                    page.locator('#language-toggle').click()
                    self.assertEqual(page.locator('html').get_attribute('lang'),'zh')
                    page.goto(self.origin+'#/lessons',wait_until='networkidle')
                    page.locator('.save-heart').first.click()
                    page.goto(self.origin+'#/saved',wait_until='networkidle')
                    self.assertEqual(page.locator('.lesson-card').count(),1)
                    self.assertFalse(errors,errors)
                    context.close()
            browser.close()


if __name__ == '__main__':
    unittest.main()
