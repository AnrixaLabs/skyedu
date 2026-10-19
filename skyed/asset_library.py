from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .image_semantics import clean_visual_label


INDEX_REL_PATH = Path("manifests/library_index.json")


@dataclass(slots=True)
class AssetRecord:
    asset_id: str
    asset_type: str
    visual_class: str
    target: str
    target_norm: str
    pos: str = ""
    zh: str = ""
    theme: str = "fun_mission"
    category: str = ""
    usage: List[str] | None = None
    tags: List[str] | None = None
    image_relpath: str = ""
    metadata_relpath: str = ""
    approved: bool = True
    width: int = 0
    height: int = 0
    source_backend: str = ""
    source_status: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["usage"] = list(self.usage or [])
        data["tags"] = list(self.tags or [])
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssetRecord":
        return cls(
            asset_id=str(data.get("asset_id") or ""),
            asset_type=str(data.get("asset_type") or "vocabulary"),
            visual_class=str(data.get("visual_class") or "scene"),
            target=str(data.get("target") or ""),
            target_norm=str(data.get("target_norm") or normalize_target(str(data.get("target") or ""))),
            pos=str(data.get("pos") or ""),
            zh=str(data.get("zh") or ""),
            theme=str(data.get("theme") or "fun_mission"),
            category=str(data.get("category") or ""),
            usage=list(data.get("usage") or []),
            tags=list(data.get("tags") or []),
            image_relpath=str(data.get("image_relpath") or ""),
            metadata_relpath=str(data.get("metadata_relpath") or ""),
            approved=bool(data.get("approved", True)),
            width=int(data.get("width") or 0),
            height=int(data.get("height") or 0),
            source_backend=str(data.get("source_backend") or ""),
            source_status=str(data.get("source_status") or ""),
        )


def normalize_target(text: str) -> str:
    clean = clean_visual_label(text or "")
    clean = clean.strip().lower()
    clean = re.sub(r"\s+", "_", clean)
    clean = re.sub(r"[^a-z0-9_\-]+", "", clean)
    return clean or "item"


def default_asset_library_root(project_root: str | Path | None = None) -> Path:
    env = str(__import__("os").environ.get("SKYED_LOCAL_ASSET_LIBRARY_DIR", "")).strip()
    if env:
        root = Path(env)
    elif project_root is not None:
        root = Path(project_root) / "asset_library"
    else:
        root = Path("asset_library")
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifests").mkdir(parents=True, exist_ok=True)
    return root


def index_path(root: str | Path) -> Path:
    return Path(root) / INDEX_REL_PATH


def load_index(root: str | Path) -> List[AssetRecord]:
    path = index_path(root)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [AssetRecord.from_dict(x) for x in data if isinstance(x, dict)]
    except Exception:
        return []


def save_index(root: str | Path, records: Iterable[AssetRecord]) -> Path:
    path = index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [r.to_dict() for r in records]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _asset_subdir(record: AssetRecord) -> Path:
    asset_type = (record.asset_type or "vocabulary").strip().lower()
    visual_class = (record.visual_class or "scene").strip().lower()
    pos = normalize_target(record.pos or record.category or "misc")
    theme = normalize_target(record.theme or "fun_mission")
    if asset_type == "background":
        cat = normalize_target(record.category or "general")
        return Path("background") / visual_class / cat / theme
    if asset_type == "sentence_scene":
        return Path("sentence_scene") / visual_class / pos / theme
    return Path("vocabulary") / visual_class / pos / theme


def build_asset_id(asset_type: str, visual_class: str, pos: str, target: str, theme: str, version: str = "v1") -> str:
    parts = [asset_type or "vocabulary", visual_class or "scene", pos or "misc", target or "item", theme or "fun_mission", version]
    return "__".join(normalize_target(p) for p in parts)


def make_record(
    *,
    root: str | Path,
    asset_type: str,
    visual_class: str,
    target: str,
    pos: str = "",
    zh: str = "",
    theme: str = "fun_mission",
    category: str = "",
    usage: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    width: int = 0,
    height: int = 0,
    source_backend: str = "",
    source_status: str = "",
) -> AssetRecord:
    target_norm = normalize_target(target)
    rec = AssetRecord(
        asset_id=build_asset_id(asset_type, visual_class, pos or category or "misc", target_norm, theme),
        asset_type=asset_type,
        visual_class=visual_class,
        target=target,
        target_norm=target_norm,
        pos=pos,
        zh=zh,
        theme=theme,
        category=category,
        usage=list(usage or []),
        tags=list(tags or []),
        approved=True,
        width=width,
        height=height,
        source_backend=source_backend,
        source_status=source_status,
    )
    subdir = _asset_subdir(rec)
    rec.image_relpath = str(subdir / f"{rec.asset_id}.png")
    rec.metadata_relpath = str(subdir / f"{rec.asset_id}.json")
    return rec


