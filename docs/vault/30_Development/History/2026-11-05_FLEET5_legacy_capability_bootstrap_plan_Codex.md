---
doc_id: "HISTORY-FLEET5-LEGACY-CAPABILITY-BOOTSTRAP-PLAN-20261105-CODEX"
title: "FLEET5 legacy capability bootstrap and replacement renewal plan"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-05T21:41:54+09:00"
source_of_truth: "Git"
---

Card `FLEET5-LEGACY-CAPABILITY-BOOTSTRAP-PLAN-20261105`; task
`task_38393b5d1865`, dispatch `ctx_ceecb3824e33`; Codex owner, independent Claude
review via root required. Base `f0278daffa616cae4485e4b1d4c07671715892dc`, own
branch `agent/codex/fleet5-consecutive-leaf-rotation-20261105`, start21:19:35 KST.
Coordinator Index1.0.406/Codex1.0.367, AGENTS, retained required governance reads,
agent-delivery1.1.0/core-reliability1.0.0 and Orca guides govern this follow-up.
Accepted source2fb is frozen. This is a **nonexecuting design**, with no bootstrap
implementation, runnable migration commands or permission to operate equipment.

## Current decision — HOLD, unpublished targets remain null

There is **no existing safe binary-only helper path**. Claude's actual audit
`f6817f3d354bcae50f51c00c544295de3fd07662` accepts f027 with C1–C4 and identifies
the G1–G10 gap; it does not approve a bootstrap or its implementation. This worker
read its exact formal History and JSON review from Git objects. Root reports
review Docs42024928449 SUCCESS; this is attributed to root, not a runtime proof.
The new P0 Go M2/schema3 implementation is uncompiled/unfrozen at assignment.
Every future target source, executable, image/config/layers, helper, guard,
immutable renewal plan, CI/proof/verdict and operational binding is **null/HOLD**
in the plan. The audit SHA, this plan's Docs, and a proposed interface are never
substituted for those absent product artifacts.

Evidence lives in `../Evidence/fleet5-legacy-capability-bootstrap-plan-20261105/`:
`bootstrap-plan.json`, `parameter-gates.json`, `acceptance-matrix.json`, the closed
nonexecuting `bootstrap-plan.schema.json`/`schema-cases.json`, source bindings and
validation receipts. Schema success means a well-formed **HOLD document**, not
an executable or approved migration. Filling any placeholder requires an actual
published and reviewed successor revision, not a force flag or an unsigned file.

## Root observations and schedule chronology

- At20:34 root observed the exact selected old r5 containers on physical PC2/PC4:
  floor1/hash equals active policy, scoped double read stable, UID/mode consistent,
  host helper journal absent/archives0; six historical Node containers per host.
  It is unsigned, unfenced **context only**, neither M2 nor past/future renewal
  safety. This worker did not inspect private state or the containers.
- The original f027 report and f681 review's unchanged-schedule observations
  remain historically true for the observations they describe. They are not
  rewritten to claim that a later administrative action had already occurred.
- **New root fact21:14:42 KST:** root disabled exactly Orca entries
  `286d975e-75e2-4e54-b1fb-2805f7d68959`,
  `a3a9e396-3b48-4aaa-8b73-f8377670f968`, and
  `3e08faa1-4e85-4877-8b13-5645178b41b8`, each enabled true→false. Only enabled
  and updatedAt changed; all other config/prompt/precheck/timezone/rrule/dtstart
  remained equal. No RunNow or Node action occurred. This is root-reported;
  **no automation writes or readback were performed by this worker**.
- Before any operation, root must obtain a fresh disabled readback of those exact
  IDs, the unchanged configuration digest/target binding and proof of no overlapping
  attempt/descendant or other launch surface for this cohort. Disabling entries
  does not prove that already launched work has quiesced. Old callbacks stay
  read/evaluate/report HOLD only; B5 itself has no documentary-HOLD enforcement.
  **Never simply re-enable the old source03/B5 normal-v1 plan.**

## G2: two image semantics and proposed choice

