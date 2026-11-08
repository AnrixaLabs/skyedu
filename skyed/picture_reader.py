from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .ocr_utils import (
    configure_pytesseract,
    preferred_ocr_backends,
    resolve_ocr_device,
    tesseract_ready,
)

try:  # pragma: no cover - optional at runtime
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore


_EASYOCR_READERS: Dict[str, object] = {}
_PADDLE_READERS: Dict[str, object] = {}


@dataclass
class OCRSpan:
    text: str
    x1: float
    y1: float
    x2: float
    y2: float
    score: float = 1.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)


@dataclass
class ReaderLine:
    en: str = ""
    zh: str = ""
    order: int = 0


def _split_manual_numbered_items(text: str) -> List[str]:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    matches = list(re.finditer(r"(?ms)(?:^|\n)\s*(\d+)\s*[.)]?\s*(.+?)(?=(?:\n\s*\d+\s*[.)]?\s*)|\Z)", normalized))
    if matches:
        out: List[str] = []
        for match in matches:
            full_item = _clean_line_text(match.group(0))
            if full_item:
                out.append(full_item)
        return out
    return [_clean_line_text(line) for line in normalized.split("\n") if _clean_line_text(line)]


def _extract_en_display_and_tts(text: str) -> Tuple[str, str, str, str]:
    clean = _clean_line_text(text)
    if not clean:
        return "", "", "", ""

    colon_idx = clean.find(":")
    if colon_idx <= 0:
        return clean, "", "", clean

    prefix_raw = _clean_line_text(clean[:colon_idx])
    body = _clean_line_text(clean[colon_idx + 1 :])
    if not prefix_raw or not body:
        return clean, "", "", clean

    number = ""
    speaker = prefix_raw
    number_match = re.match(r"^(?P<number>\d{1,3})\s*[.)]?\s*(?P<speaker>.+)$", prefix_raw)
    if number_match:
        number = _clean_line_text(number_match.group("number") or "")
        speaker = _clean_line_text(number_match.group("speaker") or "")

    if not speaker or not re.search(r"[A-Za-z]", speaker):
        return clean, "", "", clean
    if re.search(r"\d", speaker):
        return clean, "", "", clean
    if len(speaker) > 72 or len(speaker.split()) > 10:
        return clean, "", "", clean
    if re.search(r"[^A-Za-z /&+.,'\-]", speaker):
        return clean, "", "", clean

    if number:
        display_prefix = f"{number}. {speaker}:"
    else:
        display_prefix = f"{speaker}:"
    return clean, display_prefix, speaker, body


def _build_reader_sentence_entry(en: str = "", zh: str = "", *, order: int = 0) -> Dict[str, Any]:
    en_clean = _clean_line_text(en)
    zh_clean = _clean_line_text(zh)
    display_en, display_prefix_en, speaker_en, spoken_en = _extract_en_display_and_tts(en_clean) if en_clean else ("", "", "", "")
    entry: Dict[str, Any] = {"en": display_en or en_clean, "zh": zh_clean}
    if order:
        entry["order"] = int(order)
    if display_prefix_en:
        entry["display_prefix_en"] = display_prefix_en
    if spoken_en:
        entry["display_body_en"] = spoken_en
    if speaker_en:
        entry["speaker_en"] = speaker_en
    if spoken_en:
        entry["tts_en"] = spoken_en
    elif en_clean:
        entry["tts_en"] = en_clean
    if zh_clean:
        entry["tts_zh"] = zh_clean
    return entry


