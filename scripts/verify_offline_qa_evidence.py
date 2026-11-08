"""Read-only verifier for SkyED offline QA evidence archives.

An offline QA PASS is only claimed when every required stage has a matching
machine-readable artifact. A missing or incomplete ZIP is always BLOCKED.
This tool never invokes WordPress, GitHub, or the lesson generator.

Usage:
  python scripts/verify_offline_qa_evidence.py SkyED-Offline-QA-Evidence.zip
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

CHECKS = (
    "git_root",
    "qa_venv_creation",
    "minimum_dependencies",
    "python_source_compile",
    "source_integrity",
    "generator_cli",
    "unit_tests",
    "four_theme_dry_run",
)
EXPECTED_THEMES = {"sky", "sky_tiles", "fun_mission", "strict_dark"}
MAX_FILE_SIZE = 4 * 1024 * 1024


def _read_json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    if name not in archive.namelist():
        raise ValueError(f"Missing evidence: {name}")
    entry = archive.getinfo(name)
    if entry.file_size > MAX_FILE_SIZE:
        raise ValueError(f"Evidence size exceeds safety limit: {name}")
    try:
        parsed = json.loads(archive.read(name).decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JSON evidence: {name} ({type(exc).__name__})") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object: {name}")
    return parsed


def _read_log_text(raw: bytes) -> tuple[str, str]:
    """Decode historical Windows PowerShell UTF-16 and current UTF-8 logs."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    if len(raw) >= 10 and raw[1::2].count(0) * 4 > len(raw[1::2]) * 3:
        return raw.decode("utf-16-le"), "utf-16-le"
    return raw.decode("utf-8"), "utf-8"


def verify(archive_path: Path) -> dict[str, Any]:
    verdict: dict[str, Any] = {
        "status": "BLOCKED",
        "production_modified_by_this_check": False,
        "evidence_file": str(archive_path),
        "checks": {},
    }
    try:
        with zipfile.ZipFile(archive_path, "r") as z:
            names = z.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Duplicate ZIP members")
            if any(name.startswith("/") or ".." in Path(name).parts for name in names):
                raise ValueError("Unsafe ZIP member path")
            results = _read_json(z, "results.json")
            verdict["reported_status"] = results.get("status")
            verdict["reported_error"] = str(results.get("error") or "")[:500]
            verdict["commit"] = str(results.get("commit") or "")
            verdict["checks"] = dict(results.get("checks") or {})
            if results.get("status") != "OFFLINE_QA_PASS":
                raise ValueError(f"Windows QA is not PASS: {results.get('status')!r}")
            if not bool(results.get("read_only_production")):
                raise ValueError("Production read-only declaration absent")
            if not bool(results.get("original_windows_project_untouched")):
                raise ValueError("Original workspace protection declaration absent")
            if not re.fullmatch(r"[a-f0-9]{40}", str(results.get("commit") or ""), re.I):
                raise ValueError("Full Git commit SHA absent")
            for check in CHECKS:
                if verdict["checks"].get(check) != "PASS":
                    raise ValueError(f"Required check not PASS: {check}")
            if "UNVERIFIED" in str(verdict["checks"].get("php_lint", "")):
                verdict["php_lint"] = "UNVERIFIED"
            integrity = _read_json(z, "integrity.json")
            if integrity.get("status") != "PASS" or integrity.get("missing_count") != 0:
                raise ValueError("Source import integrity is not PASS")
            smoke = _read_json(z, "smoke-report.json")
            if smoke.get("result") != "PASS" or smoke.get("publish_performed") is not False:
                raise ValueError("Offline generator smoke incomplete or unsafe")
            variants = smoke.get("themes")
            if not isinstance(variants, list) or len(variants) != len(EXPECTED_THEMES):
                raise ValueError("Incomplete four-theme generator coverage")
            if {item.get("theme") for item in variants if isinstance(item, dict)} != EXPECTED_THEMES:
                raise ValueError("Incorrect generator theme set")
            for item in variants:
                if (item.get("status") != "PASS" or item.get("media_generated") is not False
                    or item.get("wp_calls") != 0 or item.get("questions", 0) < 1
                    or item.get("vocabulary", 0) < 1 or item.get("sentences", 0) < 1):
                    raise ValueError(f"Incomplete/unsafe theme smoke: {item.get('theme')}")
            if "unit-tests.log" not in names:
                raise ValueError("Missing unit test execution log")
            if z.getinfo("unit-tests.log").file_size > MAX_FILE_SIZE:
                raise ValueError("Unit log exceeds safety limit")
            test_log, log_encoding = _read_log_text(z.read("unit-tests.log"))
            match = re.search(r"Ran\s+(\d+)\s+tests?\s+in\s+[\d.]+s", test_log)
            if not match:
                raise ValueError("No test-count summary")
            if not re.search(r"(?m)^OK(?:\s|$)", test_log):
                raise ValueError("Tests do not report OK")
            verdict["status"] = "PASS"
            verdict["unit_test_count"] = int(match.group(1))
            verdict["test_log_encoding"] = log_encoding
            verdict["theme_count"] = len(variants)
            verdict["limitations"] = [
                "Dry-run does not generate or validate real MP3/image bytes",
                "No WordPress posting or live HTTP media verification",
                "No physical-device or WeChat browser testing",
            ]
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        verdict["failure_reason"] = str(exc)
    return verdict


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = verify(args.archive)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.report:
        if args.report.exists():
            print("Refusing to overwrite earlier verifier report", file=sys.stderr)
            return 3
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