Exact public source03 `start-node.sh` uses resolved actual image as the container
runtime image and manifest `agentImage` as the value of `--image`. Go main binds
that flag to `Config.Image`; `runtime/permit.go:67` compares a signed workload
`Launch.ImageDigest` to it. That check does **not** attest the Node's own binary
or image. `lan_pilot.py:manifest_for_node` copies the global CP `agentImage` into
worker manifests; bundle preparation records a runtime build into that global
field. The old field therefore conflates artifact/runtime provenance with the
initial permit image value. Source hashes and line anchors are captured in
`public-source-bindings.json`; complete Git reads exited0. Selective PowerShell
display pipelines earlier returned1; final evidence uses full, checked blob
reads rather than treating a partial display as a source or test gate.

**Proposed choice A — preserve permit semantics, split runtime inventory:**

1. Preserve the exact old Cmd, including `--image` and `/inv-node` executable,
   profile and every argument. Its allowed permit/workload digest remains fixed.
   Change the actual Node **runtime image only**. An old permitted workload digest
   and a new Node runtime digest can differ deliberately under this explicit
   contract; they are no longer described as the same identity.
2. Add a NEW typed per-Node runtime inventory/migration receipt with distinct
   `runtimeImageDigest` and `preservedPermitImageDigest`, actual binary hash,
   source/provenance, old/new container IDs, inspect/state/M2/mTLS bindings and
   root ownership. Keep the legacy CP `agentImage` and old manifests byte-frozen
   as historical bundle/default records. They cannot continue serving as current
   runtime truth after migration. New consumers must require the new typed record
   and block on its absence, rather than silently fall back to the global field.
3. Commit both fixed-cohort inventory entries under one owned compare-and-publish
   transaction after both new Nodes pass M2/mTLS. Compare old inventory/global
   state digests and unchanged Node channel vector `(C, certHash, enabled, endpoint)`;
   this is a **new inventory metadata CAS**, never a Node channel/leaf CAS. A mixed
   physical cutover stays in explicit per-Node migration states, not a false
   all-member inventory commit.

Root's G2 choice is **null** pending independent review. This requires new helper,
inventory/API and consumer contracts; the old bundle builder is not an updater
for this purpose. Alternative B, rewriting `--image` to the new runtime image and
changing CP `agentImage`, changes permit policy/Cmd and violates literal G1
image-only scope. It needs a separate scope decision and cannot happen silently.
Neither the allowed workload image nor CP's old global field is rewritten here.
Early G2 analysis was delivered to root `msg_a2ae896bbfb8` and P0 owner
`msg_a5740d259671`; it is a proposal, not root's approval.

## Closed G1–G10 gates

`parameter-gates.json` is normative for required inputs, evidence and refusal.
All bindings must describe the **same two old r5 identities** on PC2/PC4, not the
fresh five-Node issuer/cohort. Every unknown, missing, stale or inconsistent value
blocks before its dependent side effect. No arbitrary extra keys or bypass knobs
exist in the proposed interface.

`parameter-contract.json` closes the future method input sets and defines source,
artifact, identity, P/H/C, time, ownership, volume and proof types/predicates.
`inspect-comparison-contract.json` enumerates image/lifecycle paths separately
from exact Config/HostConfig/Mounts/endpoint comparisons; actual Engine version
and old inspect stay null until root binds and tests them. Unsupported or unknown
configuration cannot be ignored to make an image-only comparison pass.