def parse_picture_manual_text(
    manual_text: str,
    *,
    title: str = "",
    tags: Optional[List[str]] = None,
    source_image: str | Path | None = None,
) -> Dict[str, Any]:
    items = _split_manual_numbered_items(manual_text)
    sentences: List[Dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        entry = _build_reader_sentence_entry(item, "", order=idx)
        if entry.get("en") or entry.get("zh"):
            sentences.append(entry)

    image_label = Path(str(source_image)).stem.replace("_", " ").replace("-", " ").strip() if source_image else ""
    page_title = _norm(title) or image_label or "Picture Reader"
    spoken_en_lines = [str(item.get("tts_en") or item.get("en") or "").strip() for item in sentences if str(item.get("tts_en") or item.get("en") or "").strip()]
    spoken_zh_lines = [str(item.get("tts_zh") or item.get("zh") or "").strip() for item in sentences if str(item.get("tts_zh") or item.get("zh") or "").strip()]

    return {
        "title": page_title,
        "tags": tags or ["picture_reader"],
        "vocab": [],
        "sentences": sentences,
        "qa": [],
        "reading_block": {"title": page_title, "text": "\n".join(spoken_en_lines).strip()},
        "listening_block": {"title": page_title, "text": "\n".join(spoken_zh_lines).strip()},
        "comprehension_questions": [],
        "picture_reader": {
            "source_image": str(source_image or ""),
            "source_image_local": str(source_image or ""),
            "input_mode": "manual_text",
            "ocr_backend": "manual_text",
            "ocr_variant": "manual_text",
            "ocr_device": "manual",
            "ocr_attempts": [],
            "render_style": "single_flow_reader",
            "grouped_lines": items,
            "lines": sentences,
        },
    }


@dataclass
class OCRCandidate:
    backend: str
    spans: List[OCRSpan]
    filtered_spans: List[OCRSpan]
    grouped_lines: List[str]
    paired_lines: List[ReaderLine]
    score: float
    variant: str = "default"
    device: str = "cpu"
    mean_confidence: float = 0.0
    error: str = ""


def _norm(s: str) -> str:
    s = (s or "").strip()
    s = s.replace("：", ":")
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _has_zh(s: str) -> bool:
    return bool(re.search(r"[一-鿿]", s or ""))


def _looks_en(s: str) -> bool:
    return bool(re.search(r"[A-Za-z]", s or "")) and not _has_zh(s)


def _base_rgb_image(image_path: Path) -> Image.Image:
    with Image.open(image_path) as raw:
        return ImageOps.exif_transpose(raw.convert("RGB"))


def _enhanced_gray_image(img: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray)
    gray = ImageEnhance.Sharpness(gray).enhance(2.4)
    gray = ImageEnhance.Contrast(gray).enhance(1.85)
    gray = gray.filter(ImageFilter.MedianFilter(size=3))
    w, h = gray.size
    if max(w, h) < 2400:
        gray = gray.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
    return gray


def _deskew_binary(arr: np.ndarray) -> np.ndarray:
    if cv2 is None:
        return arr
    coords = np.column_stack(np.where(arr < 250))
    if coords.shape[0] < 120:
        return arr
    rect = cv2.minAreaRect(coords.astype(np.float32))
    angle = float(rect[-1])
    if angle < -45.0:
        angle = 90.0 + angle
    angle = -angle
    if abs(angle) < 0.35 or abs(angle) > 12.0:
        return arr
    h, w = arr.shape[:2]
    center = (w / 2.0, h / 2.0)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(arr, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=255)


def _prepare_ocr_variants(image_path: Path) -> List[Tuple[str, Image.Image]]:
    base = _base_rgb_image(image_path)
    gray = _enhanced_gray_image(base)
    variants: List[Tuple[str, Image.Image]] = [
        ("original_rgb", base),
        ("enhanced", gray),
    ]
    if cv2 is None:
        return variants

    gray_np = np.array(gray, dtype=np.uint8)
    blur = cv2.GaussianBlur(gray_np, (3, 3), 0)
    _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    adaptive = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)
    deskewed = _deskew_binary(otsu)
    variants.extend([
        ("binary_otsu", Image.fromarray(otsu)),
        ("adaptive", Image.fromarray(adaptive)),
        ("deskewed", Image.fromarray(deskewed)),
    ])
    return variants


def _variant_array(img: Image.Image) -> np.ndarray:
    return np.array(img.convert("RGB"))


def _get_paddle_reader(device: str):
    key = device
    cached = _PADDLE_READERS.get(key)
    if cached is not None:
        return cached
    from paddleocr import PaddleOCR  # type: ignore

    try:
        reader = PaddleOCR(use_angle_cls=True, lang="ch", use_gpu=(device == "cuda"), show_log=False)
    except TypeError:
        reader = PaddleOCR(use_angle_cls=True, lang="ch", use_gpu=(device == "cuda"))
    _PADDLE_READERS[key] = reader
    return reader


def _get_easyocr_reader(device: str):
    key = device
    cached = _EASYOCR_READERS.get(key)
    if cached is not None:
        return cached
    import easyocr  # type: ignore

    reader = easyocr.Reader(["en", "ch_sim"], gpu=(device == "cuda"), verbose=False)
    _EASYOCR_READERS[key] = reader
    return reader


