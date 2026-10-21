"""Fail-closed pre-publication guards for SkyED WordPress homework."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List
from urllib.parse import urlsplit


class PublishGateError(RuntimeError):
    pass


def validate_destination(wp_base: str, expected_host: str = "skyed.org") -> str:
    u = urlsplit((wp_base or "").strip().strip('"').strip("'"))
    host = (u.hostname or "").lower().rstrip(".")
    target = (expected_host or "skyed.org").strip().lower().rstrip(".")
    if (u.scheme.lower() != "https" or not host or host != target
        or u.username is not None or u.password is not None
        or u.path not in ("", "/") or u.query or u.fragment
        or u.port not in (None, 443)):
        raise PublishGateError(
            f"Refusing WordPress publication: expected https://{target}, "
            f"got scheme={u.scheme!r}, host={host!r}. "
            "Correct WP_BASE_URL and SKYED_EXPECTED_WP_HOST explicitly."
        )
    return host


def _check_asset(root: Path, rel: str, kind: str, failures: List[str]) -> None:
    root = root.resolve()
    path = (root / rel).resolve()
    if not path.is_relative_to(root):
        failures.append(f"Unsafe asset path: {rel}")
        return
    if not path.is_file():
        failures.append(f"Missing {kind}: {rel}")
        return
    minimum = 1024 if kind == "audio" else 64
    if path.stat().st_size < minimum:
        failures.append(f"Too-small {kind} ({path.stat().st_size} B): {rel}")
        return
    if kind == "image":
        with path.open("rb") as f:
            if f.read(8) != b"\x89PNG\r\n\x1a\n":
                failures.append(f"Invalid PNG signature: {rel}")


def validate_local_media(
    lesson_root: Path, spec: Dict[str, Any], *,
    card_stem: Callable[[str], str],
    sentence_stem: Callable[[str], str],
    page_kind: str = "lesson",
) -> Dict[str, Any]:
    root = Path(lesson_root)
    failures: List[str] = []
    inspected: set[tuple[str, str]] = set()

    def add(rel: str, kind: str) -> None:
        k = (rel, kind)
        if k not in inspected:
            inspected.add(k)
            _check_asset(root, rel, kind, failures)

    if page_kind != "picture_reader":
        for v in spec.get("vocab", []) or []:
            if not isinstance(v, dict):
                continue
            en = str(v.get("en") or "").strip()
            if not en:
                continue
            stem = card_stem(en)
            add(f"cards/{stem}.png", "image")
            add(f"audio/en/{stem}.mp3", "audio")
            add(f"audio/zh/{stem}.mp3", "audio")
    for item in spec.get("sentences", []) or []:
        if isinstance(item, str):
            en, zh = item.strip(), ""
        elif isinstance(item, dict):
            en, zh = str(item.get("en") or "").strip(), str(item.get("zh") or "").strip()
        else:
            continue
        base = en or zh
        if base:
            stem = sentence_stem(base)
            if en:
                add(f"audio/en/sent_{stem}.mp3", "audio")
            if zh:
                add(f"audio/zh/sent_{stem}.mp3", "audio")

    if page_kind == "picture_reader":
        source = root / "source_image"
        if not source.is_dir() or not any(x.is_file() for x in source.iterdir()):
            failures.append("Missing picture-reader source image")
    result = {"status": "PASS" if not failures else "BLOCKED", "required_assets": len(inspected), "errors": failures}
    if failures:
        raise PublishGateError("Local media preflight blocked publication:\n" + "\n".join(failures[:30]))
    return result


def validate_image_source_quality(lesson_root: Path, spec: Dict[str, Any], page_kind: str = "lesson") -> Dict[str, Any]:
    """Prevent publishing vocabulary cards whose source is a placeholder/fallback.

    Does not replace teacher review: an 'accepted' AI or local asset may still
    depict the wrong word. This gate only detects known machine-reported
    nonproduction image sources.
    """
    if page_kind == "picture_reader":
        return {"status": "PASS", "checked": 0, "reason": "picture_reader_skip"}
    words = [
        str(item.get("en") or "").strip()
        for item in spec.get("vocab", []) or []
        if isinstance(item, dict) and str(item.get("en") or "").strip()
    ]
    if not words:
        return {"status": "PASS", "checked": 0}
    report_path = Path(lesson_root) / "cards" / "image_report.json"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise PublishGateError(
            f"Image source report unavailable or invalid: {report_path} ({type(exc).__name__}). "
            "Refusing to publish without image provenance."
        ) from exc
    if not isinstance(report, list):
        raise PublishGateError("Image source report must be a list of vocabulary rows")
    by_word = {}
    for item in report:
        if not isinstance(item, dict):
            continue
        normalized = str(item.get("word") or "").strip().casefold()
        if normalized:
            by_word[normalized] = item
    allowed = {"accepted", "local_asset_match"}
    blocked = []
    for word in words:
        status = str(by_word.get(word.casefold(), {}).get("status") or "missing")
        if status not in allowed:
            blocked.append(f"{word}: {status}")
    if blocked:
        raise PublishGateError(
            "Placeholder/fallback/unknown image source blocks publication: "
            + "; ".join(blocked[:20])
            + ". Generate suitable images and obtain teacher review before publishing."
        )
    # Existing library images are provisionally usable during the Sunny QLoRA
    # transition. This does not certify their visual semantics or licensing.
    interim = all(str(by_word[word.casefold()].get("status")) == "local_asset_match"
                  for word in words)
    return {"status": "PASS", "checked": len(words),
            "teacher_visual_review": "RECOMMENDED_INTERIM" if interim else "REQUIRED"}



def validate_picture_choice_review(lesson_root: Path) -> Dict[str, Any]:
    """Validate picture-quiz provenance and optional strict label-free review.

    Current SkyED library images may be used provisionally for guided
    practice, even when they have labels. For independent listening
    assessment set SKYED_REQUIRE_LABEL_FREE_REVIEW=1 and provide a signed
    image-hash manifest. Other existing publishing/media gates remain active.
    """
    import hashlib
    from datetime import date

    root = Path(lesson_root).resolve()
    try:
        quiz = json.loads((root / "quiz.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise PublishGateError("Picture-quiz data missing/invalid for label-free review") from exc
    questions = quiz.get("questions") or []
    picture = [q for q in questions if isinstance(q, dict) and
               q.get("kind") == "listen_to_picture"]
    if not picture:
        return {"status": "NOT_REQUIRED", "images_checked": 0}

    required = set()
    for q in picture:
        if not q.get("prompt_audio"):
            raise PublishGateError("Picture quiz missing audio prompt")
        for choice in q.get("choices") or []:
            if not isinstance(choice, dict):
                raise PublishGateError("Picture quiz must use image choices")
            raw = str(choice.get("img") or "").strip()
            if not raw.startswith("cards/") or not raw.endswith(".png"):
                raise PublishGateError(f"Unsafe picture choice path: {raw}")
            rel = Path(raw)
            if ".." in rel.parts or rel.is_absolute():
                raise PublishGateError(f"Unsafe picture choice path: {raw}")
            required.add(rel.as_posix())

    # Existing SkyED asset-database pictures are an allowed interim teaching
    # resource. Require real image provenance, but do not make a NEW signed
    # label-free manifest a default precondition for this established workflow.
    # Opt in to the stricter assessment gate after Sunny QLoRA image upgrades.
    strict = str(os.environ.get("SKYED_REQUIRE_LABEL_FREE_REVIEW", "") or "").strip().lower() in {
        "1", "true", "yes", "on"
    }
    review_path = root / "picture_choice_review.json"
    if not strict and not review_path.exists():
        try:
            report = json.loads((root / "cards" / "image_report.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError) as exc:
            raise PublishGateError("Existing asset provenance missing for interim picture quiz") from exc
        if not isinstance(report, list):
            raise PublishGateError("Invalid asset provenance for interim picture quiz")
        local_choices = {
            "cards/" + str(item.get("slug") or "").strip() + ".png"
            for item in report if isinstance(item, dict)
            and str(item.get("status") or "") == "local_asset_match"
            and str(item.get("slug") or "").strip()
        }
        if required.issubset(local_choices):
            return {"status": "INTERIM_ASSET_LIBRARY", "images_checked": len(required),
                    "teacher_visual_review": "RECOMMENDED_INTERIM",
                    "note": "Existing library pictures are suitable for guided practice; labels may help answer questions."
                    }
        raise PublishGateError(
            "Interim picture quiz may use only existing local_asset_match illustrations; "
            "non-library pictures require an explicit label-free teacher review"
        )

    try:
        review = json.loads(review_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise PublishGateError(
            "Picture quiz publication blocked until a teacher has inspected the "
            "label-free final image choices and saved picture_choice_review.json"
        ) from exc
    if (review.get("schema") != "skyed.picture-choice-review.v1" or
        review.get("label_free_confirmed") is not True or
        review.get("meaning_confirmed") is not True or
        not str(review.get("reviewer") or "").strip()):
        raise PublishGateError("Picture-quiz teacher review is incomplete")
    try:
        stamp = date.fromisoformat(str(review.get("reviewed_date") or ""))
        if stamp > date.today():
            raise ValueError("Future teacher review date")
    except ValueError as exc:
        raise PublishGateError("Invalid picture-quiz review date") from exc
    reviewed_files = review.get("images")
    if not isinstance(reviewed_files, list) or len(reviewed_files) != len(required):
        raise PublishGateError("Picture-quiz image review coverage differs from quiz")
    indexed = {
        str(x.get("path") or ""): x for x in reviewed_files if isinstance(x, dict)
    }
    if set(indexed) != required:
        raise PublishGateError("Picture-quiz reviewed image paths differ from quiz")
    for rel in sorted(required):
        item = indexed[rel]
        p = (root / rel).resolve()
        if not p.is_relative_to(root) or not p.is_file():
            raise PublishGateError(f"Reviewed picture missing: {rel}")
        expected = str(item.get("sha256") or "").strip().lower()
        current = hashlib.sha256(p.read_bytes()).hexdigest()
        if (expected != current or item.get("label_free") is not True or
            item.get("meaning_correct") is not True):
            raise PublishGateError(f"Picture review missing, not label-free or stale: {rel}")
    return {"status": "PASS", "images_checked": len(required),
            "reviewed_date": stamp.isoformat(), "human_review": "EXPLICIT"}



def _check_url(url: str, context: str, failures: List[str]) -> None:
    u = urlsplit(str(url or "").strip())
    if (u.scheme.lower() != "https" or not u.hostname
        or u.username is not None or u.password is not None
        or u.hostname.lower().rstrip(".") in {"skyedu.fun", "www.skyedu.fun"}):
        failures.append(f"Missing, insecure or retired media URL: {context}")


def validate_remote_payload(payload: Dict[str, Any], original_quiz: Dict[str, Any] | None = None) -> Dict[str, Any]:
    failures: List[str] = []
    inspected = 0

    def check(url: str, context: str) -> None:
        nonlocal inspected
        inspected += 1
        _check_url(url, context, failures)

    if payload.get("page_kind") != "picture_reader":
        for i, v in enumerate(payload.get("vocab") or []):
            if not isinstance(v, dict) or not str(v.get("en") or "").strip():
                continue
            for key in ("img", "audio_en", "audio_zh"):
                check(v.get(key, ""), f"vocab[{i}].{key}")
    for i, v in enumerate(payload.get("sentences") or []):
        if not isinstance(v, dict):
            continue
        for lang in ("en", "zh"):
            if str(v.get(lang) or "").strip():
                check(v.get(f"audio_{lang}", ""), f"sentences[{i}].audio_{lang}")

    rewritten = payload.get("practice") or payload.get("quiz") or {}
    orig_questions = (original_quiz or {}).get("questions") or []
    new_questions = rewritten.get("questions") or []
    if original_quiz is not None and len(orig_questions) != len(new_questions):
        failures.append("Quiz question count changed during media rewrite")
    for i, question in enumerate(orig_questions):
        if not isinstance(question, dict):
            continue
        mapped = new_questions[i] if i < len(new_questions) and isinstance(new_questions[i], dict) else {}
        for key in ("prompt_audio", "prompt_image"):
            if question.get(key):
                check(mapped.get(key, ""), f"quiz.questions[{i}].{key}")
        old_choices, new_choices = question.get("choices") or [], mapped.get("choices") or []
        if len(old_choices) != len(new_choices):
            failures.append(f"Choice count changed in quiz question {i}")
        for j, old_choice in enumerate(old_choices):
            if not isinstance(old_choice, dict):
                continue
            new_choice = new_choices[j] if j < len(new_choices) and isinstance(new_choices[j], dict) else {}
            for key in ("img", "audio"):
                if old_choice.get(key):
                    check(new_choice.get(key, ""), f"quiz.questions[{i}].choices[{j}].{key}")

    for i, item in enumerate(payload.get("extra_audio") or []):
        if isinstance(item, dict):
            check(item.get("url", ""), f"extra_audio[{i}].url")
    for block in ("reading_block", "listening_block"):
        info = payload.get(block) or {}
        if isinstance(info, dict):
            for i, variant in enumerate(info.get("audio_variants") or []):
                if isinstance(variant, dict):
                    check(variant.get("url", ""), f"{block}.audio_variants[{i}].url")
    result = {"status": "PASS" if not failures else "BLOCKED", "checked_urls": inspected, "errors": failures}
    if failures:
        raise PublishGateError("Remote media preflight blocked publication:\n" + "\n".join(failures[:30]))
    return result
