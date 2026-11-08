# SkyED Stage B certified; Stage C media QA handoff — 2026-10-20

## Audited Windows evidence (user-provided)

- Archive: SkyED-Offline-QA-Evidence(1).zip
- Archive SHA-256: `cd415194a28b884364e363f4cf8f2ed14f15b55fbf76d61769c1ac91a6897c30`
- Audited checkout: `e573bf0214eeabdb4081596a3c53c78fdb113512`
- Result: `OFFLINE_QA_PASS`, **24/24 unittest PASS**, **4/4 real generator dry-run themes PASS**, `missing_count=0`.
- Sky / Mission / Strict = 8 questions each, Tiles = 5; parser = 7 vocab/4 sentences.
- `php_lint=UNVERIFIED_PHP_CLI_MISSING` on local Windows; PHP renderer syntax PASS in GitHub Linux CI.
- Original PyCharm project, WordPress and DNS unaffected.

## Log-format fix verified

Historical Windows logs are UTF-16LE (PowerShell 5.1) and contain
`NativeCommandError` wrappers even when Python exit status is zero.
Updated `scripts/verify_offline_qa_evidence.py` supports UTF-16 and UTF-8,
records real unittest count and verified this archive as PASS.
Updated QA runner uses `scripts/qa_capture.py` to capture real subprocess
output in clean UTF-8, preserving nonzero exit codes and refusing overwrites.

## GitHub CI after change

Successful latest checked [run 39294509294](https://github.com/AnrixaLabs/skyedu/actions/runs/39294509294)
on commit `b030460dd71f5f6017ba8a278cccbd11c3be539e`:
**verify-homework=SUCCESS, verify-windows-homework=SUCCESS**.

## Next product gate: real bilingual media, strictly nonpublishing

- `scripts/qa_real_media.py` generates a new small generic classroom lesson
  using local-assets-only images and real EN/ZH Edge TTS. It explicitly requires
  `--generate` and uses an output location separate from the original PyCharm project.
- `scripts/Start-SkyED-Media-QA-v2.1.0.ps1` creates a fresh checkout and venv,
  installs minimal QA dependencies, produces `SkyED-Real-Media-QA-Evidence.zip`.
- Technical gate checks required vocabulary/sentence/quiz media references,
  PNG decoding/dimensions, MP3 duration/bitrate via mutagen, hashes, and HTML
  files. Teacher review for actual pedagogical image/audio content remains required.
- Run does **not** pass WordPress credentials or call `--publish`. Real Edge TTS
  network requests are expected and may fail on restrictive networks.

## Release governance

Stage B **PASS**. Stage C **PENDING**. WordPress draft, mobile and WeChat
tests **NOT STARTED**. No existing lessons updated, plugin v0.4.6 unchanged,
production release/scheduler **NOT AUTHORIZED**.

Historical skyed.org ECS IP 8.210.9.172 should not be treated as a fresh DNS observation.
