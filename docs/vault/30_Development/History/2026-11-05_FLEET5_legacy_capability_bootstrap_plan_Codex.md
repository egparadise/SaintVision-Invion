---
doc_id: "HISTORY-FLEET5-LEGACY-CAPABILITY-BOOTSTRAP-PLAN-20261105-CODEX"
title: "FLEET5 legacy capability bootstrap and replacement renewal plan"
version: "1.0.2"
status: "review"
author: "Codex"
updated: "2026-11-05T22:50:12+09:00"
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

**Root selected choice A FOR THIS NONEXECUTING PLAN** in `msg_f517e89d6a16`
after publication1057. This is a real architecture/planning selection, not code,
contract, independent-review or operational acceptance. Its message is bound in
`root-g2-planning-choice.json`. The future reviewed contract/operation binding
`rootBindings.rootG2Decision` remains null, along with every product binding;
it cannot be populated merely with that planning message. This requires new helper,
inventory/API and consumer contracts; the old bundle builder is not an updater
for this purpose. Alternative B, rewriting `--image` to the new runtime image and
changing CP `agentImage`, changes permit policy/Cmd and violates literal G1
image-only scope. It needs a separate scope decision and cannot happen silently.
Neither the allowed workload image nor CP's old global field is rewritten here.
Early G2 analysis was delivered to root `msg_a2ae896bbfb8` and P0 owner
`msg_a5740d259671`; at that point it was only a proposal. The later Root planning
selection above is not operational approval.

The versioned proposed record is explicit in `runtime-inventory-contract.json`:
Docker local **image ID**, repository manifest/index **RepoDigest**, selected
platform manifest/config digest, ordered RootFS diffIDs, archive digest, executable
byte SHA256 and Git source SHA are distinct. RepoDigest is not image ID, binary
hash or source SHA. An authenticated offline publication may explicitly have no
RepoDigest only with its real archive/config/layer/build mapping proof; never
invent a repository digest from an image ID or accept unsigned absence. Current
target values remain null, including the added Docker-ID/repository-or-offline/
archive bindings.

The **desired NEW M2 v2 must supply** a separately signed actual executable-BYTES
hash, nonce and live same-executable UID/PID1/journal/scope binding. The inspected
unaccepted6c M2 does **not** supply executable bytes: its `servingProcessSHA256`
hashes raw NUL cmdline, with SameFile proof only. This correction is N1 below;
v1 cannot satisfy the desired executable proof. Even the desired bytes hash alone does not prove a Docker
image. Root's trusted owned-daemon inspection separately binds the same exact
container ID and stable live PID/start/restart observations to its `.Image`,
resolved `.Config.Image`, published config/layers/platform and no executable
mount/overlay substitution. Cross-read before/after M2 and join both proofs to
the published executable/source build. Inventory publication requires that join;
neither an image label nor Node's image claim nor an old Node key alone can stand
in for it. Proposed receipt has an authenticated immutable versioned cohort
envelope and per-Node typed records; actual M2 wire/signature contract is still
unpublished and must be mapped from the reviewed compiled implementation.

Before/after canonical ordered Cmd argv hashes and exact argv arrays must match,
including the preserved permit-image value; Entrypoint and actual live PID1 argv
are checked separately. Protected tree equality plus typed Node/CP cert DER
hashes, Node key public SPKI hash, CA/signer raw hashes, policy raw hash, floor
P/H/raw-file identity and journal tenant/Node/epoch scope bind the unchanged
authority. Private key bytes stay local inside protected-state comparison.

`legacy-consumer-closure.json` enumerates the source03 code readers/producers
and their disposition. In particular old `bundle/manifest_for_node`, start/repair
credential paths, runtime validation against old image descriptors, execution/
workspace installers and storage replacement paths cannot be used as a migrated
cohort updater. New runtime/guard/renewal readers must require the typed record;
out-of-scope helpers stay blocked. Test/report fields using the old ambiguous
name remain historical and cannot become bootstrap provenance. Any newly
discovered/private consumer must be added and independently closed or BLOCK;
there is no fallback to old global `agentImage` after typed migration.

## Actual independent revision findings and bounded response

Actual Claude task `task_03867932b2f0` / `ctx_37e3f120fac0` reviewed1057 at
`830efd9317d28fa27b696db709c9a6e7a3076331`, then exact cde/delta at
`eace0e2de11801be0e6d63a5cf08817c37214ea3`. This worker read both complete formal
History pages and original JSON findings from Git. **cde verdict: REVISION
REQUIRED** — R1/N1 required, R2 partial, R4/N2 additions; R3 is closed for
source03 scope. Root reports exact review Docs42033242038/42033713492 successful.
Those are review/document receipts, not P0/code or operational acceptance.
Candidate `6c0fc4adf53562909e3d8246ddf293d8aadb0d0e` remains NOT ACCEPTED.
The following are proposed contract corrections, not claims of implemented fixes.

