# SkyED Bright Course Hub v2.5.0 — Integration and publication handoff

**Scope:** Windows SkyED Control Panel, Course Hub editorial workspace, local Bright root release candidate, gated SSH deployment. This release does not publish the website automatically.

## What changed

- Resolved the navigation regression: the Bright candidate now serves `/` as its homepage; `/#/program/...` and `/#/lesson/...` stay in the same Bright application. Original `index.html` remains byte-for-byte at `/classic.html` for intentional fallback. There is no implicit link back to the old homepage.
- Regenerated **five** learning-path illustrations and **eleven** topic thumbnails as **1280px** high-DPI artwork, composed from the user's original 800x600 authenticated course-card images. No 200px card art is stretched; no original audio/card image was overwritten.
- Editor uses current program title/subtitle, supports Chinese editorial titles, lesson display titles/subtitles, group titles, updated hero copy, and creates extra draft lesson records. Existing source-backed eleven lessons, quizzes, MP3 and images remain immutable. New draft lessons must not be represented as published until separate media/content approval.
- Editor now supports 800×500 or larger **PNG/WebP** uploads (up to 12 MB) to a private loopback workspace with unpredictable filenames based on SHA-256, guarded by per-session token, allowed request origin, verified format and image dimensions, with atomic writes. File references are saved to local lobby.json only on explicit Save.
- Control Panel **Operations → Course Hub Integration** now provides "Build full Bright root candidate", "Preview full Bright website", and copyable preflight / guarded publication commands. All original Control Panel tasks are retained.
- Candidate builder verifies full source catalog, media hashes and all eleven routes, and writes a candidate manifest plus an empty, deliberately pending teacher-review template. Publication approval binds the **entire candidate file-tree SHA**, not only homepage markup.
- Versioned release deployment uses SSH strict host-key verification, full on-server SHA validation, an atomic current-symlink swap, independent public HTTPS smoke, and automatic rollback if smoke fails. It refuses to deploy if current is not a symlink or the live source differs from the captured authoritative baseline. A rollback receipt is generated after a successful promotion.

## Exact local workflow

1. Install the Control Panel update ZIP into `C:\Users\user\PycharmProjects\skyed_automation` using `scripts/Install-SkyED-ControlPanel-v2.5.0.ps1`. This verifies every source member, backs up existing executable files, preserves user-edited `lobby.json`, runs local QA, and restores previous files/shortcuts if a gate fails.
2. In Control Panel choose **Operations → Lobby Designer** to edit content. Select Programs / Units & groups / Lessons. For images click the upload field, then **Save to workspace**. You may add/delete/duplicate draft records; referenced records cannot be deleted.
3. In **Operations → Course Hub Integration** choose the original captured `snapshot-*` folder (autoselected when found), then **Build full Bright root candidate** and **Preview full Bright website**. The root is now Bright, old site only at `classic.html`.
4. In the generated `bright-report-*` folder, review `candidate-manifest.json` and `teacher-review-template.json`. Teacher sign-off remains required for each source lesson; complete the fields only following real teacher review.
5. Use **Copy production preflight** for a read-only SSH server audit. Actual publication requires the explicit guarded command, matching signed review manifest, and the host's current symlink to match the captured files. No other sites, WP databases, DNS, or ClassFlow servers are touched.

## Production limitations / explicit gates

- The remote host `8.210.9.172` is historical project context and must be independently confirmed before connecting; the release tool never auto-accepts an unknown SSH host key.
- Current server `current` must be an existing **symlink** and the releases parent must already exist. If not, preflight blocks safely without converting any existing directory to a symlink.
- The captured source catalog is still `published:false`. Technical route verification does **not** confer teacher approval; publishing remains gated by the human review file.
- The browser tests are performed with synthetic lesson records in CI; run final real-device acceptance on the staged candidate and inspect actual visual content before production.
- No external image-generation service, cloud AI, audio generator, or WordPress admin is connected to the local editor.

## Rollback and data preservation

- The Windows installer creates `backups/control-panel-v2.5.0-*` and retains prior shortcuts. Existing `site/content/lobby.json` is never overwritten.
- The production deployer uploads into a new version-specific release directory and requires the current symlink to point at the precise previous target before switching. The previous release stays in place. HTTP smoke failure triggers automatic rollback. A successful deployment records the prior and new release targets in `deployment-receipt.json`, which enables a guarded manual rollback.