def _ocr_with_paddle(img: Image.Image, device: str) -> List[OCRSpan]:
    ocr = _get_paddle_reader(device)
    result = ocr.ocr(_variant_array(img), cls=True)
    spans: List[OCRSpan] = []
    for page in result or []:
        for item in page or []:
            if len(item) != 2:
                continue
            box, info = item
            if not box or not info:
                continue
            text = _norm(info[0] if isinstance(info, (list, tuple)) and len(info) >= 1 else "")
            score = float(info[1] if isinstance(info, (list, tuple)) and len(info) >= 2 else 1.0)
            xs = [float(p[0]) for p in box]
            ys = [float(p[1]) for p in box]
            if text:
                spans.append(OCRSpan(text=text, x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys), score=score))
    return spans


def _ocr_with_easyocr(img: Image.Image, device: str) -> List[OCRSpan]:
    reader = _get_easyocr_reader(device)
    result = reader.readtext(_variant_array(img), detail=1, paragraph=False)
    spans: List[OCRSpan] = []
    for item in result or []:
        if len(item) < 3:
            continue
        box, text, score = item[0], _norm(item[1]), float(item[2])
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        if text:
            spans.append(OCRSpan(text=text, x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys), score=score))
    return spans


def _tesseract_languages() -> str:
    pytesseract, _, _ = configure_pytesseract()
    if pytesseract is None:
        return "eng"

    try:
        langs = {str(x).strip() for x in (pytesseract.get_languages(config="") or []) if str(x).strip()}
    except Exception:
        langs = set()
    preferred = [lang for lang in ("eng", "HanS", "chi_sim", "chi_tra") if not langs or lang in langs]
    if "eng" not in preferred:
        preferred.insert(0, "eng")
    ordered: List[str] = []
    seen = set()
    for lang in preferred:
        if lang and lang not in seen:
            ordered.append(lang)
            seen.add(lang)
    return "+".join(ordered) or "eng"


def _ocr_with_tesseract(img: Image.Image, *, psm: int = 6) -> List[OCRSpan]:
    pytesseract, _, note = configure_pytesseract()
    if pytesseract is None:
        raise RuntimeError(note)
    ok, readiness = tesseract_ready()
    if not ok:
        raise RuntimeError(readiness)

    lang = _tesseract_languages()
    data = pytesseract.image_to_data(
        img,
        lang=lang,
        config=f"--oem 1 --psm {int(psm)}",
        output_type=pytesseract.Output.DICT,
    )
    spans: List[OCRSpan] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = _norm(data["text"][i])
        if not text:
            continue
        x = float(data["left"][i])
        y = float(data["top"][i])
        w = float(data["width"][i])
        h = float(data["height"][i])
        conf_raw = str(data.get("conf", ["0"])[i])
        try:
            score = max(0.0, min(1.0, float(conf_raw) / 100.0))
        except Exception:
            score = 0.5
        spans.append(OCRSpan(text=text, x1=x, y1=y, x2=x + w, y2=y + h, score=score))
    return spans


def _filter_spans(spans: Iterable[OCRSpan]) -> List[OCRSpan]:
    spans = [s for s in spans if _norm(s.text)]
    if not spans:
        return []
    max_x = max(s.x2 for s in spans)
    max_y = max(s.y2 for s in spans)
    kept: List[OCRSpan] = []
    for s in spans:
        txt = _norm(s.text)
        compact = re.sub(r"\s+", "", txt)
        lower = compact.lower()
        if not txt:
            continue
        if lower in {"微信", "wx", "weixin", "qr"}:
            continue
        if re.fullmatch(r"[\/_|~`.,:;\-–—]+", txt):
            continue
        if s.x1 > max_x * 0.84 and s.width < max_x * 0.14 and len(re.sub(r"\W+", "", txt)) <= 4:
            continue
        if s.y1 > max_y * 0.94 and len(re.sub(r"\W+", "", txt)) <= 8 and s.score < 0.9:
            continue
        if s.score < 0.12 and len(compact) <= 2:
            continue
        kept.append(s)
    return kept


def _gap_join(parts: List[OCRSpan]) -> str:
    if not parts:
        return ""
    parts = sorted(parts, key=lambda s: s.x1)
    out = parts[0].text
    prev = parts[0]
    for cur in parts[1:]:
        gap = cur.x1 - prev.x2
        gap_ratio = gap / max(prev.height, cur.height, 1.0)
        prev_has_zh = _has_zh(prev.text)
        cur_has_zh = _has_zh(cur.text)
        if prev_has_zh and cur_has_zh:
            joiner = " " if gap_ratio > 0.95 else ""
        else:
            joiner = " " if gap_ratio > 0.18 else ""
        out += joiner + cur.text
        prev = cur
    return _norm(out)