def upsert_record(root: str | Path, record: AssetRecord) -> Path:
    root = Path(root)
    records = load_index(root)
    out: List[AssetRecord] = []
    replaced = False
    for existing in records:
        if existing.asset_id == record.asset_id:
            out.append(record)
            replaced = True
        else:
            out.append(existing)
    if not replaced:
        out.append(record)
    save_index(root, out)
    meta_path = root / record.metadata_relpath
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return meta_path


def rebuild_index(root: str | Path) -> Path:
    root = Path(root)
    records: List[AssetRecord] = []
    for meta in root.rglob("*.json"):
        if meta == index_path(root):
            continue
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and data.get("asset_id") and data.get("image_relpath"):
            records.append(AssetRecord.from_dict(data))
    return save_index(root, records)


def find_best_asset(
    root: str | Path,
    *,
    target: str,
    pos: str = "",
    visual_class: str = "",
    theme: str = "",
    asset_type: str = "vocabulary",
    usage: str = "",
) -> Optional[AssetRecord]:
    target_norm = normalize_target(target)
    pos_norm = normalize_target(pos)
    visual_class = (visual_class or "").strip().lower()
    theme_norm = normalize_target(theme)
    asset_type = (asset_type or "vocabulary").strip().lower()
    best: Optional[AssetRecord] = None
    best_score = -1
    for rec in load_index(root):
        if not rec.approved:
            continue
        image_path = Path(root) / rec.image_relpath
        if not image_path.exists():
            continue
        score = 0
        if (rec.asset_type or "vocabulary").strip().lower() == asset_type:
            score += 80
        elif asset_type == "sentence_scene" and rec.asset_type == "vocabulary":
            score += 20
        if rec.target_norm == target_norm:
            score += 100
        elif target_norm and (target_norm in rec.target_norm or rec.target_norm in target_norm):
            score += 30
        else:
            continue
        if visual_class and (rec.visual_class or "").strip().lower() == visual_class:
            score += 40
        if pos_norm and normalize_target(rec.pos or rec.category or "") == pos_norm:
            score += 20
        if theme_norm and normalize_target(rec.theme or "") == theme_norm:
            score += 20
        if usage and usage in (rec.usage or []):
            score += 10
        if best is None or score > best_score:
            best = rec
            best_score = score
    return best if best_score >= 100 else None


def copy_record_image(root: str | Path, record: AssetRecord, target_path: str | Path) -> Path:
    root = Path(root)
    src = root / record.image_relpath
    dst = Path(target_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def _candidate_target_keys(target: str) -> List[str]:
    base = normalize_target(target)
    compact = re.sub(r"[^a-z0-9]+", "", (target or "").strip().lower()) or base.replace("_", "")
    parts = [p for p in re.split(r"[_\-\s]+", base) if p]
    variants = {base, compact, base.replace("_", "-"), base.replace("_", " "), "_".join(parts), "-".join(parts), "".join(parts)}
    return [v for v in variants if v]


def find_loose_file_asset(
    root: str | Path,
    *,
    target: str,
    folders: Iterable[str] = ("Pictures", "Flashcards"),
) -> Optional[Path]:
    root = Path(root)
    if not root.exists():
        return None
    keys = {k.lower() for k in _candidate_target_keys(target)}
    candidates: List[Path] = []
    for folder in folders:
        base = root / str(folder)
        if not base.exists():
            continue
        for p in base.rglob('*'):
            if not p.is_file() or p.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            stem_norm = normalize_target(p.stem)
            stem_compact = re.sub(r"[^a-z0-9]+", "", p.stem.strip().lower())
            if stem_norm.lower() in keys or stem_compact in keys:
                candidates.append(p)
    if not candidates:
        return None
    candidates.sort(key=lambda p: (0 if p.parent.name.lower() == 'pictures' else 1, len(p.stem), str(p).lower()))
    return candidates[0]
