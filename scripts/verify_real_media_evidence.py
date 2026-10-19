"""Independent fail-closed verification of SkyED's real-media QA evidence ZIP.

Reads only the supplied archive, never contacts WordPress. Distinguishes
technical media integrity from machine-detected visual placeholders and manual
teaching-quality approval.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import PurePosixPath, Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect(path: Path) -> dict:
    result = {"status": "BLOCKED", "archive": str(path),
              "media_technical_status": "UNVERIFIED",
              "visual_content_status": "UNVERIFIED",
              "manual_teacher_review": "REQUIRED"}
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Duplicate archive members")
            if any(x.startswith("/") or "\\" in x or ".." in PurePosixPath(x).parts for x in names):
                raise ValueError("Unsafe archive paths")
            for key in ("media-validation.json", "generation.log",
                        "lesson/quiz.json", "lesson/spec_debug.json"):
                if key not in names:
                    raise ValueError(f"Missing media QA evidence: {key}")
            manifest = json.loads(z.read("media-validation.json"))
            info = manifest.get("result") or {}
            files = manifest.get("files") or []
            result["generator_exit_code"] = info.get("generator_exit_code")
            result["source_commit"] = info.get("source_commit")
            if info.get("generator_exit_code") != 0:
                raise ValueError("Generator did not complete successfully")
            if info.get("wordpress_posts_created") != 0 or info.get("production_publish_authorized") is not False:
                raise ValueError("Unsafe publication status")
            if not re.fullmatch("[0-9a-f]{40}", str(info.get("source_commit") or ""), re.I):
                raise ValueError("No verified 40-character source commit")
            if not files:
                raise ValueError("No verified media file manifest (older validator crash)")
            expected = set()
            images, audio = 0, 0
            for item in files:
                rel = str(item.get("path") or "")
                if (not rel.startswith(("cards/", "audio/")) or
                    PurePosixPath(rel).suffix.lower() not in {".png", ".mp3"}):
                    raise ValueError(f"Unsafe media reference: {rel}")
                if rel in expected:
                    raise ValueError(f"Duplicate media manifest path: {rel}")
                expected.add(rel)
                key = "lesson/" + rel
                if key not in names:
                    raise ValueError(f"Missing archived media: {key}")
                member = z.getinfo(key)
                if member.file_size > 8 * 1024 * 1024:
                    raise ValueError(f"Oversized media: {key}")
                data = z.read(key)
                if sha256(data) != item.get("sha256") or len(data) != item.get("bytes"):
                    raise ValueError(f"Media member hash/size mismatch: {key}")
                if item.get("status") != "PASS":
                    raise ValueError(f"Media validation error: {key}")
                if rel.endswith(".png"):
                    images += 1
                else:
                    audio += 1
            result.update({"media_technical_status": "PASS",
                           "verified_png": images, "verified_mp3": audio})
            if images != 4 or audio != 12:
                raise ValueError(f"Expected 4 cards and 12 EN/ZH clips; got {images} images, {audio} MP3")
            visual = info.get("visual_quality_status")
            blockers = info.get("visual_quality_blockers")
            if not isinstance(blockers, list):
                raise ValueError("Visual-source report absent")
            result["visual_content_status"] = visual
            result["visual_blockers"] = blockers
            if visual == "BLOCKED_PLACEHOLDER_OR_FALLBACK" and blockers:
                if info.get("status") != "BLOCKED_VISUAL_CONTENT":
                    raise ValueError("Image quality blocker not reflected in overall status")
                result["status"] = "TECHNICAL_MEDIA_PASS_VISUAL_BLOCKED"
            elif visual == "REVIEW_REQUIRED" and not blockers:
                if info.get("status") != "TECHNICAL_MEDIA_PASS":
                    raise ValueError("Media status is inconsistent")
                result["status"] = "TECHNICAL_MEDIA_PASS_TEACHER_REVIEW_REQUIRED"
            else:
                raise ValueError("Unrecognized/inconsistent visual quality state")
            result["production_approval"] = "NOT_GRANTED"
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        result["failure"] = str(exc)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", type=Path)
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    result = inspect(args.archive)
    summary = json.dumps(result, ensure_ascii=False, indent=2)
    print(summary)
    if args.report:
        if args.report.exists():
            print("Refusing to overwrite verifier evidence", file=sys.stderr)
            return 3
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(summary + "\n", encoding="utf-8")
    return 0 if result["status"].startswith("TECHNICAL_MEDIA_PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
