# SkyED Homework — Controlled Product Hardening / Release Plan

Date: 2026-10-19. Status: DEVELOPMENT BRANCH — NOT DEPLOYED.
Scope: generate + publish homework for existing physical-classroom students.
Excluded: worksheet generator, parent accounts, online courses, ecosystem integration, automated live publishing until authorized.

## Authority and host

- Canonical website and publication destination: `https://skyed.org`.
- Legacy `skyedu.fun` has no usable lesson payload and is forbidden for new writes.
- Historical confirmed A-record evidence from SkyED production ECS: apex and www -> `8.210.9.172`.
- **Current A/AAAA answers are not proven** by this work environment (external resolver/network access fails).
- Never change the DNS zone or pin website traffic to a remembered IP.
- Before deployment run `python scripts/check_production_network.py --expect-ip 8.210.9.172 --report dns-report.json` from a networked workstation. Investigate discrepancies, do not silently overwrite.

## Source-of-truth blocker (G0)

The GitHub checkout is incomplete, as proven by Python imports referencing absent files.
Known examples: `skyed/pipeline_helpers.py`, `skyed/lesson_metadata.py`,
`skyed/tag_registry.py`, `skyed/picture_reader.py`,
`skyed/tag_creator.py`, `skyed/tag_game_profiles.py`,
`skyed/asset_library.py`, `skyed/scene_fallbacks.py`, `skyed/thematic_backgrounds.py`,
`skyed/tag_s_env.py`, `skyed/fallback_cards.py`, and `skyed/image_semantics.py`.
A read-only source scan identified at least **12 distinct missing modules**.
The integrity tool is the authoritative checker, including dynamic source additions. Some files may be only present on Windows.
GitHub commits for several named paths had no historical copy.

Run:
```powershell
git clone https://github.com/AnrixaLabs/skyedu.git
cd skyedu
git switch feature/homework-automation-v2
python scripts/verify_repo_integrity.py --repo . --json integrity-before.json
# Choose --source as the ACTUAL original SkyED working directory, not output/ or a new checkout
python scripts/recover_local_modules.py --source "C:\PATH\TO\WORKING\SKYED" --repo . --report recovery-preview.json
# Review file identities, source SHA256 and listed file paths
python scripts/recover_local_modules.py --source "C:\PATH\TO\WORKING\SKYED" --repo . --apply --report recovery-applied.json
python scripts/verify_repo_integrity.py --repo . --json integrity-after.json
python -m unittest discover -s tests -v
```
If modules remain missing, STOP and locate originals. Do not create placeholder files to bypass the gate.
Before committing recovered files, inspect for embedded credentials, tokens, private student information, and absolute machine paths.
Commit recovered source to the same branch after manual review. Never commit `.env` or credential files.

## Current corrections (development branch)

1. Default .env example switches canonical publishing host to `skyed.org`.
2. Preflight rejects missing/too-small generated media before any WordPress call.
3. Rewritten remote vocabulary, sentence and quiz media references validated before publishing pages.
4. WordPress session must not transparently retry non-idempotent POSTs; ambiguous writes now raise explicit failure.
5. Existing renderer plugin's raw internal `fun_mission` eyebrow replaced by readable copy.
6. Existing misleading teacher vocabulary coverage warning removed from public child pages; report coverage computed consistently in pipeline.
7. Kindergarten audio-first package builder is additive and NOT wired into live renderer yet.
8. Scheduler foundation exists on branch, but no scheduler service is configured or deployed.

## Release gates

G0 — Source recovered: all project imports resolvable and known Windows runtime compared against GitHub. BLOCKING.
G1 — Unit tests: 100% passing, Python syntax, PHP lint, input examples and all established quiz modes. BLOCKING.
G2 — WordPress stage: clone or separate staging page; verify plugin version and API auth outside code, test production-shaped lesson creation as **draft**. BLOCKING.
G3 — Asset QA: generated EN and ZH audio playable, images correct; actual remote URLs GET 200/206 with sane MIME and body; no missing quiz assets. BLOCKING.
G4 — UX QA: Lesson 181 mission and Lesson 182 tiles in real mobile browser AND actual WeChat; tap/replay, right/wrong feedback, retry/finish, 390px viewport. BLOCKING.
G5 — Controlled rollout: verify one new draft, teacher approval, then publish a single NEW lesson. Existing /en/lesson181/ and /en/lesson182/ immutable.
G6 — Operations: backup WP DB/plugin/media, observe error logs, keep rollback candidate. Only after G0-G5 PASS evaluate daily scheduler. No unattended publishing yet.

## Safety notes and known limitations

- Preflight only checks that local files look present/nontrivial and generated remote references look like secure URLs; it does **not** prove remote files return playable media. A separate network smoke test is still mandatory.
- A failed or ambiguous WordPress write can leave an uploaded asset or a created post; no automatic retry until remote state is reconciled.
- Current WordPress media uploads can duplicate files; content-hash dedupe/upsert is deferred until API attachment identity and race behavior are verified.
- New publication currently creates a post/page with new slug; updating existing pages is NOT implemented or authorized.
- WordPress plugin release file is `wp_plugin/skyed-lesson-renderer/skyed-lesson-renderer.php` v0.4.6 on branch; never upload until G0-G4.
- Source, audit, and generated packages must not contain WP application passwords, session cookies, or student records.
- Existing GUI/pipeline cannot run from incomplete GitHub snapshot; safe recovery of original dependencies takes priority over feature expansion.

## Rollback

Retain original plugin ZIP and a database snapshot. Rollback is file restore + WordPress plugin cache clearing after confirming stored payload compatibility. Do not delete the successful old lesson pages. If live smoke test fails, stop new publishing immediately and revert only the new components.

## Current completion criteria

Current task is **development hardening**, NOT production-ready: pass missing-source gate and run complete end-to-end rehearsal before release approval.
