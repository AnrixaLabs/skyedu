"""
skyed/pipeline_helpers.py
--------------------------
Pure helper functions extracted from run_pipeline.py.
Nothing here imports from run_pipeline — this module has no circular deps.
"""
from __future__ import annotations

import copy
import hashlib
import html
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils import slugify, slugify_file, ensure_dir
from .quizgen import normalize_theme_variant


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log_step(message: str) -> None:
    print(str(message or ""), flush=True)


# ---------------------------------------------------------------------------
# Slug / tag-s helpers
# ---------------------------------------------------------------------------

def sentence_audio_stem(base_text: str) -> str:
    """
    Stable filename stem for sentence audio files.
    Uses a short slug from the text + a hash suffix to avoid collisions.
    Result is used as: sent_<stem>.mp3
    """
    t = (base_text or "").strip()
    short = slugify_file(t[:60] if len(t) > 60 else t)
    h = hashlib.sha1(t.encode("utf-8")).hexdigest()[:10]
    return f"{short}_{h}" if short else h


# tag_s_output_root is re-exported from tag_s_env for callers that import it from here.
from .tag_s_env import tag_s_output_root  # noqa: F401


# ---------------------------------------------------------------------------
# HTML escaping shorthands
# ---------------------------------------------------------------------------

def h(text: str) -> str:
    """HTML-escape for text content (quotes not escaped)."""
    return html.escape(text or "", quote=False)


def hu(text: str) -> str:
    """HTML-escape for attribute values (quotes escaped)."""
    return html.escape(text or "", quote=True)


# ---------------------------------------------------------------------------
# Lesson / reader HTML builders
# ---------------------------------------------------------------------------

