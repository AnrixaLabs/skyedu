# SkyED Control Panel v2.3.3 — Course Hub source integration

**Release scope:** additive Windows control-panel upgrade plus a read-only capture and local staging workflow for the existing `course.skyed.org` application. **Not a site deployment.**

## What changed

The v2.3.0 desktop launcher, Homework Studio, WordPress publishing, TTS, asset tools, visual Lobby Designer, and live draft preview are preserved. A new **Operations → Course Hub Integration** workspace accepts a read-only snapshot of the currently deployed static Course Hub. The builder copies every original public file without changes and installs the new tile lobby under `/lobby-preview/` in a *new, local* staged directory. It generates a SHA-256 preservation report, candidate link inventory, and a lesson linking review CSV. No original live lesson, MP3, PNG, `index.html`, Nginx config, WordPress file, or database is modified.

The release includes source files, design editor, JSON drafts, tests, guarded Windows installer, and read-only SSH capture script. **Do not upload this ZIP to the server.** Only a separately verified public-site build should ever be deployed.

## Installation

1. Download the full `SkyED-ControlPanel-Lobby-v2.3.3.zip` from the verified GitHub Actions run or the conversation attachment.
2. Extract into Windows Downloads, retaining the `SkyED-ControlPanel-Lobby-v2.3.3` root directory.
3. Run this in Windows PowerShell 5.1:

```powershell
$ErrorActionPreference = 'Stop'
$zip = "$HOME\Downloads\SkyED-ControlPanel-Lobby-v2.3.3.zip"
$dest = "$HOME\Downloads\SkyED-ControlPanel-Lobby-v2.3.3"
Expand-Archive -LiteralPath $zip -DestinationPath "$HOME\Downloads" -Force
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$dest\scripts\Install-SkyED-ControlPanel-v2.3.3.ps1" -ProjectRoot 'C:\Users\user\PycharmProjects\skyed_automation'
```

The installer verifies all member hashes, retains an existing edited `lobby.json`, backs up replaced files, runs Qt startup plus integration and editor API tests, and recreates the same desktop/Start Menu shortcuts. A failure reverts previously installed source files.

## Capture and stage the actual site — no production mutations

From a regular PowerShell console after installation:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\Users\user\PycharmProjects\skyed_automation\scripts\Start-SkyED-CourseHub-Integration-v2.3.3.ps1' -Mode CaptureAndStage -ProjectRoot 'C:\Users\user\PycharmProjects\skyed_automation' -ServerIP '8.210.9.172'
```

This **first verifies that the historical host and `/var/www/course.skyed.org/current` exist and are readable**, then downloads the public static files using OpenSSH. SSH host key checking is **strict**; an unknown host fingerprint blocks the operation instead of accepting an unverified key. The password prompt, if any, is handled by OpenSSH and never recorded. **The historical IP is not independently revalidated from this release; verify ownership/fingerprint before running it.**

An existing site export can be used without SSH:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\Users\user\PycharmProjects\skyed_automation\scripts\Start-SkyED-CourseHub-Integration-v2.3.3.ps1' -Mode StageLocal -ProjectRoot 'C:\Users\user\PycharmProjects\skyed_automation' -SourceRoot 'C:\PATH\TO\CURRENT\COURSE-HUB\PUBLIC'
```

Both paths write only to `Documents\SkyED-CourseHub-Integration`, not to the source. They require the full live 433-media-class library (at least 400 images/audio combined), verify all original SHA-256 hashes after staging, and do not allow unpublished lesson cards to become live.

The final output includes `staged-<timestamp>`, `report-<timestamp>/integration-report.json`, `legacy-link-candidates.csv`, and `lesson-linking-review.csv` and `verified-lesson-evidence.csv` (11 rows). Candidate links are suggestions, **not approvals**. The old index remains the root homepage; the new design is available only under `/lobby-preview/` of the staged copy.

For a local HTTP preview:

```powershell
& 'C:\Users\user\PycharmProjects\skyed_automation\.venv\Scripts\python.exe' 'C:\Users\user\PycharmProjects\skyed_automation\scripts\course_hub_integration.py' preview --stage 'C:\FULL\PATH\TO\staged-<timestamp>'
```

Open the exact `SKYED_STAGE_PREVIEW` URL printed. This server binds only to `127.0.0.1`, disallows POST, and serves only the local stage directory. From the desktop application, **Operations → Course Hub Integration** can perform the local build and open the preview without typing command arguments.

## Release boundaries and open gates

- Do **not** replace the current production homepage, upload drafts, or set a card status to `published` before lesson routing and media parity are verified.
- The legacy curriculum remains at the root; `/lobby-preview/` is additional.
- A staged site is a **local test only**. No remote URL availability, SSH authentication, production edit, browser playback, or DNS/TLS status is certified by CI.
- Real capture and the 11-lesson mapping remain outstanding. The deployment/promotion function intentionally does not exist in this release.
- Unrecognized production file types or unexpectedly missing media block staging for investigation. Excluded private files must never be re-exported into a public deployment.
- No approval is implied for the four placeholder curricula or the previous vocabulary defect.

## Rollback

The existing desktop application remains operational. The Windows installer backs up touched files under `backups/control-panel-v2.3.3-*` before applying any source replacement; its `finally` block restores them on failure. Production was never touched, so there is no server rollback action at this stage.


## v2.3.3 Windows installer corrective release

In v2.3.1, the existing draft-preservation preflight used an inline Python
`-c` expression. Windows PowerShell 5.1 stripped nested double quotes from
the native command line and caused `NameError: name 'utf' is not defined`.
That failure occurs before the installer copies any files or changes shortcuts.
The existing `lobby.json` is not invalid merely because this check failed.

v2.3.3 replaces the fragile inline expression with a dedicated
`validate_lobby_content_v233.py` executable. It reads UTF-8 (including BOM),
uses the same validation rules as the local editor, does not edit or normalize
the draft, and preserves the original file byte-for-byte. Any genuinely
invalid draft still blocks the update before any mutation.

The full release archive includes every previous 2.3.1 overlay component;
it does not replace original legacy automation, asset libraries, or website
files. Staging is still offline only, and no publication action is included.


## Authenticated snapshot reconciliation v2.3.3

If the captured site contains the catalog v1 + content v1 pair, stage-only mode validates and connects all 11 source pilot lessons using the current website’s `/#/lesson/<slug>` hash router. It checks every referenced media object, catalog slug, cover image, content and question count; never edits the original `lobby.json` and never mutates the captured site. The generated preview-only `lobby-preview/content/lobby.json` contains technically verified links and existing cover art. Formal teacher review and production promotion are **not** granted. The report includes a verified-lesson-evidence.csv. Without the authoritative pair, it retains unlinked placeholders and does not guess.
