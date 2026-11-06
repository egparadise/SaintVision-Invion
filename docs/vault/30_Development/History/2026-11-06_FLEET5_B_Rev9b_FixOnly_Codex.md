---
doc_id: "HIST-FLEET5-B-REV9B-FIXONLY-001"
title: "FLEET5 Rev9b terminal parity and complete constructor use-site proof"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Actual independent Claude Rev9b delta through Root pending"
updated: "2026-11-06T20:17:00+09:00"
source_of_truth: "Git"
---

# Scope and immutable inputs

Owner Codex; FLEET5-B-REV9B-FIX-ONLY-20261106;
`task_a8fd2969f0b3 / ctx_6f0f8253b8a7`. Branch
`agent/codex/fleet5-b-rev9b-20261106` starts at immutable Rev9
`3daf1a0d24c220586474a4b376609e62960b8ca6`. Product source stays
`72028cbac903c4415d9979f980a6e0f9948e914f`. This derivative is not integrated.

Root decision `msg_b6b4813cb5c2` authorizes only the Rev9b fixes to M1/M2/L1
and tracked information below, followed by ONE actual independent Claude delta
review through Root. Cross-module A7, NodeChannels.snapshot implementation,
NodeDelivery and full A8 remain outside this cut. Root's proposed subsequent
snapshot-only decision is not a present grant. No dependent A7 work was begun.

The Evidence directory is
`docs/vault/30_Development/Evidence/fleet5-b-rev9b-20261106-codex`.
Its `input-receipts.json` records the exact first-read canonical Root documents,
IDs, versions, hashes, KST, branch base, owner/reviewer and scope: Index1.0.453
and Codex1.0.414, updated2026-11-06T19:17:15+09:00; AGENTS;
agent-delivery1.1.0 and core-reliability1.0.0; canonical first-read design,
roadmap, continuity, ADR, handoff and operating documents; task registry hash.
The Root vault was read only. Shared boards, registry, ADRs, Card150, workflows
and source originals were not edited. Only unique own History/Evidence is added.

Actual independent Claude review
`a7e9f9d7ca7803533bccf84f443591cbcd2bd5dc` of Rev9 says
REVISION_REQUIRED: B9-M1 and B9-M2 MEDIUM, L1 LOW. Root verified17 unique
documents and exact Docs42196493024/job127820921026, workflow_dispatch,
docs.yml, attempt1, correlation
`claude-b-rev9-3daf-review-a7e9f9d7-ctx_de2750e94f9d`, all19 steps successful.
Full verdict, original scripts and results are retained byte-exact. OWNER
reproductions are explicitly labeled and are not independent review. Closed
matched-claim/tombstone, cleanup-read separation, hint authorization, recovery
and bounded categorization findings remain closed within their accepted scope.

**Actual B Go/crypto/PG/Engine/crash/concurrency/equipment evidence remains0;
A1-A16 PENDING; all real bindings NULL/HOLD.** No code, DB, credential, port,
registration, runtime, partial freeze or five-PC acceptance is granted. The
original R4 coexistence gap still returns expected exit1 on unmodified source;
folder preparation is not active contributed storage. Root admin-login,
K2/Core and combined baseline work supply no B authority or evidence here.

# M1: terminal projection and tenant execution containment

Product `services/control-plane/src/inv/terminal.py:66` calls
`require_execution`; `services/control-plane/src/inv/containment.py:15` through
:18 refuses missing tenant controls or an active kill switch. Terminal:78
through:85 requires Node status online/draining and current recovery epoch.
The existing matched run/attempt, deadline>now+5 and unreleased/unexpired lease
requirements at terminal:67 through:99 remain unchanged in the proposal.

Own `lifecycle.py` now requires current epoch, Node projection online/draining,
and a known tenant execution gate with kill switch false at TERMINAL_FRAME
registration, invocation and confirmation for both PLAIN and B. The symbolic
tenant gate is existing containment data, not a new writer, wire or port.
Current per-claim version, original EXECUTE parent PENDING/LIVE, attempt/run,
owner/project rights, complete leases and strictly bounded deadline stay
required. DRAIN is still the sole bounded business-fact exception. Ordinary
admission has the same tenant-stop gate; both independent Node frames refuse
after tenant stop. Node activity booleans cannot substitute for these rights.

