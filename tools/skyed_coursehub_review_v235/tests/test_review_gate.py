"""Portable regression suite for the ZIP/paired-directory review verifier.

Fixtures contain small, invented files only: no captured student records, media,
or private user data are shipped in the review package.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parents[1]
SCRIPT = HERE / "scripts" / "verify_stage_report.py"
spec = importlib.util.spec_from_file_location("skyed_review_verifier", SCRIPT)
verifier = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(verifier)

STAMP = "20261104-234112"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(base: Path, relative: str, content: bytes | str) -> bytes:
    payload = content.encode("utf-8") if isinstance(content, str) else content
    dst = base / relative
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(payload)
    return payload


def csv_bytes(rows: list[dict[str, str]]) -> bytes:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def build_fixture(root: Path, stamp: str = STAMP) -> tuple[Path, Path]:
    report = root / f"report-{stamp}"
    stage = root / f"staged-{stamp}"
    report.mkdir(parents=True)
    stage.mkdir(parents=True)
    old: dict[str, str] = {}

    def old_file(name: str, data: bytes | str):
        old[name] = digest(write(stage, name, data))

    old_file("index.html", "<!doctype html><title>Old homepage preserved</title>")
    old_file("assets/app-v1.2.0.js", "// Existing dynamic /#/lesson/ router")
    old_file("assets/css.css", "/* keep unchanged */")
    lessons = [{"slug": f"lesson-{n:02d}", "title": f"Lesson {n}"} for n in range(11)]
    catalog = {"published": False, "approval": {"formal_teacher_review_record": False}, "lessons": lessons}
    content = {"entries": [{"slug": item["slug"]} for item in lessons]}
    old_file("data/catalog.v1.json", json.dumps(catalog))
    old_file("data/content.v1.json", json.dumps(content))

    for n in range(342):
        old_file(f"assets/media/audio/{n:03d}.mp3", f"Original audio {n}".encode("ascii"))
    for n in range(91):
        old_file(f"assets/media/covers/{n:03d}.png", f"Original cover {n}".encode("ascii"))

    lobby_entries = []
    routes = []
    review_rows = []
    for n in range(11):
        lesson_id = f"lesson-id-{n:02d}"
        slug = lessons[n]["slug"]
        path = f"assets/media/covers/{n:03d}.png"
        url = "/#/lesson/" + slug
        lobby_entries.append({"id": lesson_id, "status": "verified-preview", "url": url, "media": "/" + path})
        routes.append({"lesson_id": lesson_id, "lesson_title": lessons[n]["title"],
                       "catalog_slug": slug, "verified_existing_route": url,
                       "cover_file_sha256": old[path], "approved_for_publication": False,
                       "review_status": verifier.PENDING_REVIEW})
        review_rows.append({"lesson_id": lesson_id, "verified_existing_route": url})

    lb: dict[str, str] = {}
    for path, data in {
        "index.html": "<html><title>Lobby preview</title></html>",
        "assets/app.js": "console.log('preview-only')",
        "assets/styles.css": "body {margin: 0}",
        "assets/favicon.svg": "<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        "content/lobby.json": json.dumps({"lessons": lobby_entries}),
    }.items():
        lb[path] = digest(write(stage, "lobby-preview/" + path, data))

    statement = {
        "release": "2.3.3", "status": "STAGED_NOT_DEPLOYED",
        "production_mutation": False, "production_promotion_authorized": False,
        "teacher_review_required": True, "existing_entrypoint_unchanged": True,
        "all_media_bytes_preserved": True, "legacy_files": old, "lobby_files": lb,
        "media": {"audio": 342, "images": 91, "total_media": 433},
        "media_references_checked": 433,
        "source_catalog_sha256": old["data/catalog.v1.json"],
        "source_content_sha256": old["data/content.v1.json"],
        "source_router_sha256": old["assets/app-v1.2.0.js"],
        "reconciled_lesson_count": 11, "verified_lesson_routes": routes,
    }
    write(report, "integration-report.json", json.dumps(statement, indent=2))
    write(report, "lesson-linking-review.csv", csv_bytes(review_rows))
    write(report, "verified-lesson-evidence.csv", csv_bytes(review_rows))
    write(report, "legacy-link-candidates.csv", csv_bytes(review_rows))
    return report, stage


def archive_pair(report: Path, stage: Path, output: Path):
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for root in (report, stage):
            for p in sorted(root.rglob("*")):
                if p.is_file():
                    z.write(p, f"{root.name}/{p.relative_to(root).as_posix()}")


class ReviewGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="skyed-v235-tests-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.report, self.stage = build_fixture(self.root)

    def test_paired_directories_pass(self):
        result = verifier.verify(report_dir=self.report, stage_dir=self.stage)
        self.assertEqual(result["result"], "PASS_STAGED_TECHNICAL_GATE_ONLY")
        self.assertEqual((result["original_files"], result["lobby_files"]), (438, 5))
        self.assertEqual(result["lessons_mapped"], 11)
        self.assertEqual(result["source_kind"], "local_report_and_staged_directories")
        self.assertIsNone(result["source_archive_sha256"])
        self.assertFalse(result["production_promotion"])

    def test_existing_zip_compatibility(self):
        target = self.root / "stage.zip"
        archive_pair(self.report, self.stage, target)
        result = verifier.verify(target)
        self.assertEqual(result["result"], "PASS_STAGED_TECHNICAL_GATE_ONLY")
        self.assertEqual(result["source_archive_sha256"], digest(target.read_bytes()))
        self.assertEqual(result["source_kind"], "zip_archive")

    def test_auto_discovery_only_matches_timestamp(self):
        newer_report, newer_stage = build_fixture(self.root, stamp="20261104-235000")
        self.assertEqual(verifier.discover_pair(self.root), (newer_report, newer_stage))
        self.assertEqual(verifier.discover_pair(self.root, STAMP), (self.report, self.stage))
        shutil.rmtree(newer_stage)
        self.assertEqual(verifier.discover_pair(self.root), (self.report, self.stage))

    def test_report_and_stage_timestamp_must_match(self):
        newer_report, newer_stage = build_fixture(self.root, stamp="20261104-235000")
        with self.assertRaisesRegex(verifier.ValidationError, "TIMESTAMPS_DIFFER"):
            verifier.verify(report_dir=self.report, stage_dir=newer_stage)

    def test_missing_match_fails_without_mixing(self):
        with self.assertRaisesRegex(verifier.ValidationError, "NO_MATCHING_REPORT_AND_STAGE_PAIR"):
            verifier.discover_pair(self.root, "20261105-100000")

    def test_absent_staged_media_is_blocked(self):
        (self.stage / "assets/media/audio/003.mp3").unlink()
        with self.assertRaisesRegex(verifier.ValidationError, "STAGED_FILE_SET_MISMATCH"):
            verifier.verify(report_dir=self.report, stage_dir=self.stage)

    def test_modified_media_hash_is_blocked(self):
        (self.stage / "assets/media/audio/003.mp3").write_bytes(b"corrupted")
        with self.assertRaisesRegex(verifier.ValidationError, "HASH_MISMATCH"):
            verifier.verify(report_dir=self.report, stage_dir=self.stage)

    def test_unreported_extra_stage_file_is_blocked(self):
        write(self.stage, "unexpected.js", "this was not captured")
        with self.assertRaisesRegex(verifier.ValidationError, "STAGED_FILE_SET_MISMATCH"):
            verifier.verify(report_dir=self.report, stage_dir=self.stage)

    def test_publication_flag_cannot_be_altered(self):
        p = self.report / "integration-report.json"
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["production_promotion_authorized"] = True
        p.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaisesRegex(verifier.ValidationError, "PRODUCTION_GATE_UNSAFE"):
            verifier.verify(report_dir=self.report, stage_dir=self.stage)

    def test_changed_lesson_route_cannot_pass_even_when_new_hash_reported(self):
        p = self.stage / "lobby-preview/content/lobby.json"
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["lessons"][0]["url"] = "/#/somewhere-else"
        payload = json.dumps(doc).encode("utf-8")
        p.write_bytes(payload)
        report_path = self.report / "integration-report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["lobby_files"]["content/lobby.json"] = digest(payload)
        report_path.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(verifier.ValidationError, "BAD_CAPTURED_ROUTE"):
            verifier.verify(report_dir=self.report, stage_dir=self.stage)

    def test_symlinks_and_links_rejected(self):
        link = self.stage / "assets/media/audio/link.mp3"
        try:
            link.symlink_to(self.stage / "index.html")
        except (OSError, NotImplementedError):
            self.skipTest("Platform does not permit symlinks for non-admin test runner")
        with self.assertRaisesRegex(verifier.ValidationError, "SOURCE_FILE_LINK_NOT_ALLOWED"):
            verifier.verify(report_dir=self.report, stage_dir=self.stage)

    def test_zip_traversal_directory_is_blocked(self):
        archive = self.root / "stage.zip"
        archive_pair(self.report, self.stage, archive)
        payload = self.root / "traversal.zip"
        with zipfile.ZipFile(archive) as src, zipfile.ZipFile(payload, "w") as dst:
            for info in src.infolist():
                dst.writestr(info, src.read(info))
            dst.writestr("../escape/", b"")
        with self.assertRaisesRegex(verifier.ValidationError, "UNSAFE_ZIP_PATH"):
            verifier.verify(payload)

    def test_zip_duplicate_stage_member_is_blocked(self):
        archive = self.root / "stage.zip"
        archive_pair(self.report, self.stage, archive)
        payload = self.root / "duplicate.zip"
        with zipfile.ZipFile(archive) as src, zipfile.ZipFile(payload, "w") as dst:
            for info in src.infolist():
                dst.writestr(info, src.read(info))
            with __import__("warnings").catch_warnings():
                __import__("warnings").simplefilter("ignore", UserWarning)
                dst.writestr(f"{self.report.name}/integration-report.json", b"{}")
        with self.assertRaisesRegex(verifier.ValidationError, "ZIP_DUPLICATE_MEMBERS"):
            verifier.verify(payload)

    def test_no_archive_path_available_returns_blocked(self):
        with self.assertRaisesRegex(verifier.ValidationError, "STAGE_ARCHIVE_NOT_FOUND"):
            verifier.verify(self.root / "user-downloads-no-such-file.zip")

    def test_cli_autodiscovery_and_receipt(self):
        output = self.root / "review-receipts" / "receipt.json"
        p = subprocess.run([sys.executable, str(SCRIPT), "--workspace", str(self.root),
                            "--output", str(output)], text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        receipt = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(receipt["result"], "PASS_STAGED_TECHNICAL_GATE_ONLY")
        self.assertTrue(receipt["source_stage_directory"].endswith(self.stage.name))

    def test_receipt_cannot_overwrite_original_report(self):
        target = self.report / "integration-report.json"
        original_hash = digest(target.read_bytes())
        p = subprocess.run([sys.executable, str(SCRIPT), "--workspace", str(self.root),
                            "--output", str(target)], text=True, capture_output=True)
        self.assertEqual(p.returncode, 1)
        self.assertIn("AUDIT_OUTPUT_OVERWRITES_SOURCE", p.stderr)
        self.assertEqual(digest(target.read_bytes()), original_hash)

    def test_receipt_cannot_overwrite_zip(self):
        archive = self.root / "stage.zip"
        archive_pair(self.report, self.stage, archive)
        original_hash = digest(archive.read_bytes())
        p = subprocess.run([sys.executable, str(SCRIPT), str(archive),
                            "--output", str(archive)], text=True, capture_output=True)
        self.assertEqual(p.returncode, 1)
        self.assertIn("AUDIT_OUTPUT_OVERWRITES_SOURCE", p.stderr)
        self.assertEqual(digest(archive.read_bytes()), original_hash)

    def test_cli_missing_stamp_is_nonzero_and_writes_blocked_receipt(self):
        output = self.root / "blocked.json"
        p = subprocess.run([sys.executable, str(SCRIPT), "--workspace", str(self.root),
                            "--stamp", "20261105-000000", "--output", str(output)],
                           text=True, capture_output=True)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["result"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
