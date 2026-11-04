"""Authoritative catalog-to-lobby reconciliation, with no human-approved publication.

Synthetic v1 catalog and media are used so CI never needs real school assets.
Tests validate stable IDs/routes, content and cover hashes, tamper detection,
source immutability, and explicit blocking when evidence is incomplete.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'scripts'))
from course_hub_integration import GateError, digest, stage, verify_existing, write_reports

UNITS = ['source-unit-1','source-unit-2','source-unit-3','lesson-series','topic-sessions']


class PilotRouteReconciliation(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.original=self.base/'authoritative-snapshot'
        self.original.mkdir()
        self.staged=self.base/'new-stage'
        self.report=self.base/'reports'
        self.lobby=ROOT/'skyed_lobby/site'
        self.lessons=[]
        self.content={}
        for idx in range(11):
            folder=f'pilot-test-{idx+1:02d}'
            slug=f'hw-pilot-test-{idx+1:02d}-c0ffee21'
            cover=f'assets/media/v1/{folder}/cards/cover.png'
            audio=f'assets/media/v1/{folder}/audio/en/hello.mp3'
            for p,data in [(cover,b'\x89PNG\r\n\x1a\n'+bytes([idx])),(audio,b'ID3'+bytes([idx]))]:
                path=self.original/p
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(data)
            self.lessons.append({
                'id':folder,'sourceFolder':folder,'slug':slug,'title':f'Test lesson {idx+1}',
                'unitId':UNITS[idx%5],'cover':cover,'mediaCount':2,'catalogStatus':'approved-pilot',
                'questions':1,'sourceLabel':f'Lesson {idx+1}',
            })
            self.content[slug]={'vocab':[{'text':'hello','audio':audio,'image':cover}],
                                'quiz':{'questions':[{'q':'hello','choices':[{'audio':audio}]}]}}
        self.cat={
            'schema':'skyed.course-hub.catalog.v1','site':'course.skyed.org',
            'published':False,'approval':{'formal_teacher_review_record':False},
            'lessons':self.lessons,
            'units':[{'id':u,'title':f'Authentic {u}','subtitle':'Captured source group'} for u in UNITS],
        }
        self._update_source()
        (self.original/'index.html').write_text('<script src="assets/app-v1.2.0.js" defer></script>')
        js=(self.original/'assets/app-v1.2.0.js')
        js.parent.mkdir(parents=True,exist_ok=True)
        js.write_text("`#/lesson/${encodeURIComponent(l.slug)}`; bits[0]==='lesson'; state.content.lessons?.[slug];",encoding='utf-8')

    def _update_source(self):
        data=self.original/'data'
        data.mkdir(parents=True,exist_ok=True)
        (data/'catalog.v1.json').write_text(json.dumps(self.cat),encoding='utf-8')
        (data/'content.v1.json').write_text(json.dumps({'schema':'skyed.course-hub.content.v1','lessons':self.content}),encoding='utf-8')

    def test_maps_all_11_real_routes_without_overwriting_original(self):
        old={p.relative_to(self.original).as_posix():digest(p) for p in self.original.rglob('*') if p.is_file()}
        draft_before=digest(self.lobby/'content/lobby.json')
        report=stage(self.original,self.lobby,self.staged,min_media=0)
        verify_existing(self.original,self.staged,report)
        self.assertEqual(report['reconciled_lesson_count'],11)
        self.assertEqual(report['media_references_checked'],22)
        self.assertEqual(report['lesson_mapping_status'],'VERIFIED_CAPTURED_ROUTES_TEACHER_REVIEW_PENDING')
        self.assertTrue(report['teacher_review_required'])
        self.assertFalse(report['production_mutation'])
        self.assertFalse(report['production_promotion_authorized'])
        self.assertEqual(len(report['verified_lesson_routes']),11)
        self.assertTrue(all(not x['approved'] for x in report['candidate_links']))
        derived=json.loads((self.staged/'lobby-preview/content/lobby.json').read_text(encoding='utf-8'))
        self.assertEqual({x['url'] for x in derived['lessons']},{f"/#/lesson/{x['slug']}" for x in self.lessons})
        self.assertTrue(all(x['status']=='verified-preview' for x in derived['lessons']))
        self.assertTrue(all(x['media'].startswith('/assets/media/v1/') for x in derived['lessons']))
        self.assertEqual({p.relative_to(self.original).as_posix():digest(p) for p in self.original.rglob('*') if p.is_file()},old)
        self.assertEqual(digest(self.lobby/'content/lobby.json'),draft_before)
        self.assertEqual((self.staged/'index.html').read_bytes(),(self.original/'index.html').read_bytes())
        write_reports(report,self.report)
        with (self.report/'lesson-linking-review.csv').open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),11)
        self.assertTrue(all(x['review_status'].endswith('TEACHER_REVIEW_PENDING') for x in rows))
        with (self.report/'verified-lesson-evidence.csv').open(encoding='utf-8-sig',newline='') as f:
            self.assertEqual(len(list(csv.DictReader(f))),11)

    def test_missing_media_blocks_before_creating_stage(self):
        (self.original/self.lessons[0]['cover']).unlink()
        with self.assertRaisesRegex(GateError,'MEDIA_GATE=BLOCKED'):
            stage(self.original,self.lobby,self.staged,min_media=0)
        self.assertFalse(self.staged.exists())

    def test_quiz_count_mismatch_blocks(self):
        self.lessons[0]['questions']=3
        self._update_source()
        with self.assertRaisesRegex(GateError,'CONTENT_GATE=BLOCKED'):
            stage(self.original,self.lobby,self.staged,min_media=0)

    def test_unapproved_catalog_blocks(self):
        self.lessons[0]['catalogStatus']='draft'
        self._update_source()
        with self.assertRaisesRegex(GateError,'CATALOG_GATE=BLOCKED'):
            stage(self.original,self.lobby,self.staged,min_media=0)

    def test_missing_legacy_router_blocks(self):
        (self.original/'assets/app-v1.2.0.js').write_text('/* unsupported route */')
        with self.assertRaisesRegex(GateError,'ROUTE_GATE=BLOCKED'):
            stage(self.original,self.lobby,self.staged,min_media=0)

    def test_malformed_schema_blocks(self):
        self.cat['site']='untrusted.example'
        self._update_source()
        with self.assertRaisesRegex(GateError,'CATALOG_GATE=BLOCKED'):
            stage(self.original,self.lobby,self.staged,min_media=0)

    def test_wrong_slug_mismatch_blocks(self):
        self.content.pop(self.lessons[0]['slug'])
        self._update_source()
        with self.assertRaisesRegex(GateError,'CATALOG_GATE=BLOCKED'):
            stage(self.original,self.lobby,self.staged,min_media=0)

    def test_case_status_never_claims_publication(self):
        report=stage(self.original,self.lobby,self.staged,min_media=0)
        staged_data=json.loads((self.staged/'lobby-preview/content/lobby.json').read_text(encoding='utf-8'))
        self.assertTrue(all(x['status']!='published' for x in staged_data['lessons']))
        self.assertFalse(report['production_promotion_authorized'])

    def test_tampered_generated_route_detected_even_with_matching_content_digest(self):
        report=stage(self.original,self.lobby,self.staged,min_media=0)
        fp=self.staged/'lobby-preview/content/lobby.json'
        doc=json.loads(fp.read_text(encoding='utf-8'))
        doc['lessons'][0]['url']='/#/lesson/evil'
        fp.write_text(json.dumps(doc),encoding='utf-8')
        # even if a corrupted report hash is updated, semantic route set catches it
        report['lobby_files']['content/lobby.json']=digest(fp)
        with self.assertRaisesRegex(GateError,'Verified lesson routes changed'):
            verify_existing(self.original,self.staged,report)


if __name__=='__main__': unittest.main()
