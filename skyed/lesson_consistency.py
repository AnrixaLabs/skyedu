"""Canonical sentence coverage computation shared across SkyED homework themes.

Only patches the existing report's sentence-coverage field, preserving all
other generator diagnostics and maintaining backward-compatible payload shape.
"""
from __future__ import annotations

import re
from typing import Any


def _sentence_english(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(item.get("en") or "").strip()
    return ""


def unused_vocabulary(spec: dict[str, Any]) -> list[str]:
    sentences = " ".join(_sentence_english(x) for x in spec.get("sentences", []) or [])
    unused = []
    seen = set()
    for item in spec.get("vocab", []) or []:
        if not isinstance(item, dict):
            continue
        word = str(item.get("en") or "").strip()
        normalized = " ".join(word.casefold().split())
        if not word or normalized in seen:
            continue
        seen.add(normalized)
        # Boundary + flexible whitespace for multiple-word expressions.
        needle = r"(?<!\w)" + r"\s+".join(re.escape(part) for part in word.split()) + r"(?!\w)"
        if not re.search(needle, sentences, flags=re.IGNORECASE):
            unused.append(word)
    return unused


def correct_consistency_report(spec: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    report = dict(existing or {})
    report["vocab_not_seen_in_sentences"] = unused_vocabulary(spec)
    return report
