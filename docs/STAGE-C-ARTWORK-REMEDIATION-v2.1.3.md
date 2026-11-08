# SkyED Stage C artwork gate — verified local inspection (2026-10-20)

The user ran the read-only v2.1.2 inspector on the **31-member** Windows evidence archive with SHA-256 `99b90c6bf6723f1f48d62a4c4ed96454d79b08cf7032591caa87a008852e4219`.

**Verified by user's Windows read-only report:** generator exit 0, 12/12 MP3 bytes matched their evidence hashes, 4/4 vocabulary PNG bytes matched, 0 missing/corrupt media references and no WordPress writes. All 4 image provenance statuses are `local_asset_missing_placeholder`: `cat`, `dog`, `apple`, `ball`.

This is an intended **BLOCKED_VISUAL_CONTENT** release gate, **not** evidence of a generator or TTS failure. Do **not** weaken the image-source publication gate, and do not repeat Edge TTS just to replace images.

## Image remediation workflow

An additive offline helper package `SkyED-Homework-Release-QA-v2.1.3.zip` now includes:
- `Repair-SkyED-Artwork-v2.1.3.ps1`: read-only preview by default, with an explicit apply mode;
- `scripts/qa_reuse_audio_artwork.py`: hash-pinned archive inspection and teacher-supplied image lookup, rebuilding cards through **existing** `skyed.cards.generate_vocab_cards` in a separate working copy, retaining the original MP3 hashes;
- `tests/test_qa_reuse_audio_artwork.py`: 4 isolated tests including duplicate image rejection, source SHA validation and unchanged audio in a mocked card renderer;
- an isolated review.html contact sheet plus provenance/report ZIP on an approved-image rebuild.

This optional tooling is provided in the successor ZIP, **not yet merged into production code**. Real end-to-end image import against the actual Windows venv is NOT YET VERIFIED. Use only user-owned/licensed and teacher-selected images. The original GitHub generator remains authoritative; do not reimplement it. No live WordPress or DNS modifications.

## Required next evidence

1. Inspect the *existing* PyCharm `asset_library/Pictures` and `asset_library/Flashcards` folders for proper exact-word images (preview only).
2. If available, rebuild only cards in a newly created QA folder; preserve all original audio bytes and original 31-member archive. If unavailable, source/approve real illustrations.
3. Teacher inspection of picture-to-word correctness and EN/ZH audio quality; uploading the real 31-member ZIP enables independent content review.
4. One strictly draft-only WordPress rehearsal after technical and teacher approval.
5. User-requested full visual/pedagogical audit on the final rendered page: layout, icons, CJK fonts, mobile/WeChat, learning progression, response correctness and navigation. Existing Lessons 181/182 remain untouched until approval.

Current release: **HOLD**. This report does not claim voice or child-facing illustration semantics were inspected directly.
