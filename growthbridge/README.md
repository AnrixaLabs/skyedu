# SkyED GrowthBridge · 家校成长台

GrowthBridge is the independent family-facing growth/evidence platform in the SkyED ecosystem. It remains separate from ClassFlow and uses stable API/domain boundaries rather than direct ClassFlow database coupling.

## Current controlled release

**v2.2.0 — multi-institution foundation**

Production target: `https://growth.skyed.org`

- Parent Client: `/parent/`
- Teacher Client: `/teacher/`
- Versioned API: `/api/v1/`

## v2.2 model

GrowthBridge is no longer demo-seed-driven. The authoritative persistent model is institution-scoped and includes:

- global Parent and Teacher accounts plus multi-device sessions;
- institutions/schools with `owner`, `admin`, and `teacher` memberships;
- teacher self-registration;
- school-code join requests with Owner/Admin approval;
- secure teacher invitations with optional class pre-assignment;
- institution-owned class database;
- institution-owned student database;
- class rosters;
- teacher ↔ class access assignments;
- one-time Parent ↔ child claim codes;
- parent accounts that can link children from multiple institutions;
- institution/class/student-scoped growth evidence;
- class sessions and attendance records;
- audit records for security-relevant mutations.

## Access rules

Backend authorization is authoritative.

- Owner/Admin: institution-wide management.
- Teacher: only explicitly assigned classes and their students/evidence unless elevated to Owner/Admin.
- Parent: only explicitly linked children; only published parent-visible/report evidence is returned.
- Registration alone grants no access to private student or institution data.

## Synchronization

Parent and Teacher desktop/mobile PWAs use the same `/api/v1/` backend and persistent store. The service worker never caches `/api/` responses. Client state refreshes after mutations, on focus/visibility changes, and at a bounded interval.

## Current persistence

Single-node production uses SQLite WAL at:

`/opt/skyed-growthbridge/data/growthbridge.db`

The schema is normalized and intentionally PostgreSQL-mappable. PostgreSQL is the required scale gate before multi-node API deployment.

## Release artifacts

Canonical source package: `SkyED-GrowthBridge-v2.2.0-source.zip`

Canonical deployment launcher: `Start-SkyED-GrowthBridge-v2.2.0-Deploy-SFX-v1.0.0.ps1`

See `RELEASE-v2.2.0.md` for SHA-256 values and validation gates.
