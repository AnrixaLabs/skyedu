"""
skyed/tag_s_env.py
------------------
Single source of truth for all tag_s environment / path configuration.

Previously these helpers were duplicated across ``pipeline_helpers.py`` and the
standalone scripts.  Centralising them here gives every caller a consistent
contract and makes the env-var names easy to audit in one place.

Public API
~~~~~~~~~~
- ``tag_s_output_root()``       – resolved local output directory for game bundles
- ``tag_s_deploy_enabled()``    – should the pipeline push tag_s to SFTP on publish?
- ``tag_s_remote_root()``       – SFTP remote path for tag_s bundles
- ``tag_s_public_base()``       – public HTTPS base URL for tag_s games

Environment variables (all optional unless noted)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
TAGS_OUT_DIR          Local filesystem root where game bundles are written.
                      Default: <project_root>/tag_s

SKYED_DEPLOY_TAG_S_ON_PUBLISH
                      Controls whether ``deploy_tag_games_for_publish`` is active.
                      Values "0", "false", "no", "off", "disabled" disable it.
                      Any other value (including the default "auto") enables it.

TAGS_REMOTE_ROOT /
SFTP_TAGS_REMOTE_ROOT /
TAGS_SFTP_REMOTE_ROOT /
SFTP_REMOTE_ROOT      Remote SFTP path for tag_s bundles, checked in this order.
                      Example: /var/www/html/en/tag_s

TAGS_PUBLIC_BASE      Public HTTPS base URL served at the above remote path.
                      Example: https://skyedu.fun/en/tag_s
"""
from __future__ import annotations

import os
from pathlib import Path


# ---------------------------------------------------------------------------
# Local output path
# ---------------------------------------------------------------------------

def tag_s_output_root(project_root: Path | None = None) -> Path:
    """Return the local directory where tag_s game bundles are written.

    Resolution order:
    1. ``TAGS_OUT_DIR`` env var
    2. ``<project_root>/tag_s``
    """
    env_root = os.environ.get("TAGS_OUT_DIR", "").strip()
    if env_root:
        return Path(env_root).expanduser()
    base = project_root or Path(__file__).resolve().parents[1]
    return base / "tag_s"


# ---------------------------------------------------------------------------
# Deployment toggle
# ---------------------------------------------------------------------------

_DISABLED_VALUES: frozenset[str] = frozenset({"0", "false", "no", "off", "disabled"})


def tag_s_deploy_enabled() -> bool:
    """Return True when standalone tag_s bundles should be deployed via SFTP.

    Controlled by ``SKYED_DEPLOY_TAG_S_ON_PUBLISH`` (default: "auto" → enabled).
    """
    raw = os.getenv("SKYED_DEPLOY_TAG_S_ON_PUBLISH", "auto").strip().lower()
    return raw not in _DISABLED_VALUES


# ---------------------------------------------------------------------------
# Remote / public URLs
# ---------------------------------------------------------------------------

_REMOTE_ROOT_ENV_KEYS: tuple[str, ...] = (
    "TAGS_REMOTE_ROOT",
    "SFTP_TAGS_REMOTE_ROOT",
    "TAGS_SFTP_REMOTE_ROOT",
    "SFTP_REMOTE_ROOT",
)


def tag_s_remote_root() -> str:
    """Return the SFTP remote path for tag_s bundles (trailing slash stripped).

    Checks ``TAGS_REMOTE_ROOT``, ``SFTP_TAGS_REMOTE_ROOT``,
    ``TAGS_SFTP_REMOTE_ROOT``, then ``SFTP_REMOTE_ROOT`` in order.
    Returns an empty string when none are set.
    """
    for key in _REMOTE_ROOT_ENV_KEYS:
        value = os.getenv(key, "").strip()
        if value:
            return value.rstrip("/")
    return ""


def tag_s_public_base() -> str:
    """Return the public HTTPS base URL for deployed tag_s games (trailing slash stripped).

    Controlled by ``TAGS_PUBLIC_BASE``.
    """
    return os.getenv("TAGS_PUBLIC_BASE", "").strip().rstrip("/")