| Gate | Required boundary |
|---|---|
| G1 | Exact old name+label+container ID/daemon, full inspect frozen; storage-free observe only. Cmd, Env, Entrypoint, User, resources, security, mounts, labels and host endpoint all preserved. Runtime Image changes only; explicit lifecycle deltas are restart=no, retained backup name and new generated container identity. |
| G2 | Root-reviewed choice A and new split inventory/consumer contract; preserve permit image/CP legacy bytes, explicitly publish new runtime metadata after all-member proofs. No channel CAS. |
| G3 | No credential copy or prepare/repair/finish/install_files; reuse exact owned volume bytes. Host copies, if consulted by root, are read-only comparisons and never authority for restoration. |
| G4 | Fresh **fenced, unsigned** pre-cutover double read with actual journal/active policy hash and protected tree; bind P/H. Post-start signed nonce-bound M2 from new live same-executable UID/PID1 must match P/H/scope and active hash. This bridge is bootstrap-only, not unsigned normal-renewal fallback. |
| G5 | All uncertain/failure paths preserve both containers, image evidence, volume, backups and attempt journal; forward-only/BLOCKED. Never start old image, restore old policy, downgrade, clear lock/latch/floor or widen expiry/offline recovery. |
| G6 | After P0 native green, actual old/new Go fixture proof must show compatible existing journal and **no protected-state write** on exact startup/replay/M2/mTLS. Observer branch never OpenJournal. Missing files/migration requirements block. |
| G7 | Fresh fixed P/H/C, identity/key/certs/CA/signer/policies, volume identity+all consumers, no workloads/claims/offers, reservations and process quiescence. Durable intent before image/consumer/name publication and before first new start. |
| G8 | Old backup stays restart=no. New container remains restart=no until signed M2 plus actual mTLS, unchanged authorities and explicit root step permit restoring its original unless-stopped policy; never restore backup restart policy. |
| G9 | Fresh exact disabled readback and no overlapping/direct executor/precheck attempt; no RunNow or old plan reuse. Replacement guard must enforce HOLD and capability/provenance gates in code. |
| G10 | Actual P0 source/binary/image provenance, native two **completed** cycles, journal/M2 proofs, all relevant CI and independent verdict first. Null product bindings mean HOLD even when this document's Docs is green. |

For G1, freeze raw inspect and a versioned closed comparison projection. Image
references/IDs are the single configuration change. Docker-generated identity,
creation timestamp and ephemeral internal paths/network IDs are listed separately
as lifecycle observations, not broad wildcards: the new helper must reject
unsupported nondefault/unknown config fields. Explicitly compare host bindings,
endpoint scope, mount source/name/type/RW/propagation and volume metadata, and
all resource/security/command fields. No reconstructed defaults, workspace flags,
docker socket, storage arguments, extra mounts or new container labels. The
external reservation journal binds new container ownership by exact ID and the
unchanged Node label; a convenience migration label would itself violate G1.

## Required new interface and state machine (not implemented)

Minimum NEW interface is a storage-free `LegacyBinaryMigration` lifecycle plus
the typed CP runtime-inventory compare-and-publish API. Read-only inspect and
capture methods feed an immutable plan; advance accepts only exact next phase,
plan digest, prior event digest and held ownership token. No generic shell,
repair, credential install, force, rollback, supersede, clock or skip parameter.
Reuse control ideas from public `worker_replacement.capture` and `worker_replace`,
not their storage-required command paths/imports or workspace downgrade behavior.
No such new helper/API is claimed runnable or implemented by this report.

