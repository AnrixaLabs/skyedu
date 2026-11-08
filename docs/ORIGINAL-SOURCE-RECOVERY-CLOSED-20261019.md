# SkyED original source recovery — verified checkpoint (2026-10-19)

## Outcome

**G0: ORIGINAL SOURCE FILE RECOVERY — PASS.**
**CI result on recovered branch — PENDING (queued at time of report).**
**Production readiness — NOT YET VERIFIED.**

- Repository: `AnrixaLabs/skyedu`
- Feature branch: `feature/homework-automation-v2`
- Original-only restore commit: [`301db8e47d86bb8b5bb268d325a0e60f57bebf22`](https://github.com/AnrixaLabs/skyedu/commit/301db8e47d86bb8b5bb268d325a0e60f57bebf22)
- Source authority: `C:\Users\user\PycharmProjects\skyed_automation`
- Recovery action: user-executed Windows fresh checkout, module verification, source integrity scan, pure regression test, commit and non-force push.
- Status recorded in Windows output: `PUSHED_TO_FEATURE_BRANCH`; `tests_passed=true`; `production_modified=false`.

## Independent GitHub verification

Authenticated GitHub commit API confirms commit `301db8e` is the feature-branch HEAD and its changeset **added** exactly these 13 modules:

```text
skyed/asset_library.py
skyed/fallback_cards.py
skyed/image_semantics.py
skyed/lesson_metadata.py
skyed/ocr_utils.py
skyed/picture_reader.py
skyed/pipeline_helpers.py
skyed/scene_fallbacks.py
skyed/tag_creator.py
skyed/tag_game_profiles.py
skyed/tag_registry.py
skyed/tag_s_env.py
skyed/thematic_backgrounds.py
```

The initial 12 files were checked against the user-supplied originals using **both**
SHA-256 on original ZIP members and Git blob SHA-1 hashes on the GitHub branch.
All **12 of 12** exact binary Git blob hashes and sizes match.

The 13th recovered file `skyed/ocr_utils.py` is present in GitHub at size 4517 bytes;
the Windows recovery reports SHA-256
`af3d7b2b094449b5867720320a5cf2848ce38f5083ad0ac83449edd4be744128`.
This SHA-256 value originates from the Windows recovery log; it was not independently
recomputed against the GitHub blob in this checkpoint.

## Verification status and gates

| Gate | Result |
|---|---|
| G0A: Original 12 source contents recovered | PASS: 12/12 exact Git object matches |
| G0B: OCR additional module present | PASS: present in recovery commit |
| G0C: Complete static import graph | PASS reported by user-executed integrity check; CI pending |
| G0D: Pure regression tests in recovered checkout | PASS reported by Windows recovery |
| G1: GitHub CI on recovery commit | PENDING — run [39279481154](https://github.com/AnrixaLabs/skyedu/actions/runs/39279481154) queued |
| G2: Runtime generator, image/TTS integrations | NOT RUN from this environment |
| G3: Stage WordPress draft, media HTTP verification | NOT RUN |
| G4: Real mobile and WeChat interactive exercises | NOT RUN |
| G5: Production release / automated scheduler | NOT AUTHORIZED |

## Immediate next steps

1. Allow GitHub Actions for recovery commit `301db8e` to finish; inspect integrity
   artifact, 17+ pure tests, Python syntax, PowerShell parser, PHP lint and
   renderer packaging. **Do not interpret a queued run as success.**
2. Use the new feature-branch checkout to test `python run_pipeline.py --help` in a
   controlled local environment with dependencies installed. No credentials needed.
3. Run a real lesson-generation rehearsal with new temporary output and no `--publish`.
   Verify local English/Chinese audio, cards, practice JSON and theme isolation.
4. Perform WordPress **draft-only** staging with an isolated test slug, after proper
   backups and explicit approval; verify media URLs / WeChat compatibility.
5. Only then consider releasing the reviewed plugin and enabling the scheduler.

Do not update existing lessons 181/182, reconfigure `skyed.org` DNS,
merge PR #3, or install production plugin while post-recovery release gates remain open.
