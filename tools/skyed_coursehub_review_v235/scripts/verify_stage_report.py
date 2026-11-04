#!/usr/bin/env python3
"""Verify a SkyED Course Hub stage ZIP OR paired local directories, without deployment.

This independently checks *reported* SHA-256 values against actual source files,
reconciles the 11 catalog routes and their cover images, and keeps teacher approval
separate from purely technical verification. Requires only Python >= 3.10.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
import json
import re
import stat
import sys
import zipfile
from pathlib import PurePosixPath, Path
from collections import Counter

RELEASE_VERSION = "2.3.5"
ALLOWED_STATUS = "STAGED_NOT_DEPLOYED"
PENDING_REVIEW = "TECHNICALLY_VERIFIED_TEACHER_REVIEW_PENDING"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ValidationError(ValueError):
    pass


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)



class DirectoryArchive:
    """Read existing report/stage directories through the same read-only ZIP API.

    No extraction, file writes or network I/O. Reject symlinks and junctions
    everywhere, including empty folders, and ensure every file stays below its
    own root before reading any bytes.
    """

    def __init__(self, report_dir: Path, stage_dir: Path):
        self.report_dir = report_dir.resolve(strict=True)
        self.stage_dir = stage_dir.resolve(strict=True)
        assert_true(report_dir.is_dir() and stage_dir.is_dir(), "SOURCE_DIRECTORIES_MISSING")
        assert_true(bool(re.fullmatch(r"report-[0-9]{8}-[0-9]{6}", report_dir.name)),
                    "REPORT_DIRECTORY_NAME_INVALID")
        assert_true(stage_dir.name == "staged-" + report_dir.name.removeprefix("report-"),
                    "REPORT_AND_STAGE_TIMESTAMPS_DIFFER")
        assert_true(not _is_unsafe_link(report_dir) and not _is_unsafe_link(stage_dir),
                    "SOURCE_ROOT_SYMLINK_NOT_ALLOWED")
        self._members: dict[str, Path] = {}
        for base in (report_dir, stage_dir):
            for current, dirs, files in os.walk(base, topdown=True, followlinks=False):
                here = Path(current)
                assert_true(not _is_unsafe_link(here), f"SOURCE_DIRECTORY_LINK_NOT_ALLOWED: {here}")
                for name in dirs:
                    child = here / name
                    assert_true(not _is_unsafe_link(child), f"SOURCE_DIRECTORY_LINK_NOT_ALLOWED: {child}")
                for name in files:
                    child = here / name
                    assert_true(not _is_unsafe_link(child), f"SOURCE_FILE_LINK_NOT_ALLOWED: {child}")
                    assert_true(child.resolve(strict=True).is_relative_to(base.resolve(strict=True)),
                                f"FILE_OUTSIDE_SOURCE_ROOT: {child}")
                    key = base.name + "/" + child.relative_to(base).as_posix()
                    assert_true(key not in self._members, f"DUPLICATE_SOURCE_MEMBER: {key}")
                    self._members[key] = child
        assert_true(bool(self._members), "EMPTY_STAGE_AND_REPORT_DIRECTORIES")

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        return False

    def infolist(self) -> list[zipfile.ZipInfo]:
        result = []
        for name, path in sorted(self._members.items()):
            item = zipfile.ZipInfo(name)
            item.file_size = path.stat().st_size
            item.external_attr = 0o100644 << 16
            result.append(item)
        return result

    def read(self, name: str) -> bytes:
        path = self._members.get(name)
        assert_true(path is not None, f"FILE_NOT_IN_STAGE: {name}")
        assert_true(not _is_unsafe_link(path), f"SOURCE_FILE_LINK_NOT_ALLOWED: {name}")
        assert_true(path.stat().st_size <= 10 * 1024 * 1024,
                    f"UNEXPECTED_LARGE_MEMBER: {name}")
        return path.read_bytes()


def _is_unsafe_link(path: Path) -> bool:
    """Guard symlinks and Windows junctions (Python 3.12+) when supported."""
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def discover_pair(workspace: Path, expected_stamp: str | None = None) -> tuple[Path, Path]:
    """Pick the latest matching report/staged pair, never mismatched runs."""
    assert_true(workspace.is_dir(), f"INTEGRATION_WORKSPACE_NOT_FOUND: {workspace}")
    candidates = []
    for report in workspace.iterdir():
        if not report.is_dir() or _is_unsafe_link(report):
            continue
        match = re.fullmatch(r"report-([0-9]{8}-[0-9]{6})", report.name)
        if match is None or (expected_stamp and match.group(1) != expected_stamp):
            continue
        stage = workspace / ("staged-" + match.group(1))
        if (stage.is_dir() and not _is_unsafe_link(stage)
                and (report / "integration-report.json").is_file()
                and (stage / "index.html").is_file()):
            candidates.append((report, stage))
    assert_true(bool(candidates),
                f"NO_MATCHING_REPORT_AND_STAGE_PAIR: {workspace}"
                + (f" timestamp={expected_stamp}" if expected_stamp else ""))
    return max(candidates, key=lambda pair: pair[0].name)


def load_json(archive: zipfile.ZipFile | DirectoryArchive, path: str) -> dict:
    data = json.loads(archive.read(path).decode("utf-8-sig"))
    assert_true(isinstance(data, dict), f"NOT_JSON_OBJECT: {path}")
    return data


def csv_rows(archive: zipfile.ZipFile | DirectoryArchive, path: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(archive.read(path).decode("utf-8-sig"))))


def identify_roots(archive: zipfile.ZipFile | DirectoryArchive) -> tuple[str, str]:
    names = [info.filename for info in archive.infolist() if not info.is_dir()]
    report_names = [x for x in names if re.fullmatch(r"report-[^/]+/integration-report\.json", x)]
    assert_true(len(report_names) == 1, "REPORT_MISSING_OR_AMBIGUOUS")
    reports = report_names[0].rsplit("/", 1)[0] + "/"
    stage_names = [x for x in names if re.fullmatch(r"staged-[^/]+/index\.html", x)]
    assert_true(len(stage_names) == 1, "STAGE_MISSING_OR_AMBIGUOUS")
    staged = stage_names[0].rsplit("/", 1)[0] + "/"
    return reports, staged


def verify(archive_path: Path | None = None, *, report_dir: Path | None = None,
           stage_dir: Path | None = None) -> dict:
    """Verify exactly one stage source: an archive or a matching directory pair."""
    assert_true((archive_path is not None) != (report_dir is not None and stage_dir is not None),
                "PROVIDE_EXACTLY_ONE_ARCHIVE_OR_DIRECTORY_PAIR")
    assert_true((report_dir is None) == (stage_dir is None),
                "REPORT_AND_STAGE_DIRECTORIES_BOTH_REQUIRED")
    result = {"schema": "skyed.course-hub.review-gate.v2.3.5",
              "source_archive_sha256": None, "checks": [],
              "failed_checks": [], "production_promotion": False,
              "teacher_review": "PENDING"}
    if archive_path is not None:
        assert_true(archive_path.is_file(), f"STAGE_ARCHIVE_NOT_FOUND: {archive_path}")
        source = zipfile.ZipFile(archive_path)
        result["source_kind"] = "zip_archive"
        result["source_archive_sha256"] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    else:
        source = DirectoryArchive(report_dir, stage_dir)
        result["source_kind"] = "local_report_and_staged_directories"
        result["source_report_directory"] = str(report_dir.resolve())
        result["source_stage_directory"] = str(stage_dir.resolve())
        result["source_report_sha256"] = hashlib.sha256(
            (report_dir / "integration-report.json").read_bytes()).hexdigest()
    with source as z:
        # Reject duplicate entries, symlink and ZIP slip members. Check the *entire* ZIP.
        all_infos = z.infolist()
        all_names = [x.filename for x in all_infos]
        assert_true(len(all_names) == len(set(all_names)), "ZIP_DUPLICATE_MEMBERS")
        # Directory entries are checked too: a malicious ZIP may hide its only
        # path traversal or symlink in an otherwise empty directory member.
        for item in all_infos:
            path = PurePosixPath(item.filename)
            assert_true(not path.is_absolute() and ".." not in path.parts and "\\" not in item.filename,
                        f"UNSAFE_ZIP_PATH: {item.filename}")
            mode = item.external_attr >> 16
            assert_true(not stat.S_ISLNK(mode), f"ZIP_SYMLINK_NOT_ALLOWED: {item.filename}")
            assert_true(item.file_size <= 10 * 1024 * 1024, f"UNEXPECTED_LARGE_MEMBER: {item.filename}")
        names = [x.filename for x in all_infos if not x.is_dir()]
        reports, staged = identify_roots(z)
        report = load_json(z, reports + "integration-report.json")
        assert_true(report.get("release") == "2.3.3", "UNEXPECTED_REPORT_RELEASE")
        assert_true(report.get("status") == ALLOWED_STATUS, "UNEXPECTED_STAGE_STATUS")
        assert_true(report.get("production_mutation") is False and report.get("production_promotion_authorized") is False,
                    "PRODUCTION_GATE_UNSAFE")
        assert_true(report.get("teacher_review_required") is True, "TEACHER_REVIEW_FLAG_MISSING")
        assert_true(report.get("existing_entrypoint_unchanged") is True, "EXISTING_ENTRYPOINT_NOT_PRESERVED")
        assert_true(report.get("all_media_bytes_preserved") is True, "MEDIA_PRESERVATION_NOT_CONFIRMED")
        result["checks"].append("STAGE_NON_PUBLICATION_CONTRACT=PASS")

        existing = report.get("legacy_files")
        lobby = report.get("lobby_files")
        assert_true(isinstance(existing, dict) and len(existing) > 0, "NO_LEGACY_HASHES")
        assert_true(isinstance(lobby, dict) and len(lobby) == 5, "LOBBY_MEMBER_COUNT_WRONG")
        expected = {staged + relative: digest for relative, digest in existing.items()}
        expected.update({staged + "lobby-preview/" + relative: digest for relative, digest in lobby.items()})
        stage_names = {n for n in names if n.startswith(staged)}
        assert_true(stage_names == set(expected), f"STAGED_FILE_SET_MISMATCH missing={len(set(expected)-stage_names)} extra={len(stage_names-set(expected))}")
        for path, digest in expected.items():
            assert_true(bool(SHA256_PATTERN.fullmatch(digest)), f"BAD_HASH_IN_MANIFEST: {path}")
            actual = hashlib.sha256(z.read(path)).hexdigest()
            assert_true(actual == digest, f"HASH_MISMATCH: {path}")
        assert_true(hashlib.sha256(z.read(staged + "index.html")).hexdigest() == existing.get("index.html"),
                    "ORIGINAL_HOMEPAGE_CHANGED")
        result["checks"].append(f"ALL_STAGED_FILE_HASHES=PASS ({len(expected)})")

        media = report.get("media", {})
        audio = [k for k in existing if k.endswith(".mp3")]
        images = [k for k in existing if k.endswith((".png", ".jpg", ".jpeg", ".webp"))]
        assert_true(len(audio) == media.get("audio") == 342, "AUDIO_COUNT_MISMATCH")
        assert_true(len(images) == media.get("images") == 91, "IMAGE_COUNT_MISMATCH")
        assert_true(media.get("total_media") == 433 and report.get("media_references_checked") == 433,
                    "MEDIA_REFERENCE_COUNT_MISMATCH")
        result["checks"].append("SOURCE_MEDIA_INTACT=PASS (342 audio, 91 images)")

        catalog_data = z.read(staged + "data/catalog.v1.json")
        content_data = z.read(staged + "data/content.v1.json")
        router_data = z.read(staged + "assets/app-v1.2.0.js")
        for data, k in [(catalog_data, "source_catalog_sha256"), (content_data, "source_content_sha256"),
                        (router_data, "source_router_sha256")]:
            assert_true(hashlib.sha256(data).hexdigest() == report[k], f"SOURCE_ANCHOR_DRIFT: {k}")
        catalog = json.loads(catalog_data)
        assert_true(catalog.get("published") is False, "CATALOG_PUBLICATION_CHANGED")
        assert_true(catalog.get("approval", {}).get("formal_teacher_review_record") is False, "CATALOG_REVIEW_STATE_CHANGED")
        source_lessons = catalog.get("lessons", [])
        assert_true(len(source_lessons) == 11, "CATALOG_LESSON_COUNT_CHANGED")
        source_slugs = {v["slug"] for v in source_lessons}
        assert_true(len(source_slugs) == 11, "DUPLICATE_SOURCE_SLUG")
        result["checks"].append("SOURCE_CATALOG_AND_ROUTER_ANCHORS=PASS")

        derived_data = load_json(z, staged + "lobby-preview/content/lobby.json")
        linked = derived_data.get("lessons", [])
        assert_true(len(linked) == report.get("reconciled_lesson_count") == 11, "DERIVED_LESSON_COUNT_MISMATCH")
        assert_true(len({v["id"] for v in linked}) == 11, "DUPLICATE_LOBBY_LESSON_ID")
        evidence = report.get("verified_lesson_routes", [])
        assert_true(len(evidence) == 11, "EVIDENCE_ROUTE_COUNT_WRONG")
        by_id = {v["lesson_id"]: v for v in evidence}
        assert_true(len(by_id) == 11, "DUPLICATE_EVIDENCE_ID")
        for item in linked:
            record = by_id.get(item.get("id"))
            assert_true(record is not None, f"NO_ROUTE_EVIDENCE: {item.get('id')}")
            assert_true(item.get("status") == "verified-preview", f"LESSON_STATUS_CHANGED: {item['id']}")
            assert_true(item.get("url") == record["verified_existing_route"] == "/#/lesson/" + record["catalog_slug"],
                        f"BAD_CAPTURED_ROUTE: {item['id']}")
            assert_true(record["catalog_slug"] in source_slugs, f"UNKNOWN_CATALOG_SLUG: {item['id']}")
            assert_true(record.get("approved_for_publication") is False and
                        record.get("review_status") == PENDING_REVIEW, f"UNEXPECTED_REVIEW_APPROVAL: {item['id']}")
            image = item.get("media", "").lstrip("/")
            assert_true(image in existing and image.endswith(".png"), f"BAD_COVER_PATH: {item['id']}")
            assert_true(existing[image] == record["cover_file_sha256"], f"COVER_HASH_MISMATCH: {item['id']}")
        result["checks"].append("PILOT_HASH_ROUTES_AND_COVERS=PASS (11/11)")

        csv_links = csv_rows(z, reports + "lesson-linking-review.csv")
        csv_evidence = csv_rows(z, reports + "verified-lesson-evidence.csv")
        csv_candidates = csv_rows(z, reports + "legacy-link-candidates.csv")
        assert_true(len(csv_links) == len(csv_evidence) == len(csv_candidates) == 11, "REVIEW_CSV_LESSON_COUNT_MISMATCH")
        csv_by_id = {r["lesson_id"]: r for r in csv_links}
        assert_true(len(csv_by_id) == 11, "DUPLICATE_REVIEW_CSV_ID")
        for lesson_id, record in by_id.items():
            row = csv_by_id.get(lesson_id)
            assert_true(row is not None and row["verified_existing_route"] == record["verified_existing_route"],
                        f"REVIEW_CSV_DRIFT: {lesson_id}")
        result["checks"].append("REVIEW_CSV_CONSISTENCY=PASS")
        result.update({"result": "PASS_STAGED_TECHNICAL_GATE_ONLY", "original_files": len(existing),
                       "lobby_files": len(lobby), "audio_files": len(audio), "image_files": len(images),
                       "lessons_mapped": len(linked), "teacher_review": "PENDING",
                       "production_promotion": False, "audit_constraints": ["offline archive inspection, not interactive browser testing",
                                                                "no current production re-capture", "no teacher sign-off"]})
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("archive", nargs="?", type=Path,
                    help="Optional combined report-and-staged ZIP")
    ap.add_argument("--report-dir", type=Path, help="Existing report-YYYYMMDD-HHMMSS folder")
    ap.add_argument("--stage-dir", type=Path, help="Matching staged-YYYYMMDD-HHMMSS folder")
    ap.add_argument("--workspace", type=Path,
                    help="Auto-find the latest paired run within this workspace")
    ap.add_argument("--stamp", help="Restrict auto-discovery to YYYYMMDD-HHMMSS")
    ap.add_argument("--output", type=Path, help="Write machine-readable JSON receipt")
    args = ap.parse_args()
    try:
        if args.workspace is not None:
            assert_true(args.archive is None and args.report_dir is None and args.stage_dir is None,
                        "WORKSPACE_MUST_NOT_BE_COMBINED_WITH_OTHER_INPUTS")
            report_dir, stage_dir = discover_pair(args.workspace, args.stamp)
            report = verify(report_dir=report_dir, stage_dir=stage_dir)
        else:
            report = verify(args.archive, report_dir=args.report_dir, stage_dir=args.stage_dir)
    except (ValidationError, KeyError, ValueError, OSError, zipfile.BadZipFile, TypeError) as error:
        report = {"result": "BLOCKED", "reason": str(error), "production_promotion": False}
    if args.output:
        # A receipt must never overwrite the evidence being qualified. This
        # applies to explicit paths as well as automatic workspace discovery.
        target = args.output.resolve()
        protected = []
        if args.archive is not None:
            protected.append(args.archive.resolve())
        if args.workspace is not None:
            try:
                source_report, source_stage = discover_pair(args.workspace, args.stamp)
                protected.extend((source_report.resolve(), source_stage.resolve()))
            except (ValidationError, OSError):
                pass
        if args.report_dir is not None and args.stage_dir is not None:
            protected.extend((args.report_dir.resolve(), args.stage_dir.resolve()))
        if any(target == p or (p.is_dir() and target.is_relative_to(p)) for p in protected):
            print("BLOCKED: AUDIT_OUTPUT_OVERWRITES_SOURCE", file=sys.stderr)
            return 1
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["result"].startswith("PASS_") else 1


if __name__ == "__main__":
    sys.exit(main())