Late offline/tenant-stopped frame confirmation leaves UNCERTAIN/POISONED and a
same-Node unresolved HOLD. Existing protected settlement with independently
proved outcome is required; generic ACK, receipt or row-state changes cannot
clear it. CANCEL, RECEIPT_OBSERVE and protected BUILD_CLEANUP_READ retain their
separate recovery/read purposes. No recovery lane acquires terminal rights.
Schema, authority and reader/IO policy artifacts carry the same proposed rules.

# M2 and L1: derived constructors and bounded use sites

`source_bindings.py` inventories candidate files by frozen-source grep and
parses20 source files serially, resolving imports, relative imports, class and
module aliases. `constructor_graph.py` derives six production calls and20
separately catalogued harness calls across ObservationWorker, NodeObservation
and RestrictedWorkspaceRuntime. Three hand-selected roots are no longer the
coverage proof. The graph derives all three class database-input unions as
exactly inv.db.Database, retaining unknown alternatives as failures.

The production source includes
`tools/lan_pilot.py:3945` ObservationWorker(runtime(state), ...).
`tools/lan_pilot.py:902` through:903 has a single local Database return, with
no helper alias/rebind/import shadow. The same local proof covers
`tools/remote_workspace_entry.py` database helper and its constructor chain.
Object/foreign returns, helper rebinding and unknown additional production
roots fail RECEIVER_UNION_UNPROVEN. Local helpers are not deferred cross-module
A7. All source spans, hashes, aliases, argument ASTs and derivations are in
`t1-mark-offline-closure.json`; harness evidence never upgrades production types.

`use_sites.py` replaces mutation denylists with bounded use-site allowlists.
Every proven receiver load must belong to an individually checked recorded DB
call, cursor/transaction, yield or validated forwarding context. Keyword,
container, star, lambda, dictionary, alias and callable-method escapes refuse.
Each use also binds to its enclosing function argument/decorator/annotation
headers, so an unchanged body cannot hide a new shadowing parameter or a
decorator replacing its callable. This checks headers without freezing bodies.
Protected class/module aliases, owner/root DB loads and all Attribute/Subscript
Store/Del contexts are checked; observer/sink post-construction writes and
setattr/__setattr__/vars/globals/__dict__/builtins/module-alias paths cannot
gain a generic exception. Current producer spans/hashes are checked before
receiver reasoning, so a stale record does not masquerade as a semantic refusal.

Legitimate observed forwarding, metric and ContextVar uses retain individual
checks. The narrow dataclass default_factory=dict exception additionally proves
the builtin factory is unshadowed; imported, assigned or class-rebound foreign
factories refuse. lan_pilot:4258 globals dispatch is allowed only for its exact existing
span/hash, frozen main AST and closed CLI command set, with no protected class
or receiver selection. This grants no general namespace or callable purity.
The local-list append exception identifies the equivalent node within the
current function AST; it does not compare identities from separately parsed ASTs.

Seven actual Database constructor defaults and BoundDatabase observer/sink
copying remain source proofs. P-T1-OBSERVER-LOCK-SAFETY is explicitly
NAMED_RUNTIME_PENDING outside the unchanged fixed19-edge census, anchored to
both callbacks. None defaults do not prove installed handler effects. Required
runtime behavior is in-process, nonblocking, exception-contained, without
network/subprocess or authority effects while locks are held. Real handler,
role, credential, PG and concurrency validation is NOT_RUN.

# Tracked information and retained accounting

I1 version/attempt tombstone CAS stays tracked INFO ONLY; no new receipt/wire
fields were introduced and normal newer-original admission remains guarded.
I2 unreachable nested terminal/cleanup predicate was removed only in the own
model. I3 late-frame HOLD needs protected settlement as above. I4 the observer
lock-safety row is outside the19-edge count. I5 the full harness census is
authoritative; old selected grep is labeled legacy. I6 only the new regression
wrapper requires an existing model directory and verifies imported model.__file__
is under that exact input. Original reviewer scripts remain byte-exact.

