# SkyED Course Hub · Bright Learning v2.4.0

## Scope

Working responsive frontend for the previously approved bright SkyED identity.
The new interface is staged at `/lobby-preview/`, and **never** replaces the existing website root.
It contains a real Discover page, program cards, the five actual source groups,
a listing for the eleven captured lessons, a full lesson player for original media,
local vocabulary/audio, listening and speaking self-practice, and the original
8/5-question quizzes with genuinely checked answers. Chinese/English UI and saved
lessons are supported. The same Control Panel editor and existing draft schema are retained.

## Constraints & integrity

* All 442 original website files, 342 audio files and 91 picture files are **byte-identical** to the captured source.
* The 18 WebP decorative assets are derived from the user-approved generated SkyED visual mockups. They are UI artwork, never replacement vocabulary sources.
* The original `lobby.json` in the user's Control Panel is preserved. Derived routes are written only to a new temporary staged copy.
* Four example programs are clearly labelled **Coming soon**, not falsely presented as live. Only eleven source-backed pilot lessons are opened.
* Original source age bands are unspecified. UI makes no unsupported age, duration, teacher approval or completion claims.
* Browser progress/favorites use localStorage only; not a service-side student record. The Speak tab offers guided repeat-after-audio; there is no speech-recognition score or recording.
* The source `published:false` and teacher-review-pending status remain unchanged.
* No WordPress edits, production SSH writes, Nginx changes, API secrets, telemetry, ad scripts or backend modifications.

## Installation

Use `scripts/Install-SkyED-ControlPanel-v2.4.0.ps1` from the verified release ZIP. Windows PowerShell 5.1 is supported. Installer copies only manifest-allowlisted paths, verifies individual SHA-256, backs up modified files, runs local QA, restores on failure, and retains the saved lobby JSON. The desktop shortcut is updated.

## Local staging and preview

Run `scripts/Start-SkyED-CourseHub-Integration-v2.4.0.ps1 -Mode StageLocal -ProjectRoot <root> -SourceRoot <original-capture>` (no SSH required), or choose **Operations > Course Hub Integration** in Control Panel. Open the printed localhost preview URL. The original `/#/lesson/<slug>` routes continue working from the preserved root homepage. New lesson activities use the same **captured** `data/catalog.v1.json`, `data/content.v1.json` and 433 original media files.

## Release gates

Current state is **staged technical design preview only**. Remaining: real-device UI interaction and audio/speaking UX audit, individual teacher content approval, current live site revalidation, explicit production authorization, and controlled rollback plan. Do **not** deploy automatically.
