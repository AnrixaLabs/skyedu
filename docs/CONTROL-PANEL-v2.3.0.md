# SkyED Control Panel v2.3.0 — Course Hub Lobby Designer integration

## Actual functionality

This is a **complete additive successor** to Control Panel v2.2.1. It includes
all existing shell files, existing lobby v1.3.0 visuals, and a new private
in-app editing workspace. The original `pyside_gui.py`, `run_pipeline.py`,
WordPress renderer, ComfyUI, school databases and live websites are untouched.

- Select **Operations → Lobby Designer** to open an in-app PySide6 designer.
  The full editor is embedded using Qt WebEngine if installed. If unavailable,
  it opens in the default browser with the same local save functionality.
- **Operations → Lobby Live Preview** shows the exact same draft in-app.
  Switch between `Edit content` and `Live preview` at any time. Refresh preview
  after saving draft content.
- `Save to workspace` writes `skyed_lobby/site/content/lobby.json` atomically,
  with a local backup at `skyed_lobby/backups/lobby.json.previous`.
  `Export JSON` remains available as a portable backup.
- Embedded editor uses an ephemeral `127.0.0.1` listener, a random process-only
  token, same-origin and host checks, and strict schema / URL validation.
  The server is terminated when the integrated window closes.
- Original lesson placeholders and the 4 unapproved programs remain **drafts**.
  None of the 11 entries is linked to actual production lesson URLs.
- The original standalone lobby v1.3.0 package remains independently usable.
  The integrated 1.4 editor supports local Save, which the older package lacked.

## Install/upgrade (Windows PowerShell 5.1)

Extract the `SkyED-ControlPanel-Lobby-v2.3.0.zip` into Downloads, preserving
its root folder. Run:

```powershell
$ErrorActionPreference='Stop'
$zip="$HOME\Downloads\SkyED-ControlPanel-Lobby-v2.3.0.zip"
$dest="$HOME\Downloads\SkyED-ControlPanel-Lobby-v2.3.0"
Expand-Archive -LiteralPath $zip -DestinationPath "$HOME\Downloads" -Force
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$dest\scripts\Install-SkyED-ControlPanel-v2.3.0.ps1" -ProjectRoot 'C:\Users\user\PycharmProjects\skyed_automation'
```

**The installer verifies SHA-256 of every member before modifying files**,
requires the existing project/venv, validates an existing lobby.json rather than
clobbering it, backs up replaced Control Panel and lobby files, runs Python/Qt
smoke tests and a real loopback API test suite, and creates the same Desktop and
Start Menu app shortcuts as v2.2.1. Failure rolls back installed source files.

## Content safety

Site content is a local draft only, editable in the GUI or as JSON. Changes never
publish automatically. The local HTTP server serves only `site/` and `tools/`;
source scripts, test files, `.env` and backups cannot be fetched. No third-party
font or network dependencies. Untrusted published URLs are rejected. The server
has no SSH, GitHub, upload, WordPress or deployment endpoint.

## Integration contract

This overlay intentionally does not replace the production homepage of
`course.skyed.org` or the existing Course Hub v1.2.x source, which was not
available in this runtime. The 11 draft lessons must first be mapped to
verified live lessons and media before any production promotion. Do not
upload the private `tools/`, server script, or desktop editor to the web root.

**Only `skyed_lobby/site/` is a public-safe preview frontend**, and even that
must be staged under a separate preview path with routing/media verification
prior to any live replacement. Original `skyed.org`, `portal.skyed.org`,
`growth.skyed.org` and all other domains are out of scope.

## Verification

The package includes tests covering schema links, guarded publishing URLs,
atomic save and backups, localhost security, unauthorized POST, traversal,
real HTTP read/write, source syntax and GUI task navigation. GitHub Actions
runs Windows and Linux tests for this particular update branch.