The historical reviewer bad relative-directory0/0/0 invocation is preserved in
`rev9-review-owner-reruns.tsv.txt`, separately from the corrected absolute
inputs and the new hardened wrapper's expected1/1/0 results. No bad-path result
is interpreted as a model pass. The old16-case mutation report's three meta/
control reports remain historically explained; they are not reopened findings.

Fixed accounting remains19 T1 edges,16 source-analysis closures,3 named runtime
pending edges,12 shared entries,598 distinct unknown refs,757 missing labels,
1071 occurrences and21 parents. The exact19+6 target refs yield25 unique refs
and33 category rows;573 outside rows and218 unreviewed fallback rows remain
unchanged. No parent status is upgraded. P-PUBLIC-SIGNATURE-VERIFY remains an
authority-bearing pending dependency, never crypto purity. Stage1 contracts
are intermediate; pending_contracts.py then edge_categories.py produces the
hashed final ordered artifact. All actual bindings remain NULL/not grantable.

# Owner verification and next handoff

Main repository Python3.14.7 was used with -B; no packages were installed.
`proof-checks.json` records20 serial exact commands, expected/actual exits,
KST, elapsed times, logs and measured process peaks. All20 match expectation:
182 retained model cases;47 new terminal/wrapper cases;79 recovery/hint and8
closed prior cases;31 analysis-rule cases;83 T1 cases; original70 fresh AST
mutations with zero gaps/positive failures plus19 additional census/use-site
checks,4 focused factory-binding controls and3 function-header controls. No
effectful mutant was imported or executed. Both expected old-model
terminal reds exit1, new model exit0; R4 baseline exit0/require-coexistence exit1.

Measured proof-process and publication-process peaks are recorded separately
in proof-checks.json and publication-gates.json. Resource receipts
are observations, not hard quotas or OS-enforced limits; subprocess peaks are
not added to the parent peak. Core selected source bodies stay at most10 files
and below2MiB, with a separate two-file remainder and serial constructor census.
The full523-file assembler,3485-plan recomputation and giant ledger copy were
NOT_RUN. `development-failures.json` retains the initially missed unbound class
write, invalid fixture ID, corrected cross-AST local-list check and UTF-16
development-log publication failure, with its preserved failed receipt. The
extra static factory-binding red records prior acceptance of a rebound factory;
four focused controls now preserve the safe positive and reject three substitutions.
The separate function-header red records prior acceptance of a shadowing
parameter and foreign decorator; both refuse with a semantic use-site reason,
while the unchanged positive passes.

`publication-gates.json` records the eight publication checks and their exact
exits; `canonical-sync-check-conflicts.json` is a fresh check using the official
sync-state path, with state SHA before/after unchanged. No apply/adopt/resolve
or state write occurs. `proof-producer-hashes.json` binds final producers,
original scripts, logs and command receipts. Git staging/check, own branch
push, exact same-SHA Docs CI and remote/tree verification are required before
Root handoff. The final Root ask supplies the concrete docs-only commit and
Docs run/job/head/ref/event/path/attempt/correlation/19-step proof; product
source stays the separate fixed SHA above.

No helper, remote SSH, physical/private config, key/passphrase/issuer/CA/leaf/
enrollment/install, workload/offer/policy, host Docker/WSL/UAC/trust/VM/clock/
schedule/pin, protected pilot/state/claim/lock/cleanup or Obsidian mutation was
performed. Old active PC2/PC4 identities remain separate; new all5 remains
uninitialized. Existing48/VFCL statuses are unchanged.

Next owner Root: obtain ONE actual independent Claude Rev9b delta review, then
return a concrete accepted/revision decision. Rev9b independent review and
operational acceptance are PENDING. No worker_done or whole-B completion is
claimed while this decision is pending; no future snapshot/A7 cut begins here.
