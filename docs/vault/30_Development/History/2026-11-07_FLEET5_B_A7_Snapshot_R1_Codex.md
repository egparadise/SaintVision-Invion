---
doc_id: "HIST-FLEET5-B-A7-SNAPSHOT-R1-001"
title: "FLEET5 A7 snapshot source body and unresolved caller ownership"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Independent A7 static review through Root pending after D04 reviewer exit/release"
updated: "2026-11-07T06:12:28+09:00"
source_of_truth: "Git"
---

# Scope and actual predecessor acceptance

FLEET5-B-A7-SNAPSHOT-R1-20261107 is owned by Codex, Orca task_a8fd2969f0b3 /
ctx_6f0f8253b8a7, under Root msg_35937c8787d1. Work started at
2026-11-07T05:51:30.578744+09:00. Branch
agent/codex/fleet5-b-a7-snapshot-r1-20261107 starts from exact
0e66b5ab2b5fbc131dd6e98f5d5e8930ac045148. Product source stays
72028cbac903c4415d9979f980a6e0f9948e914f. Only this new History and
Evidence/fleet5-b-a7-snapshot-r1-20261107-codex are added; no product, workflow,
shared board, registry, ADR or original source is changed.

Root accepted Rev9g from actual independent Claude review
90cccfb34718a8bb375bd7c1b7e06beb49670823, branch
agent/claude/fleet5-b-rev9g-0e66-review-20261107, direct parent0e66.
B9f-L1/L2 are CLOSED, no MEDIUM/LOW; the local-shadow binder imprecision is
pre-existing INFO and relevant full provenance refuses it. Its34 full probes,
11 binder cases,10 units and21 guard/followup overlays are historical review,
not newly executed A7 cases. Seven main expectation mismatches are qualified:
one invalid six-root input, five older full-use-site refusals, one binder INFO.
Its Docs42290423828/job128142107526/manual docs.yml/attempt1/title
claude-b-rev9g-0e66-review-90cccfb3-ctx_b48554022c90 has19 successful steps.
All19 actual review Git blobs were read and preserved with original object IDs,
byte hashes and paths in input-receipts.json; raw copies are not new coverage.

The read-only Root vault was at b112b32450a378cd12bddbc711a98cb8cb8816dd:
INDEX-PROGRESS-001 v1.0.481 and WORKBOARD-CODEX-001 v1.0.442.
Canonical first reads and exact hashes are recorded in input-receipts.json:
INDEX-VIRTUAL-COMPUTER-001/ROADMAP-VIRTUAL-COMPUTER-001 v1.0.0,
GOV-CONTINUOUS-001 v1.1.0, GUIDE-001 v1.1.0, ADR-INDEX-001 v1.37.0,
GOV-AGENT-001 v1.1.3, GOV-GIT-001 v1.1.4, GOV-CONTINUITY-001 v1.0.0,
AGENTS and task registry. Agent-delivery1.1.0, core-reliability1.0.0 and
version-matched Orca orchestration instructions apply. No helper was dispatched.

# Source contract and bounded proof

Frozen services/control-plane/src/inv/node_channels.py:124-153 defines
NodeChannels.snapshot. The finite semantic AST grammar requires the original
signature/default, self.db.transaction(node.tenant_id), node SELECT FOR SHARE
with DB clock, node recovery epoch, and channel recovery epoch in both modes.
NORMAL alone requires the local relative containment.require_execution(conn)
call and online/heartbeat age in[0,15]. Observation mode skips exactly those
two checks. It still constructs ChannelProof and calls assert_channel on the
same connection: channel FOR SHARE, enabled, unexpired certificate using the
DB clock, and equality with the current proof are required in both modes.
Original Python truthiness is retained; no runtime exact-bool check is invented.

The sidecar attests the selected require_execution body and execute result,
proof field order/types, frozen dataclass declaration, assert_channel body,
DomainError route, NodeChannels database field store and class construction.
Necessary lexical loads retain the actual frozen binding scope/event multiset,
including str for epoch/proof conversion. Necessary Database constructor,
transaction and observed-connection method AST bodies/signatures/imports are
locked to the original; observed execute returns its original result and the
transaction yields the original observed/plain connection union. Digests bind
evidence, not authority. This dependency/body attestation remains conditional
on actual receiver/database/caller ownership; no live DB effects are proven.

