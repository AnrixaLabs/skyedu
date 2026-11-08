"""Validate and preserve existing editable SkyED lobby content without mutation.

A standalone Python file avoids Windows PowerShell 5.1's quote rewriting
of Python -c commands. An invalid draft blocks installation before any
file or shortcut is changed. The existing draft is never normalized,
migrated, backed up into distribution, or otherwise rewritten here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "skyed_lobby" / "scripts"))
from control_server import MAX_CONTENT, validate_content  # noqa: E402


def validate_file(path: Path) -> dict:
    """Load UTF-8 or UTF-8 BOM, reuse the actual editor's schema validator."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("Lobby draft must be a regular file, not a symlink")
    data = path.read_bytes()
    if len(data) > MAX_CONTENT:
        raise ValueError("Lobby draft exceeds the editor's maximum size")
    doc = json.loads(data.decode("utf-8-sig"))
    return validate_content(doc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("content_path", type=Path)
    args = parser.parse_args(argv)
    try:
        validate_file(args.content_path)
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"SKYED_PREVIOUS_LOBBY_CONTENT=INVALID error={type(exc).__name__}", file=sys.stderr)
        return 2
    print("SKYED_PREVIOUS_LOBBY_CONTENT=PRESERVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
