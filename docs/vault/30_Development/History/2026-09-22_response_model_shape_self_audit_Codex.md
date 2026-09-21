---
doc_id: "CODEX-RESPONSE-SHAPE-AUDIT-2026-09-22"
title: "Strict response model producer-shape self-audit"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-09-22T05:06:00+09:00"
source_of_truth: "Git"
---

# Strict response model producer-shape self-audit

## Scope and method

Audited the 19 response-model classes added or narrowed in the 2026-09-22 contract work: ProjectCreate, DiscoveryAdmission, MemberRoleResult, ResourceOfferResult, WorkspaceStatus, NodeEnroll, ContributionRegistration/Contribution, HeartbeatAccepted, NodeLivenessSweep, DiscoveryAnnouncement, DiscoveryDecline, ProjectMemberRemoval, UserStatus, ProjectStatus, WorkspaceToolReadiness, WorkspaceToolResult, NodeResponse, and WorkspaceSummary. Read each producer/route serializer and compared branch output with its shared fixture and route/core tests. Conditional branches were checked separately for field presence, null-vs-omitted behavior, nested response bodies, and state values.

This was source review plus focused tests, not a live PostgreSQL or deployed-server audit. Source checks covered the relevant producers in `src/saintvision/services/projects.py`, `src/saintvision/services/settings.py`, `src/saintvision/services/storage.py`, and `src/saintvision/api/v1/{nodes,pools,projects,settings,storage}.py`; test/fixture coverage was checked in the focused response-contract suites and existing API tests.

## Findings

No currently produced response branch was found that the bound model rejects. Strict extra-field rejection remains intact. Several fixture/test shapes were narrower or unlike the actual producer branches, so regression coverage was expanded:

- Project creation has three `kernel_link` conditions and two wire shapes: `kernelNote` is a string when unlinked or linked-but-disabled, and is omitted when linked-and-enabled. Added a producer-level test for all three conditions. The route omission test remains; current real-PG evidence is unlinked only.
- Resource-offer responses have `kernelReason` omitted for an applied offer and present for recognized non-applied outcomes. Existing real-PG cases cover applied and `resource_not_registered`; existing integrity coverage includes `device_mapping_required`. This audit did not rerun those PostgreSQL cases.
- Workspace-tool responses have three relevant shapes: tool cleared (`toolName` and `toolReadiness` are explicit nulls); tool selected without a node (readiness object with null `nodeId`); tool selected with a node (populated readiness). Added route-response tests for the first two; existing fixture covers the populated case. Added service assertions for cleared and unassigned-node outputs, but that PostgreSQL-backed test skipped in this environment.
- Contribution response serialization always includes both capacity keys, each independently nullable, and status can be pending/active/revoked. Added a 3-by-4 serializer/model test covering all 12 status and nullable-field combinations. The route-contract tests for activation/revocation still use a synthetic response fixture; no live PostgreSQL lifecycle write was run here.
- Fresh node enrollment creates sequence 0 and no heartbeat timestamp. The shared enrollment fixture incorrectly represented a previously heartbeating node (sequence 12 with non-null timestamp). Corrected it to sequence 0 and `lastHeartbeatAt: null`; made the route-contract harness accept null and added assertions to the actual enrollment API test. That API test skipped because the PostgreSQL DSN is absent in this environment.
- Workspace summaries require `nodeId` and `toolName` keys and allow null values; create and populated-list fixtures exercise the all-null and populated cases. Workspace status tests enumerate all five lifecycle states and exact outgoing transition sets. Discovery announcement schema tests enumerate all four response states; the machine-credential route itself only returns `candidate` and rejects refreshes in other states.

The contract allows `ProjectCreateResponse.kernelNote` to be explicitly null although its current producer emits either a string or omits the key. This is a permissive schema shape, not an unaccepted producer output or current 500 risk; it was left unchanged because the response is intentionally optional and the broader nullable contract is already consumed by validation tests.

## Verification

At integration SHA `1c68b32beff0e09d6cc5cf48ca55e173502fb0e4`, `.venv/Scripts/python.exe` (Python 3.14.6), focused response-contract run:

`python -m pytest -q tests/core/test_write_response_contracts.py tests/core/test_workspace_response_contract.py tests/core/test_low_risk_write_response_contracts.py tests/test_projects.py::test_the_tool_choice_is_recorded_on_the_workspace tests/test_api.py::test_enrolled_node_is_registered_and_readable`

Repeated on the clean integration tip at 2026-09-22 05:04:32 KST. Result: exit 0, 101 passed, 2 skipped. Both skips were explicitly caused by absent `INV_TEST_ADMIN_DSN` (workspace-tool producer and real node-enrollment API tests); therefore their DB-backed actual output remains unverified in this run. A separate run of `tests/integration/test_write_response_contract_real_pg.py` also exited 0 with all 5 PostgreSQL cases skipped for the same reason (rerun at 2026-09-22 05:05:55 KST). At the same SHA, `check_contract_bindings.py` passed (46 fixtures/12 serving anchors), `check_docs.py` passed (731 versioned documents), and `check_ontology.py` passed. `sync_obsidian.py --check` was read-only and reported 21 pending exports, 0 conflicts; no apply was performed. No deployed HTTP/browser run was performed.

The first attempted run used system `C:\Python314\python.exe` and failed collection because its dependencies were unavailable; rerunning with the repository `.venv` succeeded. The failed attempt is an environment/interpreter mismatch, not a product test failure.

## Status

Author review and focused non-PG verification complete. The fixture correction and shape-coverage tests are author changes; independent review is pending. PostgreSQL-backed producer branches and hosted CI remain unverified at this SHA.
