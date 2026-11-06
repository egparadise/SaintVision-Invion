---
doc_id: "HIST-FLEET5-B-REV9C-FIXONLY-001"
title: "FLEET5 Rev9c bounded root, forwarding and owner discovery fixes"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Actual independent Claude narrow delta through Root pending"
updated: "2026-11-06T23:21:00+09:00"
source_of_truth: "Git"
---

# Authority and immutable inputs

FLEET5-B-REV9C-FIX-ONLY-20261106, owner Codex,
`task_a8fd2969f0b3 / ctx_6f0f8253b8a7`. Root's concrete answer
`msg_8f20f55b48dc` authorizes this continuation without another routine approval.
Branch `agent/codex/fleet5-b-rev9c-20261106` starts at exact Rev9b
`870486f98ba8fdc6d82f24c2610352a426f23a16`; product source is fixed at
`72028cbac903c4415d9979f980a6e0f9948e914f`.

Actual independent Claude review
`aa3387b80765e9a4b3cb06c71b86086b490c495b`, Root-verified Docs42224817650
with exact head/ref/manual docs.yml/attempt1/all19 steps successful, found only
B9b-L1/L2/L3 LOW. B9-M1 is CLOSED, and actual-source T1/A8 closure at72028
stands. This document describes the bounded proof reuse fixes; no product,
port, DB, effects or runtime authority is added. The next NodeChannels.snapshot
A7 cut is still deferred until actual Rev9c acceptance and a new Root decision.

Evidence is under
`docs/vault/30_Development/Evidence/fleet5-b-rev9c-20261106-codex`.
`input-receipts.json` records first-read Root head, KST, canonical document
IDs/versions/hashes, AGENTS, task registry and skills. Root boards were
Index1.0.458/Codex1.0.419, updated2026-11-06T22:08:52+09:00. The
agent-delivery1.1.0/core-reliability1.0.0 and Orca orchestration/CLI procedures
continue to apply. Root vault and prior owner/reviewer documents are read only.
Seventeen actual Rev9b review inputs and fifteen earlier review copies are
byte-preserved, with provenance distinct from OWNER fixture execution.

Only this new History and uniquely named Evidence are added. Shared boards,
registry, ADRs, original sources, prior branches, protected pilot/state and
Card150 are untouched. Product diff must be zero. Model and lifecycle bytes
remain exact Rev9b:

| File | SHA256 |
| --- | --- |
| model.py | f7384016f72b5f6b9d369925a3a6d864012f286351db38d97993a5f95be78acf |
| lifecycle.py | 710c6aafa1829d9aecc25b8e591c4f2a8ec01b0927a45cf6e7ba7b13b75977b0 |

The accepted model182/terminal47, recovery79+8 and old/new terminal exits1/1/0
are retained by reference to870486, without rerunning unchanged model logic
for these static-only fixes. Schema/authority/IO semantics are reused.

# B9b-L1: root preservation and enumerated reflection

`constructor_graph.py` compares the current production root multiset against
the frozen constructor roots by path, enclosing function, resolved constructor
and normalized call AST. Line shifts and equivalent import/module aliases
cannot substitute for a missing root. Changed or removed roots refuse
UNRESOLVED:CONSTRUCTOR_ROOT_REMOVED_OR_HIDDEN. Extra roots still undergo
ordinary input-union and complete provenance checks.

`use_sites.py` audits the enumerated sys.modules, importlib, operator
attrgetter/methodcaller and inspect getattr_static/getmembers surfaces, their
module aliases and relevant protected-name strings in reflection contexts.
New unknown reflection uses refuse; unused imports and non-reflective strings
remain benign. This is not a claim of arbitrary Python reflection completeness.

Fixtures retain all six genuine roots and add an extra hidden reflective root,
which the reflection audit refuses even though the visible root count remains
six. Separate state/runtime(state) substitutions remove a genuine root and
trigger the root-preservation error. This distinguishes the fix from a count
check. Witness spans/hashes are checked before verdicts; a deliberately changed
root span is explicitly identified. Bound names avoid NameError-only examples.

# B9b-L2: forwarding caller source view

`forwarding_discovery.py` starts from actual constructor arguments forwarded
from function parameters. For current T1, the derived seed is
inv.workspace_config.configured_workspace. Symbol-driven grep and serial AST
resolution find caller files and aliases, direct function/module re-exports
and parameter-forwarding functions to a fixed point. The actual production
caller files are workspace_config.py:87 and app.py:1323. Harness callers are
catalogued separately and cannot contaminate production unions.

The CORE list selects proof bodies; it is no longer the coverage authority.
Every relevant discovered production source must be present in the supplied
proof inputs, otherwise UNCATALOGUED_PRODUCTION_SOURCE refuses. Re-export
bindings and unknown relevant star imports are retained or refused. The
artifact combines constructor and relevant forwarding source surfaces; any
derived inventory delta is explicit, with no parent/category status upgrades.

Tests model the reviewer's additional business_handoff.py alias caller with an
explicit in-memory source universe: frozen git72028 plus bounded source
overlays. Nothing is written to production files. A missing relevant file,
function re-export, module re-export and a second forwarding caller are each
discovered and refused. Current import/module alias controls pass. A harness
caller with an object argument remains HARNESS_ONLY_PROVENANCE.