def build_lesson_html(
    title: str,
    vocab_items: List[Dict[str, str]],
    sentence_items: List[Dict[str, str]],
    quiz_url: str,
    *,
    quiz_embed_mode: str = "embed",  # embed | link | off
    quiz_note: str = "",
    extra_audio_items: Optional[List[Dict[str, str]]] = None,
    qa_items: Optional[List[Dict[str, str]]] = None,
    theme: str = "sky",
) -> str:
    """
    LMS-style lesson page:
      - Vocab grid: each card contains image + EN+CN + audio (EN+CN).
      - Sentences section: EN+CN line pairs + audio (EN+CN).
      - Quiz block: always shows a 'Start Quiz' button when URL is available.
        iframe is optional (Tutor LMS may sanitise/limit iframe/script behaviour).
    """
    css = """
    <style>
      :root{
        --max:1100px; --r:16px; --stroke:rgba(0,0,0,.10);
        --shadow:0 10px 25px rgba(0,0,0,.10);
        --bg:#f6f7fb; --card:#fff; --muted:#6b7280;
        --brand1:#2563eb; --brand2:#38bdf8;
      }
      body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:var(--bg);color:#111827;}
      .wrap{max-width:var(--max);margin:0 auto;padding:18px 14px 60px;}
      .hero{background:linear-gradient(90deg,var(--brand1),var(--brand2));color:#fff;border-radius:18px;padding:16px 16px 12px;margin-bottom:14px;box-shadow:var(--shadow);}
      .hero h2{margin:0;font-size:20px;}
      .hero .sub{opacity:.9;margin-top:6px;font-size:13px;}
      .h3{font-size:14px;margin:16px 0 10px;color:#0f172a;}
      .grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;}
      @media (max-width:980px){.grid{grid-template-columns:repeat(2,minmax(0,1fr));}}
      @media (max-width:620px){.grid{grid-template-columns:1fr;}}
      .card{background:var(--card);border:1px solid var(--stroke);border-radius:var(--r);overflow:hidden;box-shadow:var(--shadow);display:flex;flex-direction:column;}
      .media{aspect-ratio:4/3;background:#eef2ff;display:flex;align-items:center;justify-content:center;}
      .media img{width:100%;height:100%;object-fit:contain;display:block;background:#eef2ff;}
      .bd{padding:12px 12px 14px;display:flex;flex-direction:column;gap:10px;}
      .row{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap;}
      .en{font-weight:800;font-size:18px;}
      .zh{font-weight:650;color:var(--muted);}
      audio{width:100%;}
      .note{font-size:12px;color:var(--muted);margin-top:6px;}
      .sentwrap{display:flex;flex-direction:column;gap:10px;}
      .skyed-sent{background:var(--card);border:1px solid var(--stroke);border-radius:16px;box-shadow:var(--shadow);padding:12px;}
      .skyed-sent .txt{display:flex;flex-direction:column;gap:6px;margin-bottom:10px;}
      .skyed-sent .txt b{color:#0f172a;}
      .skyed-sent .aud{display:flex;flex-direction:column;gap:8px;}
      .quizbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:6px 0 12px;}
      .btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:10px 14px;border-radius:999px;
           text-decoration:none;font-weight:800;border:1px solid rgba(255,255,255,.25);}
      .btn-primary{background:linear-gradient(90deg,var(--brand1),var(--brand2));color:#fff;}
      .btn-ghost{background:#fff;color:#0f172a;border:1px solid var(--stroke);}
      .warn{background:#fff7ed;border:1px solid rgba(249,115,22,.25);color:#9a3412;border-radius:14px;padding:10px 12px;}
      iframe{width:100%;height:900px;border:0;border-radius:16px;box-shadow:var(--shadow);background:#fff;}
      .extraaud{display:flex;flex-direction:column;gap:10px;}
      .extraaud .track{background:var(--card);border:1px solid var(--stroke);border-radius:16px;box-shadow:var(--shadow);padding:12px;}
      .extraaud .track b{display:block;margin-bottom:8px;color:#0f172a;}
      .qa-dialogues{display:flex;flex-direction:column;gap:12px;}
      .qa-card{background:var(--card);border:1px solid var(--stroke);border-radius:18px;box-shadow:var(--shadow);padding:14px;}
      .qa-top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px;flex-wrap:wrap;}
      .qa-badge{display:inline-flex;align-items:center;justify-content:center;min-width:42px;height:42px;border-radius:14px;background:#dbeafe;color:#1d4ed8;font-weight:900;}
      .qa-title{font-size:14px;font-weight:800;color:#0f172a;}
      .qa-controls{display:flex;gap:8px;flex-wrap:wrap;}
      .qa-bubble{border-radius:18px;padding:12px 14px;max-width:88%;display:flex;flex-direction:column;gap:8px;}
      .qa-bubble + .qa-bubble{margin-top:10px;}
      .qa-bubble--q{background:#eff6ff;border:1px solid rgba(37,99,235,.18);margin-right:auto;}
      .qa-bubble--a{background:#f8fafc;border:1px solid rgba(15,23,42,.10);margin-left:auto;}
      .qa-role{font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#475569;}
      .qa-text{font-size:16px;line-height:1.5;color:#0f172a;font-weight:700;white-space:pre-wrap;}
    </style>
    """

    vocab_cards: List[str] = []
    for it in vocab_items:
        en = (it.get("en") or "").strip()
        zh = (it.get("zh") or "").strip()
        img = (it.get("img") or "").strip()
        a_en = (it.get("audio_en") or "").strip()
        a_zh = (it.get("audio_zh") or "").strip()

        card = ['<div class="card">']
        card.append('<div class="media">')
        if img:
            card.append(f'<img src="{hu(img)}" alt="{hu(en)}" loading="lazy">')
        card.append("</div>")
        card.append('<div class="bd">')
        card.append('<div class="row">')
        card.append(f'<div class="en">{h(en)}</div>')
        card.append(f'<div class="zh">{h(zh)}</div>' if zh else '<div class="zh"></div>')
        card.append("</div>")
        if a_en:
            card.append(f'<audio controls src="{hu(a_en)}"></audio>')
        if a_zh:
            card.append(f'<audio controls src="{hu(a_zh)}"></audio>')
        card.append("</div></div>")
        vocab_cards.append("".join(card))

    sent_cards: List[str] = []
    for it in sentence_items:
        en = (it.get("en") or "").strip()
        zh = (it.get("zh") or "").strip()
        a_en = (it.get("audio_en") or "").strip()
        a_zh = (it.get("audio_zh") or "").strip()

        row = ['<div class="skyed-sent">']
        row.append('<div class="txt">')
        if en:
            row.append(f"<div><b>EN:</b> {h(en)}</div>")
        if zh:
            row.append(f"<div><b>CN:</b> {h(zh)}</div>")
        row.append("</div>")
        row.append('<div class="aud">')
        if a_en:
            row.append(f'<audio controls src="{hu(a_en)}"></audio>')
        if a_zh:
            row.append(f'<audio controls src="{hu(a_zh)}"></audio>')
        row.append("</div></div>")
        sent_cards.append("".join(row))

    q_url = (quiz_url or "").strip()
    embed = (quiz_embed_mode or "embed").strip().lower() == "embed"
    link_ok = bool(q_url) and q_url.lower() != "about:blank"

    quiz_block = []
    if quiz_note:
        quiz_block.append(f'<div class="warn">{h(quiz_note)}</div>')
    quiz_block.append('<div class="quizbar">')
    if link_ok:
        quiz_block.append(f'<a class="btn btn-primary" href="{hu(q_url)}" target="_blank" rel="noopener">&#9654; Start Practice</a>')
        quiz_block.append(f'<a class="btn btn-ghost" href="{hu(q_url)}">Open here</a>')
    else:
        quiz_block.append('<span class="warn">Practice URL not configured.</span>')
    quiz_block.append("</div>")
    if embed and link_ok:
        quiz_block.append(f'<iframe src="{hu(q_url)}" loading="lazy"></iframe>')

    extra_audio_block: List[str] = []
    if extra_audio_items:
        section_title = "Extra Audio"
        for item in extra_audio_items:
            candidate_title = str(item.get("title") or "").strip()
            if candidate_title:
                section_title = candidate_title
                break
        extra_audio_block.append(f'<div class="h3">{h(section_title)}</div>')
        extra_audio_block.append('<div class="extraaud">')
        for item in extra_audio_items:
            label = h(str(item.get("label") or section_title))
            url = hu(str(item.get("url") or ""))
            if not url:
                continue
            extra_audio_block.append(f'<div class="track"><b>{label}</b><audio controls src="{url}"></audio></div>')
        extra_audio_block.append("</div>")

    qa_block: List[str] = []
    if (theme or "sky").strip().lower() == "sky" and qa_items:
        qa_block.append('<div class="h3">Questions and Answers</div>')
        qa_block.append('<div class="qa-dialogues">')
        for idx_qa, item in enumerate(qa_items, start=1):
            q_txt = h(str(item.get("q") or "").strip())
            a_txt = h(str(item.get("a") or "").strip())
            q_audio = hu(str(item.get("q_audio_en") or "").strip())
            a_audio = hu(str(item.get("a_audio_en") or "").strip())
            if not q_txt and not a_txt:
                continue
            qa_block.append('<div class="qa-card">')
            qa_block.append('<div class="qa-top">')
            qa_block.append(f'<div style="display:flex;align-items:center;gap:10px;"><div class="qa-badge">{idx_qa}</div><div class="qa-title">Dialogue Practice</div></div>')
            controls: List[str] = []
            if q_audio:
                controls.append(f'<audio controls preload="none" src="{q_audio}"></audio>')
            if a_audio:
                controls.append(f'<audio controls preload="none" src="{a_audio}"></audio>')
            qa_block.append(f'<div class="qa-controls">{"".join(controls)}</div>')
            qa_block.append('</div>')
            if q_txt:
                qa_block.append('<div class="qa-bubble qa-bubble--q">')
                qa_block.append('<div class="qa-role">Speaker A</div>')
                qa_block.append(f'<div class="qa-text">{q_txt}</div>')
                qa_block.append('</div>')
            if a_txt:
                qa_block.append('<div class="qa-bubble qa-bubble--a">')
                qa_block.append('<div class="qa-role">Speaker B</div>')
                qa_block.append(f'<div class="qa-text">{a_txt}</div>')
                qa_block.append('</div>')
            qa_block.append('</div>')
        qa_block.append('</div>')

    return f"""{css}
    <div class="wrap">
      <div class="hero">
        <h2>{h(title)}</h2>
        <div class="sub">Vocabulary → Sentences → Practice</div>
      </div>

      <div class="h3">Vocabulary Cards</div>
      <div class="grid">
        {"".join(vocab_cards)}
      </div>
      <div class="note">Keep practice 5–10 minutes. Audio optional.</div>

      <div class="h3">Sentences</div>
      <div class="sentwrap">
        {"".join(sent_cards)}
      </div>

      {"".join(extra_audio_block)}

      {"".join(qa_block)}

      <div class="h3">Practice</div>
      {"".join(quiz_block)}
    </div>
    """