| State | Durable evidence and permitted next action in a future reviewed implementation |
|---|---|
| DRAFT_HOLD | Current state: null product/private bindings; no runtime action. |
| PROVENANCE_LOCKED | G10 plus independently reviewed G2/helper/API/guard and immutable candidate parameters; root execution decision remains required. |
| RESERVED | Atomically reserve both identities/daemon/volume/channel vector under owned root/CP guards; fresh G9/no overlap; append reservation intent outside Go volume. Never reclaim a lock on PID age or timeout alone. |
| FENCE_INTENT | Persist exact old inspect, restart policy and stop intent before changing lifecycle; record per-member outcome. |
| OLD_FENCED | Exact old container restart=no, stopped/not restarting, owned descendant/workload quiescence proved, no other volume consumers/writers. Unknown stop outcome cannot advance. |
| CAPTURED | Two bounded read-only state archives from stopped exact old container, no extra mounted reader, identical tree/content/UID/mode/scope/volume/consumer readbacks; coherent actual P/H and current valid authority/C. |
| PUBLICATION_INTENT | Immutable proposed new-image binding and full pre-state/reservations recorded before rename/create/volume exposure; separate first-start intent required later. |
| OLD_PRESERVED | Rename exact old ID to reserved backup name; keep stopped/restart=no forever. Backup collision, altered name/ID or extra consumer blocks; never overwrite/delete one. |
| NEW_CREATED | Create from reviewed image, exact configuration projection, same volume, restart=no. Allowed consumer set becomes exactly retained old ID plus recorded new ID; old remains stopped. No credential copy. |
| NEW_START_INTENT | Revalidate G1–G10/fresh deadline and byte digest immediately before first start; record durable barrier because startup may pin. No automatic rollback on any later path. |
| NEW_STARTED_UNVERIFIED | Start only new recorded ID; stable process is insufficient. Verify protected-state tree unchanged, actual binary/image/UID/PID1, signed M2 matching captured P/H, then authenticated mTLS on unchanged endpoint/certs. |
| BOOTSTRAP_VERIFIED_RESTART_NO | Both members prove G4/G6 and unchanged P/H/C/authorities; atomically publish new per-Node runtime inventory, read it back. Keep normal renewal HOLD and all old entries disabled. |
| RESTART_POLICY_RESTORED | Optional explicit root step only after fresh M2/mTLS and authority equality: change **new** container restart=no to original unless-stopped, then read back exact inspect delta. |
| READY_FOR_NEW_RENEWAL_PLAN | Bootstrap completion evidence available; distinct new schema3 renewal plan/guard still needs review, valid timing and its own authorization. No legacy re-enable. |
| BLOCKED_FORWARD_ONLY / QUIESCENCE_UNKNOWN | Preserve every object and reservation. No further start/publication if exact ownership, stop, state or authority cannot be proved. Root resolves exact current state through a separately reviewed forward action; no automatic retry/downgrade. |

Every side effect has write-ahead intent, exact readback and a checkpoint test
seam before/after it. Append-only no-overwrite events are chained by prior digest;
latest-state projection may be atomically replaced only from its exact prior
digest after fsync. Journal path/parents must be owned, private, regular, no
symlink/hardlink aliases; publication collision preserves all bytes and blocks.
Held OS and logical ownership span check→mutation→readback; no stale-lock removal.
The Go volume, old Node, failed new Node, backup containers and migration evidence
are **never deleted**. A pre-side-effect cancellation can record no-effects and
release only its exact reservation through CAS with evidence; after uncertain
side effects, ownership remains reserved until root's explicit reviewed resolution.

States are a **per-member vector plus cohort barriers**. Proposed deterministic
order is PC2 then PC4, subject to root's reviewed plan choice; both members must
pass nonmutating G1/G2/G9/G10 and be reserved before the first lifecycle change.
Record fence intent and read back restart=no for **both** old containers before
the first member is stopped, preventing daemon recovery from silently starting
an old backup/remaining old image. Then stop/capture/replace/start/prove PC2;
only after its M2/mTLS and unchanged-state acceptance may PC4 enter that sequence.
The second old process may continue running with restart=no until its own turn;
that is not an old-binary restart. Failure/unknown state in PC2 blocks PC4 cutover,
preserves both fences and keeps all-cohort inventory uncommitted. This plan never
labels a mixed phase vector ready, and never restores the old restart policies.
Immediately revalidate shared C/authority/time/ownership before each member's
mutation; a mismatch requires BLOCK, not rebasing the frozen plan in place.

Read-only state capture must stay private/in-memory and bounded; hash path,
file content, mode, UID/GID, type and protected structure, reject unsafe archive
paths/aliases. No key bytes, full archive, private configs or M2 key material are
published. Startup compatibility requires every protected byte/metadata field
unchanged; atime and process telemetry are outside that explicitly versioned
protected digest. Unexpected journal creation/repair/mode normalization is a
failure, not an allowed migration. Old/new format conversion needs another card.

## Replacement normal renewal and deadlines

