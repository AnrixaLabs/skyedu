from __future__ import annotations

import html
import json
import random
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .asset_library import copy_record_image, default_asset_library_root, find_best_asset, find_loose_file_asset
from .parser import parse_homework_text
from .tag_game_profiles import (
    CATEGORY_SUGGESTIONS,
    GAME_LABELS,
    GAME_PROFILES,
    STYLE_LABELS,
    coerce_game_settings,
    default_settings_for_game,
    get_game_profile,
)
from .tag_registry import safe_tag
from .tts_edge import generate_word_audio_set


@dataclass(slots=True)
class TagCreatorOptions:
    tag: str
    title: str
    category: str
    game_type: str
    game_id: str
    style: str
    voice: str
    rate: str
    settings_json: str = ""
    use_local_assets: bool = True
    generate_audio: bool = True


@dataclass(slots=True)
class TagCreatorResult:
    tag: str
    game_id: str
    title: str
    category: str
    preview_root: Path
    preview_index: Path
    publish_root: Optional[Path]
    publish_index: Optional[Path]
    vocab_count: int
    assets_used: int
    placeholders_used: int
    audio_generated: int
    catalog_files: List[Path]


def normalize_category_slug(text: str) -> str:
    slug = safe_tag((text or "").strip().lower().replace("&", " and "))
    return slug or "general"


def category_title_from_slug(slug: str) -> str:
    raw = str(slug or "general").replace("_", " ").replace("-", " ").strip()
    return " ".join(part.capitalize() for part in raw.split()) or "General"


def default_game_id(game_type: str) -> str:
    base = safe_tag(game_type) or "tag_game"
    if base.endswith("_v1") or base.endswith("-v1"):
        return base
    return f"{base}_v1"


def preview_root(project_root: Path) -> Path:
    return project_root / "output" / "tag_s_preview"


def published_root(project_root: Path) -> Path:
    return project_root / "tag_s"


