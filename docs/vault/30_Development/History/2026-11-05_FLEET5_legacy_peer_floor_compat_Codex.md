---
doc_id: "HISTORY-FLEET5-LEGACY-PEER-FLOOR-COMPAT-20261105-CODEX"
title: "FLEET5 legacy peer-floor source compatibility audit"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-11-05T20:52:00+09:00"
source_of_truth: "Git"
---

Task `FLEET5-LEGACY-PEER-FLOOR-COMPAT-20261105`, Orca task
`task_fb415493ffa5`, dispatch `ctx_373e829bc65e`; Codex owner, Claude reviewer
via root pending. Start base `9ec6d6bf4697745bfe41602bb720473b1ff9b22f`, branch
`agent/codex/fleet5-consecutive-leaf-rotation-20261105`. Accepted implementation
`2fb52bbe5e500354b323eb8e46d5aa5066690d2d` and its prior report remain frozen.

Read coordinator `INDEX-PROGRESS-001` 1.0.406 / `WORKBOARD-CODEX-001` 1.0.367,
AGENTS instructions, `agent-delivery` 1.1.0, `core-reliability` 1.0.0, and
the installed Orca orchestration/CLI guides. Required governance and plan reads
from the preceding source card are retained; this bounded follow-up overrides
board updates, product implementation, broad tests and Obsidian apply.

Scope is public Git objects at source03 / executorB5, the already published
native fe7/5023 proof, and the proposed M2 interface contract. No private
configuration, PKI, old guard parameter bodies, protected r5 working folders,
SSH, Docker/WSL/remote actions, process restarts, schedules, pins, claims or clocks
are accessed or changed. The root-supplied unsigned 20:34 KST observation is
attributed context only; this worker does not independently inspect runtime.

## Source verdict and its limits

**Public source03 and executorB5 inherit the confirmed normal-v1 peer phase
version collision.** If their unmodified normal producer/helper and Go Authority
run through overlap then final, the overlap floor has version `C+1` and its exact
raw hash; final has the **same version and different raw bytes**, so Go rejects
final with `NODE-0041: peer policy rollback rejected`. This is a policy version
collision, not a cryptographic SHA256 collision. It does not establish that an
actual private renewal plan has run, failed, or used this helper.

The proposed M2 `inv-node --observe-peer-policy-floor` capability is absent from
the public legacy main. A binary built unmodified from that main cannot supply
the new CLI mode. Actual running image bytes/build provenance were **not**
inspected here, so source identity is not a measurement of a deployed binary.
Root must treat legacy capability as unproven until exact executable provenance
and the reviewed capability protocol establish it. Accepted helper2fb remains
accepted within its original fixture/source scope, with this separate Go/P0
dependency explicit.

## Exact public sources and native proof

All reads use `git cat-file blob <SHA>:<allowlisted-path>` in this worktree;
`audit_public_sources.py` records raw Git-blob SHA, raw-byte SHA256, byte counts,
function slice hashes and line anchors in `public-source-index.json` under
`../Evidence/fleet5-legacy-peer-floor-compat-20261105/`. It runs no imported
product code, fixture PKI, Go executable or host/container/remote command.
Python function slices use `ast.get_source_segment`; Go slices start at the
named top-level function and end before the next function, with trailing
whitespace removed. Whole-file SHA256 is always the raw Git object bytes.

Compared commits:

| Label | Full SHA |
|---|---|
| source03 | `03e17c31cf535008d39534aaa80d3ae274bd75cc` |
| executorB5 | `b5b8ca68398517f6227a81caac02654a848c8b1d` |
| accepted2fb | `2fb52bbe5e500354b323eb8e46d5aa5066690d2d` |
| nativeFe7 proof code | `fe7ebeff1f695e0744a7f25eace52c7321dcc1d7` |
| Existing native proof/report | `5023ce7d72b7f13431cb6a7182e2677eb6926662` |

The following **whole files are byte-identical across all four code commits**:

| Path | SHA256 |
|---|---|
| `services/node-agent/runtime/journal.go` | `0bf50af78984eed047c1fdb2a10e230a8e7eb4669893539d54d05d454097f9b6` |
| `services/node-agent/transport/trust.go` | `3b5dd89f9d6bdeb777d81f822688ece6c04b549080f53e8f7487bf70789b20df` |
| `services/node-agent/cmd/inv-node/main.go` | `e4f8803823838d04a4bfbf783b36b9117383742d66ba4452836d69a8ec773fb9` |
| `deploy/lan/worker_config.py` | `bb2b750ac294a2558f0214f8822c02da2f015486767f361b385ccc58e3c18992` |

