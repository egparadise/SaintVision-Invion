---
doc_id: "HISTORY-FLEET5-20261106-K1-TEMPORAL-CODEX"
title: "FLEET5 K1 durable history and current projection corrections"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude via Root pending corrected-source delta review"
updated: "2026-11-06T08:00:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "c6f0d95ecbcd79fac96673c194e2368b510ad827"
task_ids: ["FLEET5-BOOTSTRAP-V5-K1-OFFLINE-VERIFIER-20261106"]
tags: ["fleet5", "codex", "offline-verifier", "temporal"]
---

# Scope and actual review

Owner Codex; independent reviewer Claude through Root. This continues Orca task
`task_38393b5d1865` / dispatch `ctx_ceecb3824e33`. Root messages
`msg_87002d358dbb` and `msg_2a098fb1f4d3` select durable multi-time history and
require M1/M2 plus L1–L5 corrections. Actual first code review is
`c2b15b707d94bca001d0d63c6486cfe9fd5cbcae`, **REVISION REQUIRED**; its exact
Docs run 42119997927 is Root-confirmed SUCCESS, not product acceptance.

Started 2026-11-06T07:36:35+09:00 on Orca-created worktree
`fleet5-bootstrap-v5-k1-temporal-fixes-20261106`, branch
`agent/codex/fleet5-bootstrap-v5-k1-temporal-fixes-20261106`, exact base above.
Root Index 1.0.426 / Codex 1.0.387 were read; AGENTS, required governance,
agent-delivery 1.1.0 and core-reliability 1.0.0 apply. Original source c6f and
qualified report `37fe879ff37f4e673f059cc8e41f1c7c787f45dc` stay frozen.
This branch changes only migrationverify and owner History/Evidence. No runtime,
transport, DB, workflow, shared board, registry, source originals, private files,
schedule, physical clock or operational authority is changed. No helper agent.

The c6f Core 42113810160, source Docs 42113815556 and report Docs 42121661622
succeeded for that rejected source only. They are not validation of this change.
New exact-source Core/Docs and an actual delta review remain required.

# Design and boundary

`Verify` authenticates offline history at the actual signed containing record's
time. API requests use their first exact signed request event; projections use
their exact latest signed event; RELEASED leases use the signed release outcome.
The complete signatures and graph authenticate these causal joins. Historical
HELD lease hashes/windows and original challenges are independently pinned in
`History`, separate from live `Operations` and `Challenges`. No caller time field,
backdated Now, extended 120-second cap or new wire freshness mode is introduced.
Historical key grants must cover both proof and consuming time. Current external
publication/nonrevocation checks still use trusted Now. The output remains data,
never admission or transferable current permission.

Current derivation first authenticates history, then requires the exact trusted
HELD lease, no same-operation RELEASED lease or higher scoped fence epoch, and
the maximal authenticated operation sequence. It matches the complete independent
current head and both original member projections. The head readback is separately
reverified at Now. Both ordered current native witnesses are original producer
wire authenticated against current member/operation/epoch/nonce and expected
state. Retained native receipts cannot satisfy these new current checks.

L1 uses checked time/type access and constructor validation of required semantic
roots/plan expiry/evidence age. L2 requires explicit ServerAuth EKU and
DigitalSignature usage. L3 requires IssuedAt−30s ≤ signed observation < ExpiresAt;
five seconds before issue remains allowed. L4 takes one bounded defensive packet
map/byte snapshot at verification entry. Callers must not mutate input concurrently
during the call; the copy provides isolation, not synchronization. L5 preserves
earlier dated attempts and labels their counts as historical observations.

# Reproduction and fixture evidence

Evidence root: `Evidence/fleet5-bootstrap-v5-k1-temporal-20261106-codex`.
The initial M1 regression at 07:36:53 KST exits 1: consistent views33/35 are
accepted by c6f, while34 fails only on incidental Node binding. Log and command
are `m1-before-change.log/json`.

