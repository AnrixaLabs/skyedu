"""Generate and verify a real SkyED EN/ZH media lesson, with NO WordPress writes.

Requires an isolated Git checkout (not the PyCharm original), Edge TTS network
access, Pillow and mutagen. Image backend is local_assets_only: outputs MUST be
teacher reviewed, especially fallback/placeholder scenes.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

SAMPLE = """#Title: SkyED Media QA - Animals and Toys
#Tags: animals, toys
#Vocabulary:
noun: cat-猫, noun: dog-狗, noun: apple-苹果, noun: ball-球
#Sentences:
This is a cat.
这是一只猫。
I see a dog.
我看到一只狗。
"""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_lesson(lesson: Path) -> tuple[dict, list[dict]]:
    from PIL import Image
    from mutagen.mp3 import MP3
    from skyed.publish_gates import validate_local_media
    from skyed.utils import slugify_file
    from skyed.pipeline_helpers import sentence_audio_stem

    lesson = lesson.resolve()
    spec = json.loads((lesson / "spec_debug.json").read_text(encoding="utf-8"))
    quiz = json.loads((lesson / "quiz.json").read_text(encoding="utf-8"))
    gate = validate_local_media(lesson, spec, card_stem=slugify_file,
                                sentence_stem=sentence_audio_stem, page_kind="lesson")
    inspected = {}
    failures = []

    def require(raw: str, origin: str) -> None:
        rel = Path(str(raw or "").strip())
        if (not raw or rel.is_absolute() or ".." in rel.parts or
            not rel.parts or rel.parts[0] not in {"audio", "cards"}):
            failures.append(f"Unsafe or blank media reference: {origin}: {raw}")
            return
        path = (lesson / rel).resolve()
        if not path.is_relative_to(lesson) or not path.is_file():
            failures.append(f"Missing media: {origin}: {raw}")
            return
        if raw in inspected:
            inspected[raw]["references"].append(origin)
            return
        item = {"path": raw, "bytes": path.stat().st_size,
                "sha256": sha256(path), "references": [origin],
                "status": "PASS"}
        try:
            if path.suffix.lower() == ".png":
                with Image.open(path) as img:
                    w, h = img.size
                    img.verify()
                if w < 128 or h < 128:
                    raise ValueError(f"Image too small: {w}x{h}")
                item["dimensions"] = [w, h]
            elif path.suffix.lower() == ".mp3":
                audio = MP3(str(path))
                duration = float(audio.info.length)
                if duration < 0.2:
                    raise ValueError(f"Audio too short: {duration}s")
                item["duration_seconds"] = round(duration, 3)
                item["bitrate"] = int(audio.info.bitrate)
            else:
                raise ValueError(f"Unsupported type {path.suffix}")
        except Exception as exc:
            failures.append(f"Media integrity failed: {origin}: {raw}: {exc}")
            item["status"] = "FAIL"
        inspected[raw] = item

    for i, v in enumerate(spec.get("vocab") or []):
        word = str(v.get("en") or "").strip()
        if not word:
            continue
        stem = slugify_file(word)
        for suffix, name in [("png", f"cards/{stem}.png"),
                             ("en", f"audio/en/{stem}.mp3"),
                             ("zh", f"audio/zh/{stem}.mp3")]:
            require(name, f"vocab[{i}].{suffix}")

    for i, s in enumerate(spec.get("sentences") or []):
        en, zh = str(s.get("en") or "").strip(), str(s.get("zh") or "").strip()
        if not (en or zh):
            continue
        stem = sentence_audio_stem(en or zh)
        for language, text in (("en", en), ("zh", zh)):
            if text:
                require(f"audio/{language}/sent_{stem}.mp3", f"sentences[{i}].{language}")

    for i, q in enumerate(quiz.get("questions") or []):
        if not isinstance(q, dict):
            failures.append(f"Invalid question object #{i}")
            continue
        for key in ("prompt_audio", "prompt_image"):
            if q.get(key):
                require(str(q[key]), f"quiz[{i}].{key}")
        for j, choice in enumerate(q.get("choices") or []):
            if isinstance(choice, dict):
                for key in ("img", "audio"):
                    if choice.get(key):
                        require(str(choice[key]), f"quiz[{i}].choices[{j}].{key}")

    for name in ("lesson.html", "index.html", "lesson_manifest.json"):
        if not (lesson / name).is_file():
            failures.append(f"Missing rendered file {name}")
    fallbacks = [
        p.relative_to(lesson).as_posix() for p in lesson.rglob("*")
        if p.is_file() and p.name.endswith((".fallback.txt", ".fail.txt"))
    ]
    summary = {
        "status": "PASS" if not failures else "FAIL",
        "media_count": len(inspected),
        "image_count": sum(p.endswith(".png") for p in inspected),
        "mp3_count": sum(p.endswith(".mp3") for p in inspected),
        "local_media_gate": gate,
        "fallback_markers": sorted(fallbacks),
        "manual_image_and_audio_review": "REQUIRED",
        "production_publish_authorized": False,
        "failures": failures,
    }
    return summary, sorted(inspected.values(), key=lambda x: x["path"])


def _git_head(repo: Path) -> str:
    try:
        r = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else "UNVERIFIED"
    except (OSError, subprocess.TimeoutExpired):
        return "UNVERIFIED"


def generate(repo: Path, output: Path, timeout: int) -> dict:
    repo, output = repo.resolve(), output.resolve()
    if (repo.name.casefold() == "skyed_automation" or output == repo or
        output.is_relative_to(repo) or repo.is_relative_to(output)):
        raise ValueError("Refusing to modify the original PyCharm source or nested paths")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite media QA evidence: {output}")
    if not (repo / "run_pipeline.py").is_file():
        raise ValueError("Missing run_pipeline.py in selected checkout")
    output.mkdir(parents=True)
    homework = output / "media-qa-homework.txt"
    homework.write_text(SAMPLE, encoding="utf-8")
    env = dict(os.environ)
    env.update({
        "OUTPUT_DIR": str(output / "generated"),
        "IMG_BACKEND": "local_assets_only",
        "SKYED_DRY_RUN": "0",
        "SKYED_PIPELINE_ENTRYPOINT": "", "SKYED_NG_ACTION": "",
        "SKYED_ENABLE_SHARED_TAG_DISCOVERY": "0",
        "WP_BASE_URL": "", "WP_BASE": "", "WP_USER": "",
        "WP_APP_PASSWORD": "", "WP_PUBLISH_STATUS": "draft",
        "QUIZ_PUBLIC_BASE": "", "TAGS_PUBLIC_BASE": "",
        "SKYED_TTS_RETRIES": "2", "SKYED_TTS_CONCURRENCY": "2",
        "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
    })
    cmd = [sys.executable, "run_pipeline.py", "--input", str(homework),
           "--theme", "sky_tiles", "--publish-status", "draft"]
    log = output / "generation.log"
    try:
        with log.open("wb") as handle:
            child = subprocess.run(cmd, cwd=repo, env=env, check=False,
                                   stdin=subprocess.DEVNULL,
                                   stdout=handle, stderr=subprocess.STDOUT,
                                   timeout=timeout)
        code = int(child.returncode)
    except subprocess.TimeoutExpired:
        code = 124
        with log.open("ab") as handle:
            handle.write(b"\nGENERATION_TIMEOUT\n")
    folder = output / "generated"
    lessons = [p for p in folder.iterdir() if p.is_dir()] if folder.is_dir() else []
    result = {
        "status": "BLOCKED",
        "generator_exit_code": code,
        "source_commit": _git_head(repo),
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "wordpress_posts_created": 0,
        "production_publish_authorized": False,
        "manual_image_and_audio_review": "REQUIRED",
    }
    checked_files = []
    if code != 0:
        result["failures"] = ["Generator failed: inspect generation.log"]
    elif len(lessons) != 1:
        result["failures"] = ["Expected exactly one isolated lesson output"]
    else:
        try:
            summary, checked_files = validate_lesson(lessons[0])
            result.update(summary)
            result["status"] = "TECHNICAL_MEDIA_PASS" if summary["status"] == "PASS" else "BLOCKED"
        except Exception as exc:
            result["failures"] = [f"Validation failed: {type(exc).__name__}: {exc}"]

    report = output / "media-validation.json"
    report.write_text(json.dumps({"result": result, "files": checked_files},
                                 ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archive = output / "SkyED-Real-Media-QA-Evidence.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
        for p in (homework, log, report):
            if p.is_file():
                z.write(p, p.relative_to(output).as_posix())
        if len(lessons) == 1:
            for name in ("quiz.json", "spec_debug.json", "image_report.json", "lesson_manifest.json"):
                p = lessons[0] / name
                if p.is_file():
                    z.write(p, f"lesson/{name}")
            for entry in checked_files:
                p = lessons[0] / entry["path"]
                if p.is_file() and p.stat().st_size <= 8 * 1024 * 1024:
                    z.write(p, f"lesson/{entry['path']}")
    result["evidence_zip"] = str(archive)
    result["evidence_sha256"] = sha256(archive)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--output-root", required=True, type=Path)
    p.add_argument("--generate", action="store_true",
                   help="Explicitly enable real Edge TTS calls and local image generation")
    p.add_argument("--timeout", type=int, default=480)
    args = p.parse_args()
    try:
        if not args.generate:
            raise ValueError("--generate is required; no implicit network work")
        result = generate(args.repo, args.output_root, args.timeout)
    except Exception as exc:
        result = {"status": "BLOCKED",
                  "error": f"{type(exc).__name__}: {exc}",
                  "production_publish_authorized": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "TECHNICAL_MEDIA_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
