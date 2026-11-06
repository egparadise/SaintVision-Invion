---
doc_id: "HIST-FLEET5-B-REV8-REVOKE-PORTCUT-001"
title: "FLEET5 Rev8 recovery lanes, candidate hints and bounded revoke analysis pilot"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Actual independent Claude Rev8 delta review via Root pending"
updated: "2026-11-06T15:40:00+09:00"
source_of_truth: "Git"
---

# Scope and exact inputs

Owner Codex, card FLEET5-B-REV8-REVOKE-PORTCUT-20261106, same dispatched
`task_a8fd2969f0b3 / ctx_6f0f8253b8a7`. Branch
`agent/codex/fleet5-b-rev8-revoke-portcut-20261106` starts at final Rev7
`33f7c6b48883cb06d1ea7d645bdb88634eb1bca0`. The unchanged product source is
`72028cbac903c4415d9979f980a6e0f9948e914f`. This is a DOCS/schema/static/symbolic
proposal, not an integrated product candidate. Root decision
`msg_aca0d787de3d` grants this one narrow delta and subsequent ONE actual Claude
delta review through Root. No product, DB, port, credential, code, partial freeze,
runtime or physical acceptance grant follows.

Actual prior independent Claude review
`97bb2f6734ee328fe86031053bb7490ab011a523` says REVISION_REQUIRED B7-M1/M2 and
L1/L2. Root verified its exact Docs42172425569/job127743102797/head/ref/event/
workflow/correlation/attempt1 and all19 steps. Those prior verdict and attack
bytes are retained in own Evidence. Review delivery success is not proposal
acceptance. B6 closed lock/source/plain-owner parts and B5 signer/outbox/root
proofs are retained without inventing a new independent review.

Root's decision named Index443/Codex404; the actual first read observed
Index1.0.444/Codex1.0.405 updated2026-11-06T15:18:50+09:00. Exact Root head,
doc IDs/versions/hashes, KST, owner/reviewer/base/task/scope, canonical first reads
and skills agent-delivery1.1.0/core-reliability1.0.0 are in `input-receipts.json`.
Only this unique History and unique Evidence directory were added. Shared boards,
registry, ADRs, source originals, Card150 and workflows remain unchanged; no
Obsidian apply/adopt/resolve or canonical state write.

Evidence directory:
`docs/vault/30_Development/Evidence/fleet5-b-rev8-revoke-portcut-20261106-codex`.
All references below name files inside that directory unless explicitly marked
immutable Rev7. No old74MB aggregate or44MB ledger copy was made.

**Actual new B Go/crypto/PG/Engine/crash/concurrency/equipment evidence remains0;
A1-A16 PENDING; every real binding NULL/HOLD.** Existing48/VFCL and old active
PC2/PC4 identities remain unchanged; new all5 is uninitialized. Separate K2/K1/
Test/PG/Core work supplies no B authority. No helper, remote SSH, physical/private
configuration, key/passphrase/issuer/CA/leaf/enrollment/install, actual workload/
offer/policy, host Docker/WSL/UAC/trust/VM/clock/schedule/pin or protected pilot/
state/claims/lock/cleanup operation occurred.

# M1: per-kind continuation and original receipt boundary

| Kind | Allowed continuation | Still required | Refused / retained |
| --- | --- | --- | --- |
| TERMINAL_FRAME | Exact already claimed terminal; DRAIN allowed | Original owner/run/claim/command, live execution lease/deadline/workload and activation rights; current channel/epoch/generation | QUARANTINE/RETIRE, expired terminal rights, wrong parent; no new workload authority |
| CANCEL | Existing exact operation recovery, including contained/offline/stale/expired business lease or activation lease; may control UNCERTAIN EXECUTE | Exact durable original parent/run/claim/owner/permit/command SHA plus new request SHA; current authenticated tenant/Node/epoch/process generation/channel C/DER/key/cert/observe grant; fixed method scope | Revoked/disabled/expired auth, wrong identity/binding; own ACK never settles original UNKNOWN or releases a claim |
| RECEIPT_OBSERVE | Same current-auth recovery lane after business start authority lost | All CANCEL identity/binding conditions plus original parent PENDING and LIVE current-incarnation completion capability at registration, invoke and completion | SIDE_EFFECT because actual Go can Stop/Remove/Save. Unknown/dead parent requires protected reconciliation, never ordinary late confirmation |
| OBJECT_READ / BUILD_CLEANUP_READ | Original exact read/build authorization | Retained original owner/source/target/parent policy | No new host path, contribution writeback or arbitrary workload path access |

