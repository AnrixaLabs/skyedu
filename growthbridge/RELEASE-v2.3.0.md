# SkyED GrowthBridge v2.3.0 — Operational Product Release

Status: built and locally validated; production promotion remains a separate fail-closed deployment operation.

## Baseline

v2.2.0 is the validated multi-institution architectural baseline. v2.3.0 preserves that tenancy/account model and adds daily operational workflows rather than replacing the backend or resetting data.

## Operational scope

Teacher client:
- institution switching and institution edit;
- class create/edit/archive;
- student create/edit/archive and multi-class enrollment;
- class roster operations;
- guardian claim-code generation/history/revocation;
- class session history and corrections;
- attendance plus participation/confidence/homework notes;
- evidence editing/publishing and milestone evidence;
- parent actions;
- teacher report preview;
- teacher join-request approval/rejection;
- teacher invitation creation/revocation;
- staff role/status controls;
- teacher-class assignment matrix;
- institution audit viewer.

Parent client:
- cross-institution child linking and switching;
- child unlinking without deleting the school-owned student;
- published evidence and milestones;
- attendance/classroom history;
- parent actions and completion synchronization;
- week/month/term/all reports;
- profile/password management;
- multi-device session listing/revocation.

## Data safety

- additive schema migration only;
- no production database reset;
- persistent SQLite WAL database remains outside immutable releases;
- pre-deploy database integrity check;
- database snapshot backup and backup integrity check;
- post-migration integrity check;
- core v2.2 table row-preservation gate;
- immutable application release and atomic current symlink activation;
- protected-path guards for the main SkyED site and ClassFlow.

## Validation completed before packaging

The v2.2 regression suite remains green:

```text
BACKEND_MULTI_TENANT_INTEGRATION_GATE=PASS
CROSS_INSTITUTION_PARENT_MODEL_GATE=PASS
TEACHER_CLASS_SCOPE_GATE=PASS
STUDENT_CREATE_ATOMICITY_GATE=PASS
EVIDENCE_OWNERSHIP_GATE=PASS
MEMBERSHIP_DOWNGRADE_GUARD_GATE=PASS
```

The v2.3 operational suite passes:

```text
SCHOOL_OPERATION_WORKFLOW_GATE=PASS
CLASS_ROSTER_WORKFLOW_GATE=PASS
SESSION_HISTORY_CORRECTION_GATE=PASS
PARENT_CHILD_LINK_WORKFLOW_GATE=PASS
PARENT_ACTION_SYNC_GATE=PASS
MILESTONE_REPORT_GATE=PASS
INVITATION_REVOCATION_GATE=PASS
JOIN_REQUEST_REJECTION_GATE=PASS
STAFF_ROLE_POLICY_GATE=PASS
MULTI_DEVICE_SESSION_GATE=PASS
AUDIT_VIEWER_GATE=PASS
```

Static/source validation also passed. The local environment did not provide the npm dependency registry, so the real `npm install` + `tsc -b && vite build` is deliberately retained as a fail-closed deployment gate on the ECS; production must not be declared until those remote gates and the final TLS operational gate pass.

## Canonical artifacts

Source ZIP SHA-256:

`2d80f1e4dbb0021fb45a6a4a6a2da271a5554a0794c34958731f93656e810d79`

Deployment source tar SHA-256:

`6be8aba9c1d63c502483e993e23f61978c2de3c3ae0d779c75f90e41fc866b79`

Remote deployment controller SHA-256:

`785b5dd091ea5061be96cf3bd45bf1669c3d7fa92671525520f1c0a1775278a9`

Self-extracting PowerShell deployment launcher SHA-256:

`108584cf2d784118eb133d1ab2db28c740e8bf80ca27e43dedf02a847a2053e8`

Expected production final gate:

`FINAL_GATE=PASS state=DEPLOYED_TLS_OPERATIONAL_V2_3`
