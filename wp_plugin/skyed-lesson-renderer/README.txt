SkyED Lesson Renderer v0.4.7 — controlled staging candidate

Changes in this review build:
- Sky Tiles picture questions use a compact accessible 2 × 2 choice grid.
- Wrong picture taps do not count as completed listening rounds.
- Check answers cannot prematurely expose solutions before all kid rounds finish.
- Improves picture-option accessibility labels; preserves all existing lesson themes.
- All existing cards, audio, practice variants and safe WordPress renderer features remain.

Release status: REVIEW ONLY. NOT APPROVED FOR PRODUCTION INSTALLATION.
The connected generator also requires teacher-approved label-free picture
choices with matching SHA-256 evidence before any publishing operation.

Do not deploy on skyed.org or overwrite the current live plugin until:
(1) local QA, (2) draft-only WordPress staging, (3) mobile/WeChat
interactive testing, (4) backup and rollback approval are complete.
