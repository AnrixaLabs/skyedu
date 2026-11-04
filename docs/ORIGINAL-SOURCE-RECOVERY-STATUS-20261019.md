# SkyED original Python module recovery — verified upload, pending GitHub import

Date: 2026-10-19

**AUTHENTIC ORIGINAL SOURCE FOUND — DO NOT REIMPLEMENT MODULES.**
**12 source modules recovered and verified externally; NOT YET COMMITTED TO GITHUB.**

The user supplied `SkyED-Original-Modules-REVIEW.zip`, exported read-only from
`C:\\Users\\user\\PycharmProjects\\skyed_automation`.
The archive has 12 Python modules and a SHA-256 manifest. All twelve file hashes match
both the archive manifest and the original Windows inventory. All twelve parse as Python,
and the original-code screening found no embedded credential-pattern matches.
No code was copied into the repository or deployed as part of this documentation commit.

## Verified exact source-file SHA-256 values

| Module under `skyed/` | SHA-256 |
|---|---|
| asset_library.py | `36a87729c79b9f121ac596a110c779bad455890872a71b6aed59280c0031ffbb` |
| fallback_cards.py | `2e8c6b700e806798f9ad345bb4a2ec02042b1a0631d0f90d604e1eda33c12c88` |
| image_semantics.py | `091747fecc82e3cfb7df2d49feadd77d55c7b4f79cfa67cf5f73c9e627a304bf` |
| lesson_metadata.py | `f70fb30555cf5e32502ad3ca4238817b3bfbb591c544a77d44dde69139540dea` |
| picture_reader.py | `1eea728e494e877120cb0270c97122903bb96b628010cab14324a3c0ad36aa7b` |
| pipeline_helpers.py | `2dafadb04cd476d58821e59e6806ef6f293188aa92b52a1e2007e3a1fbb3b89e` |
| scene_fallbacks.py | `77957ff6782097d927d6c92743fe135bce6d671b1ef53a7669947475e21b861c` |
| tag_creator.py | `8bca0d6690cf3a3626fac4bd70b7094f14388d778d960c5142d4201a3065c83d` |
| tag_game_profiles.py | `24a553473fc578575860fa553646fbb303d93b416c34b9e25766449f75492a2f` |
| tag_registry.py | `8d9a5d0d51a37b0a0f8d23d734656c515d2679c5ccd9e87537297838d9c1b354` |
| tag_s_env.py | `f0409f1c23450b13a259b95e9e5b7fda4a1d0c33d05c672bff7d5a39d4415e14` |
| thematic_backgrounds.py | `be578d93e6a66b2f2ce36e92fb0aa3ca4eced8ca06be87481e73160d3f1e6d6f` |

## Transitive dependency discovered after restoring missing files for static analysis

`skyed/picture_reader.py` imports `skyed.ocr_utils`, which does not exist on the
GitHub development branch and is **not included** in the uploaded 12-module ZIP.
It could not have appeared in the initial 12-module repo scan because the importer
(`picture_reader.py`) was absent.

Recover `ocr_utils.py` from the user's same working Windows project if it exists,
then rerun the full recursive source integrity scan. Newly exposed imports must be
recovered only from authentic sources, not recreated or stubbed.

## Next step: vetted Windows restoration (no automatic server changes)

The separate deliverable `SkyED-Homework-Source-Restoration-v2.0.6.zip` contains the
verified 12 original modules, their SHA-256 manifest, and a safe fresh-clone
`Restore-SkyED-Originals-v2.0.6.ps1` procedure. Run it on the Windows host containing
the original PyCharm workspace. It can resolve further missing `skyed/*.py` imports
from that same verified source root, run source-integrity and regression tests,
then make a source-only commit and **optionally** push to
`feature/homework-automation-v2`. It never touches production WordPress, DNS,
the original PyCharm folder or other branches.

Do NOT declare G0 source recovery PASS or merge PR #3 until actual module commits
and GitHub CI successfully verify the complete import graph and regression suite.
No production plugin upload or unattended publishing is authorized.
