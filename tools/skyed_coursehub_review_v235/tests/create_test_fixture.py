"""Create a disposable, synthetic SkyED review gate fixture for Windows CI.

No student data, production content or real media is included.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from test_review_gate import build_fixture


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("workspace", type=Path)
    opts = p.parse_args()
    opts.workspace.mkdir(parents=True, exist_ok=True)
    report, stage = build_fixture(opts.workspace)
    print(f"SYNTHETIC_FIXTURE_REPORT={report}")
    print(f"SYNTHETIC_FIXTURE_STAGE={stage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
