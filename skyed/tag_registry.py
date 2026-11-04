from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Dict, List

from .tag_s_env import tag_s_output_root


def _default_tag_s_root(project_root: Path | None = None, game_out_root: Path | None = None) -> Path:
    if game_out_root is not None:
        return Path(game_out_root)
    return tag_s_output_root(project_root or Path.cwd())


def safe_tag(text: str) -> str:
    t = (text or "").strip().lower().replace(" ", "-")
    return "".join(ch for ch in t if ch.isalnum() or ch in "-_ ").replace(" ", "-").strip("-_")


def _load_game_payload(game_dir: Path) -> Dict[str, Any] | None:
    game_json = game_dir / "game.json"
    if not game_json.exists():
        return None
    try:
        payload = json.loads(game_json.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _read_game_entry_from_local_root(local_root: str | Path, *, base: str = "") -> Dict[str, Any] | None:
    game_dir = Path(local_root).expanduser()
    if not game_dir.exists() or not game_dir.is_dir():
        return None
    tag_norm = safe_tag(game_dir.parent.name)
    if not tag_norm:
        return None
    return _read_game_entry(tag_norm, game_dir, base=base)


def _read_game_entry(tag_norm: str, game_dir: Path, *, base: str = "") -> Dict[str, Any] | None:
    index_path = game_dir / "index.html"
    if not index_path.exists():
        return None
    game_id = game_dir.name
    game_title = f"{tag_norm} · {game_id.replace('_', ' ').replace('-', ' ').title()}"
    renderer = ""
    payload = _load_game_payload(game_dir)
    if payload:
        meta = payload.get("meta") if isinstance(payload, dict) else {}
        if isinstance(meta, dict):
            game_title = str(meta.get("title") or game_title).strip() or game_title
            renderer = str(meta.get("renderer") or "").strip()
    url = f"{base}/{tag_norm}/{game_id}/index.html" if base else ""
    category = ""
    category_title = ""
    thumbnail = ""
    description = ""
    style = ""
    imported_from: List[str] = []
    source_focus = ""
    item_count = 0
    if payload:
        meta = payload.get("meta") if isinstance(payload, dict) else {}
        if isinstance(meta, dict):
            category = str(meta.get("category") or meta.get("category_slug") or "").strip()
            category_title = str(meta.get("category_title") or category.replace("-", " ").replace("_", " ").title() or "").strip()
            thumbnail = str(meta.get("thumbnail") or "").strip()
            description = str(meta.get("description") or "").strip()
            style = str(meta.get("style") or "").strip()
            imported_from = [str(x).strip() for x in list(meta.get("imported_from") or []) if str(x).strip()]
            source_focus = str(meta.get("source_focus") or "").strip()
            item_count = int(meta.get("item_count") or len(list(payload.get("items") or [])) or 0)
    out = {
        "tag": tag_norm,
        "game_id": game_id,
        "title": game_title,
        "renderer": renderer,
        "url": url,
        "local_root": str(game_dir.resolve()),
        "category": category,
        "category_title": category_title,
        "thumbnail": thumbnail,
        "description": description,
        "style": style,
        "imported_from": imported_from,
        "source_focus": source_focus,
        "item_count": item_count,
    }
    if payload:
        out["data"] = payload
    return out


def list_all_tag_games(*, project_root: Path | None = None, tags_public_base: str = "", game_out_root: Path | None = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    project_root = project_root or Path.cwd()
    game_out_root = _default_tag_s_root(project_root=project_root, game_out_root=game_out_root)
    base = (tags_public_base or os.getenv("TAGS_PUBLIC_BASE", "")).rstrip("/")
    if not game_out_root.exists():
        return out
    for tag_dir in sorted([p for p in game_out_root.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
        tag_norm = safe_tag(tag_dir.name)
        if not tag_norm:
            continue
        for game_dir in sorted([p for p in tag_dir.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
            entry = _read_game_entry(tag_norm, game_dir, base=base)
            if entry:
                out.append(entry)
    return out

def discover_tag_games(tags: List[str], *, project_root: Path | None = None, tags_public_base: str = "", game_out_root: Path | None = None, theme: str = "") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    project_root = project_root or Path.cwd()
    game_out_root = _default_tag_s_root(project_root=project_root, game_out_root=game_out_root)
    base = (tags_public_base or os.getenv("TAGS_PUBLIC_BASE", "")).rstrip("/")
    for tag in tags:
        tag_norm = safe_tag(tag)
        if not tag_norm:
            continue
        tag_dir = game_out_root / tag_norm
        if not tag_dir.exists():
            continue
        for game_dir in sorted([p for p in tag_dir.iterdir() if p.is_dir()]):
            index_path = game_dir / "index.html"
            if not index_path.exists():
                continue
            entry = _read_game_entry(tag_norm, game_dir, base=base)
            if entry:
                out.append(entry)
    return out


def get_tag_game_entry(tag: str, game_id: str, *, project_root: Path | None = None, tags_public_base: str = "", game_out_root: Path | None = None) -> Dict[str, Any] | None:
    project_root = project_root or Path.cwd()
    tag_norm = safe_tag(tag)
    game_norm = safe_tag(game_id)
    if not tag_norm or not game_norm:
        return None
    game_out_root = _default_tag_s_root(project_root=project_root, game_out_root=game_out_root)
    game_dir = game_out_root / tag_norm / game_norm
    if not game_dir.exists() or not game_dir.is_dir():
        return None
    base = (tags_public_base or os.getenv("TAGS_PUBLIC_BASE", "")).rstrip("/")
    return _read_game_entry(tag_norm, game_dir, base=base)


def hydrate_tag_game_entries(entries: List[Dict[str, Any]], *, project_root: Path | None = None, tags_public_base: str = "", game_out_root: Path | None = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    base = (tags_public_base or os.getenv("TAGS_PUBLIC_BASE", "")).rstrip("/")
    for item in entries or []:
        if not isinstance(item, dict):
            continue
        tag = str(item.get("tag") or "").strip()
        game_id = str(item.get("game_id") or "").strip()
        local_root = str(item.get("local_root") or "").strip()
        if not tag or not game_id:
            if local_root:
                resolved = _read_game_entry_from_local_root(local_root, base=base)
                if isinstance(resolved, dict):
                    tag = str(resolved.get("tag") or "").strip()
                    game_id = str(resolved.get("game_id") or "").strip()
                    item = {**item, **resolved}
            if not tag or not game_id:
                continue
        key = (tag, game_id)
        if key in seen:
            continue
        seen.add(key)
        merged: Dict[str, Any] = dict(item)
        resolved = None
        if local_root:
            resolved = _read_game_entry_from_local_root(local_root, base=base)
        if not isinstance(resolved, dict):
            resolved = get_tag_game_entry(tag, game_id, project_root=project_root, tags_public_base=tags_public_base, game_out_root=game_out_root)
        if isinstance(resolved, dict):
            merged.update(resolved)
        out.append(merged)
    return out
