# SkyED Control Panel v2.2.1 — additive Windows desktop release

## Scope

Modern PySide6 launch shell that does not rewrite, delete, or downgrade existing workflow implementations. The original pyside_gui.py remains responsible for homework generation, previews, TTS, images, batches, tag_s, NG, Picture Reader, publishing, and ComfyUI. The shell routes to the existing tab names and preserves the original main workroom.

The dashboard has 17 workflows, searchable Ctrl+K palette, light/dark appearance, optional add-on checks, read-only local diagnostics, local folder browsing, and separate browser links to course.skyed.org, portal.skyed.org, and growth.skyed.org. No publishing or network connection runs on GUI startup.

## Windows install

Download the complete SkyED-ControlPanel-v2.2.1.zip release artifact from the successful GitHub Actions control-panel-ci workflow. Extract it to:

    C:\Users\user\Downloads\SkyED-ControlPanel-v2.2.1

Run in Windows PowerShell 5.1:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$HOME\Downloads\SkyED-ControlPanel-v2.2.1\scripts\Install-SkyED-ControlPanel-v2.2.1.ps1" -ProjectRoot "C:\Users\user\PycharmProjects\skyed_automation"

The installer verifies five member SHA-256 digests; checks for the existing pyside_gui.py, run_pipeline.py, and the Python virtual environment; backs up any earlier Control Panel overlay; installs only three new Python files; runs Python compilation and actual Qt offscreen startup; then creates the Desktop and Start Menu shortcuts using the project's pythonw.exe. Validation failures restore previous overlay files. It does not alter original automation, media, configuration, .env, production sites, WordPress or database.

## Workflow mapping

CREATE: Homework Studio, Audio, Images, Batch, Asset Batcher, Card Cutter, tag_s Creator, NG, Picture Reader.

OPERATE: Publishing (original safety checks), existing output library, canonical asset library.

WEBSITES: Course Hub, ClassFlow, GrowthBridge links only; not new API integrations.

SYSTEM: local diagnostics, visual settings (existing credentials never copied into QSettings).

Optional modules missing from the local environment are not simulated. They will report original dependency errors. External website navigation requires a confirmation dialog.

## Release gates

GitHub Actions: Linux registry tests, Qt offscreen smoke, Windows syntax tests, Qt offscreen smoke, deterministic ZIP with member manifest.

Real on-device verification still requires access to the user's Windows workstation. GitHub CI cannot certify real Desktop shortcuts, actual local model installation, access to production backends, media quality, WordPress writes or server deployment.

## Credential incident

The separate private skyed_asset_batcher repository previously tracked a non-placeholder-looking HF_TOKEN. The current default branch now ignores .env and deletes the tracked file, but the token survives in Git history and should be revoked/rotated by its owner. No secrets are included in this release package. Workstation .env should remain local and not be committed.

## Rollback

Installer backups reside in <project>\backups\control-panel-YYYYMMDD-HHmmss. Previously installed modern Control Panel overlay files are restored if validation fails. The original tool remains launchable with:

    .\.venv\Scripts\python.exe pyside_gui.py

The new Desktop shortcut points to skyed_control_panel.py only.

## Qt offscreen font diagnostic (v2.2.1)

The earlier installer completed all checks but Qt printed a QFontDatabase
warning about a non-existent PySide6/lib/fonts directory. This arises when
using the Qt offscreen platform plugin for smoke tests, and is **not** evidence
that the normal Windows GUI has missing system fonts.

v2.2.1 points the **smoke-test process only** at the existing Windows Fonts
folder using QT_QPA_FONTDIR. It snapshots and restores the caller's
QT_QPA_PLATFORM and QT_QPA_FONTDIR settings. No fonts are installed, copied or
distributed, and the actual Windows launcher's environment is unchanged.

The new GUI also makes this adjustment when invoked directly with
--smoke-test. This release preserves the original classic UI and all workflows.