def build_picture_reader_html(
    title: str,
    sentence_items: List[Dict[str, str]],
    *,
    cover_image: str = "",
) -> str:
    css = """
    <style>
      :root{
        --max:880px; --r:28px; --stroke:rgba(15,23,42,.10);
        --bg:#fff8ef; --card:#ffffff; --card-2:#fffaf3; --muted:#7d6656;
        --brand1:#f08c00; --brand2:#ffbf69; --shadow:0 18px 40px rgba(202,120,27,.12);
      }
      body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:var(--bg);color:#3a2b20;}
      .wrap{max-width:var(--max);margin:0 auto;padding:18px 14px 56px;}
      .hero{background:linear-gradient(135deg,var(--brand1),var(--brand2));color:#fff;border-radius:30px;padding:18px 18px 14px;box-shadow:var(--shadow);margin-bottom:16px;}
      .hero h2{margin:0;font-size:22px;line-height:1.25;}
      .hero .sub{margin-top:6px;font-size:13px;opacity:.95;}
      .hero .meta{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;}
      .chip{display:inline-flex;align-items:center;padding:8px 14px;border-radius:999px;background:rgba(255,255,255,.16);color:#fff;font-size:12px;font-weight:800;}
      .sheet{background:linear-gradient(180deg,var(--card),var(--card-2));border:1px solid var(--stroke);border-radius:30px;box-shadow:var(--shadow);overflow:hidden;}
      .sheet__top{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px 12px;border-bottom:1px solid rgba(240,140,0,.10);}
      .pill{display:inline-flex;align-items:center;padding:8px 14px;border-radius:999px;background:rgba(240,140,0,.12);color:#b15d00;font-size:13px;font-weight:800;}
      .note{font-size:13px;color:var(--muted);}
      .flow{padding:10px 14px 6px;}
      .line{display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:12px;width:100%;text-align:left;border:0;background:transparent;padding:12px 4px;border-radius:18px;cursor:pointer;transition:background .16s ease, transform .16s ease;}
      .line + .line{border-top:1px dashed rgba(180,123,41,.16);}
      .line:hover,.line:focus{background:rgba(255,191,105,.12);outline:none;}
      .line.is-playing{background:rgba(240,140,0,.08);}
      .idx{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:999px;background:rgba(240,140,0,.12);color:#b15d00;font-size:12px;font-weight:800;margin-top:2px;}
      .body{min-width:0;}
      .label{display:block;font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#c07a1f;margin-bottom:4px;}
      .label.zh{margin-top:10px;color:#8b6b52;}
      .en{display:inline;font-size:22px;font-weight:900;line-height:1.52;padding:1px 4px;border-radius:10px;transition:background .15s ease, box-shadow .15s ease;}
      .en-prefix{display:inline;font-size:.88em;font-weight:900;color:#a45100;margin-right:6px;}
      .en-body{display:inline;}
      .zh{display:inline-block;font-size:18px;line-height:1.68;color:#4b3a2e;padding:1px 4px;border-radius:10px;transition:background .15s ease, box-shadow .15s ease;}
      .line.is-speaking-en .en,.line.is-speaking-zh .zh{background:rgba(255,191,105,.24);box-shadow:0 0 0 6px rgba(255,191,105,.12);}
      .tap{align-self:center;white-space:nowrap;font-size:13px;color:#b15d00;font-weight:800;}
      .art{padding:4px 16px 16px;}
      .art img{display:block;width:100%;max-height:260px;object-fit:cover;border-radius:22px;border:1px solid rgba(240,140,0,.10);}
      @media (max-width:640px){
        .sheet__top{align-items:flex-start;flex-direction:column;gap:8px;}
        .line{grid-template-columns:32px minmax(0,1fr);gap:10px;padding:12px 2px;}
        .tap{grid-column:2;color:var(--muted);font-size:12px;margin-top:2px;}
        .en{font-size:19px;}
        .zh{font-size:16px;}
      }
    </style>
    """

    rows = []
    for idx, it in enumerate(sentence_items):
        en_raw = (it.get("en") or "").strip()
        en_prefix_raw = (it.get("display_prefix_en") or "").strip()
        en_body_raw = (it.get("display_body_en") or "").strip()
        zh_raw = (it.get("zh") or "").strip()
        en_text = h(en_raw)
        en_prefix = h(en_prefix_raw)
        en_body = h(en_body_raw)
        zh_text = h(zh_raw)
        a_en = hu((it.get("audio_en") or "").strip())
        a_zh = hu((it.get("audio_zh") or "").strip())
        if not en_text and not zh_text:
            continue
        row = [f'<button class="line" type="button" data-audio-en="{a_en}" data-audio-zh="{a_zh}">']
        row.append(f'<span class="idx">{idx + 1}</span>')
        row.append('<span class="body">')
        if en_text:
            row.append('<span class="label">English</span>')
            if en_prefix and en_body:
                row.append(f'<span class="en"><span class="en-prefix">{en_prefix}</span><span class="en-body">{en_body}</span></span>')
            else:
                row.append(f'<span class="en">{en_text}</span>')
        if zh_text:
            row.append('<span class="label zh">Chinese</span>')
            row.append(f'<span class="zh">{zh_text}</span>')
        row.append("</span>")
        row.append('<span class="tap">Tap to listen</span>')
        row.append("</button>")
        rows.append("".join(row))

    cover_html = (
        f'<div class="art"><img src="{hu(cover_image)}" alt="{h(title)}" loading="lazy"></div>'
        if cover_image else ""
    )

    return "".join([
        css,
        '<div class="wrap">',
        '  <div class="hero">',
        '    <div class="pill" style="background:rgba(255,255,255,.18);color:#fff;">Sky Reading Frame</div>',
        f'    <h2>{h(title)}</h2>',
        '    <div class="sub">Touch any line to hear it. English plays first, then Chinese.</div>',
        f'    <div class="meta"><span class="chip">{len(rows)} lines</span><span class="chip">Touch to listen</span></div>',
        "  </div>",
        '  <section class="sheet">',
        '    <div class="sheet__top"><div class="pill">Interactive picture text</div><div class="note">Single reading block for fast mobile replay.</div></div>',
        f'    <div class="flow">{"".join(rows)}</div>',
        f"    {cover_html}",
        "  </section>",
        "</div>",
        """<script>
    (function(){
      const entries = document.querySelectorAll('.line');
      let current = null;
      let currentEntry = null;
      function clearState(){ entries.forEach(function(el){ el.classList.remove('is-playing','is-speaking-en','is-speaking-zh'); }); }
      function stopCurrent(){ if (current) { try { current.pause(); current.currentTime = 0; } catch(e){} } current = null; currentEntry = null; clearState(); }
      function playUrl(url, onEnd){ if (!url) { if (onEnd) onEnd(); return; } const audio = new Audio(url); current = audio; audio.onended = function(){ if (onEnd) onEnd(); }; audio.onerror = function(){ if (onEnd) onEnd(); }; audio.play().catch(function(){ if (onEnd) onEnd(); }); }
      function playEntry(entry){ if (currentEntry === entry) { stopCurrent(); return; } stopCurrent(); currentEntry = entry; const enUrl = entry.getAttribute('data-audio-en') || ''; const zhUrl = entry.getAttribute('data-audio-zh') || ''; entry.classList.add('is-playing'); if (enUrl) { entry.classList.add('is-speaking-en'); playUrl(enUrl, function(){ entry.classList.remove('is-speaking-en'); if (zhUrl) { entry.classList.add('is-speaking-zh'); playUrl(zhUrl, function(){ stopCurrent(); }); } else { stopCurrent(); } }); } else if (zhUrl) { entry.classList.add('is-speaking-zh'); playUrl(zhUrl, function(){ stopCurrent(); }); } }
      entries.forEach(function(entry){ entry.addEventListener('click', function(){ playEntry(entry); }); entry.addEventListener('keydown', function(ev){ if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); playEntry(entry); } }); });
    })();
    </script>""",
    ])


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

