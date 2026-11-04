"""Offline acceptance for strictly additive SkyED Course Hub staging."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "scripts"))
from course_hub_integration import (audit, stage, verify_existing, GateError,
                                    write_reports, digest, preview, safe_tree,
                                    discover_links, safe_tree_for_lobby)


class IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.legacy = self.path / "production-copy"
        self.legacy.mkdir()
        (self.legacy / "index.html").write_text('<!doctype html><a href="lessons/unit-01.html">Lesson</a>',encoding='utf-8')
        lessons = self.legacy / "lessons"
        lessons.mkdir()
        (lessons / "unit-01.html").write_text('EXISTING LESSON CONTENT',encoding='utf-8')
        media = self.legacy / "media"
        media.mkdir()
        for i in range(342):
            (media / f"word-{i:03d}.mp3").write_bytes(b'MP3' + str(i).encode())
        for i in range(91):
            (media / f"card-{i:03d}.png").write_bytes(b'PNG' + str(i).encode())
        self.lobby = ROOT / "skyed_lobby" / "site"
        self.output = self.path / "stage"
        self.reports = self.path / "reports"

    def test_full_433_media_staged_without_modification(self):
        baseline = {p.relative_to(self.legacy).as_posix(): digest(p) for p in self.legacy.rglob('*') if p.is_file()}
        report = stage(self.legacy,self.lobby,self.output)
        self.assertEqual(report['status'],'STAGED_NOT_DEPLOYED')
        self.assertEqual(report['media'],{'audio':342,'images':91,'total_media':433})
        self.assertFalse(report['production_mutation'])
        self.assertEqual(report['original_lesson_placeholder_count'],11)
        verify_existing(self.legacy,self.output,report)
        after = {p.relative_to(self.legacy).as_posix(): digest(p) for p in self.legacy.rglob('*') if p.is_file()}
        self.assertEqual(baseline,after)
        self.assertEqual((self.output/'index.html').read_bytes(),(self.legacy/'index.html').read_bytes())
        self.assertEqual((self.output/'lessons/unit-01.html').read_bytes(),b'EXISTING LESSON CONTENT')
        self.assertTrue((self.output/'lobby-preview/assets/styles.css').is_file())
        self.assertEqual(len(report['candidate_links']),1)
        write_reports(report,self.reports)
        self.assertTrue((self.reports/'lesson-linking-review.csv').exists())
        self.assertTrue((self.reports/'integration-report.json').exists())
        self.assertFalse((self.output/'tools').exists())

    def test_media_shortfall_fails_closed(self):
        with self.assertRaisesRegex(GateError,'MEDIA_GATE=BLOCKED'):
            audit(self.legacy,500)
        self.assertFalse(self.output.exists())

    def test_no_clobber_old_stage(self):
        self.output.mkdir()
        sentinel=self.output/'KEEP'
        sentinel.write_text('original')
        with self.assertRaisesRegex(GateError,'already exists'):
            stage(self.legacy,self.lobby,self.output)
        self.assertEqual(sentinel.read_text(),'original')

    def test_symlink_rejected(self):
        if not hasattr(Path,'symlink_to'):
            self.skipTest('No symlink support')
        try:
            (self.legacy/'link.html').symlink_to(self.legacy/'index.html')
        except OSError:
            self.skipTest('Insufficient rights to create symlink')
        with self.assertRaisesRegex(GateError,'Unsafe'):
            safe_tree(self.legacy)

    def test_secret_file_rejected(self):
        (self.legacy/'.env').write_text('NEVER_INCLUDE_THIS',encoding='utf-8')
        with self.assertRaisesRegex(GateError,'private'):
            audit(self.legacy)
        self.assertFalse(self.output.exists())

    def test_unknown_executable_rejected(self):
        (self.legacy/'setup.sh').write_text('echo HI',encoding='utf-8')
        with self.assertRaisesRegex(GateError,'Unexpected'):
            safe_tree(self.legacy)

    def test_published_unverified_lesson_prevents_stage(self):
        snapshot = self.path/'lobby-copy'
        shutil.copytree(self.lobby,snapshot)
        doc=json.loads((snapshot/'content/lobby.json').read_text(encoding='utf-8'))
        doc['lessons'][0]['status']='published'
        doc['lessons'][0]['url']='https://course.skyed.org/lesson/fake'
        (snapshot/'content/lobby.json').write_text(json.dumps(doc),encoding='utf-8')
        with self.assertRaisesRegex(GateError,'LOBBY_APPROVAL_GATE=BLOCKED'):
            stage(self.legacy,snapshot,self.output)
        self.assertFalse(self.output.exists())

    def test_stage_detects_tampered_existing_media(self):
        report=stage(self.legacy,self.lobby,self.output)
        (self.output/'media/word-000.mp3').write_bytes(b'MODIFIED')
        with self.assertRaisesRegex(GateError,'Existing Course Hub file changed'):
            verify_existing(self.legacy,self.output,report)

    def test_stage_detects_extra_files(self):
        report=stage(self.legacy,self.lobby,self.output)
        (self.output/'sneaky.js').write_text('alert(1)',encoding='utf-8')
        with self.assertRaisesRegex(GateError,'Unexpected file'):
            verify_existing(self.legacy,self.output,report)

    def test_preview_file_whitelist(self):
        items=safe_tree_for_lobby(self.lobby)
        self.assertGreaterEqual(len(items),5)
        self.assertTrue(all(not s.startswith('tools/') for s,*_ in items))

    def test_source_not_found_blocks(self):
        with self.assertRaises(FileNotFoundError):
            stage(self.path/'does-not-exist',self.lobby,self.output)


if __name__ == '__main__':
    unittest.main()
