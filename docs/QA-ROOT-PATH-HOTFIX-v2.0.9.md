# SkyED offline QA Windows path compatibility — v2.0.9

Date: 2026-10-20. This is a development/testing corrective patch, not a production release.

## Evidence

User-supplied QA ZIP: `SkyED-Offline-QA-Evidence.zip`, SHA-256 `3ed622d176896e1b30e3a960402e41972dc63671f1087ef5b98e78447f34fac9`.

Its only entry is `results.json`, with `schema=skyed.qa.v2.0.8`,
`status=BLOCKED`, empty `checks`, and `error=Invalid repository root`.

This failure happens before Python virtualenv, generator CLI, unit tests, four-theme lesson dry-run, PHP lint, or media checks. No SkyED generator failure is established by this evidence.

## Root cause

On Windows, Git generally reports an absolute path such as `C:/Users/user/.../skyedu`, while Windows PowerShell's `Resolve-Path` reports `C:\Users\user\...\skyedu`.

The earlier QA runner compared the raw strings. The filesystem location can be identical despite the differing path formatting.

## Corrections

1. `scripts/Run-SkyED-Offline-QA-v2.0.8.ps1` now resolves both paths, canonicalizes them through `System.IO.Path.GetFullPath`, removes trailing separators, and checks equality using `OrdinalIgnoreCase`. It still blocks actual different roots.
2. The runner now reports `git_root=PASS` once verified, preserves a `dependencies.log` and captures Python stderr without false `ErrorActionPreference=Stop` failures under Windows PowerShell 5.1.
3. `scripts/verify_offline_qa_evidence.py` independently rejects incomplete evidence, including any reported PASS lacking the full set of real generator checks and four per-theme results.
4. `tests/test_verify_offline_qa_evidence.py` tests an internally complete archive, an early BLOCKED run and missing smoke evidence.
5. The additive `SkyED-Homework-Release-QA-v2.0.9.zip` updates the standalone Windows QA launcher and preserves all original recovered sources and verification records.

## Test and release gates

- Verified source: 13 authentic modules committed to feature branch, unchanged by this fix.
- Given Windows evidence: BLOCKED **at QA harness**, no generator tests executed.
- Hotfix logic: committed; live Windows execution remains to be verified from next evidence upload.
- GitHub expanded integration run: queued at time of update, not marked passed.
- WordPress production, plugin, skyed.org DNS and Lessons 181/182: not modified.
- Do not merge or deploy until fresh offline QA demonstrates all gates.

Windows launch command from new ZIP:

```powershell
Set-Location "$env:USERPROFILE\Downloads"
Expand-Archive -LiteralPath '.\SkyED-Homework-Release-QA-v2.0.9.zip' -DestinationPath '.\SkyED-Homework-Release-QA-v2.0.9'
powershell -NoProfile -ExecutionPolicy Bypass -File '.\SkyED-Homework-Release-QA-v2.0.9\SkyED-Homework-Release-QA-v2.0.9\Start-SkyED-QA-v2.0.9.ps1'
```

Upload the next `SkyED-Offline-QA-Evidence.zip` produced by this command.