After bootstrap, use **new reviewed schema3 helper + new guard + immutable plan
pins**, not a patched parameter file pointing at source03/B5. Same two Nodes,
tenant/epoch/keys/CA/endpoints; no fresh-five issuer or identity remap. Root must
privately bind actual physical inputs and remeasure all current leaf/CA/policy
validities and earliest deadline. The historical Nov10 14:15:35 KST earliest old
leaf expiry and Nov8 14:15:35 window are context only and cannot populate current
gate inputs. Missing/elapsed/unknown deadline, insufficient measured safety budget
or unknown state means BLOCK/separately reviewed offline work, never a CAS ladder.

Binary-only maintenance uses a separately reviewed root operator window and valid
unchanged authorities; it does not pretend to be an early leaf renewal. The later
normal renewal obeys its actual renewal window, ordinary clock/claims/locks and
operator window. Its all-member preflight must obtain fresh signed actual M2,
validate immutable target provenance/guard/plan, and freeze each current P/H/C.
Use P+1 overlap/P+2 final with C+1 channel, and in a second complete cycle P+3/P+4
with C+2. Exact phase retry must not recompute versions or rewind a final floor.
Publication/startup/pin/CAS uncertainty creates a forward-only barrier; old valid
certs or failed process startup never authorize old-policy restoration.

Do not mix bootstrap with renewal or release its reservations into an old pending
attempt. A new guard must reject legacy schema/old plan pins, stale observed floor,
wrong executable/nonce/journal, incomplete member proofs and blocked bootstrap.
Legacy failure receipts/latches/locks remain evidence, never cleared to make the
new plan appear fresh. Any replacement automation is a separately reviewed new
definition with exact plan/guard pins; its future creation/enabling belongs to root.

## Red/green acceptance and handoff

`acceptance-matrix.json` names the required isolated real-Go/Engine fault seams
and expected refusals, separately from document schema checks. No product proof
is run here. Required future GREEN includes actual old/new journal no-write
compatibility, signed same-executable M2 after image-only cutover, mTLS unchanged
authority, retained backups/restart fencing, atomic two-member runtime inventory
and two **completed** native schema3 renewals. Required RED includes old v1 same
version/different-hash final, unknown/partial state, extra volume consumer, wrong
config/image semantics, stale schedule/precheck attempt, forged observer, metadata
write, unknown stop, archive collision, each crash seam and downgrade attempts.
Docs/schema GREEN cannot substitute for any runtime GREEN.

All implementation and operational inputs remain HOLD. Root next chooses G2
after actual independent plan review, waits for P0 source/binary/proof/CI/verdict,
then assigns the new storage-free migration helper/inventory/guard work with
these acceptance seams. No migration, schedule, guard, private config, key, PKI,
SSH/WSL/Docker, state, claim/pin/window/clock or hardware action was performed;
shared boards/registry/Obsidian apply remain untouched. Source2fb, historical
audits and original48/VFCL/five-PC acceptance are unchanged. Local document/schema
gates and exact Docs publication are recorded in Evidence and the coordinator
receipt. Independent review of **this plan** must be actual, not inherited from
Claude's acceptance of f027.

Document preparation note: automatic review rejected one oversized data-generation
shell command before it ran (reported reason only: blocked by policy). The JSON
documents were then written directly with the file-edit tool; no bootstrap
implementation or runtime action was attempted. The smaller document-only schema
check ran successfully with the authorized main Python3.14.7 interpreter and
`-B`:initial12 matched cases (1 valid HOLD,11 rejected mutations),0 product cases run.
This preparation event is not a runtime failure or a reason to rerun product CI.

After the per-member sequence clarification, final document schema validation
matched **14/14 cases** (1 valid HOLD draft,13 rejected mutations,0 failures),
including rejection of an unsigned floor1 value copied into an operational
member binding and of an invented root order approval. Target27/root18 binding
fields and both member binding envelopes remain null. The parameter-name closure
matches G1–G10;24 distinct future product acceptance cases cover all ten gates
and remain **NOT RUN**. Source03/B5 G2 equality was checked for all four relevant
whole files; no new source tests or Core were dispatched. Final local gates use
the main Python3.14.7 `-B`, and `plan-validation.json` records full commands,
actual KST intervals/exits/output plus canonical Git artifact hashes. Exact final
Docs and actual independent plan review are required before this task's delivery
receipt; neither grants operational approval.