The serial source census derives30 lexical candidates,10 NodeChannels
constructors and10 linked snapshot calls, including inline and single-init-store
self.channels receivers. It records aliases, paths/spans/file/expression hashes,
caller import event multisets, reflection and no-new-use guards. Reverse
argument/signature forwarding derives seven source states and12 call events,
including ObservationWorker/configured_workspace/TerminalService paths. The
starting list of ten sites is not declared a complete dynamic closure. Two
other snapshot receivers remain unadmitted/unknown, never arbitrary NONAUTHORITY.

The overall status is SOURCE_STATIC_UNRESOLVED_RUNTIME_PENDING. Nineteen
explicit obligations block grant: NodeDelivery's observation_only or cancel_only
has unresolved value/truthiness provenance, database roots/formals/local values,
self.db, runtime(state) and a.e.db are not all authenticated genuine Database
owners, and reverse forwarding reaches unclosed source roots. A MAY-owner name
or argument mapping cannot discharge those obligations. No broad heap, alias
or Python resolver is added. NodeDelivery constructor/call text is inventoried;
deliver/network/crypto behavior is not admitted. The body proof is conditional,
not a closed A7 caller/runtime certificate.

# Validation and publication evidence

The final serial proof runs a7_tests.py, a7_build.py and a7_verify.py through
measured_run.py, with argv/cwd/Python3.14.7/KST/exits/raw logs and full per-file
before/after hashes in proof-final02.json. The fresh deterministic rebuild
checks original review blobs/object IDs, frozen accounting, original source
candidates and compiled-only overlay inputs. Each hash bracket also covers the
inherited Rev8 body predicate and Rev7 source manifest loaded by the accepted
helpers; giant ledgers and the full assembler are not replayed.

The33 source-layer cases and seven literal-truthiness units cover normal and
observation source controls, wrong imports/name/alias/rebinding/conditional
shadow, constructor DB field, receiver and connection forwarding escape,
removed containment/online/heartbeat/epoch/locks, missing enabled/expiry/current
proof checks in both modes, changed DB yield/result/body, builtin epoch binding,
and class monkeypatch. All mutated product text is only parsed/compiled.
Body gate/control-flow/ownership/import refusals are distinguished from stale
digest/parser preconditions. Caller-census counterexamples also retain the
pre-existing dynamic-mode blocker; these are not new full-provenance causal
red/green results. The monkeypatch refusal is the older full-use-site WRITE_USE
guard, not a new binder discovery. No DB runtime outcome is claimed.

Development failures are preserved: dev02-tests exit1 was a multiline fixture
literal mismatch before that case ran; dev03-tests exit1 expected CALLEE_REBOUND
for monkeypatch but actually obtained the correct older WRITE_USE refusal.
Raw logs, hashes and partial case/input results remain. Final01 passed before
the added lexical-load binding and external-dependency brackets; final02 is
the fresh execution at the final producer bytes. No old70/19/31/83/29, model,
recovery, full Core,523 assembler or3485-plan suites were rerun.

Local documentation gates and canonical CHECK are separate receipts in
docs-final02.json. CHECK uses only the existing canonical state, full immediate
state hash before/after and an own conflicts output; concurrent Root conflicts
are preserved. No apply/adopt/resolve/export/state write occurs. Per-process
peaks are observations, never aggregate limits or OS-enforced/hard quotas.
The source manifest proof-producer-hashes.json seals the final receipts and
this History. One docs-only commit/push and one exact own manual Docs run follow;
the actual immutable SHA/run/head/ref/path/title/attempt/job/19-step metadata
are returned to Root, not predicted here or represented as product CI.

# Preserved global contract and next owner

All six accounting artifacts, model/lifecycle and stage1/final contract bytes
are retained unchanged. The original pending_contracts then edge_categories
order is preserved as history; neither generator is invoked for this sidecar.
A7 is a helper sidecar, not a thirteenth grantable entry. Shared12 entries,
19 edges(16 analysis/3 runtime),598/757/1071/21,573 outside and218 backlog stay
unchanged. Observer-lock remains pending outside19. Actual runtimeB=0, real
bindings=NULL/HOLD, A1-A16=PENDING,48/VFCL and physical-PC acceptance unchanged.
No production B code/port/API/schema/role install or existing Node identity is
changed; this package does not claim same-Node storage/execution acceptance.

After publication, Root receives the pinned partial static proof and the19
explicit blockers, then queues ONE actual independent A7 static review after
D04 CODE reviewer task_6d952cac2c9f/ctx_1ddcf22e6a4c exits/releases. Author
selfacceptance, whole-B worker_done, runtime grant and follow-on scope remain
absent. Root's first next action is independent review and a concrete bounded
decision on the unresolved database-owner and dynamic-mode closure.
