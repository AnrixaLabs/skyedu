# SkyED Stage C — Real bilingual media QA and design gate (2026-10-20)

## Evidence received / verified

User uploaded `SkyED-Real-Media-QA-Evidence.zip` (SHA-256 `c6f5b254343be098719674967642d68cbf3049f06b6889791430fff146ff82bb`).
The evidence records commit `277a199295c8802299db58ecc1f877861b7c81da`, `generator_exit_code=0`, 12 successful Edge TTS synthesis jobs (eight vocabulary clips plus four sentence clips), four generated vocabulary cards, and a 4-round Sky Tiles practice quiz. No WordPress publication.

**The validator crashed after generation** on `ModuleNotFoundError: No module named 'skyed'`, because the direct script invocation had `scripts/`, not the source repository root, on its Python import path. This is a QA harness defect, **not proof that the generated MP3/PNG bytes are invalid**. The uploaded evidence does NOT include media bytes because the old bundler only archived fully validated files.

**Additional release blocker:** Image generation logged four `local_asset_missing_placeholder` outcomes (cat, dog, apple, ball). These image cards must NOT be treated as approved production illustrations. No image meaning, TTS naturalness, or playback review has been performed.

## Corrective development update v2.1.1

- Fixed real-media validator Python import root using the script's actual checkout location.
- Always archive generated cards, EN/ZH MP3s, source image provenance, quiz JSON, and lesson HTML even if verification is blocked (100 MiB evidence limit, 8 MiB/member).
- Separate **technical file integrity** from **visual-source quality**; placeholder/fallback/unknown images produce `BLOCKED_VISUAL_CONTENT` while preserving checked MP3 durations and PNG dimensions.
- Before WordPress API media uploading, require the per-word image source report to show an `accepted` image or `local_asset_match`. Missing reports and placeholders fail closed; this machine gate **does not replace teacher review**.
- Added image-source gating regressions and the successor launcher `Start-SkyED-Media-QA-v2.1.1.ps1`.
- Previous original 13-module source and v0.4.6 renderer preserved. No production write.
- Latest CI on current branch to be verified after final source commit; do not mark future checks PASS prematurely.

## Review plan, after media and draft mechanics are confirmed

The requested professional **design and homework structure audit** is a mandatory separate gate, **not an optional cosmetic step**. Run after reliable image/audio QA, then again against a WordPress staging draft. Assess:

1. **Teaching structure:** learning objectives, age-appropriate word count, sentence-use coverage, listening → recognition → recall → production progression, question difficulty distribution, repetitions, clear EN/ZH instructions, and parent-facing support.
2. **Interactive behavior:** accurate answer-key mapping, incorrect-answer feedback, retry, progress/completion, playback buttons, score persistence expectations, and accessible fallbacks.
3. **Visual system:** SkyED brand identity, typography (especially CJK), icon style, consistency across Sky Classic, Sky Tiles, Mission and Strict Dark, visual hierarchy, contrast and target sizes.
4. **Mobile/WeChat:** 360/390/430-pixel layouts, sticky controls, screen reader labels, Android/iOS in-app browser playback, touch latency, font fallback, dynamic viewport and scroll behavior.
5. **Asset semantics:** teacher-visible image preview with word-picture meaning checks and voice/pronunciation review; reject NOOP/placeholder/fallback images.
6. **Page and WP integration:** lesson theme not leaking internal names, SEO metadata, script/style isolation with WordPress theme, footer/header treatment, public routes and cache behavior.

Deliver **before/after screenshots, section inventories, defect severity, actionable patch diff, tests and rollback**, preserving Lessons 181/182. Do not update design blindly from a static payload or without reproducible browser evidence.

## Release gates

- G0 genuine source modules: PASS.
- G1 cross-platform offline generator: PASS (Windows evidence 24/24, 4 themes).
- G2 real bilingual media and image semantic QA: OPEN; current evidence harness error + placeholder image blocker.
- G3 private WordPress draft and public media delivery: OPEN.
- G4 expert UX / homework-structure audit and real mobile/WeChat QA: OPEN.
- G5 staged plugin production rollout and scheduler: NOT AUTHORIZED.

DNS has not been modified. Historical SkyED apex/www IP evidence `8.210.9.172` is not a current DNS assertion.