**R1 — typed retained migration predecessor and later renewal reachability.**
`migration-predecessor-contract.json` defines proposed journal schema
`saintvision-plain-agent-migration:1`, basename `agent-binary-migration.json`
under the trusted registered host worker root (outside the Go volume). It is
owned/private/regular0600/single-link, with no-follow parent/file checks, immutable
plan/event sequence and exact common-fence owner/generation/lease or terminal seal.
It binds exact daemon, tenant/Node/epoch, current ID/name, backup ID/literal inspect
name, frozen **post-stop/rename/restart=no** old inspect/config/image/mount digest,
and the exact same retained volume/stable identity. Backup is stopped, not
restarting and restart=no; no new labels are added and labels alone prove nothing.

Exactly current+that one recorded predecessor may consume the volume. Unknown,
unrecorded, label-only/workspace-only, wrong-owner/schema/fence/phase, missing or
third/duplicate consumer blocks without removing anything. A bootstrap M2 before
terminal inventory uses the still-held migration owner lease plus exact
NEW_START_INTENT/NEW_STARTED_UNVERIFIED context; a terminal-only check here would
create a circular dependency. Later normal:3 uses immutable terminal migration
seal/current typed inventory plus a **new common operation lease**, not a dead
migration owner lease. The static backup/container/volume binding remains fixed,
but current cert/policy/P/H/C are validated against the fresh signed normal:3
generation, **never the migration authority baseline**. The shared volume will
legitimately change during renewal; no backup deletion or restart is needed.

The candidate `worker_peer_floor` target/observe/context and `worker_plain_rotation`
floor/target/install/finalize route are explicitly in scope, with the normal:3
dispatch/restart path. Current6c only admits the labelled workspace predecessor,
so this is a required new reader branch, not existing functionality. Future GREEN
must demonstrate post-bootstrap M2 **and two later completed normal:3 cycles with
the backup retained**; RED includes unrecorded and label-only consumers.

**R2 — named common coded fence and raw invocation limit.**
The NEW proposed `agent_mutation_fence.run_owned_operation` /
`require_operation_context` API consults persistent `agent-mutation-fence.json`
and the migration journal through a trusted canonical Node/daemon registration.
Any nonterminal **or terminal** migration marker denies all generic mutators.
Known registry state with missing/malformed/unowned marker also blocks. A leaf
`no_rotation_mutation` check is not this fence; neither a bare boolean
`rotation_publication=True` nor a one-shot precheck grants an operation lease.
The common logical+OS fence must span the complete operation/children/readback,
before first mkdir/CSR/copy/image load/container action or controller publication.

`common-agent-mutation-fence-contract.json` lists repair-node.sh/Repair-Worker.ps1,
prepare-worker.sh/Prepare-Worker.ps1, finish-worker.sh, start-node.sh/Start-Worker.ps1,
credential installers, execution/workspace/storage/replacement helpers (including
rollback), new observer/normal:3 APIs and controller/guard adapters. Supported
direct Python functions require guard-owned context too; shell/PowerShell entrypoints
delegate to a fixed hash-bound guard runner that retains ownership. Generic paths
remain denied even after migration completes; only specifically guarded migration
advance/M2 or later normal:3 operations may pass their separate typed conditions.

This is NEW required code, not a magical property of placing a marker beside old
scripts. All supported entrypoints must be actually replaced/adapted and tested.
Archived/unpatched raw helpers, arbitrary imports/monkeypatches and privileged raw
Docker/shell bypass lie outside the authorized managed interface; a marker cannot
stop a privileged bypassing actor. Root must exclude them from allowed launch
surfaces and prove no in-flight work; if any such path remains authorized/reachable
or unknown, G9 stays HOLD. This plan changes no permissions, scripts or launchers.

**N1/N2 — desired separate signed bytes hash and exact argv encodings.**
Root chose a required **new** signed `servingExecutableSHA256` over bounded actual
serving executable file bytes, preserving live PID1/UID/SameFile and stable
process/file identity checks. Proposed M2 schema is
`saintvision-node-peer-policy-floor:2`, domain ASCII
`saintvision/node-peer-policy-floor/v2` plus byte00; strict producer/verifier field
sets include the new field. It is absent from unaccepted6c. Actual wire/source/
binary/CI/verdict bindings remain null. Existing `servingProcessSHA256` retains
its exact v1 meaning, SHA256 of raw cmdline including its final NUL; historical
receipts are never reinterpreted. Existing v1/missing bytes field cannot satisfy
the new bootstrap proof. Signing-body ASCII-escaped compact canonical JSON is
separate again from argv JSON encoding.