The old API had no complete source-view discovery input; its omitted-file
contrast therefore observes the old manually selected inputs. New fixtures
feed the complete source view explicitly. No claim is made that a producer
can detect a mutation that was neither in its frozen commit nor in its input
source view. Global import callers of lan_pilot.runtime remain future A7;
the accepted local single-Database-return helper proof is unchanged.

# B9b-L3: bounded owner/container relevance

`owner_transfer.py` propagates conservative ownership relevance through
assignments, tuples, attributes/subscripts, containers, For/With targets,
comprehensions and tracked forwarding-factory results. Pool values retain the
RestrictedWorkspaceRuntime owner; configured_workspace results retain the
workspace owner. Current and frozen relevant names are both audited, so a
changed binding cannot silently remove a previously relevant receiver. The
forwarding callable bindings themselves also have individual use-site checks.

The five reported foreign-call escapes now refuse: runtime, runtime.db,
runtime.db.transaction, workspace and workspace.runtime.db. Additional held
context, comprehension and attribute/subscript aliases are checked, while
unrelated container controls pass. This is bounded relevance propagation,
not a whole-program heap, alias or flow-sensitive Python proof. Existing
individual receiver checks and full provenance remain required.

I1 sorting is applied to set-derived output keys and checked with distinct
PYTHONHASHSEED values. I2 explicitly retains the graph/use-site dependency;
graph output alone is not a provenance certificate. I3 the future tenant-epoch
obligation is recorded without changing model bytes or introducing an epoch
writer. I4 namespace allowlists establish no-new-protected-use relative to
72028; they do not prove every existing use benign.

# Validation, limits and handoff

`proof-checks.json` records16 serial targeted commands and expected exits;
`publication-gates.json` records eight publication checks. The affected rule,
factory/header, original70+19 analysis, T1 and Rev9c old/new regressions are
checked without executing effectful mutants. The final29 new cases show20 old
acceptances now refused and9 controls; all16 commands match their expected exits. `rev9c-regression-results.json`
records exact old/new commands, bound source hashes, genuine-root witness
sanity, discovered files, owner targets and semantic refusal reasons. Original
review scripts are preserved; OWNER reproduction is not independent review.

`deterministic-generation-results.json` binds two serial closure generations
to different hash seeds and equal output bytes. The ordered final contract
proof is produced afterward by pending_contracts.py then edge_categories.py;
stage1 alone remains unaccepted. Producer hashes and final command receipts
are bound by `proof-producer-hashes.json`.

The original R4 fixture still returns baseline0/require-coexistence1 on the
unchanged guarded source. The expected nonzero is recorded as gap evidence;
folder preparation still cannot prove active contributed storage. No Linux
Docker mount enforcement, crash/rollback, crypto, PG, Engine, concurrency,
clock, role, equipment or fleet acceptance is claimed here.

Counts remain19 T1 edges (16 analysis/3 runtime),12 shared entries,598 unique
unknown refs,757 labels,1071 occurrences and21 parents;573 outside rows and218
fallback backlog remain unchanged. Observer lock-safety stays named runtime
pending outside the19 edges. All actual bindings are NULL/HOLD, runtimeB0 and
A1-A16 PENDING. Existing48/VFCL statuses are unchanged.

Python3.14.7 from the main repository environment runs with -B; no installation
or oldpilot interpreter is used. Actual process peaks and elapsed times are
observations, not hard quotas or aggregate limits. Nested regression/build
peaks are recorded; legacy70 inner-process peak is unmeasured. Selected actual
proof body batches retain the10-file/2MiB bound, with the separate two-file
constructor remainder and serial source discovery. Fixture overlays add only
bounded candidate source inputs. No full523-file assembler,3485-plan rebuild,
giant ledger copy or whole Core retry is run.

`local-gate-audit.json` records argv-only local checks and no unsafe protected
path removal encountered/attempted. `development-failures.json` preserves the
UTF-8 preparation decode failure and the initial extra-witness fixture failure.
A later newline-inspection guard failure made no write; AST verification
confirmed the original newline was already correct. Any later failure remains explicit. The official Obsidian sync command is
CHECK only with the canonical state path and own conflict output; state SHA
before/after must match. No apply/adopt/resolve or shared state write occurs.

Normal own-branch commit/push and ONE exact-SHA Docs CI precede the Root ask,
which supplies final/base/ref/files, hashes, expected exits and exact run/job/
head/event/path/attempt/correlation/step proof. This docs-only derivative is not
integrated. No helper worker, private configuration/key/issuer/leaf operation,
remote SSH, physical PC, live workload/service, DB/Engine, host Docker/WSL/UAC/
trust/clock/schedule or protected pilot action occurs.

Next owner Root arranges ONE actual narrow independent Claude delta review
after the current UI reviewer exits/releases, then returns the concrete
acceptance or revision decision. Rev9c review and operational acceptance remain
PENDING. No self-review, worker_done, partial freeze or future snapshot/A7 work
is claimed while that decision is pending.
