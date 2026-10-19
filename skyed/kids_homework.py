"""Generate audio-first kindergarten homework from an existing SkyED lesson spec.

Pure-data builder: does not modify the older quiz formats or publish content.
Media paths follow the existing SkyED cards/audio layout.
"""
from __future__ import annotations

import hashlib
import json
import random
from typing import Any

from .utils import slugify as card_slugify


def _sentence_stem(text: str) -> str:
    short = card_slugify(text[:60])
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"{short}_{digest}" if short else digest


def generate_kids_homework(
    spec: dict[str, Any], *, max_words: int = 6, max_sentences: int = 3
) -> dict[str, Any]:
    """Build deterministic listening, repetition, and picture-choice activities.

    Missing images do not become broken choice questions. Missing audio files
    must be caught by the media validator before publishing.
    """
    if not 1 <= max_words <= 12 or not 0 <= max_sentences <= 6:
        raise ValueError("Invalid kindergarten lesson limits")
    words: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in spec.get("vocab", []):
        if not isinstance(item, dict):
            continue
        en = str(item.get("en") or "").strip()
        key = en.casefold()
        if not en or key in seen:
            continue
        seen.add(key)
        stem = card_slugify(en)
        words.append({
            "en": en, "zh": str(item.get("zh") or "").strip(),
            "image": str(item.get("img") or f"cards/{stem}.png"),
            "audio": str(item.get("audio_en") or f"audio/en/{stem}.mp3"),
        })
        if len(words) == max_words:
            break
    if not words:
        raise ValueError("At least one vocabulary word is required")

    activities: list[dict[str, Any]] = [
        {"type": "listen", "items": words},
        {"type": "repeat", "items": [
            {"text": w["en"], "audio": w["audio"], "image": w["image"]}
            for w in words
        ]},
    ]
    # Only generate choice tasks when distinct pictures are available.
    pictured = [w for w in words if w["image"]]
    unique_images = {w["image"] for w in pictured}
    if len(pictured) >= 3 and len(unique_images) == len(pictured):
        seed = hashlib.sha256(json.dumps(words, sort_keys=True, ensure_ascii=False).encode()).digest()
        rng = random.Random(int.from_bytes(seed[:8], "big"))
        questions = []
        for target in pictured:
            distractors = [w for w in pictured if w["en"] != target["en"]]
            choices = rng.sample(distractors, min(2, len(distractors))) + [target]
            rng.shuffle(choices)
            questions.append({
                "prompt_audio": target["audio"],
                "prompt_text": target["en"],
                "choices": [{"image": w["image"], "text": w["en"]} for w in choices],
                "answer_index": choices.index(target),
            })
        activities.append({"type": "listen_and_choose", "questions": questions})

    sentences = []
    for raw in ((spec.get("sentences", []) or [])[:max_sentences] if max_sentences else []):
        text = raw.strip() if isinstance(raw, str) else str(raw.get("en") or "").strip() if isinstance(raw, dict) else ""
        if text:
            sentences.append({
                "text": text, "audio": f"audio/en/sent_{_sentence_stem(text)}.mp3"
            })
        if len(sentences) == max_sentences:
            break
    if sentences:
        activities.append({"type": "speak_with_parent", "items": sentences})

    return {
        "schema_version": 1,
        "mode": "kids_listen_play",
        "title": str(spec.get("title") or "English Practice"),
        "instructions_zh": "听一听、跟读、点图片，和家长一起说英语。",
        "activities": activities,
    }


def required_media(package: dict[str, Any]) -> set[str]:
    """Return media dependencies for fail-closed pre-publication validation."""
    media: set[str] = set()
    for activity in package["activities"]:
        for item in activity.get("items", []):
            for key in ("audio", "image"):
                if item.get(key):
                    media.add(item[key])
        for question in activity.get("questions", []):
            if question.get("prompt_audio"):
                media.add(question["prompt_audio"])
            for choice in question["choices"]:
                if choice.get("image"):
                    media.add(choice["image"])
    return media
