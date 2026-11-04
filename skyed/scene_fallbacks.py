from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont

from .image_specs import ImageSpec

BG = (239, 246, 255)
PANEL = (255, 255, 255)
INK = (17, 24, 39)
SOFT = (100, 116, 139)
ACCENT = (14, 165, 233)
RED = (239, 68, 68)
BLUE = (59, 130, 246)
GREEN = (34, 197, 94)
YELLOW = (250, 204, 21)
PURPLE = (168, 85, 247)
ORANGE = (249, 115, 22)
BROWN = (146, 64, 14)
BLACK = (31, 41, 55)
WHITE = (255, 255, 255)
PINK = (236, 72, 153)

COLOR_MAP = {
    "red": RED,
    "blue": BLUE,
    "green": GREEN,
    "yellow": YELLOW,
    "purple": PURPLE,
    "orange": ORANGE,
    "brown": BROWN,
    "black": BLACK,
    "white": WHITE,
    "pink": PINK,
}

EMOTION_STYLES = {
    "happy": {"mouth": "smile", "brows": "up", "eyes": "open", "accent": YELLOW},
    "sad": {"mouth": "sad", "brows": "tilt_up", "eyes": "open", "accent": BLUE},
    "angry": {"mouth": "flat", "brows": "down", "eyes": "open", "accent": RED},
    "tired": {"mouth": "flat", "brows": "soft", "eyes": "closed", "accent": PURPLE},
    "sick": {"mouth": "sad", "brows": "soft", "eyes": "closed", "accent": GREEN},
    "scared": {"mouth": "open", "brows": "high", "eyes": "wide", "accent": ORANGE},
    "hungry": {"mouth": "open", "brows": "soft", "eyes": "open", "accent": ORANGE},
    "thirsty": {"mouth": "open", "brows": "soft", "eyes": "open", "accent": BLUE},
    "hot": {"mouth": "open", "brows": "soft", "eyes": "closed", "accent": ORANGE},
    "cold": {"mouth": "open", "brows": "high", "eyes": "open", "accent": BLUE},
    "full": {"mouth": "smile", "brows": "soft", "eyes": "closed", "accent": GREEN},
}


