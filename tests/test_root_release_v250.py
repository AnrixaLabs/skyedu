"""Root Bright stage, rollback, fidelity and approval gates using synthetic data."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'tests'))
from test_pilot_route_reconciliation import PilotRouteReconciliation
import course_hub_release as release
import course_hub_deploy as deploy


class BrightRootRelease(PilotRouteReconciliation):
    def setUp(self):
        # Reuse the exact original 11-lesson synthetic catalog contract.
        super().setUp()
        self.candidate=self.base/'candidate'
        self.receipt=self.base/'candidate-report'

    def generate(self):
        return release.build(self.original,self.lobby,self.candidate,self.receipt,min_media=0)

    def test_root_is_bright_and_classic_retained(self):
        original=(self.original/'index.html').read_bytes()
        doc=self.generate()
        release.verify(self.original,self.candidate,doc)
        self.assertEqual((self.candidate/'classic.html').read_bytes(),original)
        self.assertNotEqual((self.candidate/'index.html').read_bytes(),original)
        bright=(self.candidate/'index.html').read_text(encoding='utf-8')
        self.assertIn('assets/bright/app.js',bright)
        self.assertNotIn('href="/" class="back-link"',bright)
        self.assertEqual(doc['reconciled_lesson_count'],11)
        self.assertEqual(len(doc['original_files']),len(list(self.original.rglob('*')))-len([p for p in self.original.rglob('*') if p.is_dir()]))
        self.assertEqual((self.candidate/'assets/app-v1.2.0.js').read_bytes(),(self.original/'assets/app-v1.2.0.js').read_bytes())
        self.assertEqual(doc['candidate_tree_sha256'],json.loads((self.receipt/'candidate-manifest.json').read_text())['candidate_tree_sha256'])

    def test_modified_original_media_is_rejected(self):
        doc=self.generate()
        (self.candidate/self.lessons[0]['cover']).write_bytes(b'tampered')
        with self.assertRaisesRegex(release.ReleaseError,'SOURCE_MEDIA_OR_FILE_MODIFIED'):
            release.verify(self.original,self.candidate,doc)

    def test_modified_root_index_is_rejected(self):
        doc=self.generate()
        (self.candidate/'index.html').write_text('old version')
        with self.assertRaisesRegex(release.ReleaseError,'BRIGHT_ROOT_INDEX_CHANGED'):
            release.verify(self.original,self.candidate,doc)

    def test_unexpected_root_file_is_rejected(self):
        doc=self.generate();(self.candidate/'private.txt').write_text('secret')
        with self.assertRaisesRegex(release.ReleaseError,'UNEXPECTED_OR_MISSING'):
            release.verify(self.original,self.candidate,doc)

    def test_existing_output_is_not_clobbered(self):
        self.candidate.mkdir();(self.candidate/'sentinel').write_text('do not touch')
        with self.assertRaisesRegex(release.ReleaseError,'OUTPUT_EXISTS'):
            self.generate()
        self.assertEqual((self.candidate/'sentinel').read_text(),'do not touch')

    def test_approval_requires_11_and_full_candidate_hash(self):
        doc=self.generate()
        template=json.loads((self.receipt/'teacher-review-template.json').read_text())
        approve_file=self.base/'approved.json'
        approve_file.write_text(json.dumps(template),encoding='utf-8')
        with self.assertRaisesRegex(deploy.DeployError,'TEACHER_REVIEW_PENDING'):
            deploy.check_approval(approve_file,doc,self.cat)
        template['decision']='APPROVED';template['reviewer']='Qualified teacher';template['attestation']=deploy.APPROVAL_SENTENCE
        template['lesson_reviews']=[{'slug':p['slug'],'status':'APPROVED'} for p in self.lessons]
        approve_file.write_text(json.dumps(template),encoding='utf-8')
        deploy.check_approval(approve_file,doc,self.cat)
        template['candidate_tree_sha256']='0'*64
        approve_file.write_text(json.dumps(template),encoding='utf-8')
        with self.assertRaisesRegex(deploy.DeployError,'WRONG_CANDIDATE'):
            deploy.check_approval(approve_file,doc,self.cat)

    def test_real_release_requires_400_media(self):
        doc=self.generate()
        with self.assertRaisesRegex(deploy.DeployError,'CONTENT_GATE'):
            deploy.load_manifest(self.receipt,self.candidate)


if __name__=='__main__':unittest.main()
