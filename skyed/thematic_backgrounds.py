from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageFilter

from .image_backends import CloudflareFluxBackend, ImageGenRequest
from .picture_reader import _run_ocr, parse_picture_manual_text  # internal reuse inside the same package

_THEME_RULES = {
    "classroom": {
        "keywords": {"school", "class", "classroom", "teacher", "student", "desk", "book", "lesson", "homework", "pencil", "eraser", "ruler"},
        "prompt": "bright classroom background with desks, books, school wall details, educational but soft, clean negative space",
    },
    "home": {
        "keywords": {"bed", "bedroom", "kitchen", "living room", "sofa", "table", "lamp", "family", "home", "house", "bathroom"},
        "prompt": "warm home interior background, simple furniture, cozy family-learning atmosphere, clean negative space",
    },
    "food": {
        "keywords": {"apple", "banana", "bread", "rice", "hamburger", "pizza", "food", "eat", "hungry", "full", "drink", "water", "juice"},
        "prompt": "light kitchen or cafe background with simple food-learning context, pastel colors, clean negative space",
    },
    "nature": {
        "keywords": {"tree", "flower", "grass", "park", "sun", "sky", "cloud", "rain", "snow", "wind", "nature", "garden"},
        "prompt": "soft outdoor nature background with sky, grass, gentle trees, child-friendly educational look, clean negative space",
    },
    "animals": {
        "keywords": {"cat", "dog", "bird", "fish", "rabbit", "tiger", "lion", "animal", "zoo", "farm"},
        "prompt": "soft animal-learning background with simple park or farm context, playful but quiet, clean negative space",
    },
    "transport": {
        "keywords": {"car", "bus", "train", "truck", "plane", "bike", "bicycle", "transport", "road", "traffic"},
        "prompt": "clean transport-learning background with road, city hints, simple vehicles in distance, lots of negative space",
    },
    "weather": {
        "keywords": {"sunny", "rainy", "snowy", "cloudy", "weather", "hot", "cold", "windy"},
        "prompt": "soft weather-learning background with sky gradient, clouds and gentle seasonal hints, subtle and calm",
    },
    "reading": {
        "keywords": {"read", "reading", "story", "page", "sentence", "word", "library", "book"},
        "prompt": "soft reading corner background with books and warm study atmosphere, subtle details, clean negative space",
    },
}


def _keywords(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z]+", (text or "").lower())


def guess_theme_from_text(text: str) -> Dict[str, str]:
    kws = set(_keywords(text))
    best_name = "classroom"
    best_score = -1
    for name, rule in _THEME_RULES.items():
        score = len(kws.intersection(rule["keywords"]))
        if score > best_score:
            best_name = name
            best_score = score
    rule = _THEME_RULES[best_name]
    return {
        "theme": best_name,
        "theme_prompt": rule["prompt"],
        "score": str(best_score),
    }