This follows actual `services/control-plane/src/inv/node_channels.py:124`:
`snapshot(observation_only=True)` skips execution containment and online/heartbeat
freshness, while `assert_channel` at:100 still requires enabled/current/unexpired
channel. Actual `services/control-plane/src/inv/dispatch.py:183` retains leases
until the authenticated physical receipt after start-authority loss. Expired
execution authorization does not mean expired authentication. Business RETIRE
alone may retain the exact recovery lane; RETIRE that revokes the required
channel/epoch/grant refuses ordinary network recovery. Neither case clears facts.

Catalog/schema/authority/model expose the same closed per-kind policy and internal
error classes. `parentCommandSHA` is a proposed CP record field binding the exact
original command; no accepted plain Node wire/profile/manifest changes. Unknown
properties, including caller `observation_only`, are rejected by the closed schema.
Method/rawPath/effect are fixed together. Receipt observation cannot be relabelled
READ_ONLY.

`services/control-plane/src/inv/node_execution.py:78` is the original
NodeReceiptStore.record boundary. Kernel receipt input must satisfy exact Node/
tenant/epoch/current-channel scope, original command/claim/run/project/plan,
immutable receipt content, unique exact unreleased allocation set, resource Node/
kind/amount/fence and same transaction record/release conditions. The symbolic
receipt fixture makes those independent verification conditions explicit; its
role-labelled digest is not a real signature or physical proof. A fully validated
original terminal receipt can release only its matched claim, including via the
exact CANCEL path. It leaves the parent EXECUTE UNCERTAIN/dead capability and
other claims/facts/obligations unchanged. A cancel ACK, CP outbox state, replay or
generic receipt label releases nothing. Actual original-command NodeStopReceipt
and exact generation/channel are admissible INPUT to protected quiescence
reconciliation, not a generic clear-all proof or ordinary UNKNOWN settlement.

`regression_red_green.py` runs the identical four C1-C4 expectations against
immutable Rev7 and Rev8. Expected/actual exit is1 for Rev7 (all four denied),0 for
Rev8 (all four allowed). These are focused symbolic contract regressions, not
Node runtime tests. `proof_tests.py` has208 passing owner assertions for both
PLAIN/B: registration/invoke retain claims, wrong parent/command/owner/claim/run/
epoch/generation/C/DER/auth scope and expired cert/key/grant refuse, retirement
cases differ, ACK vs full original terminal receipt differs, original UNKNOWN and
other facts persist, and no dead completion capability is revived.

# L2: DB candidate hints

R01/R05 use a separate `candidate_hint` result, not boolean whole-Node eligibility.
The candidate ID selects the DB-discovered resource/claim footprint in the model;
a forged caller footprint is ignored. Known PENDING A removes overlapping A;
disjoint B remains HINT_AVAILABLE. Missing DB footprint returns explicit
MISSING_RESOURCE_SCOPE without business authority or security-version mutation.
SIDE_EFFECT UNKNOWN retains Node-wide HOLD; authentication and containment still
apply. Every actual selected admission rechecks the original hard guards. This is
an internal proposed state, not an accepted wire extension or admission grant.

# M2/L1: closed analysis pilot and bounded named contracts

Only `inv.node_channels.revoke_channel`, actual source:205-226, changes its local
sidecar analysis view. Its three old unresolved edges are two fetchone results of
already recorded resolved cursor.execute calls and DomainError construction.
`pilot-closure.json` binds exact full AST spans, producer record hashes, cursor
factory provenance, constructor/import/base/body proof and the existing single
`b_revoke_node_channel` procedure join; lockPorts remains empty. All four original
DB records and control flow remain. Status is
SOURCE_TO_PROPOSED_PROCEDURE_STATIC_CLOSED_RUNTIME_PENDING, explicitly
notGrantable. Actual operator-role/PG/crypto/lock/crash proof is NOT RUN.

