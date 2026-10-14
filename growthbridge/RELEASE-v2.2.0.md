# SkyED GrowthBridge v2.2.0 Release Record

Status: **built and validated; production promotion is performed separately by the fail-closed SFX deployment controller.**

## Scope

v2.2.0 replaces the remaining demo-seed assumptions with a normalized multi-institution foundation:

- school/institution tenant model;
- global Parent and Teacher accounts;
- institution memberships: owner/admin/teacher;
- teacher self-registration;
- school-code join requests and owner/admin approval;
- secure teacher invitations with optional class pre-assignment;
- institution-owned classes and students;
- class rosters;
- teacher-to-class assignments;
- one-time parent-to-child claim codes;
- parents may link children from different institutions;
- institution/class/student-scoped evidence;
- class sessions and attendance;
- server-side authorization and audit records;
- synchronized Parent and Teacher PWAs using the same `/api/v1/` backend.

## Canonical artifacts

- `SkyED-GrowthBridge-v2.2.0-source.zip`
  - SHA-256: `73c859c39a381af9ce7c388beeaa56a5feef808a8a0cb7dc695e26cbabff1ff4`
- deployment source tar used inside the SFX
  - SHA-256: `2e9e6237a880e4725d98e46575b211aeeb05ed0ffbb6e97ba38e09eadb1e2231`
- remote fail-closed deployer
  - SHA-256: `af6559899a36d43da365b9c786baa8fae8d17925363a0f3a8ed245334ae47b22`
- `Start-SkyED-GrowthBridge-v2.2.0-Deploy-SFX-v1.0.0.ps1`
  - SHA-256: `aead1bfb2bb5667f016a84fe1bb3cb18ac930060ad037c733e20c50e1297d9ba`

## Validation gates completed before packaging

- `BACKEND_MULTI_TENANT_INTEGRATION_GATE=PASS`
- `CROSS_INSTITUTION_PARENT_MODEL_GATE=PASS`
- `TEACHER_CLASS_SCOPE_GATE=PASS`
- `STUDENT_CREATE_ATOMICITY_GATE=PASS`
- `EVIDENCE_OWNERSHIP_GATE=PASS`
- `MEMBERSHIP_DOWNGRADE_GUARD_GATE=PASS`
- TypeScript syntax validation PASS;
- permissive local structural TypeScript check PASS;
- remote deployment controller Python compile PASS;
- source archive integrity PASS;
- SFX embedded source/deployer round-trip hashes PASS;
- ASCII/CRLF/PowerShell here-string structure PASS.

A full Vite production build is intentionally repeated on the ECS during deployment. Promotion fails closed if the real TypeScript/Vite build, backend integration tests, API health, Nginx/TLS checks, or protected-path guards fail.

## Production boundary

GrowthBridge remains independent from ClassFlow. The deployment controller protects:

- `/var/www/skyed.org`
- `/opt/classflow`

Expected successful production state after an actual deployment run:

`FINAL_GATE=PASS state=DEPLOYED_TLS_MULTI_TENANT_V2_2`
