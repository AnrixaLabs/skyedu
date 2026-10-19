"""Fail-closed pre-publication guards for SkyED WordPress homework."""
from __future__ import annotations

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