A1 accepts only a recorded execute result with proven DB cursor factory and no
cursor rebind; mystery().execute and foreign cursor remain BLOCK. A2 inspects
actual non-frozen DomainError and InvError dataclass Exception constructor
closure, including InvError post_init/category_of/ErrorCategory/_STATUS/_RETRYABLE/
Exception.__init__. Non-frozen alone is not authority. Constructor DB write or
post_init IO mutations BLOCK. There is no global Exception allowlist.

A6 adds typed Session.delete/merge instance tracking with DELETE/UPSERT and
per-occurrence UPDATE lock mode. Unknown Session/instance/model is DYNAMIC_BLOCK,
never a zero-mode silent success. The incremental census consumes immutable
recorded writers and every recorded direct Session delete/merge occurrence:
387 retained writer rows + actual deletes in
`src/saintvision/services/pools.py:168` (public.resource_pool_members) and
`src/saintvision/services/settings.py:310` (public.project_members) =389 recorded
DB writer rows. The distinct B-authority writer mapping remains34, unchanged.
W23/W23b loaded B-model delete/merge mutations produce writers that would fail the
unmapped authority census. This does not close the retained267 unknown SQL/writer
scope rows or claim every dynamic DB effect resolved. `analysis_tests.py`:21
passing selected source/mutation cases.

The immutable Rev7 ledger hashes preserve523 source files,47608 calls,29573 old
unproven denominator,107 old transaction denominator and3485 source plans.
No full assembler/reconcile/link-plans rerun occurred. All21 critical parent
entry rows remain byte-identical/referenced; only the one pilot has a separate
closed static view. `critical-edge-categories.json` covers all598 distinct unknown
references behind the757 critical missing-label occurrences, with exact source/
type/receiver/binding/proof/futureWork/blocksGrant. Labels are proof obligations,
not allowlists or757 new runtime ports. Only the three pilot edges close; other
entry statuses remain unchanged. Noncritical unknowns retain immutable fail-closed
source references, with no exemption or grant. Reviewer646/757 taxonomy remains
triage only.

A3/A4/A5/A7/A8 are explicit reusable pending rule contracts; they were not broadly
implemented or used to close another entry. They require module-proven ContextVar
phase/control flow; exact library/import/readonly package-literal resource/public
crypto summaries; proven builtin receivers with real clocks retained; exact
tools.lan_pilot runtime import/Database return across four sites; and all actual
production constructor propagation with subclass-override rejection and retained
harness provenance. Each includes required mutation negatives. NodeObservation.
mark_offline is a second T1 contract demonstrator only, with no support upgrade.

`pending-interface-contracts.json` names exact existing source wiring/auth/input/
output/error/owner/transaction/effect/verification dependencies:

| Contract | Bounded design; all real bindings NULL |
| --- | --- |
| T1 + P-DBROLE | ONE shared Database/BoundDatabase transaction owner: actual non-owner/non-superuser/no-RLS-bypass role check, READ COMMITTED, SET LOCAL tenant/timeouts, current control epoch SHARE, fixed tenant-controls SHARE/UPDATE. Observability callbacks require constructor-site proof and restricted effects; no unchecked callback trust or13 duplicate grants |
| T2 | NodeTLSClient request/connection/socket/timer implements the retained19 caller boundaries and exact kind/effect; no new network permission |
| T3 | Protected JSON/content reads bound to exact owned path/parent/owner/mode/descriptor and existing health/cleanup/object purpose. Current verify_content Path.open alone is not no-symlink proof; missing enforcement remains pending, no generic filesystem port |
| P-INJECT-BUILD | Clock/now, request-ID factory and runner/subprocess remain separate actual effects under production composition root. No random/signing/clock/buildctl pure-value exemption |
| P-DBFUNC | Actual apply_capability_offer is defined by0031_resource_offer_integrity, superseding0030 apply_resource_offer; business_admin_allowed comes from0027. Fixed SECURITY DEFINER/search_path/execute grants/current tenant-active principal/admin checks, named tables and offered writes remain explicit pending PG/effect/rank proof |
| P-API-DI | Actual bearer verifier Principal, tenant-scoped Session and current DB administrator checks, never a caller role string |
| P-GETATTR | Per-edge exact receiver/constructor/attribute proof; genuine dynamic dispatch stays DYNAMIC_BLOCK |
| P-LOCKRANK | Exactly11 existing unranked DML tables remain pending; no default rank or silent omission |
| P-SQLSCOPE | Actual bound_lock_wait validates an integer range before fixed SET LOCAL formatting in tenant transaction; original rollback/error mapping preserved |