def _clean_line_text(text: str) -> str:
    text = _norm(text)
    if not text:
        return ""
    if _has_zh(text):
        text = re.sub(r"(?<=[一-鿿])\s+(?=[一-鿿])", "", text)
    text = text.replace(" ,", ",").replace(" .", ".")
    text = text.replace(" ?", "?").replace(" !", "!")
    text = text.replace(" ;", ";").replace(" :", ":")
    text = re.sub(r"\s+([.,!?;:])", r"", text)
    return _norm(text)


def _drop_noise_lines(lines: List[str]) -> List[str]:
    out: List[str] = []
    for raw in lines:
        text = _clean_line_text(raw)
        compact = re.sub(r"\s+", "", text)
        low = compact.lower()
        if not compact:
            continue
        if low in {"fe", "ny", "wx", "qr", "mw", "iw"}:
            continue
        if re.fullmatch(r"[a-z]{1,2}", low) and low not in {"a", "i"}:
            continue
        if re.fullmatch(r"[A-Z]{2,3}", compact):
            continue
        if re.fullmatch(r"[\/_|~`.,:;\-–—()\[\]{}]+", compact):
            continue
        if len(compact) <= 2 and not _has_zh(compact) and not compact.isalpha():
            continue
        if out and compact == re.sub(r"\s+", "", out[-1]):
            continue
        out.append(text)
    return out


def _group_spans_to_lines(spans: Iterable[OCRSpan]) -> List[str]:
    ordered = sorted(_filter_spans(spans), key=lambda s: (s.cy, s.x1))
    groups: List[List[OCRSpan]] = []
    for span in ordered:
        compact = re.sub(r"\s+", "", span.text)
        if not compact:
            continue
        if len(compact) == 1 and not (compact.isalpha() or _has_zh(compact)):
            continue
        if not groups:
            groups.append([span])
            continue
        prev_group = groups[-1]
        prev_cy = sum(x.cy for x in prev_group) / len(prev_group)
        prev_h = max(16.0, max((x.height) for x in prev_group))
        if abs(span.cy - prev_cy) <= prev_h * 0.72:
            prev_group.append(span)
        else:
            groups.append([span])
    lines: List[str] = []
    for group in groups:
        text = _clean_line_text(_gap_join(group))
        if text:
            lines.append(text)
    return _drop_noise_lines(lines)


def _pair_bilingual_lines(lines: List[str]) -> List[ReaderLine]:
    out: List[ReaderLine] = []
    i = 0
    order = 1
    while i < len(lines):
        cur = _clean_line_text(lines[i])
        nxt = _clean_line_text(lines[i + 1]) if i + 1 < len(lines) else ""
        if _looks_en(cur) and _has_zh(nxt):
            out.append(ReaderLine(en=cur, zh=nxt, order=order))
            i += 2
        elif _has_zh(cur) and _looks_en(nxt):
            out.append(ReaderLine(en=nxt, zh=cur, order=order))
            i += 2
        else:
            en_val = cur if _looks_en(cur) else ""
            zh_val = cur if _has_zh(cur) else ""
            compact_en = re.sub(r"\s+", "", en_val)
            if compact_en.isupper() and len(compact_en) <= 3:
                en_val = ""
            out.append(ReaderLine(en=en_val, zh=zh_val, order=order))
            i += 1
        order += 1
    cleaned: List[ReaderLine] = []
    seen = set()
    for item in out:
        if not item.en and not item.zh:
            continue
        key = (re.sub(r"\s+", "", item.en).lower(), re.sub(r"\s+", "", item.zh))
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def _score_candidate(lines: List[str], pairs: List[ReaderLine], filtered_spans: List[OCRSpan]) -> float:
    bilingual_pairs = sum(1 for item in pairs if item.en and item.zh)
    en_only = sum(1 for item in pairs if item.en and not item.zh)
    zh_only = sum(1 for item in pairs if item.zh and not item.en)
    english_chars = sum(len(re.sub(r"\s+", "", item.en)) for item in pairs)
    zh_chars = sum(len(re.sub(r"\s+", "", item.zh)) for item in pairs)
    noise_penalty = sum(
        1
        for line in lines
        if re.fullmatch(r"[A-Z]{2,3}", re.sub(r"\s+", "", line)) or re.fullmatch(r"[\/_|~`.,:;\-–—()\[\]{}]+", line)
    )
    mean_conf = 0.0
    if filtered_spans:
        mean_conf = sum(max(0.0, min(1.0, span.score)) for span in filtered_spans) / len(filtered_spans)
    return (
        bilingual_pairs * 120.0
        + len(pairs) * 14.0
        + min(english_chars + zh_chars, 260) * 0.18
        + min(len(filtered_spans), 160) * 0.32
        + mean_conf * 18.0
        - abs(en_only - zh_only) * 8.0
        - noise_penalty * 25.0
    )


