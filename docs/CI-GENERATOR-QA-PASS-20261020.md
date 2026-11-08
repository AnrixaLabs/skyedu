# SkyED post-recovery CI generator checkpoint — 2026-10-20

This checkpoint records an actual GitHub Actions execution, not a claimed future test.

## Verified job results

At GitHub Actions [run 39284825729](https://github.com/AnrixaLabs/skyedu/actions/runs/39284825729),
the verify-homework job **completed successfully** for commit
`31a60f122725ffabe75e9a31205e077eebf08c08`.

The job log independently reports:

- Real generator import and CLI: PASS (`REAL_GENERATOR_IMPORT=PASS`).
- Actual `run_pipeline.py --dry-run`: PASS for `sky`, `sky_tiles`, `fun_mission`, and `strict_dark`.
- Full unit-test suite using genuine package imports: **21 tests, OK**.
- Isolated regression suite: **21 tests, OK**.
- Source integrity scanner: **PASS, missing_count=0**.
- Python syntax, WordPress PHP lint, Windows PowerShell *parser* and review-only plugin ZIP build: PASS.

**Important scope:** These are Python/Linux CI tests and simulated offline lessons. They do not verify Windows runner execution, generated Edge TTS MP3s, actual picture fidelity, public media HTTP status, WordPress drafts, or WeChat interactions.

## User-supplied Windows evidence and fix

The supplied `SkyED-Offline-QA-Evidence.zip` (SHA-256
`3ed622d176896e1b30e3a960402e41972dc63671f1087ef5b98e78447f34fac9`)
contains only a BLOCKED result due to Git-for-Windows root path formatting.
The restored generator itself was not exercised by that run.

The existing feature-branch QA runner was patched to resolve and normalize both
paths, compare case-insensitively, log dependency errors and handle PowerShell 5.1
native stderr. Latest patch `6c869bd484f05c1cca8689d4dda1e757deede243`
uses explicit `char[]` in `TrimEnd`.

## Still open

1. Fresh Windows execution of successor `SkyED-Homework-Release-QA-v2.0.9.zip` QA launcher.
2. Real (non-dry-run) EN and ZH audio and cards QA.
3. Explicitly approved WordPress **draft-only** rehearsal; media verification.
4. Physical Android/iOS and in-WeChat lesson exercise tests.
5. Approved plugin rollout and rollback check.

No DNS, production WordPress, prior lesson or live publishing changes authorized by this checkpoint.