`desired-m2-v2-and-argv-contract.json` names each hash. Cmd and Entrypoint JSON
hashes preserve their separate exact ordered string arrays. Full serving argv is
direct Entrypoint+Cmd. Canonical argv JSON is compact UTF8, no BOM/newline, reference
`json.dumps(..., ensure_ascii=False, separators=(',', ':'), allow_nan=False)`;
no Unicode normalization or shell expansion. Raw cmdline is strict UTF8 argv bytes
joined with NUL plus one appended terminator; decode by removing **one** terminator
then splitting, preserving empty elements. Invalid UTF8/unpaired surrogates or
embedded NUL in an argument blocks. Compare expected raw hash only to signed
`servingProcessSHA256`; map the exact same array to its separate JSON hash, never
compare these hash domains directly. Compare desired signed executable bytes hash
only to the published binary bytes hash. Encoding fixtures are synthetic document
vectors only, not process/provenance evidence.

Exact minimal R1/N1 proposal was sent to P0 owner `ctx_6f0f8253b8a7`
(`msg_5ffb02106b2c`), Root notified (`msg_01c78fa72644`); compatibility response is
recorded separately. This plan author implements no production helper or Go change.

**R4 — exact observer ExecIDs and inherited image Config.**
`observer-exec-and-image-config-contract.json` requires actual Engine ExecCreate ID
recorded under the same guard/nonce/current container before start. Initial ExecIDs
is empty; all during/after entries must be that exact observer ID under the frozen
Engine phase contract, with exact ExecInspect finished/exit0/container/argv/UID
binding. Unknown/foreign/unrecorded ID, ambiguous outcome or process/config drift
blocks. Current CLI docker-exec exposes no such receipt, so a new host adapter is
required; no generic volatile ExecIDs ignore or guessed allowlist is accepted.
`inspect-comparison-contract.json` enumerates this controlled lifecycle delta.

Actual **image-inherited** Entrypoint/Env/Labels/User/WorkingDir must equal the old
image's fields, using the same frozen scratch/COPY/ENTRYPOINT recipe; other runtime
Config changes/unknowns block. Equal container overrides cannot hide a changed
image default. This image Config proof is separate from container Config equality
and published new config/layer digests. All actual Engine/image/exec bindings are
unbound and this correction does not claim current runtime verification.

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

All implementation and operational inputs remain HOLD. Root's planning direction
is recorded; actual independent bootstrap architecture review is next, followed
by published P0 source/binary/proof/CI/verdict and reviewed contract binding. Root
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

Root's subsequent G2 planning direction is recorded in this1.0.1 revision without
changing source2fb or filling product provenance. The revised draft has **30**
null target bindings and18 null root operational bindings; both member envelopes
remain null. Image/process/source/argv/authority distinctions and explicit legacy
consumer closure add four future product acceptance cases (**28 NOT RUN**) and
two document refusal fixtures (**16** total). Final schema/closure validation,
document gates, actual Git artifact digests and exact revised Docs are recorded
for this revision; the initial1057 receipts remain true for that initial revision.

Revised document-schema validation actually matched **16/16** (1 valid HOLD,
15 rejected,0 failures), confirmed the30/18/member null bindings and parameter
closure, and parsed every JSON with duplicate-key rejection. The28 product cases
remain NOT RUN. Eight further public consumer blobs and the B5 executor/launcher
were hash-bound with checked complete Git reads; an additional PowerShell literal
scan had expected no-match exit1, not a failed CI/test. No unlisted/private
consumer is presumed safe and no compiled product proof is inferred.

The bounded independent-review response is this1.0.2 revision. Four proposed
contract artifacts specify R1/R2/R4/N1/N2; `review-findings-closure.json` preserves
the actual prior REVISION REQUIRED verdict and marks this revision's independent
verdict null. Thirty target and18 Root binding values, both member envelopes and
the operational G2 binding remain null/HOLD. Added future A29–A36 bring product
acceptance requirements to **36 NOT RUN**. Document mutation fixtures D17–D26
cover the new refusal barriers; they do not implement a runtime guard.

`source-review-cases.json` directly checked9 static public Git facts, confirming
the6c gaps without accepting code; all9 matched. `encoding-validation.json`
checked10 measured synthetic document encoding cases (strict UTF8/NUL handling,
empty argument preservation, separate JSON/raw domains, no Unicode normalization),
all10 matched,0 failures. The fixture hashes are computed synthetic encoding
vectors, never actual process/binary/Node/provenance. Complete candidate/helper/
review Git blob digests are bound in source Evidence. No actual host script,
guard, helper, Go process or product test was invoked; main Python3.14.7 `-B`
only parsed public source/data and ran document checks. Actual owner compatibility
reply, final schema/gate/hash/Docs receipts and new independent delta review
remain separately attributable; no earlier audit ACCEPT is borrowed.

Final1.0.2 document schema/closure check matched **26/26** cases (1 valid HOLD,
25 rejected mutations,0 failures), all thirty target/eighteen Root values and
both member envelopes still null. G1–G10 parameter names and all four new contract
references resolve;36 future product cases cover all ten gates and remain NOT RUN.
Nine source cases and ten encoding cases matched independently of product code.
Actual required local gates and canonical Git hashes are captured in the revised
validation receipt; normal push/exact Docs/new actual delta review follow. No
acceptance is inferred from an author response or a passing document schema.