def _make_candidate(*, backend: str, device: str, variant: str, spans: List[OCRSpan]) -> OCRCandidate:
    filtered_spans = _filter_spans(spans)
    grouped_lines = _group_spans_to_lines(filtered_spans)
    paired_lines = _pair_bilingual_lines(grouped_lines)
    mean_conf = 0.0
    if filtered_spans:
        mean_conf = sum(max(0.0, min(1.0, span.score)) for span in filtered_spans) / len(filtered_spans)
    return OCRCandidate(
        backend=backend,
        device=device,
        variant=variant,
        spans=spans,
        filtered_spans=filtered_spans,
        grouped_lines=grouped_lines,
        paired_lines=paired_lines,
        mean_confidence=mean_conf,
        score=_score_candidate(grouped_lines, paired_lines, filtered_spans),
    )


def _run_backend(image_path: Path, backend: str, device: str) -> Tuple[OCRCandidate, List[Dict[str, Any]]]:
    variants = _prepare_ocr_variants(image_path)
    attempts: List[Dict[str, Any]] = []
    best: Optional[OCRCandidate] = None

    if backend == "easyocr":
        selected = [name for name in ("enhanced", "adaptive", "binary_otsu", "deskewed", "original_rgb")]
        variant_map = {name: img for name, img in variants if name in selected}
        for variant_name in selected:
            img = variant_map.get(variant_name)
            if img is None:
                continue
            candidate = _make_candidate(backend=backend, device=device, variant=variant_name, spans=_ocr_with_easyocr(img, device))
            attempts.append({
                "backend": backend,
                "variant": variant_name,
                "device": device,
                "ok": True,
                "score": round(candidate.score, 3),
                "mean_confidence": round(candidate.mean_confidence, 3),
                "raw_span_count": len(candidate.spans),
                "filtered_span_count": len(candidate.filtered_spans),
                "grouped_line_count": len(candidate.grouped_lines),
                "paired_line_count": len(candidate.paired_lines),
                "bilingual_pairs": sum(1 for item in candidate.paired_lines if item.en and item.zh),
            })
            if best is None or candidate.score > best.score:
                best = candidate
    elif backend == "paddle":
        selected = [name for name in ("original_rgb", "enhanced", "deskewed", "adaptive")]
        variant_map = {name: img for name, img in variants if name in selected}
        for variant_name in selected:
            img = variant_map.get(variant_name)
            if img is None:
                continue
            candidate = _make_candidate(backend=backend, device=device, variant=variant_name, spans=_ocr_with_paddle(img, device))
            attempts.append({
                "backend": backend,
                "variant": variant_name,
                "device": device,
                "ok": True,
                "score": round(candidate.score, 3),
                "mean_confidence": round(candidate.mean_confidence, 3),
                "raw_span_count": len(candidate.spans),
                "filtered_span_count": len(candidate.filtered_spans),
                "grouped_line_count": len(candidate.grouped_lines),
                "paired_line_count": len(candidate.paired_lines),
                "bilingual_pairs": sum(1 for item in candidate.paired_lines if item.en and item.zh),
            })
            if best is None or candidate.score > best.score:
                best = candidate
    elif backend == "tesseract":
        selected = [name for name in ("enhanced", "binary_otsu", "adaptive", "deskewed")]
        variant_map = {name: img for name, img in variants if name in selected}
        for variant_name in selected:
            img = variant_map.get(variant_name)
            if img is None:
                continue
            for psm in (6, 4, 11):
                candidate = _make_candidate(backend=backend, device=device, variant=f"{variant_name}_psm{psm}", spans=_ocr_with_tesseract(img, psm=psm))
                attempts.append({
                    "backend": backend,
                    "variant": candidate.variant,
                    "device": device,
                    "ok": True,
                    "score": round(candidate.score, 3),
                    "mean_confidence": round(candidate.mean_confidence, 3),
                    "raw_span_count": len(candidate.spans),
                    "filtered_span_count": len(candidate.filtered_spans),
                    "grouped_line_count": len(candidate.grouped_lines),
                    "paired_line_count": len(candidate.paired_lines),
                    "bilingual_pairs": sum(1 for item in candidate.paired_lines if item.en and item.zh),
                })
                if best is None or candidate.score > best.score:
                    best = candidate
    else:
        raise ValueError(f"Unsupported OCR backend: {backend}")

    if best is None:
        raise RuntimeError(f"No OCR result produced for backend: {backend}")
    return best, attempts


