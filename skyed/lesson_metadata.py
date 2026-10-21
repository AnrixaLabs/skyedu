from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List


def infer_categories(spec: Dict[str, Any], *, theme: str = "sky", lesson_mode: str = "standard_homework", surface_variant: str = "classic", page_kind: str = "lesson") -> Dict[str, Any]:
    vocab = spec.get("vocab", []) or []
    tags = [str(t).strip() for t in (spec.get("tags") or []) if str(t).strip()]
    pos_counter = Counter(str(v.get("pos") or "").strip().lower() for v in vocab if isinstance(v, dict))
    grammar_focus = [pos for pos, count in pos_counter.items() if pos and count >= 1 and pos not in {"noun", "phrase"}]
    lexical_focus = sorted(set(tags))
    if not lexical_focus:
        lexical_focus = ["general"]

    age_band = "kids" if theme == "sky_tiles" or lesson_mode == "kid_homework" else "general"
    device_focus = ["smartphone", "desktop"]
    skill_focus = ["listening", "speaking"]
    if spec.get("sentences"):
        skill_focus.append("reading")
    if spec.get("qa") or spec.get("comprehension_questions"):
        skill_focus.append("response")
    if page_kind == "picture_reader":
        skill_focus = ["reading", "listening", "tap_to_play"]

    return {
        "page_kind": page_kind,
        "theme_variant": theme,
        "lesson_mode": lesson_mode,
        "surface_variant": surface_variant,
        "age_band": age_band,
        "skill_focus": skill_focus,
        "grammar_focus": grammar_focus,
        "lexical_focus": lexical_focus,
        "device_focus": device_focus,
    }
