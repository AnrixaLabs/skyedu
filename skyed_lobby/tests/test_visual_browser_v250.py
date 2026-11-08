"""Real Chromium regression: Bright homepage survives every lesson transition."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'tests'))
from test_pilot_route_reconciliation import PilotRouteReconciliation
import course_hub_release
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright=None

@unittest.skipIf(sync_playwright is None,'Playwright not installed (mandatory in browser CI)')
class BrightRootNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=PilotRouteReconciliation(methodName='test_case_status_never_claims_publication')
        cls.fixture.setUp()
        cls.root=cls.fixture.base/'bright-root'
        cls.report=cls.fixture.base/'bright-report'
        course_hub_release.build(cls.fixture.original,cls.fixture.lobby,cls.root,cls.report,min_media=0)
        cls.server=subprocess.Popen([sys.executable,str(ROOT/'scripts/course_hub_release.py'),'preview','--candidate',str(cls.root)],
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
        line=cls.server.stdout.readline().strip()
        if not line.startswith('SKYED_V250_ROOT_PREVIEW='):
            raise RuntimeError('Candidate server did not start: '+line)
        cls.url=line.partition('=')[2]

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        try:cls.server.wait(timeout=5)
        except subprocess.TimeoutExpired:cls.server.kill()
        cls.fixture.doCleanups()

    def test_desktop_and_mobile_stay_on_bright(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
            try:
                for width in (1440,390):
                    page=browser.new_page(viewport={'width':width,'height':900})
                    problems=[]
                    page.on('pageerror',lambda exc:problems.append(str(exc)))
                    page.goto(self.url,wait_until='networkidle')
                    self.assertIn('SkyED',page.title())
                    self.assertEqual(page.locator('.program-card').count(),5)
                    image=page.locator('.program-card img').first
                    image.wait_for()
                    self.assertGreaterEqual(image.evaluate('(n)=>n.naturalWidth'),1000)
                    page.locator('.program-card').first.click()
                    self.assertIn('#/program/young-learners',page.url)
                    page.locator('.units-grid').wait_for(state='visible')
                    self.assertEqual(page.locator('.units-grid').count(),1)
                    page.locator('a[href^="#/lesson/"]').first.click()
                    self.assertIn('#/lesson/',page.url)
                    page.locator('.learning-tabs').wait_for(state='visible')
                    self.assertEqual(page.locator('.learning-tabs').count(),1)
                    self.assertEqual(page.evaluate('location.pathname'),'/')
                    self.assertNotIn('classic.html',page.url)
                    page.locator('[data-action="mode"][data-mode="practice"]').first.click()
                    page.locator('.choice-grid').wait_for(state='visible')
                    self.assertGreater(page.locator('.choice-grid').count(),0)
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-document.documentElement.clientWidth'),1)
                    page.locator('#language-toggle').click()
                    page.wait_for_function("document.documentElement.lang === 'zh'")
                    self.assertEqual(page.evaluate('document.documentElement.lang'),'zh')
                    self.assertFalse(problems,problems)
                    page.close()
            finally:browser.close()

if __name__=='__main__':unittest.main()
