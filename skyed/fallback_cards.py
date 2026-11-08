from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .image_specs import ImageSpec


BRAND_BG = (235, 246, 255)
BRAND_PANEL = (255, 255, 255)
BRAND_ACCENT = (14, 116, 144)
BRAND_TEXT = (22, 35, 47)
BRAND_SOFT = (111, 147, 165)


def _load_font(size: int) -> ImageFont.ImageFont:
    preferred = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for path in preferred:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def make_fallback_card(
    spec: ImageSpec,
    out_path: str | Path,
    size: tuple[int, int] = (1024, 1024),
    subtitle: Optional[str] = None,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", size, BRAND_BG)
    draw = ImageDraw.Draw(img)
    w, h = size

    outer_margin = int(w * 0.07)
    panel = (outer_margin, outer_margin, w - outer_margin, h - outer_margin)
    draw.rounded_rectangle(panel, radius=36, fill=BRAND_PANEL, outline=BRAND_ACCENT, width=6)

    title_font = _load_font(96)
    zh_font = _load_font(64)
    meta_font = _load_font(40)
    body_font = _load_font(34)

    word = spec.word.strip()
    zh = spec.zh.strip() or ""
    pos = spec.pos.upper()
    body = subtitle or spec.scene_type.replace("-", " ").title()

    draw.rounded_rectangle(
        (outer_margin + 32, outer_margin + 32, w - outer_margin - 32, outer_margin + 140),
        radius=24,
        fill=(225, 242, 250),
    )
    draw.text((outer_margin + 56, outer_margin + 58), pos, font=meta_font, fill=BRAND_ACCENT)

    title_y = outer_margin + 200
    draw.text((w // 2, title_y), word, font=title_font, fill=BRAND_TEXT, anchor="ma")

    if zh:
        draw.text((w // 2, title_y + 120), zh, font=zh_font, fill=BRAND_ACCENT, anchor="ma")

    scene_box = (outer_margin + 70, int(h * 0.57), w - outer_margin - 70, int(h * 0.83))
    draw.rounded_rectangle(scene_box, radius=28, fill=(244, 249, 252), outline=(210, 228, 236), width=3)
    draw.text((w // 2, scene_box[1] + 40), "Literal fallback card", font=meta_font, fill=BRAND_SOFT, anchor="ma")
    draw.multiline_text(
        (w // 2, scene_box[1] + 120),
        body,
        font=body_font,
        fill=BRAND_TEXT,
        anchor="ma",
        spacing=10,
        align="center",
    )

    footer_text = "Generated fallback: use when the AI image is rejected or mismatched"
    draw.text((w // 2, h - outer_margin - 60), footer_text, font=meta_font, fill=BRAND_SOFT, anchor="ma")

    img.save(out_path)
    return out_path


__all__ = ["make_fallback_card"]
