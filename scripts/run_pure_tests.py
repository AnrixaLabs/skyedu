"""Run isolated pure-Python homework tests without importing SkyED app bootstrap.

The current GitHub repository is incomplete, and skyed/__init__.py imports
modules not checked in. This runner isolates only pure helper/unit tests.
It does NOT test application startup, publishing integration or restored code;
those are enforced by the separate repository integrity release gate.
"""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if "skyed" in sys.modules:
        raise RuntimeError("Must run before importing skyed application")
    package = types.ModuleType("skyed")
    package.__path__ = [str(root / "skyed")]
    package.__package__ = "skyed"
    sys.modules["skyed"] = package
    sys.path.insert(0, str(root))
    print("TEST_SCOPE=PURE_MODULE_ONLY, NOT_APPLICATION_STARTUP", flush=True)
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
