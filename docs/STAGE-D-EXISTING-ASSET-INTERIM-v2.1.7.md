# SkyED v2.1.7 — existing asset database and interim-picture policy

Date: 2026-10-20. Supersedes the extra mandatory label-free approval requirement proposed in Stage D v2.1.6 for established SkyED images.

The existing SkyED application already implements an indexed asset database (asset_library/manifests/library_index.json) and legacy Pictures/Flashcards directories. The prior isolated QA clone did not contain the production-local picture files, which explains its placeholders; it did not prove that the real database was inadequate. The Windows evidence verified four local pictures and 12 reused MP3 files.

The generator now preserves legacy picture selection first and uses approved exact-word indexed records where loose images are absent. Existing local_asset_match picture choices are permitted for interim guided recognition/listening practice without demanding a new picture_choice_review.json file. This is not a certification of blind listening ability: preprinted word labels can give the answer away.

Image provenance, file/URL checks, safe WordPress destination validation, and placeholder/fallback rejection remain mandatory. The optional strict mode SKYED_REQUIRE_LABEL_FREE_REVIEW=1 requires a hash-matched teacher approval manifest. Current pictures stay in place; later Sunny QLoRA picture regeneration is a separate versioned improvement after model tuning.

An additive read-only inventory utility, scripts/audit_existing_asset_library.py, can examine the actual Windows library, including index counts, selected image hashes and dimensions. The complete local production database was not available here, so it has not been globally audited.

No existing lesson, WordPress plugin installation, DNS setting, scheduler or production file was changed. The v0.4.7 plugin and all other working workflows remain unchanged. WordPress draft/mobile/WeChat release checks are still open.