AUDIO_FILE_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".aac"}


def audio_rel_key(audio_root: Path, f: Path) -> str:
    """Stable key preserving language subfolder, e.g. en/apple.mp3"""
    try:
        return f.relative_to(audio_root).as_posix()
    except Exception:
        return f.name


def resolve_uploaded_audio_url(audio_url_by_rel: Dict[str, str], rel: str) -> str:
    rel_norm = str(rel or "").strip().replace("\\", "/")
    if not rel_norm:
        return ""
    candidates = [rel_norm]
    if rel_norm.startswith("audio/"):
        candidates.append(rel_norm[len("audio/"):])
    else:
        candidates.append(f"audio/{rel_norm}")
    for key in candidates:
        url = str(audio_url_by_rel.get(key) or "").strip()
        if url:
            return url
    return rel_norm


def map_special_audio_items(
    items: List[Dict[str, str]],
    audio_url_by_rel: Dict[str, str],
) -> List[Dict[str, str]]:
    mapped: List[Dict[str, str]] = []
    for item in items or []:
        rel = str(item.get("url") or "").strip()
        mapped.append({
            "label": str(item.get("label") or "Extra Audio").strip() or "Extra Audio",
            "title": str(item.get("title") or "Extra Audio").strip() or "Extra Audio",
            "url": resolve_uploaded_audio_url(audio_url_by_rel, rel),
        })
    return mapped