Correct lock counts are39 source-lock plans,33 with procedureRefs and6 without;
they are not39 actual procedure joins. The11 unranked tables remain named in the
pending contract. No other plan was regenerated or registered.

# I1/I2 and retained compute/storage boundary

`transport-delta.json` binds all nine Go anchors to actual
`services/node-agent/transport/server.go:55` ServeHTTP range, exact path selector,
rawPath guard and matching branch range/hash. Branch substitution mutation
refuses. The19 parent caller boundaries and Go Stop/Remove/Save exception remain
immutable by hash. Optional literal getattr materialize_source_capsule at
`services/control-plane/src/inv/build_execution.py:885` has no product
implementation in72028, so it always refuses RES-0006. A future implementation
requires a NEW catalog IO kind and review; it cannot inherit permission by name.

Default `deploy/lan/worker_workspace.py:76` storage guard remains unchanged.
Prepared folders are not accepted active storage. Four plain independent workers
omit contributed-storage acceptance; dedicating one to storage leaves only three
independent workspace workers. ADR100 still requires four independent Linux
workers plus the separate-kernel CP-colocated managed Linux VM excluded from
independent S05/S07. The existing46 helper/wrapper surfaces and combined-role
rollout/rollback contracts remain the immutable Rev7 carry-forward. No generic
mount copying, arbitrary/RW mount, socket relocation, permissive flag parsing,
stale/tampered/channel-mismatch policy, workload host-path access or storage
writeback is authorized. Proposed resource/headroom policies are not hard quotas.

Future approved combined-role rollout must bind the generated profile/manifest,
state volume owner and exact readonly/nonrecursive/rprivate contribution plus
existing default daemon socket. Identity/cert/channel/epoch remain the same for
that migration; later leaf/channel renewal must update and verify storage and
execution bindings together. Policy bytes and held root identity must survive;
unknown mount/policy/preflight/failed/rollback states preserve the current
container and journal. Signed storage samples remain bound to actual current
channel/leaf/root/policy and typed CP observation; folder preparation or a symbolic
sample is not active storage acceptance. Linux Docker mount/readonly enforcement,
host-path boundary, crash/rollback and true concurrency tests remain required in
future authorized CI, and were NOT RUN here.

# Verification, publication and next owner

Exact commands, KST, expected/actual exits, stdout hashes, elapsed time and measured
child peaks are in `proof-checks.json` and `publication-gates.json`. The existing
main .venv Python3.14.7 was used with -B; no package install. Fourteen serial proof
commands passed their expected exits, including Rev7 C1-C4 regression1 and R4
`--require-coexistence`1 as expected nonzero gap proofs. R4 baseline exits0; Rev8
regression0;208 new symbolic/21 selected analysis/335 retained symbolic/8 prior
closed probes pass. These OWNER reruns are not independent Claude review.

Bounded analysis reads4 files/54091 bytes; selected analysis probes5 files;
pending interface anchoring12 files/178519 bytes. All subsets stay below12 files/
2MiB and run serially. Source analysis measured peak36990976 bytes, selected
analysis26431488 bytes; symbolic/schema consumers reach about62MB. These are
actual process observations, not OS-enforced memory quotas. Full523-file assembler,
74MB aggregate load and3485-plan rebuild are NOT RUN. One development mutation
construction error and its corrected branch-swap test are preserved in
`development-failures.json`; no production fix was made.

Publication runs docs, ontology, canonical sync CHECK only with exact Root state
path and before/after hash, contract bindings, frontend integrity, duplicate
ratchet, freshness report and citation ratchet against33f7. The command receipt
records actual outcomes; docs success is not product build or equipment evidence.
No own final SHA or CI is predicted in this report: after commit/push, the exact
remote SHA/ref/Docs workflow_dispatch/correlation/attempt/job/steps are delivered
to Root in the structured question.

Next owner Root: obtain ONE actual independent Claude whole Rev8 delta verdict,
then choose the next concrete bounded contract/implementation cut. Proposed next
analysis cut is T1+A7/A8 constructor/import provenance and narrow mark_offline
demonstrator with mutation negatives, before any broader source upgrade. A3-A8,
T1-T3 and P-* labels are not grants. B remains pending; no worker_done for the
whole assigned B deliverable, no self-acceptance, registration or partial freeze.