Named function slice SHA256, likewise identical at all four commits:

| Function | SHA256 |
|---|---|
| Go `PinPeerPolicy` | `64016481a2c2496d9d31cb8ddec6a466542e54a2e460e4e0b1f77c0c73091302` |
| Go `Authority.policy` | `ced012c78c85e6b35fce4680c8d41b2065b62bd018d9242c917b297f534e1afd` |
| Python `_write_rotation_public_material` | `2509bb185dbbc1115af55916df240843f089bdfc9c872a127143f9fc732cd99f` |
| Python `prepare_leaf_rotation` | `afe9b85e5b2a12e673768e959a3886029e03b0c31e5a4da3d56b3034a2267722` |
| Python worker `_policy` | `47a27a80a4db1515028c47b83e11c42c93b24e76c8c0cb7da921f44b6de7a40f` |
| Python worker `docker_restart` | `c9620cea65f630a3e7617b50b4561e818a00baa0ecce345f792d027d36e00b08` |

The complete source03/B5 helper file is identical, SHA256
`bca76df80a7bf80a6847e9b115679b1aa3e698d8b3a80ff843aacdd1370cd9b4`.
Its `install` slice is `c8aef68a5c028427aa024c522615c8631b2cecd513ab95d8af2b4686e102d89c`
and `finalize` slice is `4b1fa4f89ea0f1e10cba43b3a8c569b217a1c88846518181f9d5e26414615063`.
The source03/B5 complete CP helper is
`1a8ccbc5c884c562ec6038a2fd20bcb88b6ecf544797f4fe4484ddd30349c49b`.
Accepted2fb/fe7 differ in lifecycle code but retain the exact phase producer,
normal preparation and worker policy validator listed above.

