# SkyED GrowthBridge v2.2 Architecture

## Tenancy

`Institution` is the tenant boundary. Every class and student belongs to exactly one institution. Teacher permissions are institution memberships plus optional class assignments. Parent access is independent of institution membership and is derived only from explicit guardian links.

## Relationship model

```text
Account(teacher)
  └─ InstitutionMembership ─ Institution
          └─ Class
              ├─ ClassStudent ─ Student
              └─ TeacherClassAssignment ─ Account(teacher)

Account(parent)
  └─ GuardianLink ─ Student ─ Institution
```

A parent with children at two institutions has two independent `GuardianLink` paths. No institution gains visibility into another institution's student data.

## Authorization

All mutating and protected read endpoints validate the account role and relationship scope server-side.

- `owner/admin`: institution-wide management.
- `teacher`: assigned classes only.
- `parent`: linked students only.

Teacher invite URLs and child claim codes are random one-time credentials stored only as SHA-256 hashes in the database.

## Synchronization

Web and mobile PWA clients call the same `/api/v1/` backend. UI state refreshes on focus and at a bounded interval. API responses are `no-store`; the service worker deliberately bypasses `/api/` traffic so stale API data is never served from PWA cache.

## Current storage

SQLite WAL is used on the current single-node ECS deployment because it keeps the deployment dependency-free and transactionally safe for the present workload. The relational model deliberately maps directly to PostgreSQL tables so a later PostgreSQL move does not require redesigning client contracts.