`reproduce_baseline.py.txt` copies public c6f Git blobs into a new ignored scratch
module and applies only test fixture API adaptations. Production source remains
byte-exact. `m2-before-change.log/json` records exit1 at both intended old gates:
expired current-time freshness with retained epoch1 current bindings, and missing
current operation when epoch1 is correctly removed. This replay uses real in-memory
crypto with separately retimed TEST records; no original dummy or private key is
accepted, reset, exported or installed.

The new durable fixture has epoch1 HELD0..300, release68, epoch2 HELD600..1200,
events610/620 and trusted Now630. Original Node proofs32/52 are older than120s
and epoch1 is absent from current Operations. Historical authentication and latest
epoch2 current derivation pass using separately signed current proofs630. The
original pinned source graph/fixtures remain byte-exact; only this ephemeral TEST
graph has new time expressions.

# Validation state and retained failures

Environment: Windows amd64 Go1.27.0, CGO_ENABLED0; main Python3.14.7 `-I -B`.
No pip, protected interpreter, Docker or remote action. Local race is NOT RUN;
hosted exact-source Core race result is required separately.

Initial isolated edit used an incorrect relative path and failed before any
fixture modification; the corrected path was then used. An initial causal-time
check incorrectly compared a per-Node phase to the aggregate event phase; focused
tests caught it and the join now uses exact event hash/sequence plus the complete
existing graph's per-member phase binding. Focused attempt1 failed six old tests
because their mutations still targeted current maps; their historical contexts
were explicitly updated without weakening required proof checks.

Focused attempt2's actual Go returncode is0, preserved in JSON. Its Python display
wrapper subsequently failed printing a Unicode parser test name to cp949; this is
not a Go test failure or successful wrapper claim. Later result summaries use
ASCII counts and preserve the complete UTF8 Go JSON log. Source SHA, CI and actual
corrected review are tracked separately.

Focused attempt3 exited1 because the signed-time negative reached the earlier
inventory head-readback freshness gate, while its assertion demanded the later
member-native path. The assertion now requires the actual inventory consuming
record and stale-proof gate; it does not bypass that earlier rejection.
Attempt4 full Node/build/vet all exited0 (71 top-level/271 PASS events;
K1 40/157). Two additional exact current-binding and scoped epoch-selector tests
justify attempt5: 07:55:35–07:56:18 KST, full Node/build/vet all exit0,
73 top-level/279 PASS events, K1 42/165, zero local skips. Attempt5's final
historical-native test was then updated to assert the new intended semantics:
after13h and leaf expiry, refreshed current publication/nonrevocation plus original
historical context authenticate history without current Operations; current
derivation rejects it. This targeted check also exits0, recorded in
`historical-13h-final.json/jsonl`. It is a test/comment change after the full suite;
the exact-source hosted run must include that final assertion.

Native Current witnesses currently require a PRESENT authenticated inventory head
whose member declarations supply expected state. An ABSENT head fails closed;
history authentication still supports earlier phases. This typed application API
addition and its K2 producer obligations require the actual delta review; it is
not a new native producer wire or deployed observer capability.

The10 required local source/document gates each exited0 between07:57:29 and
07:58:34 KST: docs, ontology generation/validation, contract bindings, frontend
integrity, path citation ratchet against c6f, single-source ratchet, sync test,
docs build and Obsidian check-only. Logs and exact argv/exits are
`local-source-gates.json` and `gate-*.log`; no apply was run. These gates do not
represent product CI or physical acceptance. Prompt authority is the Root message
pair above; context versions are recorded at start, harness is Orca1.4.248, and
the agent is Codex. Graph and all28 accepted source pins remain exact; only
ephemeral test graph times differ.

Next: Codex completes focused/full Node and required source gates, publishes one
immutable corrected source with its own Core/Docs; Root sequences one actual
Claude delta review after B. K2 and all40 future runtime cases remain NOT RUN;
whole five-PC operational acceptance remains incomplete.
