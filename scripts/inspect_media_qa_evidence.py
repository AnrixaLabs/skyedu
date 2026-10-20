"""Read-only classification of SkyED Stage C ZIPs. No TTS or WordPress calls."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

MAX_MEMBER_BYTES = 12*1024*1024
MAX_TOTAL_BYTES = 140*1024*1024

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()

def analyze(path: Path, expected_sha256: str = "") -> dict:
    report = {"schema":"skyed.media.evidence.inspection.v2.1.2","status":"UNVERIFIED",
              "read_only":True,"production_publish_authorized":False,
              "media_evidence_path":str(path),"action":"UPLOAD_ORIGINAL_EVIDENCE_ZIP"}
    try:
        if not path.is_file():
            raise ValueError("Evidence ZIP does not exist at this path")
        digest = sha256_file(path)
        report["archive_sha256"] = digest
        if expected_sha256 and digest.casefold() != expected_sha256.casefold():
            raise ValueError("EVIDENCE_SHA256_MISMATCH: report belongs to another ZIP")
        with zipfile.ZipFile(path) as z:
            entries = z.infolist()
            names = [x.filename for x in entries]
            if len(names) != len(set(names)):
                raise ValueError("Duplicate ZIP members")
            if any(x.startswith("/") or "\\" in x or ".." in PurePosixPath(x).parts for x in names):
                raise ValueError("Unsafe ZIP member path")
            if any(x.file_size > MAX_MEMBER_BYTES for x in entries):
                raise ValueError("ZIP member size exceeds review limit")
            if sum(x.file_size for x in entries) > MAX_TOTAL_BYTES:
                raise ValueError("ZIP expanded size exceeds review limit")
            report["archive_members"] = len(entries)
            if "media-validation.json" not in names:
                raise ValueError("Missing media-validation.json (possible launcher-level failure)")
            manifest = json.loads(z.read("media-validation.json").decode("utf-8-sig"))
            run, files = manifest.get("result") or {}, manifest.get("files") or []
            if not isinstance(run, dict) or not isinstance(files, list):
                raise ValueError("Invalid evidence manifest structure")
            report.update({
                "source_commit":run.get("source_commit"),
                "generator_exit_code":run.get("generator_exit_code"),
                "reported_status":str(run.get("status") or "UNKNOWN"),
                "generator_failures":list(run.get("failures") or [])[:40],
                "visual_quality_status":str(run.get("visual_quality_status") or "UNVERIFIED"),
                "visual_blockers":list(run.get("visual_quality_blockers") or [])[:50],
                "reported_counts":{"images":run.get("image_count"),"mp3":run.get("mp3_count"),
                                   "media":run.get("media_count")},
                "image_provenance":list(run.get("image_source_statuses") or [])[:50],
                "wordpress_posts_created":run.get("wordpress_posts_created"),
            })
            if run.get("wordpress_posts_created") != 0 or run.get("production_publish_authorized") is not False:
                raise ValueError("Publication safety claims absent or inconsistent")
            verified, missing, bad, counts = 0, [], [], Counter()
            for row in files:
                if not isinstance(row, dict):
                    raise ValueError("Invalid media manifest item")
                rel = str(row.get("path") or "")
                p = PurePosixPath(rel)
                if (not rel or ".." in p.parts or not rel.startswith(("cards/","audio/"))
                    or p.suffix.lower() not in (".png",".mp3")):
                    raise ValueError(f"Unsafe media filename: {rel}")
                member = "lesson/" + rel
                if member not in names:
                    missing.append(rel)
                    continue
                data = z.read(member)
                if (hashlib.sha256(data).hexdigest() != row.get("sha256") or
                    len(data) != row.get("bytes") or row.get("status") != "PASS"):
                    bad.append(rel)
                else:
                    verified += 1
                    counts[p.suffix.lower()] += 1
            report.update({"verified_media_files":verified,"verified_mp3":counts[".mp3"],
                           "verified_png":counts[".png"],"missing_media_members":missing[:40],
                           "bad_media_members":bad[:40]})
            if run.get("generator_exit_code") != 0:
                report["status"] = "BLOCKED_GENERATOR"
                report["reason"] = "Generator failed: check generation.log in archive"
            elif missing or bad or not files:
                report["status"] = "BLOCKED_MEDIA_EVIDENCE"
                report["reason"] = "Media evidence absent, corrupt or unverified"
            elif counts[".png"] != 4 or counts[".mp3"] != 12:
                report["status"] = "BLOCKED_INCOMPLETE_MEDIA"
                report["reason"] = f"Expected 4 images and 12 clips; verified {counts['.png']} and {counts['.mp3']}"
            elif report["generator_failures"]:
                report["status"] = "BLOCKED_MEDIA_VALIDATION"
                report["reason"] = "See generator_failures for exact reasons"
            elif report["visual_blockers"] or run.get("status") == "BLOCKED_VISUAL_CONTENT":
                report["status"] = "BLOCKED_VISUAL_CONTENT"
                report["reason"] = "Placeholder/fallback images require genuine illustrations"
            elif run.get("status") == "TECHNICAL_MEDIA_PASS":
                report["status"] = "TECHNICAL_MEDIA_PASS_TEACHER_REVIEW_REQUIRED"
                report["reason"] = "Audio/PNG integrity passed, but manual content review is required"
            else:
                report["status"] = "BLOCKED_UNCLASSIFIED"
                report["reason"] = "Check reported_status and generation.log"
            report["review_recommendation"] = (
                "Upload this ZIP; no need to regenerate Edge TTS for diagnosis." if verified else
                "Upload existing evidence; do not diagnose from a generic launcher status.")
    except (OSError, ValueError, KeyError, TypeError, UnicodeError,
            zipfile.BadZipFile, json.JSONDecodeError) as exc:
        report["status"] = "UNVERIFIED_EVIDENCE"
        report["reason"] = f"{type(exc).__name__}: {exc}"
    return report

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    p.add_argument("--expected-sha256",default="")
    p.add_argument("--report",type=Path)
    args=p.parse_args()
    result=analyze(args.archive,args.expected_sha256)
    output=json.dumps(result,indent=2,ensure_ascii=False)
    print(output)
    if args.report:
        if args.report.exists():
            print("Refusing to replace previous report",file=sys.stderr)
            return 3
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(output+"\n",encoding="utf-8")
    return 3 if result["status"] == "UNVERIFIED_EVIDENCE" else 0

if __name__=="__main__":
    raise SystemExit(main())