def copy_special_audio_assets_from_env(lesson_root: Path) -> List[Dict[str, str]]:
    enabled = (os.environ.get("SKYED_SPECIAL_AUDIO_ENABLED", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return []
    src_dir_raw = (os.environ.get("SKYED_SPECIAL_AUDIO_DIR", "") or "").strip()
    if not src_dir_raw:
        return []
    src_dir = Path(src_dir_raw).expanduser()
    if not src_dir.exists() or not src_dir.is_dir():
        raise RuntimeError(f"Special lesson audio folder not found: {src_dir}")
    dst_dir = ensure_dir(Path(lesson_root) / "audio" / "manual")
    title_default = (os.environ.get("SKYED_SPECIAL_AUDIO_TITLE", "Extra Audio") or "Extra Audio").strip() or "Extra Audio"
    items: List[Dict[str, str]] = []
    for src in sorted(src_dir.iterdir(), key=lambda p: p.name.lower()):
        if not src.is_file() or src.suffix.lower() not in AUDIO_FILE_EXTENSIONS:
            continue
        safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in src.name)
        dst = dst_dir / safe_name
        shutil.copy2(src, dst)
        label = src.stem.replace("_", " ").replace("-", " ").strip() or title_default
        items.append({
            "label": label,
            "title": title_default,
            "url": str(dst.relative_to(lesson_root)).replace("\\", "/"),
        })
    return items


def copy_ng_happy_practice_assets_from_env(lesson_root: Path) -> List[Dict[str, str]]:
    raw = (os.environ.get("SKYED_NG_AUDIO_FIELDS", "") or "").strip()
    if not raw:
        return []
    try:
        mapping = json.loads(raw)
    except Exception as exc:
        raise RuntimeError(f"Invalid SKYED_NG_AUDIO_FIELDS JSON: {exc}")
    if not isinstance(mapping, dict):
        return []
    dst_dir = ensure_dir(Path(lesson_root) / "audio" / "ng_happy_practice")
    items: List[Dict[str, str]] = []
    used_names: set[str] = set()
    for idx, (label, src_value) in enumerate(mapping.items(), start=1):
        label_text = str(label or "").strip()
        src_raw = str(src_value or "").strip()
        if not label_text or not src_raw:
            continue
        src = Path(src_raw).expanduser()
        if not src.exists() or not src.is_file():
            raise RuntimeError(f"NG audio file not found: {src}")
        if src.suffix.lower() not in AUDIO_FILE_EXTENSIONS:
            raise RuntimeError(f"Unsupported NG audio format: {src.name}")
        label_slug = slugify(label_text).replace("-", "_") or f"track_{idx}"
        ext = src.suffix.lower()
        safe_name = f"hp_{idx:02d}_{label_slug}{ext}"
        n = 2
        while safe_name.lower() in used_names:
            safe_name = f"hp_{idx:02d}_{label_slug}_{n}{ext}"
            n += 1
        used_names.add(safe_name.lower())
        dst = dst_dir / safe_name
        shutil.copy2(src, dst)
        items.append({
            "label": label_text,
            "title": "Happy Practice",
            "url": str(dst.relative_to(lesson_root)).replace("\\", "/"),
        })
    return items


def load_ng_selected_tag_games_from_env() -> List[Dict[str, str]]:
    raw = (os.environ.get("SKYED_NG_SELECTED_TAG_GAMES", "") or "").strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise RuntimeError(f"Invalid SKYED_NG_SELECTED_TAG_GAMES JSON: {exc}")
    if not isinstance(payload, list):
        return []
    out: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        tag = str(item.get("tag") or "").strip()
        game_id = str(item.get("game_id") or "").strip()
        if not tag or not game_id:
            continue
        key = (tag, game_id)
        if key in seen:
            continue
        seen.add(key)
        entry = {
            "tag": tag,
            "game_id": game_id,
            "title": str(item.get("title") or "").strip(),
            "renderer": str(item.get("renderer") or "").strip(),
            "url": str(item.get("url") or "").strip(),
            "local_root": str(item.get("local_root") or "").strip(),
        }
        if isinstance(item.get("data"), dict):
            entry["data"] = item.get("data")
        out.append({k: v for k, v in entry.items() if v or k == "data"})
    return out


def merge_tag_game_lists(*groups: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for group in groups:
        for item in group or []:
            if not isinstance(item, dict):
                continue
            tag = str(item.get("tag") or "").strip()
            game_id = str(item.get("game_id") or "").strip()
            if not tag or not game_id:
                continue
            key = (tag, game_id)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
    return out


def tag_game_info_from_root(game_root: Optional[Path | str]) -> Optional[Dict[str, Any]]:
    if not game_root:
        return None
    root_path = Path(game_root)
    if not root_path.exists():
        return None
    tag = root_path.parent.name
    game_id = root_path.name
    title = f"{tag} · {game_id.replace('_', ' ').replace('-', ' ').title()}"
    renderer = ""
    payload: Dict[str, Any] | None = None
    game_json = root_path / "game.json"
    if game_json.exists():
        try:
            loaded = json.loads(game_json.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(loaded, dict):
                payload = loaded
                meta = payload.get("meta") if isinstance(payload, dict) else {}
                if isinstance(meta, dict):
                    title = str(meta.get("title") or title).strip() or title
                    renderer = str(meta.get("renderer") or "").strip()
        except Exception:
            pass
    base = (os.environ.get("TAGS_PUBLIC_BASE", "") or "").rstrip("/")
    url = f"{base}/{tag}/{game_id}/index.html" if base else ""
    out: Dict[str, Any] = {"tag": tag, "game_id": game_id, "title": title, "renderer": renderer, "url": url, "local_root": str(root_path.resolve())}
    if payload:
        out["data"] = payload
    return out


# ---------------------------------------------------------------------------
# Slug / publish helpers
# ---------------------------------------------------------------------------

def extract_day_number(title: str) -> str:
    m = re.search(r"\bday\s*(\d+)\b", title or "", flags=re.IGNORECASE)
    return m.group(1) if m else ""


def build_publish_slug(title: str, tags: List[str], style: str = "auto") -> str:
    style = (style or "auto").strip().lower()
    day = extract_day_number(title)
    clean_tags = [slugify(str(t or "")) for t in (tags or []) if str(t or "").strip()]
    first_tag = clean_tags[0] if clean_tags else ""
    topic = first_tag or slugify(title.replace("Homework", "").replace("homework", ""))
    topic = re.sub(r"(^day-\d+-?|^day\d+-?|^-+)", "", topic).strip("-")
    topic = "-".join([x for x in topic.split("-")[:2] if x])
    if style == "shortcode" and day:
        return f"hw-{int(day):03d}"
    if style == "topic" and topic:
        return topic
    if style == "topic_day" and topic and day:
        return f"{topic}-{day}"
    if style == "day_topic" and day and topic:
        return f"d{int(day)}-{topic}"
    if day and topic:
        return f"d{int(day)}-{topic}"
    if topic:
        return topic
    if day:
        return f"hw-{int(day):03d}"
    return slugify(title)


def normalize_publish_slug_mode(mode: str) -> str:
    m = (mode or "auto_lesson").strip().lower()
    if m in ("auto_lesson", "title", "custom"):
        return m
    return "auto_lesson"


def clean_publish_group_path(path: str) -> str:
    raw = str(path or "").strip().strip("/")
    if not raw:
        return ""
    parts = [slugify(seg) for seg in raw.split("/") if slugify(seg)]
    return "/".join(parts)


def sanitize_publish_slug(value: str) -> str:
    return slugify(str(value or "").strip())


def infer_mode_surface_from_theme(theme: str) -> tuple[str, str]:
    theme = normalize_theme_variant((theme or "sky").strip().lower())
    if theme == "sky_tiles":
        return "kid_homework", "tiles"
    if theme == "strict_dark":
        return "reading_listening", "strict_dark"
    if theme == "ng":
        return "standard_homework", "ng"
    return "standard_homework", "classic"


# ---------------------------------------------------------------------------
# Quality / consistency checks
# ---------------------------------------------------------------------------

def build_consistency_report(spec: Dict[str, Any]) -> Dict[str, object]:
    vocab = spec.get("vocab", []) or []
    sentences = spec.get("sentences", []) or []
    vocab_words = [str(v.get("en") or "").strip() for v in vocab if str(v.get("en") or "").strip()]
    sent_texts = [str(s.get("en") or "").strip() for s in sentences if str(s.get("en") or "").strip()]
    sent_zh_texts = [str(s.get("zh") or "").strip() for s in sentences if str(s.get("zh") or "").strip()]
    used = [
        w for w in vocab_words
        if any(re.search(rf"\b{re.escape(w)}\b", s, flags=re.IGNORECASE) for s in sent_texts)
    ]
    unused = [w for w in vocab_words if w not in used]
    missing_zh = [str(v.get("en") or "").strip() for v in vocab if not str(v.get("zh") or "").strip()]
    missing_pos = [str(v.get("en") or "").strip() for v in vocab if not str(v.get("pos") or "").strip()]
    missing_sentence_en = [
        str(s.get("zh") or "").strip()
        for s in sentences
        if str(s.get("zh") or "").strip() and not str(s.get("en") or "").strip()
    ]
    missing_sentence_zh = [
        str(s.get("en") or "").strip()
        for s in sentences
        if str(s.get("en") or "").strip() and not str(s.get("zh") or "").strip()
    ]
    mixed_sentence_zh = [
        str(s.get("zh") or "").strip()
        for s in sentences
        if re.search(r"[A-Za-z]", str(s.get("zh") or "")) and re.search(r"[\u4e00-\u9fff]", str(s.get("zh") or ""))
    ]
    return {
        "vocab_count": len(vocab_words),
        "sentence_count": len(sent_texts),
        "sentence_zh_count": len(sent_zh_texts),
        "vocab_seen_in_sentences": used,
        "vocab_not_seen_in_sentences": unused,
        "missing_zh": missing_zh,
        "missing_pos": missing_pos,
        "missing_sentence_en": missing_sentence_en,
        "missing_sentence_zh": missing_sentence_zh,
        "mixed_sentence_zh": mixed_sentence_zh,
        "coverage_ratio": round(len(used) / max(1, len(vocab_words)), 3),
    }




def _map_uploaded_lesson_media_ref(
    raw: str,
    *,
    card_url_by_stem: Dict[str, str],
    audio_url_by_rel: Dict[str, str],
) -> str:
    value = str(raw or '').strip()
    if not value or value.startswith(("http://", "https://", "data:")):
        return value
    path = Path(value)
    if path.parts and path.parts[0] == "cards":
        return card_url_by_stem.get(path.stem, value)
    if path.parts and path.parts[0] == "audio":
        rel = Path(*path.parts[1:]).as_posix()
        return audio_url_by_rel.get(rel, value)
    return value




from .tag_s_env import (
    tag_s_output_root,
    tag_s_deploy_enabled as _tag_s_deploy_enabled,
    tag_s_remote_root as _tag_s_remote_root_from_env,
    tag_s_public_base as _tag_s_public_base_from_env,
)


def deploy_tag_games_for_publish(
    tag_games: List[Dict[str, Any]],
    *,
    log_func=None,
) -> List[Dict[str, Any]]:
    """Optionally deploy standalone tag_s bundles to the public website.

    This is separate from inline lesson embedding. Inline lesson rendering works
    from the lesson payload itself. Standalone /en/tag_s/... pages require an
    explicit file deployment step, which earlier pipeline versions did not do at
    all.
    """
    if not _tag_s_deploy_enabled():
        return tag_games

    remote_root = _tag_s_remote_root_from_env()
    public_base = _tag_s_public_base_from_env()
    if not remote_root:
        if log_func:
            log_func("[tag_s] deploy skipped: no TAGS_REMOTE_ROOT/SFTP_TAGS_REMOTE_ROOT configured")
        return tag_games

    try:
        from skyed.deploy_sftp import _connect, _ensure_remote_dir, load_sftp_config_from_env
    except Exception as exc:
        if log_func:
            log_func(f"[tag_s] deploy skipped: SFTP helper import failed: {exc}")
        return tag_games

    try:
        cfg = load_sftp_config_from_env()
    except Exception as exc:
        if log_func:
            log_func(f"[tag_s] deploy skipped: SFTP config unavailable: {exc}")
        return tag_games

    cfg.remote_root = remote_root
    uploaded: set[str] = set()

    def _iter_files(base: Path):
        for file_path in sorted(base.rglob('*')):
            if file_path.is_file():
                yield file_path, file_path.relative_to(base).as_posix()

    try:
        client, sftp = _connect(cfg)
    except Exception as exc:
        if log_func:
            log_func(f"[tag_s] deploy skipped: SFTP connect failed: {exc}")
        return tag_games

    try:
        out: List[Dict[str, Any]] = []
        for game in tag_games or []:
            if not isinstance(game, dict):
                continue
            cloned = dict(game)
            local_root_raw = str(cloned.get('local_root') or '').strip()
            tag = str(cloned.get('tag') or '').strip()
            game_id = str(cloned.get('game_id') or '').strip()
            if not local_root_raw or not tag or not game_id:
                out.append(cloned)
                continue
            local_root = Path(local_root_raw)
            if not local_root.exists() or not (local_root / 'index.html').exists() or not (local_root / 'game.json').exists():
                out.append(cloned)
                continue
            remote_dir = cfg.remote_root.rstrip('/') + f"/{tag}/{game_id}"
            try:
                _ensure_remote_dir(sftp, remote_dir)
                for lp, rel in _iter_files(local_root):
                    rpath = remote_dir + '/' + rel
                    _ensure_remote_dir(sftp, rpath.rsplit('/', 1)[0])
                    key = f"{local_root.resolve()}::{rel}"
                    if key not in uploaded:
                        sftp.put(str(lp), rpath)
                        uploaded.add(key)
                cloned['url'] = (public_base + f"/{tag}/{game_id}/index.html") if public_base else (remote_dir + '/index.html')
                cloned['deployed'] = True
                if log_func:
                    log_func(f"[tag_s] deployed: {tag}/{game_id}")
            except Exception as exc:
                cloned['deploy_error'] = str(exc)
                if log_func:
                    log_func(f"[tag_s] deploy failed for {tag}/{game_id}: {exc}")
            out.append(cloned)
        return out
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass


def rewrite_tag_game_media_urls(
    tag_games: List[Dict[str, Any]],
    *,
    lesson_root: Path,
    upload_media_func,
    wp_base: str,
    wp_user: str,
    wp_pass: str,
    card_url_by_stem: Dict[str, str],
    audio_url_by_rel: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Rewrite embedded tag_s media paths to public WordPress URLs.

    This keeps inline lesson embedding independent from any separate public
    /tag_s deployment. Standalone tag_s packs can still be deployed later, but
    lesson pages no longer depend on that path existing.
    """
    lesson_root = Path(lesson_root)
    uploaded_cache: Dict[str, str] = {}

    def upload_local_file(abs_path: Path) -> str:
        key = str(abs_path.resolve())
        if key in uploaded_cache:
            return uploaded_cache[key]
        result = upload_media_func(wp_base, wp_user, wp_pass, abs_path)
        url = (result or {}).get('source_url') or ''
        if url:
            uploaded_cache[key] = url
        return url

    def rewrite_value(raw: str, bundle_root: Path | None = None) -> str:
        value = str(raw or '').strip()
        if not value or value.startswith(("http://", "https://", "data:")):
            return value
        mapped = _map_uploaded_lesson_media_ref(value, card_url_by_stem=card_url_by_stem, audio_url_by_rel=audio_url_by_rel)
        if mapped != value:
            return mapped
        rel_path = Path(value)
        candidates = []
        if bundle_root is not None:
            candidates.append(bundle_root / rel_path)
        candidates.append(lesson_root / rel_path)
        for candidate in candidates:
            try:
                if candidate.exists() and candidate.is_file():
                    url = upload_local_file(candidate)
                    if url:
                        return url
            except Exception:
                continue
        return value

    def rewrite_payload(payload: Dict[str, Any], bundle_root: Path | None) -> Dict[str, Any]:
        data = copy.deepcopy(payload)
        meta = data.get('meta') if isinstance(data.get('meta'), dict) else None
        if isinstance(meta, dict):
            for key in ('thumbnail', 'cover_image', 'sheet_image'):
                if key in meta:
                    meta[key] = rewrite_value(meta.get(key, ''), bundle_root)
        for item in data.get('items', []) or []:
            if not isinstance(item, dict):
                continue
            for key in ('image', 'thumbnail', 'audio', 'audio_back', 'audio_a', 'audio_b'):
                if key in item:
                    item[key] = rewrite_value(item.get(key, ''), bundle_root)
        return data

    out: List[Dict[str, Any]] = []
    for game in tag_games or []:
        if not isinstance(game, dict):
            continue
        cloned = dict(game)
        payload = cloned.get('data') if isinstance(cloned.get('data'), dict) else None
        local_root_raw = str(cloned.get('local_root') or '').strip()
        bundle_root = Path(local_root_raw) if local_root_raw else None
        if payload:
            cloned['data'] = rewrite_payload(payload, bundle_root)
        out.append(cloned)
    return out


def rewrite_practice_media_urls(
    practice: Dict,
    card_url_by_stem: Dict[str, str],
    audio_url_by_rel: Dict[str, str],
) -> Dict:
    """Map local cards/audio references inside practice JSON to uploaded WP media URLs."""
    if not isinstance(practice, dict):
        return practice

    def map_img(value: str) -> str:
        raw = str(value or "").strip()
        if not raw or raw.startswith(("http://", "https://")):
            return raw
        path = Path(raw)
        if path.parts and path.parts[0] == "cards":
            return card_url_by_stem.get(path.stem, raw)
        return raw

    def map_audio(value: str) -> str:
        raw = str(value or "").strip()
        if not raw or raw.startswith(("http://", "https://")):
            return raw
        path = Path(raw)
        if path.parts and path.parts[0] == "audio":
            rel = Path(*path.parts[1:]).as_posix()
            return audio_url_by_rel.get(rel, raw)
        return raw

    for q in practice.get("questions", []) or []:
        if not isinstance(q, dict):
            continue
        if "prompt_image" in q:
            q["prompt_image"] = map_img(q.get("prompt_image", ""))
        if "prompt_audio" in q:
            q["prompt_audio"] = map_audio(q.get("prompt_audio", ""))
        for choice in q.get("choices", []) or []:
            if isinstance(choice, dict):
                if "img" in choice:
                    choice["img"] = map_img(choice.get("img", ""))
                if "audio" in choice:
                    choice["audio"] = map_audio(choice.get("audio", ""))
    return practice