def build_preview_from_text(
    *,
    text: str,
    options: TagCreatorOptions,
    project_root: Path,
    source_dir: Optional[Path] = None,
    output_root: Optional[Path] = None,
) -> TagCreatorResult:
    parsed = parse_homework_text(text or "")
    vocab = [dict(item) for item in list(parsed.get("vocab") or []) if isinstance(item, dict) and str(item.get("en") or "").strip()]
    if not vocab:
        raise RuntimeError("No vocabulary items found in the source text. Add a #Vocabulary section first.")

    profile = get_game_profile(str(options.game_type or "touch_listen_cards"))
    tag_value = safe_tag(options.tag or (parsed.get("tags") or [""])[0] or parsed.get("title") or "tag_s")
    if not tag_value:
        raise RuntimeError("tag_s tag is empty. Set a tag or add #Tags in the source text.")
    category_text = options.category or profile.default_category or (parsed.get("tags") or [""])[0] or "Vocabulary"
    category_slug = normalize_category_slug(category_text)
    category_title = category_title_from_slug(category_slug)
    game_type = safe_tag(options.game_type or profile.key) or profile.key
    game_id = safe_tag(options.game_id or default_game_id(game_type)) or default_game_id(game_type)
    title = str(options.title or parsed.get("title") or tag_value).strip() or tag_value
    display_title = f"{title} · {GAME_LABELS.get(game_type, game_type.replace('_', ' ').title())}"
    settings = coerce_game_settings(game_type, options.settings_json)

    out_root = Path(output_root or preview_root(project_root))
    game_root = out_root / tag_value / game_id
    if game_root.exists():
        shutil.rmtree(game_root, ignore_errors=True)
    game_root.mkdir(parents=True, exist_ok=True)

    assets_root = game_root / "assets"
    images_root = assets_root / "images"
    audio_root = assets_root / "audio"
    images_root.mkdir(parents=True, exist_ok=True)
    if options.generate_audio:
        audio_root.mkdir(parents=True, exist_ok=True)

    library_root = default_asset_library_root(project_root)

    resolved_items: List[Dict[str, Any]] = []
    assets_used = 0
    placeholders_used = 0
    audio_jobs: List[tuple[str, str]] = []
    audio_rel_by_slug: Dict[str, str] = {}

    for idx, item in enumerate(vocab, start=1):
        en = str(item.get("en") or "").strip()
        zh = str(item.get("zh") or "").strip()
        pos = str(item.get("pos") or "word").strip().lower() or "word"
        slug = safe_tag(f"{idx:03d}_{en}") or f"item_{idx:03d}"
        image_name = f"{slug}.png"
        image_path = images_root / image_name
        image_rel = f"assets/images/{image_name}"
        copied = _materialize_item_image(
            en=en,
            zh=zh,
            pos=pos,
            out_path=image_path,
            library_root=library_root,
            source_dir=source_dir,
            source_value=str(item.get("img") or "").strip(),
            style=options.style,
            use_local_assets=bool(options.use_local_assets),
        )
        if copied:
            assets_used += 1
        else:
            placeholders_used += 1

        resolved_items.append(
            {
                "id": f"item_{idx:03d}",
                "label": en,
                "text": zh,
                "block_type": pos,
                "image": image_rel,
                "audio": "",
                "first_letter": en[:1].upper(),
                "length": len(re.sub(r"[^A-Za-z]", "", en)),
            }
        )
        if options.generate_audio and en:
            audio_jobs.append((slug, en))

    if options.generate_audio and audio_jobs:
        generated = generate_word_audio_set(audio_jobs, audio_root, voice=options.voice or "en-US-GuyNeural", rate=options.rate or "-16%")
        for slug, _text in audio_jobs:
            path = generated.get(slug)
            if path is not None:
                audio_rel_by_slug[slug] = f"assets/audio/{path.name}"
        for idx, item in enumerate(resolved_items, start=1):
            slug = safe_tag(f"{idx:03d}_{item['label']}") or f"item_{idx:03d}"
            item["audio"] = audio_rel_by_slug.get(slug, "")
    audio_generated = len(audio_rel_by_slug)

    sentence_items = _build_sentence_bank(parsed, resolved_items)
    description_rounds = _build_description_rounds(sentence_items, resolved_items, settings)
    mystery_rounds = _build_mystery_rounds(resolved_items, settings)
    spelling_targets = _build_spelling_targets(resolved_items, settings)

    payload = _build_payload(
        parsed=parsed,
        tag=tag_value,
        game_id=game_id,
        title=display_title,
        category_slug=category_slug,
        category_title=category_title,
        game_type=game_type,
        style=options.style,
        settings=settings,
        items=resolved_items,
        sentence_items=sentence_items,
        description_rounds=description_rounds,
        mystery_rounds=mystery_rounds,
        spelling_targets=spelling_targets,
    )

    (game_root / "game.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (game_root / "styles.css").write_text(_runtime_css(), encoding="utf-8")
    (game_root / "runtime.js").write_text(_runtime_js(), encoding="utf-8")
    (game_root / "index.html").write_text(_runtime_html(payload), encoding="utf-8")
    catalog_files = list(write_tag_catalog_indexes(out_root).values())

    return TagCreatorResult(
        tag=tag_value,
        game_id=game_id,
        title=display_title,
        category=category_title,
        preview_root=game_root,
        preview_index=game_root / "index.html",
        publish_root=None,
        publish_index=None,
        vocab_count=len(resolved_items),
        assets_used=assets_used,
        placeholders_used=placeholders_used,
        audio_generated=audio_generated,
        catalog_files=catalog_files,
    )


def publish_preview_pack(*, preview_game_root: Path, project_root: Path) -> TagCreatorResult:
    preview_game_root = Path(preview_game_root)
    payload = json.loads((preview_game_root / "game.json").read_text(encoding="utf-8"))
    meta = payload.get("meta") or {}
    tag = safe_tag(str(meta.get("tag") or preview_game_root.parent.name))
    game_id = safe_tag(str(meta.get("game_id") or preview_game_root.name))
    if not tag or not game_id:
        raise RuntimeError("Preview pack is missing tag/game_id metadata.")
    pub_root = published_root(project_root) / tag / game_id
    if pub_root.exists():
        shutil.rmtree(pub_root, ignore_errors=True)
    pub_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(preview_game_root, pub_root)
    catalog_files = list(write_tag_catalog_indexes(published_root(project_root)).values())
    return TagCreatorResult(
        tag=tag,
        game_id=game_id,
        title=str(meta.get("title") or f"{tag} · {game_id}"),
        category=str(meta.get("category_title") or meta.get("category") or "General"),
        preview_root=preview_game_root,
        preview_index=preview_game_root / "index.html",
        publish_root=pub_root,
        publish_index=pub_root / "index.html",
        vocab_count=len(list(payload.get("items") or [])),
        assets_used=sum(1 for item in list(payload.get("items") or []) if str(item.get("image") or "").strip()),
        placeholders_used=0,
        audio_generated=sum(1 for item in list(payload.get("items") or []) if str(item.get("audio") or "").strip()),
        catalog_files=catalog_files,
    )


def write_tag_catalog_indexes(root: Path) -> Dict[str, Path]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    entries = _scan_catalog(root)
    root_index = root / "index.html"
    root_index.write_text(_catalog_page_html(entries=entries, page_title="tag_s Library", page_subtitle="Categories and reusable game packs.", page_kind="root"), encoding="utf-8")

    category_files: Dict[str, Path] = {"root": root_index}
    grouped_categories: Dict[str, List[Dict[str, Any]]] = {}
    grouped_tags: Dict[str, List[Dict[str, Any]]] = {}
    for entry in entries:
        grouped_categories.setdefault(str(entry.get("category_slug") or "general"), []).append(entry)
        grouped_tags.setdefault(str(entry.get("tag") or "general"), []).append(entry)

    categories_root = root / "categories"
    if categories_root.exists():
        shutil.rmtree(categories_root, ignore_errors=True)
    categories_root.mkdir(parents=True, exist_ok=True)
    categories_index = categories_root / "index.html"
    categories_index.write_text(_catalog_page_html(entries=entries, page_title="tag_s Categories", page_subtitle="Browse packs by website category.", page_kind="categories_root"), encoding="utf-8")
    category_files["categories"] = categories_index
    for category_slug, items in grouped_categories.items():
        category_dir = categories_root / category_slug
        category_dir.mkdir(parents=True, exist_ok=True)
        title = category_title_from_slug(category_slug)
        page = category_dir / "index.html"
        page.write_text(_catalog_page_html(entries=items, page_title=title, page_subtitle=f"tag_s packs in {title}.", page_kind="category"), encoding="utf-8")
        category_files[f"category:{category_slug}"] = page

    for tag, items in grouped_tags.items():
        tag_dir = root / tag
        if not tag_dir.exists():
            continue
        page = tag_dir / "index.html"
        page.write_text(_catalog_page_html(entries=items, page_title=tag.replace('-', ' ').title(), page_subtitle="Packs grouped by theme tag.", page_kind="tag"), encoding="utf-8")
        category_files[f"tag:{tag}"] = page
    return category_files


def _build_payload(
    *,
    parsed: Dict[str, Any],
    tag: str,
    game_id: str,
    title: str,
    category_slug: str,
    category_title: str,
    game_type: str,
    style: str,
    settings: Dict[str, Any],
    items: List[Dict[str, Any]],
    sentence_items: List[Dict[str, Any]],
    description_rounds: List[Dict[str, Any]],
    mystery_rounds: List[Dict[str, Any]],
    spelling_targets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    reading = parsed.get("reading_block") or {}
    listening = parsed.get("listening_block") or {}
    profile = get_game_profile(game_type)
    meta = {
        "schema": "tag_s.v3",
        "tag": tag,
        "game_id": game_id,
        "title": title,
        "renderer": game_type,
        "variant": "local_preview_ready",
        "skill": _skill_for_game_type(game_type),
        "difficulty": str(settings.get("difficulty") or "beginner"),
        "style": style or "sky_soft",
        "settings": settings,
        "category": category_slug,
        "category_slug": category_slug,
        "category_title": category_title,
        "thumbnail": items[0].get("image", "") if items else "",
        "description": profile.description,
        "item_count": len(items),
        "theme_tags": list(parsed.get("tags") or []),
        "reading_title": str(reading.get("title") or ""),
        "reading_text": str(reading.get("text") or ""),
        "listening_title": str(listening.get("title") or ""),
        "listening_text": str(listening.get("text") or ""),
        "source_focus": profile.source_focus,
        "imported_from": list(profile.imported_from),
    }
    payload: Dict[str, Any] = {
        "meta": meta,
        "items": items,
        "sentences": sentence_items,
        "qa": list(parsed.get("qa") or []),
        "description_rounds": description_rounds,
        "mystery_rounds": mystery_rounds,
        "spelling_targets": spelling_targets,
    }
    return payload


def _build_sentence_bank(parsed: Dict[str, Any], items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bank: List[Dict[str, Any]] = []
    seen: set[str] = set()
    source_sentences = list(parsed.get("sentences") or [])
    for idx, sent in enumerate(source_sentences, start=1):
        en = str((sent or {}).get("en") or "").strip()
        zh = str((sent or {}).get("zh") or "").strip()
        if not en:
            continue
        key = en.lower()
        if key in seen:
            continue
        seen.add(key)
        bank.append(_sentence_entry(idx, en, zh, items))
    if not bank:
        for idx, item in enumerate(items[:12], start=1):
            en = str(item.get("label") or "").strip()
            zh = str(item.get("text") or "").strip()
            if not en:
                continue
            auto_sentence = f"This is {article_for(en)} {en}."
            bank.append(_sentence_entry(idx, auto_sentence, zh, items))
    for idx, qa in enumerate(list(parsed.get("qa") or []), start=len(bank) + 1):
        q = str((qa or {}).get("q") or "").strip()
        a = str((qa or {}).get("a") or "").strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            bank.append(_sentence_entry(idx, q, a, items))
    reading_text = str((parsed.get("reading_block") or {}).get("text") or "").strip()
    if reading_text:
        for line in [ln.strip() for ln in reading_text.splitlines() if ln.strip()]:
            if line.lower() in seen:
                continue
            seen.add(line.lower())
            bank.append(_sentence_entry(len(bank) + 1, line, "", items))
    return bank[:36]


def _sentence_entry(idx: int, en: str, zh: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    tokens = [token for token in re.split(r"\s+", re.sub(r"([,.!?])", r" \1 ", en).strip()) if token]
    answer_id = _match_item_id_from_text(en, items)
    return {"id": f"sent_{idx:03d}", "text": en, "translation": zh, "tokens": tokens, "answer_id": answer_id}


def _build_description_rounds(sentence_items: List[Dict[str, Any]], items: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    choice_count = int(settings.get("choice_count") or 4)
    rounds: List[Dict[str, Any]] = []
    for sentence in sentence_items:
        answer_id = str(sentence.get("answer_id") or "").strip()
        if not answer_id:
            continue
        answer_idx = next((idx for idx, item in enumerate(items) if str(item.get("id") or "") == answer_id), -1)
        if answer_idx < 0:
            continue
        choice_ids = _choice_ids(items, answer_idx, choice_count)
        rounds.append(
            {
                "id": f"desc_{len(rounds)+1:03d}",
                "prompt": str(sentence.get("text") or "").strip(),
                "translation": str(sentence.get("translation") or "").strip(),
                "answer_id": answer_id,
                "choice_ids": choice_ids,
            }
        )
    if not rounds:
        for idx, item in enumerate(items):
            choice_ids = _choice_ids(items, idx, choice_count)
            rounds.append(
                {
                    "id": f"desc_{len(rounds)+1:03d}",
                    "prompt": f"Find {article_for(str(item.get('label') or 'word'))} {str(item.get('label') or 'word')}.",
                    "translation": str(item.get("text") or "").strip(),
                    "answer_id": str(item.get("id") or ""),
                    "choice_ids": choice_ids,
                }
            )
            if len(rounds) >= 12:
                break
    return rounds[:24]


def _build_mystery_rounds(items: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    choice_count = min(max(int(settings.get("choice_count") or 6), 3), max(len(items), 3))
    rounds: List[Dict[str, Any]] = []
    usable = items[:24]
    for idx, item in enumerate(usable):
        choice_ids = _choice_ids(usable, idx, choice_count)
        label = str(item.get("label") or "").strip()
        zh = str(item.get("text") or "").strip()
        pos = str(item.get("block_type") or "word").strip()
        clues = [
            {"title": "First letter", "text": label[:1].upper() if label else "?"},
            {"title": "Length", "text": str(max(1, len(re.sub(r"[^A-Za-z]", "", label))))},
            {"title": "Chinese", "text": zh or "—"},
            {"title": "Part of speech", "text": pos.replace("_", " ").title()},
        ]
        rounds.append({"id": f"myst_{idx+1:03d}", "answer_id": str(item.get("id") or ""), "choice_ids": choice_ids, "clues": clues})
    return rounds[:16]


def _build_spelling_targets(items: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    max_len = max(4, int(settings.get("max_word_length") or 12))
    out: List[Dict[str, Any]] = []
    for item in items:
        label = re.sub(r"[^A-Za-z]", "", str(item.get("label") or "")).lower()
        if len(label) < 3 or len(label) > max_len:
            continue
        bank = list(label)
        alphabet = list("abcdefghijklmnopqrstuvwxyz")
        random.shuffle(alphabet)
        while len(bank) < min(max_len + 2, len(label) + 4):
            bank.append(alphabet.pop())
        random.shuffle(bank)
        out.append(
            {
                "id": str(item.get("id") or ""),
                "label": str(item.get("label") or ""),
                "text": str(item.get("text") or ""),
                "image": str(item.get("image") or ""),
                "audio": str(item.get("audio") or ""),
                "letters": bank,
                "answer": label,
            }
        )
    return out[:18] or [{"id": str(items[0].get("id") or "item_001"), "label": str(items[0].get("label") or "word"), "text": str(items[0].get("text") or ""), "image": str(items[0].get("image") or ""), "audio": str(items[0].get("audio") or ""), "letters": list("word"), "answer": "word"}] if items else []


def _match_item_id_from_text(text: str, items: Sequence[Dict[str, Any]]) -> str:
    lower = f" {str(text or '').lower()} "
    for item in items:
        label = str(item.get("label") or "").strip().lower()
        if not label:
            continue
        if f" {label} " in lower:
            return str(item.get("id") or "")
    return ""


def _choice_ids(items: Sequence[Dict[str, Any]], answer_idx: int, count: int) -> List[str]:
    ids = {answer_idx}
    while len(ids) < min(count, len(items)):
        ids.add(random.randint(0, len(items) - 1))
    order = list(ids)
    random.shuffle(order)
    return [str(items[idx].get("id") or "") for idx in order]


def _scan_catalog(root: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not root.exists():
        return out
    for tag_dir in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
        if tag_dir.name.lower() == "categories":
            continue
        tag = safe_tag(tag_dir.name)
        if not tag:
            continue
        for game_dir in sorted([p for p in tag_dir.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
            game_json = game_dir / "game.json"
            if not game_json.exists():
                continue
            try:
                payload = json.loads(game_json.read_text(encoding="utf-8"))
            except Exception:
                continue
            meta = payload.get("meta") if isinstance(payload, dict) else {}
            if not isinstance(meta, dict):
                meta = {}
            renderer = str(meta.get("renderer") or "").strip()
            profile = get_game_profile(renderer)
            entry = {
                "tag": tag,
                "game_id": safe_tag(str(meta.get("game_id") or game_dir.name)) or game_dir.name,
                "title": str(meta.get("title") or f"{tag} · {game_dir.name}").strip(),
                "renderer": renderer,
                "renderer_label": profile.label,
                "category_slug": normalize_category_slug(str(meta.get("category_slug") or meta.get("category") or "general")),
                "category_title": str(meta.get("category_title") or category_title_from_slug(str(meta.get("category_slug") or meta.get("category") or "general"))),
                "description": str(meta.get("description") or profile.description).strip(),
                "thumbnail": str(meta.get("thumbnail") or "").strip(),
                "item_count": int(meta.get("item_count") or len(list(payload.get("items") or [])) or 0),
                "href_from_category": f"../../{tag}/{game_dir.name}/index.html",
                "href_from_root": f"./{tag}/{game_dir.name}/index.html",
                "href_from_tag": f"./{game_dir.name}/index.html",
                "imported_from": list(meta.get("imported_from") or []),
            }
            out.append(entry)
    return out


def _catalog_page_html(*, entries: List[Dict[str, Any]], page_title: str, page_subtitle: str, page_kind: str) -> str:
    def entry_href(entry: Dict[str, Any]) -> str:
        if page_kind == "root":
            return str(entry.get("href_from_root") or "#")
        if page_kind == "tag":
            return str(entry.get("href_from_tag") or "#")
        if page_kind == "categories_root":
            return str(entry.get("href_from_category") or "#")
        return str(entry.get("href_from_category") or "#")

    cards = []
    for entry in entries:
        thumb = str(entry.get("thumbnail") or "").strip()
        thumb_html = f'<img class="catalog-card__thumb" src="{html.escape(thumb)}" alt="" />' if thumb else '<div class="catalog-card__thumb catalog-card__thumb--placeholder">SkyEd</div>'
        imported = list(entry.get("imported_from") or [])
        imported_chip = f'<span class="catalog-chip">Imported family</span>' if imported else ''
        cards.append(
            "<a class=\"catalog-card\" href=\"{href}\">{thumb}<span class=\"catalog-card__body\"><span class=\"catalog-card__top\"><span class=\"catalog-chip\">{renderer}</span><span class=\"catalog-chip\">{category}</span>{imported}</span><strong class=\"catalog-card__title\">{title}</strong><span class=\"catalog-card__meta\">{tag} · {count} items</span><span class=\"catalog-card__desc\">{desc}</span></span></a>".format(
                href=html.escape(entry_href(entry)),
                thumb=thumb_html,
                renderer=html.escape(str(entry.get("renderer_label") or GAME_LABELS.get(str(entry.get("renderer") or ""), str(entry.get("renderer") or "tag_s").replace("_", " ").title()))),
                category=html.escape(str(entry.get("category_title") or "General")),
                imported=imported_chip,
                title=html.escape(str(entry.get("title") or "tag_s")),
                tag=html.escape(str(entry.get("tag") or "general")),
                count=int(entry.get("item_count") or 0),
                desc=html.escape(str(entry.get("description") or "Reusable tag_s game pack.")),
            )
        )
    cards_html = "\n".join(cards) or '<div class="catalog-empty">No tag_s packs yet.</div>'
    home_href = './index.html' if page_kind == 'root' else '../index.html' if page_kind == 'tag' else '../../index.html'
    cat_href = './categories/index.html' if page_kind == 'root' else '../../index.html' if page_kind == 'category' else '../index.html' if page_kind == 'categories_root' else '../../categories/index.html'
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>{html.escape(page_title)}</title>
  <style>{_catalog_css()}</style>
</head>
<body>
  <main class=\"catalog-shell\">
    <section class=\"catalog-hero\">
      <div class=\"catalog-hero__badge\">Sky Education · tag_s</div>
      <h1>{html.escape(page_title)}</h1>
      <p>{html.escape(page_subtitle)}</p>
      <div class=\"catalog-hero__nav\">
        <a href=\"{home_href}\">All games</a>
        <a href=\"{cat_href}\">Categories</a>
      </div>
    </section>
    <section class=\"catalog-grid\">{cards_html}</section>
  </main>
</body>
</html>
"""


def _materialize_item_image(
    *,
    en: str,
    zh: str,
    pos: str,
    out_path: Path,
    library_root: Path,
    source_dir: Optional[Path],
    source_value: str,
    style: str,
    use_local_assets: bool,
) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_paths: List[Path] = []
    if source_value:
        source_candidate = Path(source_value)
        if not source_candidate.is_absolute() and source_dir is not None:
            source_candidate = (source_dir / source_value).resolve()
        if source_candidate.exists() and source_candidate.is_file():
            candidate_paths.append(source_candidate)
    if use_local_assets:
        try:
            record = find_best_asset(library_root, target=en, pos=pos, theme="fun_mission", usage="tag_s")
            if record is not None:
                copy_record_image(library_root, record, out_path)
                return True
        except Exception:
            pass
        loose = find_loose_file_asset(library_root, target=en)
        if loose is not None and loose.exists():
            candidate_paths.append(loose)
    for candidate in candidate_paths:
        try:
            img = Image.open(candidate).convert("RGB")
            img.save(out_path, format="PNG", optimize=True, compress_level=9)
            return True
        except Exception:
            continue
    _render_placeholder_card(word=en, zh=zh, pos=pos, out_path=out_path, style=style)
    return False


def _render_placeholder_card(*, word: str, zh: str, pos: str, out_path: Path, style: str) -> None:
    W, H = 960, 720
    theme = {
        "sky_soft": {"bg1": (239, 247, 255), "bg2": (255, 255, 255), "accent": (255, 122, 0), "ink": (20, 58, 98), "line": (183, 214, 244)},
        "clean_light": {"bg1": (245, 248, 252), "bg2": (255, 255, 255), "accent": (0, 123, 255), "ink": (22, 50, 74), "line": (212, 226, 240)},
        "white_minimal": {"bg1": (255, 255, 255), "bg2": (250, 250, 250), "accent": (252, 123, 19), "ink": (21, 43, 64), "line": (228, 234, 241)},
        "bright_play": {"bg1": (236, 247, 255), "bg2": (250, 255, 247), "accent": (255, 137, 45), "ink": (14, 51, 92), "line": (172, 219, 255)},
    }.get(style or "sky_soft")

    img = Image.new("RGB", (W, H), theme["bg1"])
    draw = ImageDraw.Draw(img)
    header = Image.new("RGBA", (W, 200), theme["bg1"] + (0,))
    hd = ImageDraw.Draw(header)
    hd.rounded_rectangle((24, 18, W - 24, 172), radius=44, fill=(0, 123, 255, 255))
    hd.ellipse((W - 240, 88, W + 20, 240), fill=(255, 255, 255, 72))
    hd.ellipse((-80, 110, 260, 260), fill=(255, 255, 255, 84))
    header = header.filter(ImageFilter.GaussianBlur(0.2))
    img.paste(header, (0, 0), header)
    draw.rounded_rectangle((32, 120, W - 32, H - 36), radius=42, fill=theme["bg2"], outline=theme["line"], width=3)
    draw.rounded_rectangle((W - 156, 44, W - 62, 118), radius=20, fill=(255, 255, 255), outline=theme["line"], width=2)
    draw.ellipse((W - 132, 56, W - 92, 96), fill=(255, 198, 92), outline=(255, 168, 0), width=2)
    draw.line((W - 112, 46, W - 112, 36), fill=(255, 168, 0), width=3)
    draw.line((W - 112, 116, W - 112, 126), fill=(255, 168, 0), width=3)
    draw.line((W - 142, 76, W - 152, 76), fill=(255, 168, 0), width=3)
    draw.line((W - 82, 76, W - 72, 76), fill=(255, 168, 0), width=3)
    draw.rounded_rectangle((W // 2 - 72, 245, W // 2 + 72, 259), radius=8, fill=theme["accent"])

    font_word = _fit_font(word or "word", target_width=520, target_height=160, max_size=170)
    font_sub = _fit_font(zh or pos or "Sky Education", target_width=440, target_height=74, max_size=70)
    font_chip = _fit_font((pos or "word").replace("_", " ").title(), target_width=180, target_height=34, max_size=32)

    _draw_center_text(draw, word or "word", font_word, (W // 2, 408), theme["ink"], shadow=(235, 242, 249))
    sub_text = zh or (pos or "word").replace("_", " ").title()
    _draw_center_text(draw, sub_text, font_sub, (W // 2, 520), (73, 98, 121), shadow=None)
    chip_text = (pos or "word").replace("_", " ").title()
    chip_bbox = draw.textbbox((0, 0), chip_text, font=font_chip)
    chip_w = chip_bbox[2] - chip_bbox[0] + 42
    chip_h = chip_bbox[3] - chip_bbox[1] + 18
    chip_x = (W - chip_w) // 2
    chip_y = 578
    draw.rounded_rectangle((chip_x, chip_y, chip_x + chip_w, chip_y + chip_h), radius=18, fill=(244, 248, 252), outline=theme["line"], width=2)
    _draw_center_text(draw, chip_text, font_chip, (W // 2, chip_y + chip_h // 2), (84, 101, 120), shadow=None)
    img.save(out_path, format="PNG", optimize=True, compress_level=9)


def _fit_font(text: str, *, target_width: int, target_height: int, max_size: int) -> ImageFont.ImageFont:
    for size in range(max_size, 20, -4):
        font = _load_font(size)
        dummy = Image.new("RGB", (10, 10))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), text or "word", font=font)
        if (bbox[2] - bbox[0]) <= target_width and (bbox[3] - bbox[1]) <= target_height:
            return font
    return _load_font(24)


def _load_font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans-Bold.ttf", "Arial.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_center_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, center: tuple[int, int], fill: tuple[int, int, int], shadow: Optional[tuple[int, int, int]] = None) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    x = int(center[0] - (bbox[2] - bbox[0]) / 2)
    y = int(center[1] - (bbox[3] - bbox[1]) / 2)
    if shadow is not None:
        draw.text((x + 4, y + 4), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)


def _skill_for_game_type(game_type: str) -> str:
    return {
        "touch_listen_cards": "listening",
        "matching_pairs": "matching",
        "memory_pairs": "memory",
        "concentration": "memory",
        "image_cards": "study",
        "listen_click_choice": "listening_choice",
        "slow_click": "listening_choice",
        "speed_balls": "speed_choice",
        "bubbles_english": "speed_choice",
        "fast_english": "speed_choice",
        "falling_english": "speed_choice",
        "reveal_guess": "guessing",
        "desert_drag": "drag_matching",
        "phrase_maker": "sentence_building",
        "fast_phrases": "sentence_building",
        "describer": "reading_choice",
        "animal_mystery": "clue_guessing",
        "spelling_bee": "spelling",
        "hangman": "spelling",
    }.get(game_type, "practice")


def article_for(word: str) -> str:
    return "an" if str(word or "").strip().lower()[:1] in {"a", "e", "i", "o", "u"} else "a"


def _runtime_html(payload: Dict[str, Any]) -> str:
    data_json = json.dumps(payload, ensure_ascii=False, indent=2).replace("</", "<\\/")
    title = html.escape(str(((payload.get("meta") or {}).get("title") or "tag_s")))
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>{title}</title>
  <link rel=\"stylesheet\" href=\"./styles.css\" />
</head>
<body>
  <div id=\"app\"><div class=\"boot\">Loading tag_s…</div></div>
  <script id=\"game-data\" type=\"application/json\">{data_json}</script>
  <script src=\"./runtime.js\"></script>
</body>
</html>
"""


def _catalog_css() -> str:
    return """
:root{--bg:#edf4fb;--card:#ffffff;--ink:#16324a;--muted:#63809b;--line:#d8e5f3;--blue:#007bff;--orange:#fc7b13;}
*{box-sizing:border-box}body{margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;background:linear-gradient(180deg,#eef5fc 0%,#f9fbfe 100%);color:var(--ink)}
.catalog-shell{max-width:1180px;margin:0 auto;padding:24px 16px 48px}.catalog-hero{background:linear-gradient(135deg,#007bff 0%,#4ba3ff 56%,#fc7b13 100%);border-radius:28px;padding:24px;color:#fff;box-shadow:0 20px 50px rgba(17,68,123,.18)}
.catalog-hero h1{margin:8px 0 10px;font-size:clamp(1.6rem,4vw,2.4rem)}.catalog-hero p{margin:0;max-width:760px;line-height:1.6;color:rgba(255,255,255,.92)}.catalog-hero__badge{display:inline-flex;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.28);padding:8px 12px;border-radius:999px;font-weight:800;font-size:.88rem}.catalog-hero__nav{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}.catalog-hero__nav a{color:#fff;text-decoration:none;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.28);padding:10px 14px;border-radius:14px;font-weight:700}
.catalog-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px;margin-top:18px}.catalog-card{text-decoration:none;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:22px;overflow:hidden;box-shadow:0 18px 40px rgba(19,54,91,.08);display:flex;flex-direction:column;min-height:280px}.catalog-card:hover{transform:translateY(-2px);box-shadow:0 22px 46px rgba(19,54,91,.14)}
.catalog-card__thumb{width:100%;height:160px;object-fit:cover;background:#fff;display:block}.catalog-card__thumb--placeholder{display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#dff0ff,#ffffff 60%,#fff2e7);color:#2b5b86;font-weight:900;font-size:1.3rem}.catalog-card__body{padding:14px;display:flex;flex-direction:column;gap:10px}.catalog-card__top{display:flex;gap:8px;flex-wrap:wrap}.catalog-chip{display:inline-flex;padding:6px 10px;border-radius:999px;background:#f3f8fe;border:1px solid var(--line);color:var(--muted);font-weight:800;font-size:.77rem}.catalog-card__title{font-size:1.05rem;line-height:1.35}.catalog-card__meta{color:var(--muted);font-size:.9rem}.catalog-card__desc{color:#35516a;line-height:1.5;font-size:.92rem}.catalog-empty{padding:26px;border-radius:20px;background:#fff;border:1px dashed var(--line);color:var(--muted);text-align:center}
"""


def _runtime_css() -> str:
    return """
:root{--bg:#eef5fc;--shell:#ffffff;--ink:#16324a;--muted:#68809b;--line:#d9e7f5;--blue:#007bff;--blue-soft:#e8f3ff;--orange:#fc7b13;--green:#22c55e;--red:#ef4444;--shadow:0 20px 48px rgba(15,52,88,.12)}
*{box-sizing:border-box}body{margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;background:radial-gradient(circle at top right,#fff2e9 0%,rgba(255,242,233,0) 28%),linear-gradient(180deg,#eef5fc 0%,#f9fbfe 100%);color:var(--ink)}body[data-style='white_minimal']{background:#f8fafc}body[data-style='bright_play']{background:radial-gradient(circle at top left,#dbf2ff 0%,rgba(219,242,255,0) 30%),radial-gradient(circle at bottom right,#fff1e5 0%,rgba(255,241,229,0) 28%),linear-gradient(180deg,#eef7ff 0%,#fdfefe 100%)}
#app{min-height:100vh}.boot{padding:24px;color:var(--muted)}
.page{max-width:1180px;margin:0 auto;padding:20px 14px 44px}.hero{position:relative;overflow:hidden;border-radius:28px;padding:24px;background:linear-gradient(135deg,#007bff 0%,#57a8ff 54%,#fc7b13 100%);color:#fff;box-shadow:var(--shadow)}.hero:before{content:'';position:absolute;inset:auto -8% -45% auto;width:320px;height:320px;border-radius:50%;background:rgba(255,255,255,.16)}.hero:after{content:'';position:absolute;left:-60px;bottom:-90px;width:260px;height:260px;border-radius:50%;background:rgba(255,255,255,.10)}.hero__eyebrow{position:relative;display:inline-flex;gap:8px;align-items:center;padding:8px 12px;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.24);border-radius:999px;font-weight:800;font-size:.82rem}.hero h1{position:relative;margin:12px 0 10px;font-size:clamp(1.65rem,4vw,2.55rem);line-height:1.12}.hero p{position:relative;margin:0;max-width:760px;color:rgba(255,255,255,.92);line-height:1.62}.chips,.bar,.actions{display:flex;gap:10px;flex-wrap:wrap}.chips{margin-top:16px}.chip,.pill{display:inline-flex;align-items:center;gap:6px;padding:8px 12px;border-radius:999px;font-size:.84rem;font-weight:800}.chip{background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.28)}.panel{margin-top:18px;background:var(--shell);border:1px solid var(--line);border-radius:26px;padding:18px;box-shadow:var(--shadow)}.bar{margin-bottom:14px}.pill{background:#f3f8fe;border:1px solid var(--line);color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}.btn,.mini-audio{appearance:none;border:1px solid var(--line);background:#fff;color:var(--ink);padding:11px 14px;border-radius:14px;font-weight:800;cursor:pointer;box-shadow:0 8px 18px rgba(15,52,88,.06)}.btn:hover,.mini-audio:hover{border-color:#97c6ff}.btn--primary{background:linear-gradient(135deg,#007bff,#49a2ff);border-color:#007bff;color:#fff}.btn--ghost{background:#f8fbff}.btn--danger{background:#fff5f5;border-color:#ffd2d2;color:#b42318}.btn[disabled]{opacity:.55;cursor:not-allowed}
.choice-card,.memory-card,.pair-tile,.touch-card,.candidate-card,.bubble-choice{position:relative;background:#fff;border:1px solid var(--line);border-radius:22px;overflow:hidden;box-shadow:0 12px 26px rgba(15,52,88,.08)}.choice-card img,.touch-card img,.memory-card__front img,.image-main img,.candidate-card img{display:block;width:100%;height:170px;object-fit:contain;background:#fff}.choice-card__body,.touch-card__body,.candidate-card__body{padding:12px 14px;display:flex;justify-content:space-between;align-items:center;gap:8px}.choice-card__title,.touch-card__title,.candidate-card__title{font-weight:900;font-size:1.02rem}.choice-card__meta,.touch-card__meta,.candidate-card__meta{color:var(--muted);font-size:.88rem}
.choice-card.is-ok,.pair-tile.is-ok,.memory-card.is-ok,.candidate-card.is-ok,.bubble-choice.is-ok{outline:3px solid rgba(34,197,94,.55)}.choice-card.is-bad,.pair-tile.is-bad,.memory-card.is-bad,.candidate-card.is-bad,.bubble-choice.is-bad{outline:3px solid rgba(239,68,68,.48)}
.pair-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}.pair-tile{min-height:92px;padding:14px;display:flex;align-items:center;justify-content:center;text-align:center;font-weight:900;font-size:1.03rem;cursor:pointer}.pair-tile__audio{position:absolute;right:10px;top:10px}.pair-tile__media{display:flex;flex-direction:column;align-items:center;gap:8px}.pair-tile__media img{width:100%;max-height:118px;object-fit:contain;background:#fff;border-radius:14px}
.memory-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.memory-card{aspect-ratio:4/5;transform-style:preserve-3d;cursor:pointer;position:relative;transition:transform .24s ease}.memory-card.is-flipped{transform:rotateY(180deg)}.memory-card__face{position:absolute;inset:0;backface-visibility:hidden;border-radius:22px;overflow:hidden}.memory-card__back{transform:rotateY(180deg);display:flex;flex-direction:column;justify-content:center;align-items:center;padding:14px;background:linear-gradient(180deg,#ffffff,#f5faff)}.memory-card__back strong{font-size:1.1rem}.memory-card__back span{color:var(--muted);margin-top:8px;text-align:center}.memory-card__cover{width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:linear-gradient(180deg,#eaf4ff,#ffffff 62%,#fff4ea)}.memory-card__cover-badge{width:86px;height:86px;border-radius:28px;background:#fff;border:1px solid var(--line);display:flex;align-items:center;justify-content:center;font-weight:900;color:#2d5d89;box-shadow:0 14px 26px rgba(19,54,91,.10)}
.flash-wrap{display:grid;grid-template-columns:minmax(280px,500px) minmax(220px,1fr);gap:18px;align-items:start}.image-main{background:#fff;border:1px solid var(--line);border-radius:28px;overflow:hidden;box-shadow:var(--shadow)}.image-main img{height:440px}.image-main__body{padding:18px}.image-main__word{font-size:2rem;font-weight:900}.image-main__text{color:var(--muted);margin-top:8px;line-height:1.55}.study-side{display:flex;flex-direction:column;gap:12px}.study-side .btn{width:100%}
.touch-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}.touch-card{cursor:pointer}.touch-card__media{padding:12px 12px 0}.touch-card__media img{height:180px;border-radius:18px;border:1px solid #edf4fb}.touch-card.is-active{outline:4px solid rgba(0,123,255,.16)}
.prompt-box,.reveal-box,.score-box,.phrase-box,.mystery-box,.drag-box{background:linear-gradient(180deg,#f7fbff,#ffffff);border:1px solid var(--line);border-radius:22px;padding:16px;margin-bottom:14px}.prompt-title{font-size:1.28rem;font-weight:900}.prompt-sub{color:var(--muted);margin-top:6px;line-height:1.55}
.reveal-stage{position:relative;background:#fff;border:1px solid var(--line);border-radius:24px;overflow:hidden;box-shadow:var(--shadow)}.reveal-stage img{display:block;width:100%;height:min(48vh,420px);object-fit:contain;background:#fff}.reveal-mask{position:absolute;inset:0;background:linear-gradient(135deg,rgba(7,123,255,.86),rgba(252,123,19,.84));mix-blend-mode:multiply;transition:clip-path .22s ease}.reveal-mask[data-step='0']{clip-path:inset(0 0 0 0)}.reveal-mask[data-step='1']{clip-path:inset(0 50% 0 0)}.reveal-mask[data-step='2']{clip-path:inset(0 25% 0 0)}.reveal-mask[data-step='3']{clip-path:inset(0 10% 0 0)}.reveal-mask[data-step='4']{clip-path:inset(0 0 0 0);opacity:0}
.bubble-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:18px}.bubble-choice{border-radius:999px;padding:16px;min-height:160px;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;background:radial-gradient(circle at top,#ffffff 0%,#eef7ff 72%)}.bubble-choice img{width:88px;height:88px;object-fit:contain;margin-bottom:10px}.bubble-choice strong{font-size:1rem;text-align:center}.bubble-choice span{color:var(--muted);margin-top:6px;text-align:center;font-size:.86rem}
.arcade-stage{position:relative;min-height:260px;border:1px dashed var(--line);border-radius:24px;padding:16px;background:linear-gradient(180deg,#ffffff,#f6fbff)}.falling-stage{position:relative;min-height:320px;overflow:hidden}.falling-token{position:absolute;display:flex;align-items:center;justify-content:center;min-width:120px;min-height:58px;padding:10px 14px;border-radius:999px;background:#fff;border:1px solid var(--line);box-shadow:0 10px 18px rgba(15,52,88,.08);font-weight:900;cursor:pointer;animation:fallToken linear infinite}.falling-token img{width:44px;height:44px;object-fit:contain;margin-right:8px}.slow-grid .choice-card img{height:200px}.slow-grid .choice-card__title{font-size:1.12rem}
.phrase-stage{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(260px,.8fr);gap:16px}.token-bank,.answer-strip{display:flex;gap:10px;flex-wrap:wrap;padding:14px;border-radius:18px;background:#fff;border:1px solid var(--line);min-height:74px}.token-btn{appearance:none;border:1px solid var(--line);background:#fff;padding:10px 14px;border-radius:14px;font-weight:800;cursor:pointer}.token-btn.is-used{opacity:.35;pointer-events:none}.answer-strip{background:#f8fbff}.phrase-note{color:var(--muted);line-height:1.55}
.drag-board{display:grid;grid-template-columns:1fr;gap:16px}.drag-label-bank{display:flex;gap:10px;flex-wrap:wrap}.drag-label{padding:10px 14px;border-radius:14px;background:#fff;border:1px solid var(--line);font-weight:800;cursor:grab;user-select:none}.drag-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}.drag-target{background:#fff;border:1px solid var(--line);border-radius:22px;overflow:hidden}.drag-target img{width:100%;height:150px;object-fit:contain;background:#fff}.drag-target__slot{min-height:58px;display:flex;align-items:center;justify-content:center;padding:10px;border-top:1px dashed var(--line);font-weight:900;color:var(--muted)}.drag-target__slot.is-over{background:#eef7ff}.drag-target__slot.is-ok{background:#ecfdf3;color:#166534}.drag-target__slot.is-bad{background:#fff5f5;color:#b42318}
.mystery-grid{display:grid;grid-template-columns:minmax(0,.85fr) minmax(280px,1.15fr);gap:18px}.clue-list{display:flex;flex-direction:column;gap:10px}.clue-card{padding:12px 14px;border-radius:16px;background:#fff;border:1px solid var(--line)}.candidate-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.candidate-card{cursor:pointer}.candidate-card__media{padding:12px 12px 0}.candidate-card__media img{height:120px;border-radius:16px;border:1px solid #edf4fb}.candidate-card__body{padding:10px 12px 14px}.hidden-clue{filter:blur(8px);user-select:none}
.letter-bank{display:flex;gap:10px;flex-wrap:wrap}.letter-btn{appearance:none;border:1px solid var(--line);background:#fff;padding:10px 14px;border-radius:14px;font-weight:900;cursor:pointer;min-width:48px}.letter-btn.is-used{opacity:.35;pointer-events:none}.spelling-answer,.hangman-word{display:flex;gap:8px;flex-wrap:wrap;min-height:62px;padding:12px;border-radius:18px;background:#fff;border:1px solid var(--line)}.spelling-slot,.hangman-slot{min-width:44px;height:44px;border-radius:12px;border:1px dashed #bfd7f0;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:1.05rem;background:#f8fbff}.hangman-letters{display:grid;grid-template-columns:repeat(auto-fit,minmax(44px,1fr));gap:8px}.hangman-letters .letter-btn{padding:10px 0}.miss-pill{background:#fff5f5;border-color:#ffd7d7;color:#b42318}.ok-note{color:#166534;font-weight:800}.bad-note{color:#b42318;font-weight:800}.footer-note{margin-top:14px;color:var(--muted);font-size:.92rem;line-height:1.55}
@keyframes fallToken{0%{transform:translateY(-80px)}100%{transform:translateY(360px)}}
@media (max-width:900px){.phrase-stage,.mystery-grid{grid-template-columns:1fr}.flash-wrap{grid-template-columns:1fr}.image-main img{height:340px}}@media (max-width:680px){.page{padding:14px 10px 34px}.hero{padding:18px;border-radius:22px}.panel{padding:14px;border-radius:22px}.grid,.pair-grid,.memory-grid,.touch-grid,.candidate-grid,.drag-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.bubble-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media (max-width:520px){.grid,.pair-grid,.memory-grid,.touch-grid,.candidate-grid,.drag-grid,.bubble-grid{grid-template-columns:1fr}.choice-card img,.touch-card img{height:190px}}
"""


def _runtime_js() -> str:
    return r"""
(function(){
  const root = document.getElementById('app');
  const embedded = document.getElementById('game-data');
  let game = {meta:{},items:[]};
  try {
    if (embedded && embedded.textContent.trim()) {
      game = JSON.parse(embedded.textContent);
    }
  } catch (err) {
    root.innerHTML = `<div class="page"><div class="panel">Could not load game data. ${escapeHtml(String(err))}</div></div>`;
    return;
  }
  const meta = game.meta || {};
  const items = Array.isArray(game.items) ? game.items : [];
  const sentences = Array.isArray(game.sentences) ? game.sentences : [];
  const settings = meta.settings || {};
  document.body.dataset.style = String(meta.style || 'sky_soft');
  const renderer = String(meta.renderer || 'touch_listen_cards');
  const needsItems = !['phrase_maker','fast_phrases'].includes(renderer);
  if (needsItems && !items.length) {
    root.innerHTML = `<div class="page"><div class="panel">No items available in this tag_s pack.</div></div>`;
    return;
  }
  if (renderer === 'touch_listen_cards') return renderTouchListen();
  if (renderer === 'matching_pairs') return renderMatchingPairs();
  if (renderer === 'memory_pairs' || renderer === 'concentration') return renderMemoryPairs(renderer);
  if (renderer === 'image_cards') return renderImageCards();
  if (renderer === 'listen_click_choice' || renderer === 'slow_click' || renderer === 'speed_balls' || renderer === 'bubbles_english' || renderer === 'fast_english' || renderer === 'falling_english') return renderChoiceArcade(renderer);
  if (renderer === 'reveal_guess') return renderRevealGuess();
  if (renderer === 'desert_drag') return renderDesertDrag();
  if (renderer === 'phrase_maker' || renderer === 'fast_phrases') return renderPhraseMaker(renderer);
  if (renderer === 'describer') return renderDescriber();
  if (renderer === 'animal_mystery') return renderAnimalMystery();
  if (renderer === 'spelling_bee') return renderSpellingBee();
  if (renderer === 'hangman') return renderHangman();
  root.innerHTML = `<div class="page"><div class="panel">Unknown renderer: ${escapeHtml(renderer)}</div></div>`;

  function shell(inner, pills){
    const chips = [
      chip(meta.category_title || meta.category || 'General'),
      chip(rendererLabel(renderer)),
      chip(`${items.length || (sentences.length || 0)} items`),
    ].concat(Array.isArray(pills) ? pills : []).join('');
    return `
      <main class="page">
        <section class="hero">
          <div class="hero__eyebrow">Sky Education · tag_s</div>
          <h1>${escapeHtml(meta.title || 'tag_s')}</h1>
          <p>${escapeHtml(meta.description || 'Reusable themed practice pack.')}</p>
          <div class="chips">${chips}</div>
        </section>
        <section class="panel">${inner}</section>
      </main>
    `;
  }

  function rendererLabel(value){
    const map = {
      touch_listen_cards:'Touch and Listen',
      matching_pairs:'Matching Pairs',
      memory_pairs:'Memory Pairs',
      concentration:'Concentration',
      image_cards:'Image Cards',
      listen_click_choice:'Listen and Choose',
      slow_click:'Slow Click',
      speed_balls:'Speed Balls',
      bubbles_english:'Bubbles English',
      fast_english:'Fast English',
      falling_english:'Falling English',
      reveal_guess:'Reveal and Guess',
      desert_drag:'Desert Drag',
      phrase_maker:'Phrase Maker',
      fast_phrases:'Fast Phrases',
      describer:'Describer',
      animal_mystery:'Animal Mystery',
      spelling_bee:'Spelling Bee',
      hangman:'Hangman',
    };
    return map[value] || value.replaceAll('_',' ');
  }

  function chip(text){ return `<span class="chip">${escapeHtml(String(text || ''))}</span>`; }
  function sleep(ms){ return new Promise(resolve => setTimeout(resolve, ms)); }
  const byId = new Map(items.map(item => [String(item.id || ''), item]));
  const audioCache = new Map();
  function playAudio(src){
    if(!src) return;
    let audio = audioCache.get(src);
    if(!audio){ audio = new Audio(src); audioCache.set(src, audio); }
    try{ audio.currentTime = 0; audio.play(); }catch(err){}
  }
  function shuffled(source){
    const arr = source.slice();
    for(let i=arr.length-1;i>0;i--){ const j=Math.floor(Math.random()*(i+1)); [arr[i],arr[j]]=[arr[j],arr[i]]; }
    return arr;
  }
  function uniqueChoices(correctIndex, count){
    const ids = new Set([correctIndex]);
    while(ids.size < Math.min(count, items.length)){ ids.add(Math.floor(Math.random() * items.length)); }
    return shuffled(Array.from(ids)).map(idx => ({ idx, item: items[idx] }));
  }
  function choiceIdsFromRound(round){ return (Array.isArray(round.choice_ids) ? round.choice_ids : []).map(id => byId.get(String(id))).filter(Boolean); }
  function escapeAttr(text){ return escapeHtml(text).replaceAll('"','&quot;'); }
  function escapeHtml(text){ return String(text || '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }

  function renderTouchListen(){
    root.innerHTML = shell(`
      <div class="bar"><span class="pill">Tap a card to play audio</span></div>
      <div class="touch-grid">${items.map((item, idx) => `
        <button class="touch-card" type="button" data-idx="${idx}">
          <div class="touch-card__media"><img src="${escapeAttr(item.image || '')}" alt="${escapeAttr(item.label || '')}" /></div>
          <div class="touch-card__body"><div><div class="touch-card__title">${escapeHtml(item.label || 'Word')}</div><div class="touch-card__meta">${escapeHtml(item.text || item.block_type || '')}</div></div><span class="chip">▶</span></div>
        </button>
      `).join('')}</div>
      <div class="footer-note">Local preview works directly from the generated index.html file. No local server is needed.</div>
    `);
    root.querySelectorAll('.touch-card').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = Number(btn.dataset.idx || 0);
        playAudio(String((items[idx] || {}).audio || ''));
        btn.classList.remove('is-active'); void btn.offsetWidth; btn.classList.add('is-active');
      });
    });
  }

  function renderMatchingPairs(){
    const deck = [];
    items.forEach((item, idx) => {
      deck.push({pairId:`p-${idx}`, kind:'en', text:item.label || 'Word', audio:item.audio || '', image:item.image || ''});
      deck.push({pairId:`p-${idx}`, kind:'zh', text:item.text || item.label || 'Text', audio:item.audio || '', image:''});
    });
    const tiles = shuffled(deck); let first = null; let lock = false; let hits = 0; let moves = 0;
    root.innerHTML = shell(`<div class="bar"><span class="pill" id="moves">Moves: 0</span><span class="pill" id="hits">Hits: 0/${items.length}</span></div><div class="pair-grid" id="pairGrid"></div>`);
    const grid = root.querySelector('#pairGrid'); const movesEl = root.querySelector('#moves'); const hitsEl = root.querySelector('#hits');
    tiles.forEach(tile => {
      const btn = document.createElement('button'); btn.type='button'; btn.className='pair-tile'; btn.dataset.pairId=tile.pairId;
      btn.innerHTML = tile.image && tile.kind === 'en' ? `<div class="pair-tile__media"><img src="${escapeAttr(tile.image)}" alt="${escapeAttr(tile.text)}" /><strong>${escapeHtml(tile.text)}</strong></div><button type="button" class="mini-audio pair-tile__audio">▶</button>` : `<div>${escapeHtml(tile.text)}</div><button type="button" class="mini-audio pair-tile__audio">▶</button>`;
      btn.addEventListener('click', (ev) => {
        if (ev.target.closest('.pair-tile__audio')) { playAudio(tile.audio); return; }
        if(lock || btn.classList.contains('is-ok')) return;
        if(tile.audio) playAudio(tile.audio);
        if(!first){ first = btn; btn.classList.add('is-ok'); return; }
        if(btn === first) return;
        moves += 1; movesEl.textContent = `Moves: ${moves}`;
        const same = first.dataset.pairId && first.dataset.pairId === btn.dataset.pairId;
        if(same){ btn.classList.add('is-ok'); hits += 1; hitsEl.textContent = `Hits: ${hits}/${items.length}`; first = null; return; }
        lock = true; btn.classList.add('is-bad'); first.classList.add('is-bad');
        setTimeout(() => { btn.classList.remove('is-bad'); first.classList.remove('is-bad'); first.classList.remove('is-ok'); first = null; lock = false; }, 620);
      });
      grid.appendChild(btn);
    });
  }

  function renderMemoryPairs(mode){
    const deck = [];
    items.forEach((item, idx) => { deck.push({pairId:`m-${idx}`, face:'image', title:item.label || 'Word', sub:item.text || '', image:item.image || '', audio:item.audio || ''}); deck.push({pairId:`m-${idx}`, face:'text', title:item.label || 'Word', sub:item.text || '', image:'', audio:item.audio || ''}); });
    const cards = shuffled(deck); let first = null; let lock = false; let hits = 0; let moves = 0;
    root.innerHTML = shell(`<div class="bar"><span class="pill" id="moves">Moves: 0</span><span class="pill" id="hits">Hits: 0/${items.length}</span><span class="pill">${escapeHtml(rendererLabel(mode))}</span></div><div class="memory-grid" id="memoryGrid"></div>`);
    const grid = root.querySelector('#memoryGrid'); const movesEl = root.querySelector('#moves'); const hitsEl = root.querySelector('#hits');
    cards.forEach(card => {
      const btn = document.createElement('button'); btn.type='button'; btn.className='memory-card'; btn.dataset.pairId=card.pairId;
      btn.innerHTML = `<div class="memory-card__face memory-card__cover"><div class="memory-card__cover-badge">${mode === 'concentration' ? 'Focus' : 'Sky'}</div></div><div class="memory-card__face memory-card__back">${card.face === 'image' ? `<img src="${escapeAttr(card.image)}" alt="${escapeAttr(card.title)}" style="width:100%;height:56%;object-fit:contain;background:#fff;border-radius:16px;border:1px solid #edf4fb;" />` : `<strong>${escapeHtml(card.title)}</strong><span>${escapeHtml(card.sub || 'Tap to check')}</span>`}</div>`;
      btn.addEventListener('click', () => {
        if(lock || btn.classList.contains('is-ok') || btn.classList.contains('is-flipped')) return;
        if(card.audio) playAudio(card.audio);
        btn.classList.add('is-flipped');
        if(!first){ first = btn; return; }
        if(btn === first) return;
        moves += 1; movesEl.textContent = `Moves: ${moves}`;
        const same = first.dataset.pairId === btn.dataset.pairId;
        if(same){ first.classList.add('is-ok'); btn.classList.add('is-ok'); first = null; hits += 1; hitsEl.textContent = `Hits: ${hits}/${items.length}`; return; }
        lock = true;
        setTimeout(() => { btn.classList.remove('is-flipped'); first.classList.remove('is-flipped'); first = null; lock = false; }, 760);
      });
      grid.appendChild(btn);
    });
  }

  function renderImageCards(){
    let current = 0;
    root.innerHTML = shell(`<div class="bar"><span class="pill" id="counter"></span><span class="pill" id="posChip"></span></div><div class="flash-wrap"><div class="image-main"><img id="mainImg" alt="flashcard image" /><div class="image-main__body"><div class="image-main__word" id="wordText"></div><div class="image-main__text" id="subText"></div></div></div><div class="study-side"><button type="button" class="btn btn--primary" id="playBtn">Play audio</button><button type="button" class="btn" id="prevBtn">Previous</button><button type="button" class="btn" id="nextBtn">Next</button><div class="prompt-box"><div class="prompt-title">Study note</div><div class="prompt-sub">Use this mode as a calm review deck. It works well for self-study, warm-up, or parent-child revision.</div></div></div></div>`);
    const counter = root.querySelector('#counter'); const posChip = root.querySelector('#posChip'); const mainImg = root.querySelector('#mainImg'); const wordText = root.querySelector('#wordText'); const subText = root.querySelector('#subText'); const playBtn = root.querySelector('#playBtn');
    root.querySelector('#prevBtn').addEventListener('click', () => { if(current > 0){ current -= 1; render(); } });
    root.querySelector('#nextBtn').addEventListener('click', () => { if(current < items.length - 1){ current += 1; render(); } });
    playBtn.addEventListener('click', () => playAudio(String((items[current] || {}).audio || '')));
    function render(){ const item = items[current] || {}; counter.textContent = `Card ${current+1} / ${items.length}`; posChip.textContent = item.block_type || 'word'; mainImg.src = item.image || ''; wordText.textContent = item.label || 'Word'; subText.textContent = item.text || ''; playBtn.disabled = !item.audio; }
    render();
  }

  function renderChoiceArcade(mode){
    let order = shuffled(items.map((_, idx) => idx)); let round = 0; let score = 0; let timer = Number(settings.timer_seconds || (mode === 'slow_click' ? 0 : mode === 'speed_balls' || mode === 'fast_english' ? 45 : 0));
    const useTimer = timer > 0; let timerHandle = null;
    root.innerHTML = shell(`<div class="prompt-box"><div class="prompt-title" id="promptTitle">${escapeHtml(rendererLabel(mode))}</div><div class="prompt-sub" id="promptSub">Use the prompt and choose the correct answer.</div><div class="actions" style="margin-top:12px"><button type="button" class="btn btn--primary" id="playPrompt">Play prompt</button><button type="button" class="btn btn--ghost" id="nextRound">Next round</button><span class="pill" id="scorePill">Score: 0</span>${useTimer ? '<span class="pill" id="timerPill">Time: 0</span>' : ''}</div></div><div id="choiceHost"></div>` , [chip(`${settings.choice_count || 4} choices`), useTimer ? chip(`${timer}s timer`) : '']);
    const playPromptBtn = root.querySelector('#playPrompt'); const nextRoundBtn = root.querySelector('#nextRound'); const scorePill = root.querySelector('#scorePill'); const timerPill = root.querySelector('#timerPill'); const promptTitle = root.querySelector('#promptTitle'); const promptSub = root.querySelector('#promptSub'); const host = root.querySelector('#choiceHost');
    let answerIndex = -1; let currentChoices = [];
    function startTimer(){ if(!useTimer) return; clearInterval(timerHandle); timerPill.textContent = `Time: ${timer}`; timerHandle = setInterval(() => { timer -= 1; timerPill.textContent = `Time: ${Math.max(0,timer)}`; if(timer <= 0){ clearInterval(timerHandle); host.innerHTML = `<div class="score-box"><div class="prompt-title">Time is up</div><div class="prompt-sub">Final score: ${score}</div></div>`; playPromptBtn.disabled = true; nextRoundBtn.disabled = true; } }, 1000); }
    function buildRound(){
      if(round >= Math.min(order.length, Number(settings.round_limit || order.length))){ host.innerHTML = `<div class="score-box"><div class="prompt-title">Finished</div><div class="prompt-sub">Final score: ${score}</div></div>`; playPromptBtn.disabled = true; nextRoundBtn.disabled = true; return; }
      answerIndex = order[round]; const answerItem = items[answerIndex] || {}; currentChoices = uniqueChoices(answerIndex, Number(settings.choice_count || 4));
      promptTitle.textContent = rendererLabel(mode); promptSub.textContent = answerItem.audio ? `Tap Play prompt, then choose the correct card for “${answerItem.label || ''}”.` : `Choose the correct card for “${answerItem.label || ''}”.`;
      host.className = mode === 'bubbles_english' ? 'bubble-grid' : (mode === 'falling_english' ? 'arcade-stage falling-stage' : (mode === 'slow_click' ? 'grid slow-grid' : 'grid'));
      if(mode === 'falling_english'){
        host.innerHTML = currentChoices.map((choice, ix) => `<button type="button" class="falling-token" data-idx="${choice.idx}" style="left:${(ix*23)%70}%;animation-duration:${4.2 + (ix%3)*1.1}s"><img src="${escapeAttr(choice.item.image || '')}" alt="" /><span>${escapeHtml(choice.item.label || '')}</span></button>`).join('');
      } else if(mode === 'bubbles_english'){
        host.innerHTML = currentChoices.map(choice => `<button type="button" class="bubble-choice" data-idx="${choice.idx}"><img src="${escapeAttr(choice.item.image || '')}" alt="${escapeAttr(choice.item.label || '')}" /><strong>${escapeHtml(choice.item.label || '')}</strong><span>${escapeHtml(choice.item.text || '')}</span></button>`).join('');
      } else {
        host.innerHTML = currentChoices.map(choice => `<button type="button" class="choice-card" data-idx="${choice.idx}"><img src="${escapeAttr(choice.item.image || '')}" alt="${escapeAttr(choice.item.label || '')}" /><div class="choice-card__body"><div><div class="choice-card__title">${escapeHtml(choice.item.label || '')}</div><div class="choice-card__meta">${escapeHtml(choice.item.text || '')}</div></div><span class="chip">Pick</span></div></button>`).join('');
      }
      host.querySelectorAll('[data-idx]').forEach(btn => btn.addEventListener('click', async () => {
        const idx = Number(btn.dataset.idx || -1); const ok = idx === answerIndex;
        if(ok){ score += 1; scorePill.textContent = `Score: ${score}`; }
        btn.classList.add(ok ? 'is-ok' : 'is-bad');
        if(!ok){ const correct = host.querySelector(`[data-idx="${answerIndex}"]`); if(correct){ correct.classList.add('is-ok'); } }
        if(mode === 'speed_balls' || mode === 'fast_english' || mode === 'bubbles_english' || mode === 'falling_english'){ await sleep(550); round += 1; buildRound(); }
      }, { once: true }));
      playPromptBtn.disabled = !answerItem.audio;
      if((settings.auto_play !== false) && answerItem.audio){ playAudio(String(answerItem.audio || '')); }
    }
    playPromptBtn.addEventListener('click', () => playAudio(String((items[answerIndex] || {}).audio || '')));
    nextRoundBtn.addEventListener('click', () => { round += 1; buildRound(); });
    startTimer(); buildRound();
  }

  function renderRevealGuess(){
    let order = shuffled(items.map((_, idx) => idx)); let round = 0; let step = 0; let score = 0;
    root.innerHTML = shell(`<div class="prompt-box"><div class="prompt-title" id="revealTitle">Reveal and guess</div><div class="prompt-sub">Reveal more of the picture if needed, then pick the correct answer.</div><div class="actions" style="margin-top:12px"><button type="button" class="btn btn--primary" id="playReveal">Play prompt</button><button type="button" class="btn" id="stepReveal">Reveal more</button><button type="button" class="btn btn--ghost" id="nextReveal">Next round</button><span class="pill" id="revealScore">Score: 0</span></div></div><div class="reveal-stage"><img id="revealImg" alt="reveal image" /><div class="reveal-mask" id="revealMask" data-step="0"></div></div><div class="grid" id="revealChoices" style="margin-top:14px"></div>`);
    const revealImg = root.querySelector('#revealImg'); const revealMask = root.querySelector('#revealMask'); const revealChoices = root.querySelector('#revealChoices'); const revealScore = root.querySelector('#revealScore'); const playReveal = root.querySelector('#playReveal');
    function buildRound(){ if(round >= order.length){ round = 0; order = shuffled(order); } const answerIndex = order[round]; const answer = items[answerIndex] || {}; step = 0; revealImg.src = answer.image || ''; revealMask.dataset.step = String(step); const choices = uniqueChoices(answerIndex, Number(settings.choice_count || 4)); revealChoices.innerHTML = choices.map(choice => `<button type="button" class="choice-card" data-idx="${choice.idx}"><img src="${escapeAttr(choice.item.image || '')}" alt="${escapeAttr(choice.item.label || '')}" /><div class="choice-card__body"><div><div class="choice-card__title">${escapeHtml(choice.item.label || '')}</div><div class="choice-card__meta">${escapeHtml(choice.item.text || '')}</div></div><span class="chip">Pick</span></div></button>`).join(''); revealChoices.querySelectorAll('.choice-card').forEach(btn => btn.addEventListener('click', async () => { const idx = Number(btn.dataset.idx || -1); const ok = idx === answerIndex; if(ok){ score += 1; revealScore.textContent = `Score: ${score}`; } btn.classList.add(ok ? 'is-ok' : 'is-bad'); await sleep(650); round += 1; buildRound(); }, { once:true })); playReveal.disabled = !answer.audio; playReveal.onclick = () => playAudio(String(answer.audio || '')); root.querySelector('#stepReveal').onclick = () => { step = Math.min(step + 1, Number(settings.reveal_steps || 4)); revealMask.dataset.step = String(step); }; root.querySelector('#nextReveal').onclick = () => { round += 1; buildRound(); }; }
    buildRound();
  }

  function renderDesertDrag(){
    const current = items.slice(0, Math.min(items.length, Number(settings.round_limit || items.length)));
    root.innerHTML = shell(`<div class="drag-box"><div class="prompt-title">Desert Drag</div><div class="prompt-sub">Drag each word label onto the correct picture.</div></div><div class="drag-board"><div class="drag-label-bank" id="dragBank"></div><div class="drag-grid" id="dragGrid"></div><div class="bar"><span class="pill" id="dragScore">Placed: 0/${current.length}</span></div></div>`);
    const bank = root.querySelector('#dragBank'); const grid = root.querySelector('#dragGrid'); const scoreEl = root.querySelector('#dragScore'); let placed = 0;
    shuffled(current).forEach(item => { const chip = document.createElement('div'); chip.className='drag-label'; chip.draggable = true; chip.dataset.id = String(item.id || ''); chip.textContent = item.label || 'Word'; chip.addEventListener('dragstart', ev => ev.dataTransfer.setData('text/plain', chip.dataset.id)); bank.appendChild(chip); });
    current.forEach(item => { const card = document.createElement('div'); card.className='drag-target'; card.innerHTML = `<img src="${escapeAttr(item.image || '')}" alt="${escapeAttr(item.label || '')}" /><div class="drag-target__slot" data-id="${escapeAttr(item.id || '')}">Drop here</div>`; const slot = card.querySelector('.drag-target__slot'); ['dragenter','dragover'].forEach(name => slot.addEventListener(name, ev => { ev.preventDefault(); slot.classList.add('is-over'); })); ['dragleave','drop'].forEach(name => slot.addEventListener(name, () => slot.classList.remove('is-over'))); slot.addEventListener('drop', ev => { ev.preventDefault(); const dragged = String(ev.dataTransfer.getData('text/plain') || ''); const chip = bank.querySelector(`.drag-label[data-id="${dragged}"]`); if(!chip || chip.classList.contains('is-used')) return; if(dragged === String(item.id || '')){ chip.classList.add('is-used'); chip.style.opacity = '0.35'; slot.textContent = item.label || 'OK'; slot.classList.add('is-ok'); placed += 1; scoreEl.textContent = `Placed: ${placed}/${current.length}`; playAudio(String(item.audio || '')); } else { slot.classList.add('is-bad'); setTimeout(() => slot.classList.remove('is-bad'), 460); } }); grid.appendChild(card); });
  }

  function renderPhraseMaker(mode){
    const rounds = (Array.isArray(sentences) ? sentences : []).filter(s => Array.isArray(s.tokens) && s.tokens.length >= 2).slice(0, Math.min(sentences.length, Number(settings.round_limit || 10)));
    if(!rounds.length){ root.innerHTML = shell(`<div class="phrase-box">No sentence data found. Add #Sentences to create Phrase Maker packs.</div>`); return; }
    let idx = 0; let score = 0; let timer = Number(settings.timer_seconds || (mode === 'fast_phrases' ? 60 : 0)); let timerHandle = null;
    root.innerHTML = shell(`<div class="phrase-box"><div class="prompt-title">${escapeHtml(rendererLabel(mode))}</div><div class="prompt-sub">Build the sentence from the shuffled tokens.</div><div class="actions" style="margin-top:12px"><button type="button" class="btn btn--primary" id="checkPhrase">Check</button><button type="button" class="btn btn--ghost" id="nextPhrase">Next</button><button type="button" class="btn btn--danger" id="clearPhrase">Clear</button><span class="pill" id="phraseScore">Score: 0</span>${timer>0 ? '<span class="pill" id="phraseTimer"></span>' : ''}</div></div><div class="phrase-stage"><div><div class="prompt-box"><div class="prompt-title" id="phrasePrompt"></div><div class="prompt-sub" id="phraseZh"></div></div><div class="answer-strip" id="answerStrip"></div><div class="token-bank" id="tokenBank" style="margin-top:12px"></div></div><div class="prompt-box"><div class="prompt-title">How it works</div><div class="prompt-sub phrase-note">Click tokens to move them into the answer strip. Use this for phrases, full sentences, and short grammar patterns.</div><div id="phraseFeedback" class="footer-note"></div></div></div>`);
    const prompt = root.querySelector('#phrasePrompt'); const phraseZh = root.querySelector('#phraseZh'); const tokenBank = root.querySelector('#tokenBank'); const answerStrip = root.querySelector('#answerStrip'); const feedback = root.querySelector('#phraseFeedback'); const scoreEl = root.querySelector('#phraseScore'); const timerEl = root.querySelector('#phraseTimer');
    if(timer > 0){ timerEl.textContent = `Time: ${timer}`; timerHandle = setInterval(() => { timer -= 1; timerEl.textContent = `Time: ${Math.max(0,timer)}`; if(timer <= 0){ clearInterval(timerHandle); root.querySelector('#checkPhrase').disabled = true; root.querySelector('#nextPhrase').disabled = true; feedback.innerHTML = `<span class="bad-note">Time is up.</span>`; } }, 1000); }
    function render(){ const round = rounds[idx]; prompt.textContent = round.text || ''; phraseZh.textContent = round.translation || ''; feedback.textContent = ''; answerStrip.innerHTML = ''; const tokens = shuffled((round.tokens || []).map((tok, tIdx) => ({id:`${idx}_${tIdx}`, token:tok}))); tokenBank.innerHTML = ''; tokens.forEach(entry => { const btn = document.createElement('button'); btn.type='button'; btn.className='token-btn'; btn.textContent = entry.token; btn.dataset.token = entry.token; btn.addEventListener('click', () => { if(btn.classList.contains('is-used')) return; btn.classList.add('is-used'); const ans = document.createElement('button'); ans.type='button'; ans.className='token-btn'; ans.textContent = entry.token; ans.dataset.source = entry.id; ans.addEventListener('click', () => { ans.remove(); btn.classList.remove('is-used'); }); answerStrip.appendChild(ans); }); tokenBank.appendChild(btn); }); }
    root.querySelector('#checkPhrase').addEventListener('click', () => { const round = rounds[idx]; const answer = Array.from(answerStrip.children).map(el => el.textContent || '').join(' ').replace(/\s+([,.!?])/g,'$1').trim(); const expected = String(round.text || '').trim(); if(answer === expected){ score += 1; scoreEl.textContent = `Score: ${score}`; feedback.innerHTML = `<span class="ok-note">Correct.</span>`; } else { feedback.innerHTML = `<span class="bad-note">Expected:</span> ${escapeHtml(expected)}`; } if(mode === 'fast_phrases'){ setTimeout(() => { if(idx < rounds.length - 1){ idx += 1; render(); } }, 650); } });
    root.querySelector('#nextPhrase').addEventListener('click', () => { if(idx < rounds.length - 1){ idx += 1; render(); } });
    root.querySelector('#clearPhrase').addEventListener('click', render); render();
  }

  function renderDescriber(){
    const rounds = Array.isArray(game.description_rounds) ? game.description_rounds : [];
    if(!rounds.length){ root.innerHTML = shell(`<div class="prompt-box">No description rounds found. Add #Sentences or reading lines first.</div>`); return; }
    let idx = 0; let score = 0;
    root.innerHTML = shell(`<div class="prompt-box"><div class="prompt-title">Describer</div><div class="prompt-sub">Read the description and choose the matching image.</div><div class="actions" style="margin-top:12px"><button type="button" class="btn btn--ghost" id="nextDesc">Next round</button><span class="pill" id="descScore">Score: 0</span></div></div><div class="prompt-box"><div class="prompt-title" id="descPrompt"></div><div class="prompt-sub" id="descZh"></div></div><div class="grid" id="descGrid"></div>`);
    const prompt = root.querySelector('#descPrompt'); const descZh = root.querySelector('#descZh'); const grid = root.querySelector('#descGrid'); const scoreEl = root.querySelector('#descScore');
    function render(){ const round = rounds[idx]; prompt.textContent = round.prompt || ''; descZh.textContent = round.translation || ''; const choices = choiceIdsFromRound(round); grid.innerHTML = choices.map(choice => `<button type="button" class="choice-card" data-id="${escapeAttr(choice.id || '')}"><img src="${escapeAttr(choice.image || '')}" alt="${escapeAttr(choice.label || '')}" /><div class="choice-card__body"><div><div class="choice-card__title">${escapeHtml(choice.label || '')}</div><div class="choice-card__meta">${escapeHtml(choice.text || '')}</div></div><span class="chip">Pick</span></div></button>`).join(''); grid.querySelectorAll('.choice-card').forEach(btn => btn.addEventListener('click', async () => { const ok = String(btn.dataset.id || '') === String(round.answer_id || ''); if(ok){ score += 1; scoreEl.textContent = `Score: ${score}`; } btn.classList.add(ok ? 'is-ok' : 'is-bad'); await sleep(650); idx = (idx + 1) % rounds.length; render(); }, { once:true })); }
    root.querySelector('#nextDesc').addEventListener('click', () => { idx = (idx + 1) % rounds.length; render(); }); render();
  }

  function renderAnimalMystery(){
    const rounds = Array.isArray(game.mystery_rounds) ? game.mystery_rounds : [];
    if(!rounds.length){ root.innerHTML = shell(`<div class="prompt-box">No mystery rounds available.</div>`); return; }
    let idx = 0; let score = 0;
    root.innerHTML = shell(`<div class="mystery-box"><div class="prompt-title">Animal Mystery</div><div class="prompt-sub">Reveal clues and guess the mystery card.</div><div class="actions" style="margin-top:12px"><button type="button" class="btn btn--ghost" id="nextMystery">Next mystery</button><span class="pill" id="mysteryScore">Score: 0</span></div></div><div class="mystery-grid"><div><div class="prompt-box"><div class="prompt-title">Clues</div><div class="clue-list" id="clueList"></div></div></div><div class="candidate-grid" id="candidateGrid"></div></div>`);
    const clueList = root.querySelector('#clueList'); const candidateGrid = root.querySelector('#candidateGrid'); const scoreEl = root.querySelector('#mysteryScore');
    function render(){ const round = rounds[idx]; clueList.innerHTML = (round.clues || []).map((clue, cIdx) => `<div class="clue-card"><strong>${escapeHtml(clue.title || '')}</strong><div class="hidden-clue" data-clue="${cIdx}">${escapeHtml(clue.text || '')}</div><div style="margin-top:10px"><button type="button" class="btn btn--ghost btn-reveal-clue" data-clue="${cIdx}">Reveal</button></div></div>`).join(''); clueList.querySelectorAll('.btn-reveal-clue').forEach(btn => btn.addEventListener('click', () => { const target = clueList.querySelector(`[data-clue="${btn.dataset.clue}"]`); if(target){ target.classList.remove('hidden-clue'); btn.disabled = true; } })); const choices = choiceIdsFromRound(round); candidateGrid.innerHTML = choices.map(choice => `<button type="button" class="candidate-card" data-id="${escapeAttr(choice.id || '')}"><div class="candidate-card__media"><img src="${escapeAttr(choice.image || '')}" alt="${escapeAttr(choice.label || '')}" /></div><div class="candidate-card__body"><div class="candidate-card__title">${escapeHtml(choice.label || '')}</div><div class="candidate-card__meta">${escapeHtml(choice.text || choice.block_type || '')}</div></div></button>`).join(''); candidateGrid.querySelectorAll('.candidate-card').forEach(btn => btn.addEventListener('click', async () => { const ok = String(btn.dataset.id || '') === String(round.answer_id || ''); if(ok){ score += 1; scoreEl.textContent = `Score: ${score}`; } btn.classList.add(ok ? 'is-ok' : 'is-bad'); await sleep(700); idx = (idx + 1) % rounds.length; render(); }, { once:true })); }
    root.querySelector('#nextMystery').addEventListener('click', () => { idx = (idx + 1) % rounds.length; render(); }); render();
  }

  function renderSpellingBee(){
    const rounds = Array.isArray(game.spelling_targets) ? game.spelling_targets : [];
    if(!rounds.length){ root.innerHTML = shell(`<div class="prompt-box">No spelling words available.</div>`); return; }
    let idx = 0; let score = 0;
    root.innerHTML = shell(`<div class="prompt-box"><div class="prompt-title">Spelling Bee</div><div class="prompt-sub">Use the letter bank to spell the word.</div><div class="actions" style="margin-top:12px"><button type="button" class="btn btn--primary" id="playSpell">Play prompt</button><button type="button" class="btn btn--ghost" id="nextSpell">Next word</button><span class="pill" id="spellScore">Score: 0</span></div></div><div class="flash-wrap"><div class="image-main"><img id="spellImg" alt="spelling image" /><div class="image-main__body"><div class="image-main__word" id="spellHint"></div><div class="image-main__text" id="spellZh"></div></div></div><div class="study-side"><div class="spelling-answer" id="spellAnswer"></div><div class="letter-bank" id="letterBank"></div><button type="button" class="btn btn--primary" id="checkSpell">Check spelling</button><button type="button" class="btn btn--danger" id="clearSpell">Clear</button><div id="spellFeedback" class="footer-note"></div></div></div>`);
    const spellImg = root.querySelector('#spellImg'); const spellHint = root.querySelector('#spellHint'); const spellZh = root.querySelector('#spellZh'); const spellAnswer = root.querySelector('#spellAnswer'); const letterBank = root.querySelector('#letterBank'); const feedback = root.querySelector('#spellFeedback'); const scoreEl = root.querySelector('#spellScore'); const playSpell = root.querySelector('#playSpell');
    function render(){ const round = rounds[idx]; spellImg.src = round.image || ''; spellHint.textContent = `Word length: ${String(round.answer || '').length}`; spellZh.textContent = round.text || ''; feedback.textContent = ''; spellAnswer.innerHTML = Array.from(String(round.answer || '')).map(() => `<div class="spelling-slot"></div>`).join(''); letterBank.innerHTML = ''; (round.letters || []).forEach((letter, lIdx) => { const btn = document.createElement('button'); btn.type='button'; btn.className='letter-btn'; btn.textContent = String(letter).toUpperCase(); btn.dataset.letter = String(letter); btn.dataset.idx = String(lIdx); btn.addEventListener('click', () => { if(btn.classList.contains('is-used')) return; const empty = spellAnswer.querySelector('.spelling-slot:empty'); if(!empty) return; empty.textContent = btn.dataset.letter.toUpperCase(); empty.dataset.source = btn.dataset.idx; btn.classList.add('is-used'); }); letterBank.appendChild(btn); }); playSpell.disabled = !round.audio; playSpell.onclick = () => playAudio(String(round.audio || '')); }
    root.querySelector('#checkSpell').addEventListener('click', () => { const round = rounds[idx]; const answer = Array.from(spellAnswer.children).map(slot => slot.textContent || '').join('').toLowerCase(); if(answer === String(round.answer || '').toLowerCase()){ score += 1; scoreEl.textContent = `Score: ${score}`; feedback.innerHTML = `<span class="ok-note">Correct.</span>`; } else { feedback.innerHTML = `<span class="bad-note">Correct answer:</span> ${escapeHtml(String(round.label || round.answer || ''))}`; } });
    root.querySelector('#clearSpell').addEventListener('click', () => { Array.from(spellAnswer.children).forEach(slot => { const source = slot.dataset.source; if(source){ const btn = letterBank.querySelector(`.letter-btn[data-idx="${source}"]`); if(btn){ btn.classList.remove('is-used'); } } slot.textContent = ''; delete slot.dataset.source; }); });
    root.querySelector('#nextSpell').addEventListener('click', () => { idx = (idx + 1) % rounds.length; render(); }); render();
  }

  function renderHangman(){
    const rounds = Array.isArray(game.spelling_targets) ? game.spelling_targets : [];
    if(!rounds.length){ root.innerHTML = shell(`<div class="prompt-box">No hangman words available.</div>`); return; }
    let idx = 0; let score = 0; let misses = 0; let used = new Set(); let answer = '';
    root.innerHTML = shell(`<div class="prompt-box"><div class="prompt-title">Hangman</div><div class="prompt-sub">Guess letters to uncover the word.</div><div class="actions" style="margin-top:12px"><button type="button" class="btn btn--primary" id="playHangman">Play prompt</button><button type="button" class="btn btn--ghost" id="nextHangman">Next word</button><span class="pill" id="hangmanScore">Score: 0</span><span class="pill miss-pill" id="missPill">Misses: 0</span></div></div><div class="flash-wrap"><div class="image-main"><img id="hangmanImg" alt="hangman image" /><div class="image-main__body"><div class="hangman-word" id="hangmanWord"></div><div class="image-main__text" id="hangmanZh"></div></div></div><div class="study-side"><div class="hangman-letters" id="hangmanLetters"></div><div id="hangmanFeedback" class="footer-note"></div></div></div>`);
    const hangmanImg = root.querySelector('#hangmanImg'); const hangmanWord = root.querySelector('#hangmanWord'); const hangmanZh = root.querySelector('#hangmanZh'); const lettersHost = root.querySelector('#hangmanLetters'); const feedback = root.querySelector('#hangmanFeedback'); const scoreEl = root.querySelector('#hangmanScore'); const missPill = root.querySelector('#missPill'); const playHangman = root.querySelector('#playHangman');
    function render(){ const round = rounds[idx]; answer = String(round.answer || '').toLowerCase(); misses = 0; used = new Set(); hangmanImg.src = round.image || ''; hangmanZh.textContent = round.text || ''; feedback.textContent = ''; missPill.textContent = 'Misses: 0'; playHangman.disabled = !round.audio; playHangman.onclick = () => playAudio(String(round.audio || '')); drawWord(); lettersHost.innerHTML = ''; 'abcdefghijklmnopqrstuvwxyz'.split('').forEach(letter => { const btn = document.createElement('button'); btn.type='button'; btn.className='letter-btn'; btn.textContent = letter.toUpperCase(); btn.addEventListener('click', () => guess(letter, btn), { once:true }); lettersHost.appendChild(btn); }); }
    function drawWord(){ hangmanWord.innerHTML = answer.split('').map(ch => /[a-z]/.test(ch) ? `<div class="hangman-slot">${used.has(ch) ? ch.toUpperCase() : ''}</div>` : `<div class="hangman-slot">${escapeHtml(ch)}</div>`).join(''); }
    function guess(letter, btn){ used.add(letter); if(answer.includes(letter)){ drawWord(); if(answer.split('').every(ch => !/[a-z]/.test(ch) || used.has(ch))){ score += 1; scoreEl.textContent = `Score: ${score}`; feedback.innerHTML = `<span class="ok-note">Solved.</span>`; } } else { misses += 1; missPill.textContent = `Misses: ${misses}`; if(misses >= Number(settings.max_misses || 6)){ feedback.innerHTML = `<span class="bad-note">Answer:</span> ${escapeHtml(answer.toUpperCase())}`; } } btn.disabled = true; }
    root.querySelector('#nextHangman').addEventListener('click', () => { idx = (idx + 1) % rounds.length; render(); }); render();
  }
})();
"""