def _run_ocr(image_path: Path, *, backend: str = "auto", device: str = "cpu") -> Tuple[OCRCandidate, List[Dict[str, Any]]]:
    resolved_device, device_note = resolve_ocr_device(device)
    candidates = preferred_ocr_backends(backend, resolved_device)

    attempts: List[Dict[str, Any]] = []
    best: Optional[OCRCandidate] = None
    errors: List[str] = []

    for name in candidates:
        try:
            candidate, backend_attempts = _run_backend(image_path, name, resolved_device)
            for item in backend_attempts:
                item.setdefault("device_note", device_note)
            attempts.extend(backend_attempts)
            if best is None or candidate.score > best.score:
                best = candidate
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            attempts.append({"backend": name, "device": resolved_device, "ok": False, "error": err, "device_note": device_note})
            errors.append(f"{name}: {err}")

    if best is None:
        raise RuntimeError("No OCR backend is available. Install PaddleOCR/EasyOCR/pytesseract. Errors: " + " | ".join(errors))
    return best, attempts


def parse_picture_to_reader_spec(
    image_path: str | Path | None,
    *,
    title: str = "",
    tags: Optional[List[str]] = None,
    debug_out: str | Path | None = None,
    ocr_backend: str = "auto",
    ocr_device: str = "cpu",
    manual_text: str = "",
) -> Dict[str, Any]:
    manual_text = str(manual_text or "")
    image_path_obj: Path | None = None
    image_path_text = str(image_path or "").strip()
    if image_path_text and image_path_text not in {".", "./", ".\\"}:
        candidate = Path(image_path_text)
        if candidate.exists() and candidate.is_file():
            image_path_obj = candidate

    if manual_text.strip():
        spec = parse_picture_manual_text(
            manual_text,
            title=title,
            tags=tags,
            source_image=image_path_obj,
        )
        if debug_out:
            debug_path = Path(debug_out)
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            debug_path.write_text(
                json.dumps(
                    {
                        "input_mode": "manual_text",
                        "grouped_lines": list((spec.get("picture_reader") or {}).get("grouped_lines") or []),
                        "sentences": list(spec.get("sentences") or []),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return spec

    if image_path_obj is None:
        raise FileNotFoundError(f"Picture reader source image not found: {image_path}")

    best, attempts = _run_ocr(image_path_obj, backend=ocr_backend, device=ocr_device)
    pairs = best.paired_lines
    page_title = _norm(title) or image_path_obj.stem.replace("_", " ").replace("-", " ").strip() or "Picture Reader"
    sentence_items = [_build_reader_sentence_entry(item.en, item.zh, order=item.order) for item in pairs]

    spec = {
        "title": page_title,
        "tags": tags or ["picture_reader"],
        "vocab": [],
        "sentences": sentence_items,
        "qa": [],
        "reading_block": {"title": page_title, "text": "\n".join([str(item.get("tts_en") or item.get("en") or "") for item in sentence_items if str(item.get("tts_en") or item.get("en") or "").strip()]).strip()},
        "listening_block": {"title": page_title, "text": "\n".join([str(item.get("tts_zh") or item.get("zh") or "") for item in sentence_items if str(item.get("tts_zh") or item.get("zh") or "").strip()]).strip()},
        "comprehension_questions": [],
        "picture_reader": {
            "source_image": str(image_path_obj),
            "source_image_local": str(image_path_obj),
            "input_mode": "ocr",
            "ocr_backend": best.backend,
            "ocr_variant": best.variant,
            "ocr_device": best.device,
            "ocr_attempts": attempts,
            "render_style": "single_flow_reader",
            "lines": sentence_items,
        },
    }
    if debug_out:
        debug_path = Path(debug_out)
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(
            json.dumps(
                {
                    "ocr_backend": best.backend,
                    "ocr_variant": best.variant,
                    "ocr_device": best.device,
                    "ocr_attempts": attempts,
                    "raw_spans": [asdict(s) for s in best.spans],
                    "filtered_spans": [asdict(s) for s in best.filtered_spans],
                    "grouped_lines": best.grouped_lines,
                    "paired_lines": [asdict(item) for item in pairs],
                    "sentences": sentence_items,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return spec
