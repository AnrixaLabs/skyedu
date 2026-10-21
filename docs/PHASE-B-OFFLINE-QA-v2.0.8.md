# SkyED Homework — Phase B operational reliability, 2026-10-19

**Status: CODE CORRECTIONS COMMITTED; NEW RUNTIME CI CHECKS QUEUED.**
**Safe branch:** feature/homework-automation-v2. **Production deployment:** NONE.

## Completed code improvements

| Area | Change | Verification route |
|---|---|---|
| Original source | 13 authentic modules restored as commit 301db8e | SHA-256 / Git blob evidence |
| Vocabulary media | quizgen uses slugify_file compatible with card and TTS names such as living_room | tests/test_quiz_media_parity.py |
| Sentence audio | quizgen stem now uses the same filename normalization as pipeline_helpers | Media-parity test |
| Sentence cloze | Replaced four literal ASCII backspace characters with real regex word boundaries | Cloze regression tests |
| Coverage report | Used words, unused words and ratio recomputed consistently | tests/test_lesson_consistency.py |
| WordPress safety | Fail-closed local/remote media and destination gates; ambiguous POST never automatically retried | tests/test_publish_gates.py |
| Real pipeline QA | scripts/smoke_generator_offline.py tests four existing themes without generating media or making web writes | GitHub CI and Windows QA |
| Windows QA | scripts/Run-SkyED-Offline-QA-v2.0.8.ps1 creates separate venv/evidence, does not overwrite working project | Windows execution |

## What offline QA proves vs cannot prove

The dry-run exercises the real parser, lesson HTML, quiz generation, theme-specific
questions, and essential filename contracts. The generated media paths are
EXPECTED to be unresolved in dry-run because images and Edge TTS are not invoked.

Do NOT mistake green dry-run results for valid audio playback or public URLs.

## Independent execution and evidence

- Prior restored-source recovery tests: 16/16 PASS in the container (v2.0.7).
- CI workflow now includes: source syntax, PowerShell parser, PHP lint, real generator
  import and CLI, four-theme dry-run, full unittest discovery,
  source-integrity evidence, and review-only plugin packaging.
- Current CI jobs for the new commits were QUEUED at last check. No PASS claimed.
- Successor QA package: SkyED-Homework-Release-QA-v2.0.8.zip.
- Complete branch source ZIP: https://github.com/AnrixaLabs/skyedu/archive/refs/heads/feature/homework-automation-v2.zip
- Draft PR #3: https://github.com/AnrixaLabs/skyedu/pull/3

## Release gates

1. G1: Latest GitHub CI PASS, source imports complete, four dry-run variants PASS, full tests PASS. OPEN.
2. G2: Generate actual word cards and English/Chinese mp3, inspect samples and file references. OPEN.
3. G3: WordPress backup, then one NEW staging draft via --publish-status draft after explicit approval; verify media status, MIME and content. OPEN.
4. G4: Physical iOS/Android and WeChat built-in browser, listening, correct/incorrect responses, retry, and mobile layout. OPEN.
5. G5: Approved staged plugin update, production promotion, verified rollback, then scheduler. OPEN.

Production skyed.org, Lesson 181/182, DNS and WordPress remain unchanged.
Historical A-record evidence was 8.210.9.172 for apex and www; do NOT presume fresh
DNS is identical without a current external resolution probe.
