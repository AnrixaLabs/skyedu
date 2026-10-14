# SkyED GrowthBridge · 家校成长台

GrowthBridge is the independent family-facing growth/evidence platform in the SkyED ecosystem. It remains separate from ClassFlow and uses stable API/domain boundaries rather than direct ClassFlow database coupling.

## Current controlled successor

**v2.3.0 — Operational Product Release**

Production baseline while this branch is under review: **v2.2.0**.

Production target: `https://growth.skyed.org`

- Parent Client: `/parent/`
- Teacher Client: `/teacher/`
- Versioned API: `/api/v1/`

## Architectural baseline

v2.3 preserves the validated v2.2 multi-institution model. It is an operational-product release, not a tenancy/backend rewrite.

The authoritative model includes:

- global Parent and Teacher accounts plus multi-device sessions;
- institutions/schools with `owner`, `admin`, and `teacher` memberships;
- school-code join requests and secure teacher invitations;
- institution-owned classes and students;
- class rosters and teacher ↔ class access assignments;
- one-time Parent ↔ child claim codes;
- parent accounts that can link children from multiple institutions;
- institution/class/student-scoped evidence;
- class sessions and attendance;
- parent actions;
- audit records for security-relevant mutations.

## v2.3 operational scope

Teacher operations now include institution switching, class/student/roster management, claim-code management, session history and corrections, attendance, evidence editing/publishing, milestones, parent actions, reports, join-request handling, invitation revocation, staff role/status controls, teacher-class assignments, and audit viewing.

Parent operations now include cross-institution child switching, child claiming/unlinking, published evidence, milestones, attendance/classroom history, parent actions, period reports, profile/password management, and multi-device session revocation.

## Access rules

Backend authorization is authoritative.

- Owner/Admin: institution-wide management.
- Teacher: only explicitly assigned classes and their students/evidence unless elevated to Owner/Admin.
- Parent: only explicitly linked children; only published parent-visible/report evidence is returned.
- Registration alone grants no access to private student or institution data.

## Synchronization

Parent and Teacher desktop/mobile PWAs use the same `/api/v1/` backend and persistent store. The service worker never caches `/api/` responses. Clients refresh after mutations and on focus/visibility changes.

## Persistence and migration

Single-node production uses SQLite WAL at:

`/opt/skyed-growthbridge/data/growthbridge.db`

v2.3 uses additive migration only. The deployment controller performs database backup, integrity checks, post-migration integrity checks, and core-table row-preservation gates. PostgreSQL remains the scale gate before multi-node API deployment.

## Release artifacts

Canonical source package: `SkyED-GrowthBridge-v2.3.0-source.zip`

Canonical deployment launcher: `Start-SkyED-GrowthBridge-v2.3.0-Deploy-SFX-v1.0.0.ps1`

See `RELEASE-v2.3.0.md`, `ARCHITECTURE-v2.3.md`, and `SOURCE_MANIFEST-v2.3.0.txt` for the controlled release record.