def ocr_picture_summary(
    image_path: str | Path,
    *,
    ocr_backend: str = "auto",
    ocr_device: str = "cpu",
    manual_text: str = "",
) -> Dict[str, object]:
    image_path = Path(image_path)
    manual_text = str(manual_text or "").strip()
    if manual_text:
        parsed = parse_picture_manual_text(manual_text, source_image=image_path)
        sentences = list(parsed.get("sentences") or [])
        grouped = [str(item.get("en") or "").strip() for item in sentences if str(item.get("en") or "").strip()]
        spoken = [str(item.get("tts_en") or item.get("en") or "").strip() for item in sentences if str(item.get("tts_en") or item.get("en") or "").strip()]
        joined = " | ".join(spoken[:12]).strip() or " | ".join(grouped[:12]).strip()
        theme = guess_theme_from_text(joined or image_path.stem)
        return {
            "ocr_backend": "manual_text",
            "ocr_variant": "manual_text",
            "ocr_device": "manual",
            "grouped_lines": grouped,
            "paired_lines": sentences,
            "joined_text": joined,
            "theme": theme["theme"],
            "theme_prompt": theme["theme_prompt"],
            "ocr_attempts": [{"backend": "manual_text", "ok": True, "error": ""}],
            "ocr_fallback": False,
            "ocr_error": "",
            "input_mode": "manual_text",
        }
    try:
        best, attempts = _run_ocr(image_path, backend=ocr_backend, device=ocr_device)
        grouped = list(best.grouped_lines)
        paired = [{"en": p.en, "zh": p.zh, "order": p.order} for p in best.paired_lines]
        joined = " | ".join(grouped[:12]).strip()
        theme = guess_theme_from_text(joined or image_path.stem)
        return {
            "ocr_backend": best.backend,
            "ocr_variant": getattr(best, "variant", ""),
            "ocr_device": getattr(best, "device", ocr_device),
            "grouped_lines": grouped,
            "paired_lines": paired,
            "joined_text": joined,
            "theme": theme["theme"],
            "theme_prompt": theme["theme_prompt"],
            "ocr_attempts": attempts,
            "ocr_fallback": False,
            "ocr_error": "",
            "input_mode": "ocr",
        }
    except Exception as exc:
        theme = guess_theme_from_text(image_path.stem)
        attempts = [{
            "backend": (ocr_backend or "auto"),
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }]
        return {
            "ocr_backend": "fallback_none",
            "ocr_variant": "",
            "ocr_device": (ocr_device or "cpu"),
            "grouped_lines": [],
            "paired_lines": [],
            "joined_text": image_path.stem.replace("_", " ").replace("-", " ").strip(),
            "theme": theme["theme"],
            "theme_prompt": theme["theme_prompt"],
            "ocr_attempts": attempts,
            "ocr_fallback": True,
            "ocr_error": f"{type(exc).__name__}: {exc}",
            "input_mode": "ocr_fallback",
        }


def generate_thematic_background(
    image_path: str | Path,
    out_dir: str | Path,
    *,
    account_id: str,
    api_token: str,
    model: str,
    ocr_backend: str = "auto",
    ocr_device: str = "cpu",
    width: int = 1344,
    height: int = 768,
    transparency_percent: int = 76,
    manual_text: str = "",
) -> Dict[str, str]:
    summary = ocr_picture_summary(image_path, ocr_backend=ocr_backend, ocr_device=ocr_device, manual_text=manual_text)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bg = CloudflareFluxBackend(account_id=account_id, api_token=api_token, model=model)
    prompt = (
        f"soft educational worksheet background, {summary['theme_prompt']}, pastel, subtle details, "
        f"not intrusive, wide background, child-friendly, no text, no letters, no numbers, no labels, empty center space"
    )
    raw = bg.generate_png(
        ImageGenRequest(
            subject=str(summary["theme"]),
            style="cartoon",
            render_mode="attribute_scene",
            width=int(width),
            height=int(height),
            steps=1,
            positive_prompt=prompt,
            negative_prompt="text, letters, numbers, labels, logo, watermark, poster, signboard, noisy composition",
        ),
        timeout_s=180,
    )
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", image_path.stem).strip("_") or "picture"
    theme_slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(summary["theme"])).strip("_") or "theme"
    solid_path = out_dir / f"{stem}_{theme_slug}_background_solid.png"
    solid_path.write_bytes(raw)

    solid = Image.open(solid_path).convert("RGBA")
    softened = solid.filter(ImageFilter.GaussianBlur(radius=2))
    alpha_pct = max(5, min(95, 100 - int(transparency_percent)))
    alpha = int(round(255 * (alpha_pct / 100.0)))
    white = Image.new("RGBA", softened.size, (255, 255, 255, 255))
    softened = Image.blend(white, softened, 0.35)
    softened.putalpha(alpha)
    transparent_path = out_dir / f"{stem}_{theme_slug}_background_transparent.png"
    softened.save(transparent_path, format="PNG", optimize=True, compress_level=9)

    debug_path = out_dir / "ocr_theme_debug.json"
    debug_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "theme": str(summary["theme"]),
        "ocr_backend": str(summary["ocr_backend"]),
        "ocr_variant": str(summary.get("ocr_variant") or ""),
        "ocr_device": str(summary.get("ocr_device") or ocr_device),
        "joined_text": str(summary["joined_text"]),
        "input_mode": str(summary.get("input_mode") or "ocr"),
        "ocr_fallback": "1" if bool(summary.get("ocr_fallback")) else "0",
        "ocr_error": str(summary.get("ocr_error") or ""),
        "prompt": prompt,
        "solid_path": str(solid_path),
        "transparent_path": str(transparent_path),
        "debug_path": str(debug_path),
    }