The already published native Linux proof is **reported from exact fe7**, not
rerun by this audit: Core [42014770700](https://github.com/egparadise/SaintVision-Invion/actions/runs/42014770700)
is intentionally **FAILURE**, native proof exit1, valid baseline mismatch; main
Core did not run. Artifact13409265588 ZIP digest is
`dc273e5069aca4d62d0a22cb2736ff745fdd98a75ba3c72d687439e7e86e9901`.
This worker read the three public artifact files preserved in Git5023 and
recorded their exact individual blob/byte digests; it did not redownload or
reexecute that proof. Root's independent ZIP verification is prior evidence,
not a fresh ZIP verification by this worker.

Actual existing native events use one durable Journal: initial7 accepted;
overlap8 accepted, final8 rejected; overlap9 accepted, final9 rejected;
**attempted normal cycles2, completed normal cycles0**. Cycle2 is a second
attempt after the first final rejection, not evidence of a completed first
cycle. The expired-after-pin negative also saves version10 before rejecting
expiry. Exact generated public policy hashes from that fixture, never r5 hashes:

| Phase | Policy version | Policy SHA256 | Accepted |
|---|---:|---|---|
| initial | 7 | `f1218b9490dbd2704e9f8db8dcde626953d910f5c336188828cdb76f7e560466` | yes |
| cycle1 overlap | 8 | `514aded116b8dc9be726f89293e3fc03fd8b211b0e182ee5f4cda25c1b7b0895` | yes |
| cycle1 final | 8 | `73f0c7ee73289acb42b4863731da87a0268fee86f585855952b2d596b9a69580` | no |
| cycle2 overlap | 9 | `56aa6074d9ffae0f018ec03f1822e589f0e69e5e92a676326f85d8650573c178` | yes |
| cycle2 final | 9 | `b9f1d6408c46712b513ee2b9b70a4171e6722ff1f0bca2ba2d72cfb0f24a3d87` | no |

## Supported public call graph and legacy phases

At source03, `tools/lan_pilot.py:2590` normal batch preparation calls
`prepare_leaf_rotation(child)` for each active Node, sharing the new CP leaf.
The normal single-Node producer at line2840 creates `target_version=C+1`,
overlap with old+new CP fingerprints and bounded overlap expiry, and final with
only the new CP fingerprint and leaf expiry. Final inherits the same version.
The separate `_write_rotation_public_material` at line1665, exercised by the
native proof, has exactly these phase semantics. Its exact slice identity with
fe7 is additional evidence; the normal batch call graph above does not depend
on pretending that normal batch calls this second function.

`deploy/lan/worker_leaf_rotation.py:199` requires both policy versions equal
`manifest.targetChannelVersion`; `validate_bundle` verifies their exact hashes,
scope, fingerprints and respective expiries. Therefore a wrapper cannot silently
substitute final `C+2` and retain the old manifest/validator. At line508,
`install` backs up old public files, journals intent, writes the new Node leaf
and overlap policy, then calls the restart callback. The CLI passes the real
`docker_restart` callback. It copies/verifies the five credential files into
container `/state` using `worker_config.install_files`, **before** `docker
restart`; `check_running` then checks process stability, not peer-floor acceptance.
The five-file closure has no Go executable or storage-policy upgrade.

At line621, `finalize` verifies the exact CP-signed commit receipt and restarted
helper journal, writes `peer-policy-final.json` into active `peer-policy.json`,
then calls that same copy/restart callback. It marks the helper journal finalized
only after the callback returns. Its exact finalized replay returns the recorded
result without independently proving current Go floor acceptance. A runtime
preflight for the isolated Python cryptography environment supplies no Go
capability or journal observation.

Go startup (`main.go:26`) parses only the old flag set, opens/locks the actual
durable journal, then creates Authority. `NewAuthority` calls `policy()` at
startup; `Authorize` calls it again on authenticated connections. `policy()`
checks schema and scope, hashes **raw policy bytes**, calls `PinPeerPolicy`, then
checks expiry. `PinPeerPolicy` rejects lower versions and equal-version unequal
hashes, while exact equal replay is allowed. Thus an old running Go process may
pin overlap when copied into its authoritative policy path, before the requested
restart. A failed restart, absent new listener, or expired policy does not prove
that the old floor was never advanced and does not authorize restoring old bytes.
No rollback path/floor relaxation is proposed here.

The public isolated launcher `leaf_rotation_standalone_runtime.py:run_worker`
checks the pinned Python/worker closure, sets worker arguments and invokes
`runpy.run_path(..., run_name="__main__")`; `-- finalize ...` reaches the real
worker CLI branch. It does not intercept finalization, increment policy versions,
or retrofit an observer into Go. Source03 README explicitly documents CP commit
followed by Node finalize. The public standalone lifecycle check also invokes
finalize, but supplies `FAKE_DOCKER`; its success is not native Go renewal proof.

At executorB5, `Invoke-ScheduledLeafRenewal.ps1` validates the runner/tool/config
digests and invokes `tools/scheduled_leaf_renewal.py`. `load_plan` requires two
configured commands in each install/stage/finalize group. `execute` orders:
currentStatus → runtimePreflight → durable attempt intent → prepare → each install
→ each stage → commit → transition → observe → **each finalize** → finalObserve
→ changed/fresh public generation checks. `_run` validates command/input pins
and executes the supplied executable/arguments with failure propagation.
These are mandatory **configured command slots**, not embedded proof that their
opaque bodies call the leaf helper. This worker has not opened those bodies,
actual task definitions, local plan/config, guard parameters, runtime history or
renewal receipts. It neither asserts a live finalize invocation nor treats a
configured command id or fresh heartbeat as proof of completed narrowing.

The public source03 tree lacks B5's scheduled executor/wrappers; source03's
documented/helper entry points and later B5's plan executor are separate facts.
No claim is made that source03 itself schedules a renewal. This audit supplies
no authority to cancel or alter an existing automation.

## M2 capability and bootstrap boundary

The task relays the owner's proposed M2 interface (owner message240): new Go
`--observe-peer-policy-floor`, nonce bound, same executable/UID as a live PID1,
reading the actual Go journal without `OpenJournal`. This audit did not inspect
a frozen new implementation; no final source/binary hash or implemented observer
schema is claimed. The compatibility conclusion follows from the old main's
absent flag and from the relayed same-executable requirement. Later implementation
must be reviewed separately at its actual source/artifact hashes.

| Candidate observation | Satisfies production M2? | Reason |
|---|---|---|
| Old binary built from public03/B5, no new mode | no | no registered observer CLI |
| New executable side-loaded beside an old live Go PID1 | no | same-executable binding fails; matching UID/path strings do not repair it |
| Host copy/mirror of `.peer-policy`, or unsigned local JSON | no | neither actual-journal provenance nor authenticated nonce-bound capability |
| Running repaired binary with frozen provenance and reviewed M2 protocol | potentially | must still verify live PID1/UID/executable, exact actual journal, scope, fresh nonce and policy/floor coherence |
| Root's unsigned 20:34 observation | no | scoped current context only, not production M2, past proof or renewal safety |

Required preflight for the replacement renewal plan is all-member and precedes
the first CP/Node mutation: supported observer capability/build identity, nonce
and schema; same live executable/UID/PID1 and correct journal mount/path; exact
tenant/Node/epoch, current cert/key/CA/public policy bytes, authenticated actual
floor `(P, H)` and active policy hash; current CP channel version/hash `C`; no
ambiguous partial/in-flight state; and fixed cohort/mode. Derive `P+1` overlap
and `P+2` final from the authenticated **actual peer floor**, while channel moves
only `C+1`; never guess `P=C`, parse an unsigned mirror as authority, or recompute
versions on retry. Both hashes/phases and exact retry states need immutable
manifest/receipt binding under the P0 owner's reviewed schema3. Unknown flags,
missing receipt/build provenance, nonce mismatch, PID changes, unknown scope,
hash/floor mismatch, inaccessible journal or missing required member mean BLOCK
before prepare/install/publication; there is no silent legacy mode fallback.

This contract introduces a real bootstrap dependency: an old binary cannot
prove the new same-executable capability before it has been replaced. Do not
resolve that dependency by relaxing M2 or calling a side-loaded observer. A
**separate reviewed binary-only migration/maintenance contract** is needed before
the old scheduled attempt or any old-binary restart; this audit does not implement
or authorize one. Its concrete acceptance conditions must include:

1. Pin and independently review the repaired Go image/executable, helper/runtime
   closure and replacement renewal plan, including native two completed cycles,
   same-version/hash replay, stale/same-version-different-hash/expiry rejection,
   and the M2 no-write/no-`OpenJournal` paths. P0 implementation remains with
   `ctx_6f0f8253b8a7`; these are required future evidence, not tests run here.
2. Establish a separately reviewed, authenticated exact-target maintenance
   preflight while old authority is still valid. Preserve the real state volume,
   actual floor bytes, Node key, certs, policy, identity, all helper/CP/scheduler
   evidence and protected backups; do not initialize a fresh journal or infer
   their correctness from floor1 alone. If this preflight cannot be established
   without violating the M2 prerequisite, mark the migration BLOCKED for root
   decision instead of inventing an automatic bootstrap exception.
3. Define a fenced, authorized cutover to the **new** pinned binary using the
   existing exact journal/public material and unchanged `P/H/C`. It must not be
   a credential rotation or an old-binary restart. Include ownership, quiescence,
   concurrency, crash and failed-start outcomes; publication/pin uncertainty stays
   forward-only or BLOCKED. No automatic downgrade/restart of the old binary,
   old-policy restore, floor reset, latch reset or expiry bypass is permitted.
4. After the new binary is the verified live process, obtain its actual nonce-bound
   M2 proof with correct executable/UID/PID1/journal scope and confirm unchanged
   coherent floor/policy/certs/channel. Only then can a newly reviewed schema3
   renewal plan start through its ordinary guarded path. Failure stays BLOCKED;
   source repair alone does not update a frozen guard/executor plan or its pins.

Do not broaden this plain-mode bootstrap into storage/compound B or offline
recovery. Actual storage-enabled state must be identified by the owning trusted
preflight and remain blocked from the plain path; no dropping storage arguments,
mounts or sampler. Expired or partial states stay blocked for separately reviewed
offline work; no CAS ladder or widened recovery is authorized.

## Root-supplied current observation, kept separate

Per the task and root confirmation `msg_68e93c60b38e`, root made a READ-ONLY
20:34 KST observation of the exact selected r5 containers on physical PC2 and
PC4: actual peer floor1/hash equals active policy, double reads stable in scope,
file0600/UID matches identity, host helper journal absent/archive count0, containers
running and not restarting. There are six historical Node containers on each
host, and only the exact pinned r5 containers were selected; none was changed.
This worker does not independently verify or augment that observation.

The Go anti-rollback `.peer-policy`, host helper `leaf-rotation.json`/archives,
CP batch state, and scheduled attempt latch are distinct evidence. Absence of
the host helper journal/archives does not prove no historical renewal, no durable
Go floor advancement, no plan mutation, or readiness for a future normal v1
renewal. Stable floor1/hash agreement is a current scoped fact, not an M2 signed
production receipt or proof of future phase compatibility. No current live
failure, permission to disable scheduling, or whole-FIVE acceptance is claimed.

## Validation, publication and handoff

Local source audit was run with main repo CPython3.14.7
`D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe -B`, Windows PowerShell,
in this worktree based at report9ec. Exact audit command:

```text
D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe -B docs/vault/30_Development/Evidence/fleet5-legacy-peer-floor-compat-20261105/audit_public_sources.py
```

Orca CLI reports1.4.248; main interpreter reports Python3.14.7. The dispatch is
the current task/prompt boundary; no product harness/contract/ROOF/Graph or
registered task versions were changed. The source collector exited0, asserting exact three-Go-file/four-commit
equivalence, exact four-commit normal producer/preparation function equivalence,
source03/B5 worker equivalence, old observer absence, and the already published
native result0 completed cycles/2 final conflicts/Linux. Source and call-graph
review is the deliverable: **no new native proof, product Core, broad tests,
fixture generation or live experiment** was run. Required document gates, source
freeze, commit/push and exact Docs receipt are recorded in the validation JSON
and coordinator completion receipt; CI's exact report SHA is authoritative rather
than a self-referential report commit loop. Local document/source gates completed
at20:50:08 KST with direct exits captured immediately and guarded before the next
command:

| Command (Python commands use the absolute main interpreter and `-B`) | Exit / observation |
|---|---|
| `tools/check_docs.py` | 0; 24 original hashes,1210 versioned documents,48 tasks,12 outcomes |
| `tools/check_doc_path_citations.py --ratchet --base-ref 9ec6d6bf4697745bfe41602bb720473b1ff9b22f` | 0;290 baseline broken citations,no new/stale,floor unchanged |
| `tools/check_ontology.py` | 0;RDF/SHACL/equivalence/task mappings and mirrors |
| `tools/sync_obsidian.py --check` | 0;2306 managed,103 pending exports,0 conflicts,**no writes** (snapshot before adding validation receipts) |
| `git diff --exit-code 9ec6d6bf4697745bfe41602bb720473b1ff9b22f -- deploy services tools tests contracts packages .github skills docs/task-registry.json docs/vault/00_Index docs/vault/30_Development/Agent별 작업` | 0;accepted source and shared boards frozen |
| `git diff --check` | 0 |

Raw gate output is preserved in the evidence directory. Audit SHA256 values are
bound by `validation.json`; report commit/push/exact Docs final status is supplied
in the coordinator completion receipt, and remains independently visible in Git
and Actions. A document CI pass does not green the previously red native proof.

Before dispatching Docs, the first report commit
`b57e4e3874d527710d7544814f3b951133c2d4cb` exposed a report-artifact newline
binding error: Windows wrote the generated index with CRLF, while Git normalized
it to LF. Its local artifact digest therefore did not identify the committed
artifact bytes. The follow-up preserves that commit, makes the collector emit
LF explicitly, and binds validation hashes to canonical LF Git artifact bytes.
All underlying source hashes already came from raw Git blobs and are unchanged;
no product source/native proof or historical observation was changed. Post-commit
artifact hashes are checked against actual Git bytes before final handoff.

Early findings were actually sent to P0 owner (`msg_3fc68bc4c5b0`) and root
(`msg_8a638a946f1b`); root acknowledged and relayed them. Independent Claude review
of this **new audit** is pending through root, not borrowed from the prior2fb
ACCEPT. Operational acceptance is unassessed and original48/VFCL status remains
unchanged. Root owns latest-vault aggregation/sync; this worker never applies an
old vault or edits shared boards/registry.

**First next action — root:** obtain an explicit independently reviewed
capability bootstrap/migration and replacement-renewal-plan decision with P0
owner, before the old scheduled attempt or any old-binary restart; freeze the
new observer/binary/plan identities and require authenticated actual-floor
preflight before any renewal mutation. Fresh F5P0 source alone does not repair
the frozen03/B5 guard/plan. This handoff does not authorize executing migration,
changing a schedule, loosening a floor, or bypassing ordinary windows/claims.