def _font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for path in candidates:
        p = Path(path)
        if not p.exists():
            continue
        try:
            return ImageFont.truetype(str(p), size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _base_canvas(size: Tuple[int, int]) -> tuple[Image.Image, ImageDraw.ImageDraw, int, int]:
    img = Image.new("RGB", size, BG)
    d = ImageDraw.Draw(img)
    w, h = size
    d.rounded_rectangle((22, 22, w - 22, h - 22), radius=36, fill=PANEL, outline=(203, 213, 225), width=3)
    return img, d, w, h


def _draw_chip(d: ImageDraw.ImageDraw, text: str, w: int) -> None:
    if not text:
        return
    font = _font(36)
    x1, y1, x2, y2 = 48, 40, w - 48, 102
    d.rounded_rectangle((x1, y1, x2, y2), radius=22, fill=(224, 242, 254))
    d.text((w // 2, 71), text, font=font, fill=(3, 105, 161), anchor="mm")


def _draw_counting_scene(d: ImageDraw.ImageDraw, word: str, w: int, h: int) -> bool:
    try:
        n = int(word)
    except Exception:
        return False
    n = max(0, min(20, n))
    cols = 5 if n > 10 else 4
    rows = max(1, (n + cols - 1) // cols)
    r = 44
    start_x = 140
    start_y = 170
    gap_x = 110
    gap_y = 110
    if n == 0:
        d.rounded_rectangle((160, 240, w - 160, h - 160), radius=28, outline=(148, 163, 184), width=5, fill=(248, 250, 252))
        d.line((190, 270, w - 190, h - 190), fill=(148, 163, 184), width=10)
        return True
    i = 0
    colors = [RED, BLUE, GREEN, YELLOW, PURPLE, ORANGE]
    for row in range(rows):
        for col in range(cols):
            if i >= n:
                break
            cx = start_x + col * gap_x
            cy = start_y + row * gap_y
            c = colors[i % len(colors)]
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c)
            i += 1
    return True


def _draw_relation_scene(d: ImageDraw.ImageDraw, word: str, w: int, h: int) -> bool:
    ball = (RED, (0, 0, 0))
    if word == "in":
        d.rounded_rectangle((250, 250, 520, 520), radius=18, outline=INK, width=6, fill=(241, 245, 249))
        d.ellipse((340, 340, 430, 430), fill=ball[0], outline=ball[1], width=4)
    elif word == "on":
        d.rounded_rectangle((220, 410, 560, 450), radius=10, fill=BROWN)
        d.ellipse((345, 315, 435, 405), fill=ball[0], outline=ball[1], width=4)
    elif word == "under":
        d.rounded_rectangle((220, 260, 560, 300), radius=10, fill=BROWN)
        d.ellipse((345, 345, 435, 435), fill=ball[0], outline=ball[1], width=4)
    elif word == "behind":
        d.rounded_rectangle((220, 290, 560, 470), radius=18, fill=(203, 213, 225), outline=INK, width=4)
        d.ellipse((320, 325, 410, 415), fill=ball[0], outline=ball[1], width=4)
        d.rounded_rectangle((300, 290, 560, 470), radius=18, fill=(226, 232, 240), outline=INK, width=4)
    elif word == "in front of":
        d.rounded_rectangle((260, 260, 560, 470), radius=18, fill=(226, 232, 240), outline=INK, width=4)
        d.ellipse((280, 360, 370, 450), fill=ball[0], outline=ball[1], width=4)
    elif word == "next to":
        d.rounded_rectangle((300, 260, 560, 470), radius=18, fill=(226, 232, 240), outline=INK, width=4)
        d.ellipse((180, 340, 270, 430), fill=ball[0], outline=ball[1], width=4)
    elif word == "between":
        d.rounded_rectangle((160, 250, 300, 470), radius=18, fill=(226, 232, 240), outline=INK, width=4)
        d.rounded_rectangle((460, 250, 600, 470), radius=18, fill=(226, 232, 240), outline=INK, width=4)
        d.ellipse((340, 350, 430, 440), fill=ball[0], outline=ball[1], width=4)
    else:
        return False
    return True


def _draw_color_scene(d: ImageDraw.ImageDraw, word: str, w: int, h: int) -> bool:
    color = COLOR_MAP.get(word)
    if not color:
        return False
    d.ellipse((260, 150, 520, 410), fill=(255, 224, 189), outline=INK, width=4)
    d.rectangle((320, 380, 460, 460), fill=(255, 224, 189), outline=INK, width=4)
    d.rounded_rectangle((240, 450, 540, 690), radius=48, fill=color, outline=INK, width=5)
    return True


def _draw_pronoun_scene(d: ImageDraw.ImageDraw, word: str, w: int, h: int) -> bool:
    def person(cx: int, color: tuple[int, int, int]) -> None:
        d.ellipse((cx - 45, 190, cx + 45, 280), fill=(255, 224, 189), outline=INK, width=4)
        d.rounded_rectangle((cx - 70, 290, cx + 70, 540), radius=28, fill=color, outline=INK, width=4)
    if word == "he":
        person(w // 2, BLUE)
    elif word == "she":
        person(w // 2, PINK)
    elif word == "it":
        d.rounded_rectangle((260, 250, 520, 520), radius=26, fill=GREEN, outline=INK, width=5)
    elif word == "they":
        person(270, BLUE)
        person(400, PINK)
        person(530, GREEN)
    elif word == "we":
        person(310, BLUE)
        person(490, GREEN)
    else:
        return False
    d.line((650, 360, 540, 360), fill=ACCENT, width=12)
    d.polygon([(540, 360), (572, 340), (572, 380)], fill=ACCENT)
    return True


def _draw_question_scene(d: ImageDraw.ImageDraw, word: str, w: int, h: int) -> bool:
    if word == "where":
        d.rounded_rectangle((170, 240, 650, 610), radius=24, fill=(241, 245, 249), outline=INK, width=4)
        d.rounded_rectangle((230, 450, 390, 560), radius=16, fill=BROWN, outline=INK, width=4)
        d.ellipse((470, 360, 560, 450), fill=RED, outline=INK, width=4)
        d.line((590, 240, 680, 170), fill=ACCENT, width=12)
        d.ellipse((655, 140, 705, 190), fill=ACCENT)
        return True
    if word == "who":
        _draw_pronoun_scene(d, "they", w, h)
        d.line((660, 210, 560, 270), fill=ACCENT, width=12)
        d.ellipse((640, 180, 700, 240), fill=ACCENT)
        return True
    if word == "what":
        d.rounded_rectangle((220, 330, 470, 520), radius=22, fill=GREEN, outline=INK, width=4)
        d.line((610, 260, 490, 360), fill=ACCENT, width=12)
        d.ellipse((590, 230, 650, 290), fill=ACCENT)
        return True
    if word == "when":
        d.ellipse((260, 220, 520, 480), fill=WHITE, outline=INK, width=8)
        d.line((390, 350, 390, 250), fill=INK, width=8)
        d.line((390, 350, 470, 390), fill=INK, width=8)
        d.line((620, 240, 510, 270), fill=ACCENT, width=12)
        d.ellipse((600, 210, 660, 270), fill=ACCENT)
        return True
    if word in {"which", "whose", "how", "why"}:
        d.rounded_rectangle((170, 250, 650, 610), radius=26, fill=(241, 245, 249), outline=INK, width=4)
        d.rounded_rectangle((220, 330, 360, 510), radius=18, fill=BLUE, outline=INK, width=4)
        d.rounded_rectangle((460, 330, 600, 510), radius=18, fill=ORANGE, outline=INK, width=4)
        d.line((640, 240, 560, 320), fill=ACCENT, width=12)
        d.ellipse((620, 210, 680, 270), fill=ACCENT)
        return True
    return False


def _draw_face_base(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int, accent: tuple[int, int, int]) -> None:
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 235, 205), outline=INK, width=6)
    d.arc((cx - r - 26, cy - r - 26, cx + r + 26, cy + r + 26), start=210, end=330, fill=accent, width=18)


def _draw_eye(d: ImageDraw.ImageDraw, x: int, y: int, mode: str) -> None:
    if mode == "closed":
        d.arc((x - 26, y - 6, x + 26, y + 14), start=0, end=180, fill=INK, width=6)
    elif mode == "wide":
        d.ellipse((x - 20, y - 18, x + 20, y + 18), fill=WHITE, outline=INK, width=4)
        d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=INK)
    else:
        d.ellipse((x - 18, y - 12, x + 18, y + 12), fill=WHITE, outline=INK, width=4)
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=INK)


def _draw_brows(d: ImageDraw.ImageDraw, cx: int, cy: int, mode: str) -> None:
    left = (cx - 92, cy - 126)
    right = (cx + 92, cy - 126)
    if mode == "down":
        d.line((left[0] - 34, left[1] - 8, left[0] + 34, left[1] + 16), fill=INK, width=7)
        d.line((right[0] - 34, right[1] + 16, right[0] + 34, right[1] - 8), fill=INK, width=7)
    elif mode == "tilt_up":
        d.line((left[0] - 34, left[1] + 16, left[0] + 34, left[1] - 8), fill=INK, width=7)
        d.line((right[0] - 34, right[1] - 8, right[0] + 34, right[1] + 16), fill=INK, width=7)
    elif mode == "high":
        d.line((left[0] - 34, left[1] - 18, left[0] + 34, left[1] - 10), fill=INK, width=7)
        d.line((right[0] - 34, right[1] - 10, right[0] + 34, right[1] - 18), fill=INK, width=7)
    elif mode == "up":
        d.arc((left[0] - 36, left[1] - 24, left[0] + 36, left[1] + 12), start=180, end=360, fill=INK, width=6)
        d.arc((right[0] - 36, right[1] - 24, right[0] + 36, right[1] + 12), start=180, end=360, fill=INK, width=6)
    else:
        d.line((left[0] - 30, left[1], left[0] + 30, left[1]), fill=INK, width=6)
        d.line((right[0] - 30, right[1], right[0] + 30, right[1]), fill=INK, width=6)


def _draw_mouth(d: ImageDraw.ImageDraw, cx: int, cy: int, mode: str) -> None:
    if mode == "smile":
        d.arc((cx - 68, cy + 12, cx + 68, cy + 92), start=10, end=170, fill=INK, width=7)
    elif mode == "sad":
        d.arc((cx - 68, cy + 40, cx + 68, cy + 108), start=190, end=350, fill=INK, width=7)
    elif mode == "open":
        d.ellipse((cx - 32, cy + 22, cx + 32, cy + 86), fill=WHITE, outline=INK, width=6)
    else:
        d.line((cx - 56, cy + 52, cx + 56, cy + 52), fill=INK, width=7)


def _draw_emotion_scene(d: ImageDraw.ImageDraw, word: str, w: int, h: int) -> bool:
    style = EMOTION_STYLES.get(word)
    if not style:
        return False
    accent = style["accent"]
    cx, cy, r = w // 2, int(h * 0.46), 172
    for i in range(10):
        x1 = 120 + i * 56
        d.rounded_rectangle((x1, 590, x1 + 28, 670), radius=14, fill=accent)
    _draw_face_base(d, cx, cy, r, accent)
    _draw_brows(d, cx, cy, style.get("brows", "soft"))
    _draw_eye(d, cx - 66, cy - 20, style.get("eyes", "open"))
    _draw_eye(d, cx + 66, cy - 20, style.get("eyes", "open"))
    _draw_mouth(d, cx, cy, style.get("mouth", "flat"))
    if word == "sick":
        d.rectangle((cx + 120, cy - 70, cx + 170, cy - 14), fill=(229, 231, 235), outline=INK, width=4)
        d.line((cx + 145, cy - 95, cx + 145, cy + 8), fill=INK, width=4)
    elif word == "scared":
        d.polygon([(cx - 214, cy + 74), (cx - 166, cy + 20), (cx - 118, cy + 74)], fill=ACCENT)
        d.polygon([(cx + 214, cy + 74), (cx + 166, cy + 20), (cx + 118, cy + 74)], fill=ACCENT)
    elif word == "hungry":
        d.ellipse((cx - 62, 620, cx + 62, 720), fill=ORANGE, outline=INK, width=4)
    elif word == "thirsty":
        d.polygon([(cx, 610), (cx - 48, 700), (cx + 48, 700)], fill=BLUE, outline=INK)
    elif word == "hot":
        d.polygon([(cx - 12, 600), (cx - 56, 692), (cx + 12, 664), (cx - 6, 736), (cx + 64, 642)], fill=ORANGE, outline=INK)
    elif word == "cold":
        for off in (-70, 0, 70):
            d.line((cx + off - 24, 650, cx + off + 24, 650), fill=BLUE, width=6)
            d.line((cx + off, 626, cx + off, 674), fill=BLUE, width=6)
            d.line((cx + off - 18, 632, cx + off + 18, 668), fill=BLUE, width=5)
            d.line((cx + off - 18, 668, cx + off + 18, 632), fill=BLUE, width=5)
    return True


def render_deterministic_scene(
    spec: ImageSpec,
    out_path: str | Path,
    size: Tuple[int, int] = (768, 768),
    *,
    include_labels: bool = False,
) -> Path | None:
    out = Path(out_path)
    img, d, w, h = _base_canvas(size)
    word = (spec.word or "").strip().lower()
    pos = (spec.pos or "").strip().lower()
    chip = spec.word.strip()
    if spec.zh:
        chip = f"{spec.word} · {spec.zh}"
    if include_labels:
        _draw_chip(d, chip, w)

    handled = False
    if pos == "number" or word.isdigit():
        handled = _draw_counting_scene(d, word, w, h)
    elif pos == "preposition":
        handled = _draw_relation_scene(d, word, w, h)
    elif pos == "adjective":
        handled = _draw_emotion_scene(d, word, w, h) or _draw_color_scene(d, word, w, h)
    elif pos == "pronoun":
        handled = _draw_pronoun_scene(d, word, w, h)
    elif pos == "question_word":
        handled = _draw_question_scene(d, word, w, h)
    elif (spec.render_mode or "") in {"counting_scene", "relation_scene", "guided_scene", "symbolic_card"}:
        handled = (
            _draw_question_scene(d, word, w, h)
            or _draw_pronoun_scene(d, word, w, h)
            or _draw_relation_scene(d, word, w, h)
            or _draw_counting_scene(d, word, w, h)
            or _draw_emotion_scene(d, word, w, h)
        )

    if not handled:
        return None

    if include_labels:
        footer = _font(28)
        d.text((w // 2, h - 52), "Deterministic study card", font=footer, fill=SOFT, anchor="mm")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out
