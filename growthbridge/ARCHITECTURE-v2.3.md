# SkyED GrowthBridge v2.3 Architecture

Status: operational successor to the validated v2.2 multi-institution baseline.

## 1. Architectural rule

v2.3 does not redesign tenancy. The v2.2 model remains authoritative:

```text
Global Account
  ├─ teacher → institution_memberships → teacher_class_assignments
  └─ parent  → guardian_links_v2 → students → institutions
```

The backend is the permission boundary. Hiding a control in React never grants or revokes authority.

## 2. Clients

```text
/teacher/ ─┐
           ├── /api/v1/ ─── persistent SQLite WAL database
/parent/ ──┘
```

Parent and Teacher are separate installable PWAs and separate client roles. They share one versioned backend and therefore synchronize through the same source of truth.

## 3. Tenant and access model

Institution-owned entities:
- classes;
- students;
- institution memberships;
- teacher/class assignments;
- evidence;
- class sessions and attendance;
- parent actions;
- audit events.

Global relationships:
- a teacher may have memberships in multiple institutions;
- a parent may link children from multiple institutions;
- a student belongs to one institution but may be enrolled in multiple classes there.

Owners/admins have institution-wide operational authority. A normal teacher can access only assigned classes and students enrolled in those classes. A parent can access only students explicitly linked through `guardian_links_v2`.

## 4. Operational workflows

### School operations

Owner/admin creates and edits institution data, classes and students. Students can be enrolled/removed from classes without duplicating the student identity. Archiving does not delete historical evidence/session records.

### Staff access

Teacher self-registration gives no institution access. Access is obtained by:
1. creating an institution (owner),
2. school-code join request followed by owner/admin approval, or
3. secure teacher invitation, optionally pre-assigned to classes.

Invitations and pending requests can be revoked/rejected. Membership roles/status and class assignments are independently managed.

### Guardian linking

Institution staff generates a one-time child claim code. A parent redeems it after authentication. Used, revoked and expired codes are rejected. Unlinking a child removes only the guardian relationship.

### Classroom

A session is unique for class + date. Saving the same class/date updates the session so a teacher can correct historical attendance, participation, confidence, homework and notes without creating duplicate sessions.

### Growth evidence

Evidence stores source teacher, class, student, date, kind, observation, interpretation, growth dimensions, visibility and publish state. Milestones are sourced evidence records, not a separate unverifiable score system.

### Parent action

Teachers can publish specific home actions. Parents can mark them done. Status is persisted and visible to both authorized clients.

### Reports

Reports aggregate only sourced records. Dimension values are evidence counts, not synthetic ability scores. Report periods are week/month/term/all.

## 5. Operational security

- passwords: PBKDF2-HMAC-SHA256;
- authentication sessions: random bearer tokens, hashes stored server-side;
- teacher invitations and child claims: random secrets, hashes stored server-side;
- session list/revocation available to account owner;
- mutation rate limiting by source address;
- audit events for critical mutations;
- no service-worker caching for `/api/`;
- server-side authorization for every protected endpoint.

## 6. Persistence and migration

v2.3 uses additive schema migration on the existing persistent database. New operational columns/tables are created if missing. Production deployer performs:

1. pre-deploy SQLite integrity check;
2. SQLite backup API snapshot;
3. backup integrity check;
4. immutable application build;
5. API restart/migration;
6. post-migration integrity check;
7. core-table row-preservation gate;
8. HTTP/TLS application and API probes.

No production database reset is permitted.

## 7. Scale boundary

SQLite WAL remains suitable for the current single-ECS, single-API-process topology. Before horizontally scaling the API or materially increasing write concurrency, migrate the normalized schema to PostgreSQL. That migration is a future scale task, not a v2.3 architectural rewrite.
