"""Read-only inventory of SkyED's EXISTING local asset database.

This checks indexed records plus legacy Pictures/Flashcards folders. It never
copies, regenerates, renames, edits or removes pictures. Pass the actual
PyCharm asset_library path; do not assume a GitHub checkout contains its assets.

Example:
  python scripts/audit_existing_asset_library.py --root "C:\\Users\\user\\PycharmProjects\\skyed_automation\\asset_library" --words cat dog apple ball
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from skyed.asset_library import find_loose_file_asset, load_index, normalize_target
from skyed.cards import _resolve_existing_library_picture
from PIL import Image


def inspect(root: Path, words: list[str]) -> dict:
    root = root.resolve()
    report = {
        "schema": "skyed.asset-library.read-only.v2.1.7",
        "mode": "READ_ONLY",
        "root": str(root),
        "exists": root.is_dir(),
        "production_modified": False,
        "source_authority": "LOCAL_PYCHARM_ASSET_DATABASE",
        "statuses": [],
        "overall": "UNVERIFIED",
    }
    if not root.is_dir():
        report["reason"] = "Asset library root not found; nothing was modified"
        return report
    index_file = root / "manifests/library_index.json"
    records = load_index(root)
    report["index_present"] = index_file.is_file()
    report["index_record_count"] = len(records)
    report["index_approved_count"] = sum(bool(r.approved) for r in records)
    report["index_unapproved_count"] = sum(not r.approved for r in records)
    report["index_missing_files"] = sum(
        not (root / r.image_relpath).resolve().is_file()
        or not (root / r.image_relpath).resolve().is_relative_to(root)
        for r in records
    )
    if report["index_present"] and not records:
        report["index_note"] = "An index exists but no readable records were returned; inspect index separately"
    for word in dict.fromkeys(w.strip() for w in words if w.strip()):
        match = _resolve_existing_library_picture(root, word)
        matching_index = [rec for rec in records if rec.approved
                          and rec.asset_type.strip().lower() == "vocabulary"
                          and normalize_target(rec.target) == normalize_target(word)
                          and (root / rec.image_relpath).resolve().is_relative_to(root)
                          and (root / rec.image_relpath).resolve().is_file()]
        legacy = find_loose_file_asset(root, target=word)
        row = {
            "word": word,
            "status": "FOUND" if match else "MISSING",
            "indexed_approved_matches": len(matching_index),
            "legacy_picture_available": legacy is not None,
            "selected_source": "indexed" if match and any(
                (root / rec.image_relpath).resolve() == match.resolve()
                for rec in matching_index
            ) else ("legacy" if match else "missing"),
        }
        if match:
            row["path"] = str(match)
            try:
                with Image.open(match) as image:
                    row["dimensions"] = list(image.size)
                    row["format"] = image.format
                    image.verify()
                row["bytes"] = match.stat().st_size
                with match.open("rb") as f:
                    row["sha256"] = hashlib.file_digest(f, "sha256").hexdigest()
                row["status"] = "PASS"
            except (OSError, ValueError, SyntaxError) as exc:
                row["status"] = "INVALID_IMAGE"
                row["reason"] = f"{type(exc).__name__}: {exc}"
        report["statuses"].append(row)
    report["overall"] = "PASS" if report["statuses"] and all(
        row["status"] == "PASS" for row in report["statuses"]
    ) else "REVIEW_REQUIRED"
    report["note"] = (
        "Successful file/index selection does not certify image semantics or usage rights. "
        "Existing illustrations are interim assets; Sunny QLoRA replacement is deferred."
    )
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--words", nargs="+", default=["cat", "dog", "apple", "ball"])
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    data = inspect(args.root, args.words)
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    print(payload)
    if args.report:
        if args.report.exists():
            p.error(f"Refusing to overwrite existing evidence: {args.report}")
        if args.report.resolve().is_relative_to(args.root.resolve()):
            p.error("Evidence may not be written inside the asset library")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n", encoding="utf-8")
    return 0 if data["overall"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
