"""Capture a SkyED QA subprocess's output as UTF-8 without PowerShell error wrapping.

Never uses a shell, preserves return codes, and never writes outside the
explicitly provided evidence log. Python runs under the same virtualenv.

Example:
  python scripts/qa_capture.py --log result.log -- -m unittest discover -s tests -v
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    if not command:
        parser.error("Command arguments required after --")
    if args.timeout < 1 or args.timeout > 7200:
        parser.error("--timeout must be between 1 and 7200 seconds")
    if args.log.exists():
        print(f"QA_CAPTURE_BLOCKED: Evidence log already exists: {args.log}", file=sys.stderr)
        return 3
    args.log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        with args.log.open("xb") as log:
            result = subprocess.run(
                [sys.executable, *command],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                check=False,
                timeout=args.timeout,
            )
        print(f"QA_CAPTURE_EXIT_CODE={result.returncode}")
        return int(result.returncode) if result.returncode >= 0 else 2
    except subprocess.TimeoutExpired:
        with args.log.open("ab") as log:
            log.write(f"\nQA_CAPTURE_TIMEOUT={args.timeout}s\n".encode("utf-8"))
        print("QA_CAPTURE_TIMEOUT", file=sys.stderr)
        return 124
    except OSError as exc:
        print(f"QA_CAPTURE_BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(run())
