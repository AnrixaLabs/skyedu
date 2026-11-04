from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional, Tuple


def _normalized_env_path(raw: str) -> Optional[str]:
    value = (raw or "").strip().strip('"').strip("'")
    if not value:
        return None
    if value in {".", "./", ".\\"}:
        return None
    return value


def resolve_tesseract_command() -> Tuple[Optional[str], str]:
    """Return a usable tesseract command/path and a human-readable note.

    This deliberately ignores placeholder values such as '.' which otherwise
    cause pytesseract to try executing the current directory and fail with a
    PermissionError.
    """
    for env_name in ("TESSERACT_CMD", "PYTESSERACT_TESSERACT_CMD", "TESSERACT_PATH"):
        raw = os.getenv(env_name, "")
        candidate = _normalized_env_path(raw)
        if not candidate:
            if raw.strip() in {".", "./", ".\\"}:
                return None, f"Ignored invalid {env_name} value {raw!r}"
            continue
        if os.path.isabs(candidate) or any(sep in candidate for sep in ("/", "\\")):
            if Path(candidate).is_file():
                return candidate, f"Using {env_name}"
            return None, f"Configured {env_name} does not exist: {candidate}"
        resolved = shutil.which(candidate)
        if resolved:
            return resolved, f"Using {env_name}={candidate}"
        return None, f"Configured {env_name} is not on PATH: {candidate}"

    which = shutil.which("tesseract")
    if which:
        return which, "Using system PATH"

    windows_candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in windows_candidates:
        if Path(candidate).is_file():
            return candidate, "Using common Windows install path"
    return None, "Tesseract executable not found"


def configure_pytesseract() -> Tuple[Optional[object], Optional[str], str]:
    try:
        import pytesseract  # type: ignore
    except Exception as exc:
        return None, None, f"pytesseract import failed: {exc}"

    cmd, note = resolve_tesseract_command()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
        return pytesseract, cmd, note
    return pytesseract, None, note


def tesseract_ready() -> Tuple[bool, str]:
    pytesseract, cmd, note = configure_pytesseract()
    if pytesseract is None:
        return False, note
    if not cmd:
        return False, note
    try:
        _ = pytesseract.get_tesseract_version()
        return True, note
    except Exception as exc:
        return False, f"{note}; version probe failed: {exc}"


def resolve_ocr_device(requested: str) -> Tuple[str, str]:
    requested = (requested or os.getenv("SKYED_OCR_DEVICE") or "cpu").strip().lower()
    if requested != "cuda":
        return "cpu", "OCR device resolved to CPU"

    try:
        import torch  # type: ignore
    except Exception as exc:
        return "cpu", f"CUDA requested but torch is unavailable: {exc}"

    try:
        if not torch.cuda.is_available():
            return "cpu", "CUDA requested but no CUDA device is available"
        index = int(os.getenv("SKYED_OCR_CUDA_INDEX", "0") or "0")
        name = torch.cuda.get_device_name(index)
        capability = torch.cuda.get_device_capability(index)
        major, minor = int(capability[0]), int(capability[1])

        # Keep OCR on FP32 for legacy cards such as GTX 1650 / Turing.
        if hasattr(torch.backends, "cuda") and hasattr(torch.backends.cuda, "matmul"):
            torch.backends.cuda.matmul.allow_tf32 = False
        if hasattr(torch.backends, "cudnn"):
            torch.backends.cudnn.allow_tf32 = False
        os.environ.setdefault("SKYED_OCR_FORCE_FP32", "1")

        note = f"Using CUDA OCR on {name} (cc {major}.{minor}); FP32-safe mode enabled"
        if major < 8:
            note += "; legacy/pre-Ampere GPU detected"
        return "cuda", note
    except Exception as exc:
        return "cpu", f"CUDA requested but OCR runtime fell back to CPU: {exc}"


def preferred_ocr_backends(requested_backend: str, resolved_device: str) -> list[str]:
    backend = (requested_backend or os.getenv("SKYED_OCR_BACKEND") or "auto").strip().lower()
    if backend != "auto":
        return [backend]

    # Quality-first order for bilingual EN/ZH lesson pages.
    if resolved_device == "cuda":
        return ["easyocr", "paddle", "tesseract"]
    return ["easyocr", "paddle", "tesseract"]
