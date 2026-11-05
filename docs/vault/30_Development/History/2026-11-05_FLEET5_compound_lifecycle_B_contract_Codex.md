---
doc_id: "CONTRACT-FLEET5-COMPOUND-LIFECYCLE-B-001"
title: "FLEET5 B compound compute storage and leaf lifecycle proposal"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude architecture review through root pending"
updated: "2026-11-05T20:12:00+09:00"
source_of_truth: "Git"
---

# B v1: explicit preservation and compound authority renewal

Root selected **B, staged contract publication first**, in `msg_958ee1d13efe`.
Production implementation requires actual independent architecture review through
root. This document and its schema are review artifacts, not a deployed contract,
an accepted ADR, a signature verifier, or evidence of active storage.

Task `FLEET5-COMPUTE-STORAGE-CONTRACT-20261105`, owner Codex, reviewer Claude via
root. Branch `agent/codex/fleet5-compute-storage-contract-20261105`, checkout base
`0bcf9670d098fac87667fc9e2448b332db46e691`, branch-created 19:12:03 KST.
The historical guarded-source rejection remains pinned to that base. This design
targets accepted lifecycle source **`2fb52bbe5e500354b323eb8e46d5aa5066690d2d`**, read
via Git objects without merging/replacing S1, integrator or production files.
Root reports actual Claude source review `d06f93f73a211bb2d56ce2b42141c71771b7f270`;
this is attributed source feedback, not a substitute for B architecture review.

Read current guidance and root Index401/Codex362 as recorded in
[[2026-11-05_FLEET5_compute_storage_contract_Codex]]. S1 design-only feedback
`msg_fc7b89e943c8`, corroborated by root `msg_7f275154764a`, is incorporated below.
Exact object hashes and line anchors:
`docs/vault/30_Development/Evidence/fleet5-compute-storage-contract-20261105-codex/lifecycle-source-2fb.json`.

## Scope and interfaces

Rollout is **new approved read-only-storage observation Node → explicit workspace
preservation migration → owned work**. Attaching, replacing, disabling or removing
a contribution on a completed workspace remains refused. Native Linux with a
local default daemon is supported; remote daemon, CP/WSL mapping and arbitrary
mounts remain refused until separately proved. Four plain independent workers
remain a separate baseline, with contributed-storage acceptance false.

The default R4 guard and old package schema remain unchanged. A workspace package
schema 2 explicitly selects `preserve-readonly-contribution`; its dedicated CLI
requires exact `--preserve-readonly-contribution`, policy SHA and request SHA.
No discovered mount enables it implicitly. Closed argv parsing rejects duplicates,
unknown options, single-dash aliases and equals spellings in this new route.
All durable identity, profile/image/executable, socket and private-file arguments
must be unambiguous. No generic mount forwarding is permitted.

New managed-mode Node arguments have fixed paths:
`--authority-generation /state/authority-generation.json` and, for a contribution,
`--storage-mount-binding /state/storage-mount-binding.json` alongside the existing
`--storage-policy /state/storage-policy.json`. A managed generation cannot omit
its declared sampler. A plain generation explicitly declares storage absent;
it cannot discard a previously active contribution. Existing unrelated historical
contribution floors remain preserved.

Proposed schema, all objects closed and versions bounded to canonical int32:
`docs/vault/30_Development/Evidence/fleet5-compute-storage-contract-20261105-codex/proposed-contract-v1.schema.json`.
It defines mount binding, preservation proposal, compound renewal proposal,
intent, active generation decision, Node/batch journals and signed installation
acknowledgement. `deviceId`/`inode` are canonical decimal strings so JSON cannot
round a 64-bit filesystem identity; semantic validation additionally bounds uint64.
Schema shape validation is necessary but does not verify signatures, paths, actual
mounts or cross-field relationships. The rules below are mandatory.

After architecture acceptance, common definitions move into the existing canonical
schema/generator pipeline, with generated Python/Go readers and shared fixtures.
Do not install this Evidence schema directly as production truth. The existing
`NodeStorageChallenge`, `NodeStorageSampleInput` and signed sample wire remain
unchanged: source demonstrates no need to broaden their authority.

## Source constraints that B must satisfy

| Exact 2fb surface | Constraint |
|---|---|
| `services/node-agent/cmd/inv-node/main.go:84` | NewAuthority runs before NewStorageSampler; a failed startup can already have advanced peer policy |
| `services/node-agent/transport/trust.go:85` and `runtime/journal.go:341` | Peer policy pins exact version/hash; a changed hash at the same version is forbidden |
| `deploy/lan/worker_leaf_rotation.py:199` | Current overlap and final peer files are both checked against targetChannelVersion despite changed bytes; B needs a new explicit generation contract, not a weakened floor |
| `services/node-agent/transport/storage.go:30` | Full policy and channel hashes, current cert and root must validate before storage pin; policy mutation requires restart |
| `services/node-agent/storage/sample.go:84` | Leaf **DER** fingerprint and entire challenge channel must match, even if Node private key is unchanged |
| `services/node-agent/runtime/storage_policy.go:31` | Root/channel floors are independently monotonic; equal versions cannot change their hashes or raw policy |
| `services/control-plane/src/inv/migrations/0005_node_channels.sql:40` | DB trigger requires exactly old version +1, including recovery; no version jump/reset is legal |
| `deploy/lan/worker_leaf_rotation.py:577` and `tools/lan_pilot.py:1817` | Settled exact predecessor archive and raw journal/authority must match; `.next` residue refuses successor |
| `tools/lan_pilot.py:1888` | Retirement verifies exact Node finalization proof bytes, canonical CP archive and terminal journal before successor |

The peer-phase observation is source analysis corroborated by S1, **not a live
failure** and not a revocation of root's attributed 2fb review. Mocked Python
restart fixtures do not prove real Go Authority/StorageSampler startup. B must
test this boundary in both storage-enabled and plain modes.

## Immutable identity, bytes and mount boundary

Every proposal binds tenant/node/recovery epoch, endpoint, Node key identity,
current container/image/config, owned state-volume name/labels/metadata/consumer
set, bounded protected-state digest, exact old floors and cohort digest.
Node certificate DER hashes are distinct from PEM file byte hashes; both are
recorded under explicitly named fields and never substituted.

Exactly one contribution is supported. Contribution ID, approved source directory,
root `/contribution`, root_version, device/inode and read-only scope remain
unchanged through migration and normal renewal. A certificate change does not
justify a root_version change. Original raw JSON policy bytes are preserved for
migration; renewal makes a new exact policy differing only in approved channel
version and next leaf DER hash. Same-version policy-byte rewrites are rejected.
Root/channel hashes use current Go struct field order/encoding, not arbitrary
pretty printing; raw-policy SHA covers exact file bytes.

Allowed target mounts are exactly:

1. Owned named `/state` volume, RW, with the original identity/journal and correct
   `ai.saintvision.node` label. Initially only the exact current Node consumes it;
   during preservation migration the fenced backup plus exact replacement are
   the only allowed consumers. Candidate shadow-validation, if used, mounts it
   read-only and is individually recorded, then must be absent before apply.
2. Exact approved source bind at `/contribution`, `readonly`,
   `bind-recursive=disabled`, `bind-propagation=rprivate`; no alternate/nested/RW
   bind or arbitrary volume. Host path is private deployment input, never public
   Git evidence. All ancestors and source are opened without following symlinks;
   reject traversal, root/private overlap, changed inode and unproved namespaces.
3. Existing workspace daemon path only: host `/var/run/docker.sock` to that exact
   destination, RW/rprivate. Reject custom socket options, alternate sources,
   remote engines and hidden extra mounts. An observation-only storage Node may
   acquire this socket only through the explicit workspace preservation route.

The local mount binding carries expected opened root dev/inode, exact policy hash,
identity/contribution/root_version and required readonly/nonrecursive/rprivate
recipe. Before **any peer/storage floor write**, new Go shadow validation opens
the root descriptor, checks identity and actual read-only filesystem/mount state,
rejects descendant mounts, validates every candidate policy/cert/key, and checks
Docker's inspected NonRecursive/propagation recipe through the bound local
installation proof. Device/inode must agree across the native host/daemon/Node
namespace; otherwise refuse. Recheck the descriptor and named root before commit,
listen and each sample. Docker path substitution between host precheck and create
therefore produces a mismatched root before pins/listener/sample. Two lstat calls
alone are not a TOCTOU proof. A privileged hostile host administrator is outside
this trust model; no stronger host isolation is claimed.

Renewal preserves the existing container/mounts; it does not recreate the Node to
drop a mount. A path/mount substitution observed during renewal refuses and keeps
all state. Workload creation remains UID 65532, private tmpfs `/workspace` and
`/tmp`, network none and no Node contribution/socket binds. Neither a Node
contribution nor its sample grants workload host access or storage writeback.
Host-folder workspace persistence is a different feature.

## Fencing and lock order

One private per-Node operation fence serializes preservation, replacement,
execution-probe setup, managed/plain renewal, finalization and rollback. It binds
operation ID, exact request SHA, predecessor and active generation; it is not a
time lease. A timeout, process death or old date does not clear ownership.
Unrecognized/stale fence or `.next` artifact preserves state and refuses.

Local lock order is operation lock → current workflow lock → immutable request
directory lock → Node journal process lock. No helper takes these in reverse.
Apply holds the operation fence across commands, with OS flock for each mutation;
the exact same request can resume after a process exits. A running old Node's
journal lock is not stolen: stop the exact idle Node before acquiring journal
write authority. Read-only preflight never mutates/pins the journal. Legacy entry
points must check/refuse a managed fence before image load, stop or staging.

Root holds its batch-operation lock before per-node requests, visits Node IDs in
sorted order and performs no network I/O inside DB transactions. DB lock order:
control epoch → Node rows sorted → channel rows sorted → contribution rows sorted.
This follows common Node-first ordering and makes the entire planned cohort
stable at each transaction boundary. Current helper locks are not assumed to
provide this new cross-workflow fence automatically.

## Normal generation arithmetic

For each Node let finalized channel version be **C**, finalized peer-policy
version **P**, and contribution root version **R**. Peer versions are independent
of channel versions in B. They are not borrowed from targetChannelVersion.

| Generation | Channel / Node leaf | Peer policy | Storage policy |
|---|---|---|---|
| old finalized | C / old DER | P / exact old bytes | root R, channel C, old DER |
| next overlap | C+1 / next DER | P+1 / old+next CP pins, bounded overlap | root R, channel C+1, next DER |
| next final | same C+1 / same next DER | P+2 / next CP pin only | **exact same bytes** as overlap |
| second normal overlap | C+2 / next-next DER | P+3 | same root R, new channel/DER |
| second normal final | same C+2 | P+4 | unchanged from second overlap |

All additions check overflow before preparation; no wrap, silent coercion or
counter reset. Plain mode has the same peer/channel arithmetic, with explicitly
null storage/binding fields. Mixed cohort proposals still cover every active
member and cannot silently omit the storage member.

## Node compound transaction and acknowledgement

Separate `.peer-policy` and `.storage-<id>` files are **not atomic as a pair**.
Keep their existing no-regression/hash rules. Add an intent and active-generation
decision under the existing exclusive journal process lock, rather than claiming
two atomic renames form one transaction.

1. **Shadow validate:** validate the whole candidate tuple (current/next DER,
   key equality, CA/SAN/EKU/time, peer bytes/version, storage bytes/channel/root,
   mount binding/actual descriptor, exact old floors and private ownership/modes).
   This validation performs no pin and opens no listener. Any error preserves the
   old tuple, container and journal. Old startup order cannot be reused here.
2. **Durable intent:** fsync a closed, request-bound intent containing old decision
   hash, prior projection digest, next decision hash and exact file/binding hashes;
   fsync the journal directory. Do not expose next generation merely because files
   have been copied. Stopped-target file staging has separate durable phases.
3. **Project floors:** advance peer then active storage pins according to the exact
   intent, each with existing file-sync/rename/directory-sync semantics. Snapshot
   all untouched floors. A kill after either write may leave partial projections.
   **The first durable peer OR storage advance is irreversible**, even with no
   PID, listener or receipt. Unknown persistence is also forward-only.
4. **Commit decision:** after both projections are durably exact (or storage null
   is explicitly permitted), fsync and atomically publish the active generation
   decision and directory. It contains the full tuple and projection digest.
   Only then initialize serving using idempotent exact pins; shadow check again.
   A decision is the serving authority; projections preserve legacy anti-rollback
   behavior and are never erased, reseeded or treated as one atomic write.
5. **Acknowledge:** the actual Go startup emits a domain-separated signed local
   acknowledgement, binding request/operation, boot ID/time, observed DER,
   peer/storage/binding hashes and versions, actual root identity/readonly state,
   decision and projection digest. Signature domain is
   `saintvision/node-authority-acknowledgement/v1` plus NUL; payload uses existing
   canonical JSON rules and excludes `nodeSignature` itself. Node private key never
   leaves state. This is a new local startup receipt, **not** a changed storage
   sample wire or a successful operational StorageCheck.

Before a managed Node serves after restart, recovery requires exact intent,
candidate bytes, old-or-next projection values and next decision hash. For partial
projections, complete the **same** forward intent; do not restore old files.
Any unexpected hash/version, corrupt intent, wrong active decision or unproved
mount refuses while preserving state. A committed decision with contradictory
projection files is corruption, not permission to repair by resetting floors.
Missing acknowledgement never proves that no pin occurred.

Tools fence legacy containers and set backups restart=no; once the managed journal
has advanced they must never restart an older agent that ignores its active
decision. A binary rollback needs explicit compatibility with every durable floor
and generation schema, not just an old date-valid certificate. Host-admin manual
override is not a supported rollback path.

## Batch state machine and pin/CAS order

Proposed batch phases:
`prepared → all-preflight → installing → all-acknowledged → cas-intent → channels-committed → control-switched → finalizing → retired`.
Unknown phase/observations never map to success. Each record is request/cohort
bound, sequential and links the previous record hash; records and exact proof
bytes are durable. This is a replacement **new-schema** compound lifecycle, not a
silent interpretation of 2fb's legacy per-node `staging` CAS phase.

**All-member preflight barrier:** validate the fixed complete active cohort and
all old/next public files, immutable predecessor archives, source/image/helper
bindings, current DB channel/root snapshots, no owned workloads and all local
state/mount/floor receipts before any target stop, active file change, pin or CAS.
Acquiring reservations/writing new immutable preparation files is coordination
metadata, not target authority mutation; it grants no permission to skip this
barrier. A candidate verifier container, if needed, uses read-only state and no
server/socket, is uniquely owned and recorded, and must be absent before apply.
No preflight success from one member authorizes mutation of a different cohort.
Under durable reservations, recheck every member immediately before apply; stale
or missing member requires re-preflight of the fixed cohort. No TTL auto-release.

**Pin first, then all-channel CAS:** update and obtain exact signed overlap
acknowledgement from **every** member. Collect current-phase mTLS handshake/probe
proof against the manifest's explicit next DER; pre-CAS this is installation
verification against a proposed pin, not DB current authority. Do not issue a
current DB storage challenge or workload through that proposed channel yet.
Cross-host install is not atomic and has a controlled availability gap.

Before CAS, reread all current channels and unchanged contribution/root bindings
under one transaction and verify the full acknowledgement vector. Use existing
operator-only `provision_channel`, all Nodes in sorted order in **one outer DB
transaction**, advancing C→C+1 with immutable audits. Any conflict rolls back the
entire channel vector. Do not commit one channel per incoming acknowledgement.
No network calls occur in this transaction. Pin-before-CAS can strand installed
Nodes until forward recovery; it is chosen to avoid publishing DB authority for
an uninstalled/unpinned Node. It does not provide distributed ACID.

CAS intent is durable before the DB call. On crash after uncertain commit, inspect
the whole DB vector: exact all-old permits exact same CAS retry; exact all-next is
committed replay; mixed/foreign vector is unknown/external divergence and refuses.
No matching flag or file alone settles CAS. Local floor advance already prohibits
rollback even if the DB vector is still old.

Switch the shared CP leaf only after the atomic all-channel vector and all target
acknowledgements have been verified. Keep bounded old+next CP trust on every Node
until this barrier. After switch, verify actual current mTLS and existing fresh
signed storage challenge/atomic Evidence+StorageCheck against the **committed**
channel/root. Then finalize each member through another compound transaction:
peer P+1→P+2, storage unchanged, final acknowledgement from actual Go. No peer
same-version byte rewrite. Final/drop-old authority is a separate irreversible
barrier even if old certificates remain date-valid.

## Crash, restoration and forward recovery

| Observed state | Permitted action |
|---|---|
| Prepared/preflight error, no active change | Preserve existing running/stopped container and journal; abandon only new request through a recorded disposition |
| Files installed but **all** durable peer/storage floors demonstrably old; all channels old; no owned work; old authority valid | Under fence restore exact old cert/peer/storage/binding bytes and original container/mount/config; record restoration and retain snapshots |
| Start-intent, first projected peer/storage pin, compound decision, any channel CAS or uncertainty | Preserve all files/containers and resume the exact next generation forward; no old restoration, floor decrement, hash-ignore or timeout reset |
| Some members pinned, others old, channels old | Keep cohort fenced; finish the same reviewed next tuple on remaining members, then atomic CAS; no partial rollback or drop of a member |
| All pins exact, DB CAS response lost | Read entire vector and evidence, retry exact all-old transaction or recognize exact all-next; mixed vector refuses |
| Channels committed, CP switch file/journal inconsistent | Read actual public CP DER and exact manifest; converge same next leaf forward; never lower DB channels |
| Final peer pin or finalization/retirement interruption | Replay exact final generation and archive publication; preserve original receipt bytes and settled-predecessor rule |
| Unknown/failed rollback, changed container/root/volume consumer, corrupt floor/intent or foreign generation | Refuse, preserve state, and escalate with exact source/receipt; no cleanup or ready claim |

For a preservation migration, no authority floor advances are intended. Recovery
still checks actual floors, not that intention. Backup and replacement share the
same state volume, so backup container preservation is not a journal backup.
Automatic downgrade after ready or any new work remains refused.

**Expired/unusable next generation:** root `msg_4a1bc0c5516e` selected **BLOCKED
under separately reviewed offline recovery**. Exact-plan replay still requires
valid approved certificates. This staged contract and urgent P0 introduce no CAS
ladder, channel-trigger bypass, version jump, hash exception or floor reset.
The earlier v1.0.0 ladder proposal remains historical at fixed report 5023 and is
not the selected scope. Fresh trust/keys/epoch changes or a later recovery design
remain outside this worker's authority and require their own reviewed contract.

## Exact 2fb archives, successors and retirement

Preserve 2fb `_finalized_evidence` original manifest/commit receipt/journal bytes
and signature checks; never reconstruct `journalRaw` by dumping parsed JSON.
Preserve `_immutable` no-clobber publication and fsync behavior, including original
bytes on replay. The Node `_require_settled_archive` and CP predecessor guard must
continue rejecting predecessor `.next` residue **before** successor intent.
Only exact predecessor finalize/retire replay may retire its verified duplicate;
no new B command cleans arbitrary or stale artifacts.

New compound archives use explicit new schema envelopes with digest-bound exact
legacy predecessor bytes, original new manifest/Node acknowledgement/CP commit
receipts, compound decisions/projection digests and final storage/peer proofs.
The old signed archive is never augmented in place. CP retirement continues to
require every fixed-cohort Node's exact signed finalization proof and canonical
CP retirement publication before its terminal journal and successor validation.
Append/classifier/bundle readers need explicit new-schema handling; unsupported
readers refuse. A bare finalized/installed flag is never an archived proof.

## Required source changes after architecture acceptance

### P0 standalone plain-mode repair proposal, before broad B implementation

Root's `msg_954ac44a4513` prioritizes a native Linux real-Go proof. The opt-in early
step in the existing Core workflow runs the actual node-agent transport package,
Journal/OpenJournal/NewAuthority/TLS and exact accepted Python
`_write_rotation_public_material` outputs. It attempts both overlap/final phases
of two nominal normal cycles on one durable journal. A rejected first final means
that cycle did **not** complete; the proof attempts the next generated cycle to
show the repeated boundary, and reports actual completed count rather than
claiming two successful renewals. No mocked restart or replacement module exists.
An overlap must really start with valid future policy and matching leaf/key, then
final rejection must be specifically `NODE-0041: peer policy rollback rejected`
with unchanged durable floor; setup/expired-PKI/compile errors invalidate proof.
An additional deliberately expired higher-version fixture demonstrates the
current pin-before-expiry ordering and resulting durable floor advance.

If native CI confirms the source contradiction, the minimal plain fix is a
**separate reviewed new normal proposal schema** (e.g. normal leaf/batch `:3`,
distinct from current normal `:1` and offline `:2`) with explicit
`currentPeerPolicyVersion`, `overlapPeerPolicyVersion`, `finalPeerPolicyVersion`
and exact phase hashes. Read and bind actual current peer floor/hash under the
existing journal/operation ownership; do not infer it from channel version.
Generate overlap P+1 and final P+2 while retaining channel C+1. Update the helper's
strict phase validation, archive/attestation manifest binding and successor checks
to the independent generation fields; old readers reject the new schema before
mutation. Current Go same-version/different-hash rejection remains unchanged.

Plain rollback must verify **actual** durable floors and CP channel, permitting
exact old restoration only before any target pin/CAS; unknown or partial startup
requires exact forward replay. Validate expiry/cert/key/tuple before requesting
startup, without claiming that this changes current Go pin ordering. Preserve
2fb exact-byte proof/retirement and `.next` refusal. Obtain real-Go two-cycle
green, failure-boundary proof and actual independent review before inclusion.
This plain fix does not authorize storage migration or substitute for the B
compound transaction. No such production fix has been implemented here.

| Owner/surface | Planned work |
|---|---|
| Codex Node common contract | Canonical schema/generated readers, private binding/intent/decision/ack, shadow validation and journal recovery; preserve old floors and storage challenge |
| Codex deployment | Explicit workspace schema2/native route, strict combined mounts/argv/consumers, shared fence and crash/rollback; `worker_config` fixed file handling |
| Codex with S1 owner review | New compound leaf/batch proposal validators, independent peer versions, all-member preflight/acks, atomic batch CAS, CP switch/finalization/retirement and recovery ladder decision |
| All same-Node helpers | Storage bridge/replacement, execution-probe, startup/repair and wrappers either implement the exact contract or reject before image/state/container mutation |
| Package/manifest readers | `lan_workspace`, `lan_execution`, `lan_pilot`, offline package/readiness checks, source-hash wrappers, installers and generated archives/checksums; full dependency hash closure |
| Independent Claude via root | Architecture verdict before production edits; exact implementation/CI review before inclusion; do not count S1 design comments as that verdict |

Root's private generated campaign wrappers must bind these accepted source and
schema/helper hashes and be regenerated by root; this worker has not read private
configs, issuer, certificate files, addresses or accounts. Normal protected old
pilot/r5 state and existing 48-task/VF-CL statuses are untouched.

## Red/green and failure matrix

| ID | Required evidence before implementation acceptance |
|---|---|
| B01 | Historical source guard red retained; explicit migration green while default R4 unknown/storage guard remains green |
| B02 | Schema/semantic negatives: unknown/ambiguous flags, int/bool/overflow, duplicate JSON keys, PEM/DER confusion, altered raw bytes, stale/wrong channel/root/epoch/identity |
| B03 | Actual native Linux Docker: read succeeds/write denied, nonrecursive child mount hidden, rprivate propagation, source/root mount substitution at precheck→create seam rejected before any pin/listener/sample |
| B04 | Actual workload has neither contribution nor socket, private tmpfs/UID/network unchanged; no host writeback or fake hard disk quota claim |
| B05 | **Real Go** Journal+Authority+StorageSampler normal storage-enabled cycle through overlap, CAS, CP switch, final; exact signed receipt and current signed storage challenge commit |
| B06 | Two complete NORMAL cycles with **plain, storage-enabled and mixed cohort**, independent peer P→P+4 and channel C→C+2; original root R/dev/inode/policy semantics stable |
| B07 | Kill after every active-file write, intent fsync, each individual floor write, active decision, ack publication and restart before listener; exact forward replay and no silent sampler omission |
| B08 | Concurrent workspace/storage/probe/renewal/finalization, stale fence, extra volume consumers, changed inode and mount namespace; refuse without journal loss or success flag |
| B09 | Missing/stale one-member preflight, partial local install, CAS conflict, kill before/after DB commit and CP switch; all-old/all-next/mixed vector reconciliation and no subset CAS |
| B10 | Exact old restoration only with all-old floors/channels and valid unchanged root/work; first peer pin alone or unknown forbids it; no decrement/reseed/reset/older binary |
| B11 | Final/drop-old barrier, second successor, exact original-byte archives, canonical CP retirement, verified signed finalization, `.next` residue exact replay and unrelated residue rejection |
| B12 | Expired-partial refusal under separate offline-recovery ownership; actual no-ladder/no-trigger-bypass/no-version-jump/no-reset negatives |
| B13 | Existing storage signed wire: current mTLS DER, nonce/expiry/catalog/root/channel checks, tamper/replay/channel mismatch refusal and atomic Evidence/StorageCheck with authenticated readback |
| B14 | Hosted exact-SHA Linux CI plus actual architecture/code reviews, then separate root-authorized physical all-five storage/execution and ADR-100 four-independent-worker S05/S07 |

Current schema/model fixture checks exercise proposal consistency only; none is
a substitute for B03/B05–B14. No host Docker, WSL, SSH, PKI, enrollment, workload,
resource policy, privileged action or physical-PC operation occurred here.
Resource policy proposals remain distinct from measured/enforced quotas.

## Publication and next owner

### Actual P0 native Linux proof and publication, 19:56 KST

Proof/contract merge publication **`fe7ebeff1f695e0744a7f25eace52c7321dcc1d7`**
normally inherits accepted 2fb and retains the combined DB preparation/current
lan-pilot tooling bindings. No new production lifecycle fix was authored. The
sole merge conflict was those two metadata pairs; both actual SHA256/Git-blob
pairs were verified after resolution. Shared boards and task/VF-CL statuses are
unchanged. Local CPython 3.14.7 main-repo interpreter was used with `-B`, at the
exact path stated in `publication-stage-v1.json`; no local fixture PKI was run.

- Hosted Docs **42014765588**, head fe7ebeff, **SUCCESS**, including bundle build.
- Hosted Core **42014770700**, same head, **FAILURE intentionally retained**.
  The early native Go proof exited **1**, validated as an actual baseline mismatch.
  The proof artifact upload succeeded; expensive main Core suite did not run.
  The existing separate S01-storage-roundtrip job succeeded; this is not eight
  canonical jobs passing. Workflow job names/counts and ordinary gates are intact.
- Actual Linux OpenJournal/NewAuthority/TLS accepted initial peer version 7 and
  generated overlap versions 8 and 9. Both generated final files had the same
  respective version but different raw hash, and failed specifically with
  `NODE-0041: peer policy rollback rejected`; each durable floor stayed at its
  accepted overlap hash. **Two cycles attempted, zero complete normal cycles**.
- The separate expired-after-pin negative at version 10 failed with
  `NODE-0041: peer policy expired or unbounded`, yet durable floor 10 and its exact
  raw hash persisted. This directly confirms that failed startup is not a
  rollback permission or proof of unchanged journal state.
- Exact Go/runtime/helper source bytes were checked against accepted 2fb before
  execution. No GOOS, lock, mode or floor bypass; no mocked restart, replacement
  runtime or alternative module. Fixture-only keys stayed in an owned CI temporary
  directory and were not uploaded.
- Artifact **13409265588**, name `fleet5-native-peer-phase-proof-fe7ebeff1f695e0744a7f25eace52c7321dcc1d7`.
  Downloaded ZIP SHA256 **dc273e5069aca4d62d0a22cb2736ff745fdd98a75ba3c72d687439e7e86e9901**
  matches GitHub's artifact digest. Its exactly three members match extracted
  bytes: `go-events.jsonl`, `native-go-result.json`, `publication-receipt.json`.
  Source, head, runtime platform, exit and exact rejection cause were verified.

The authoritative local receipt is
`docs/vault/30_Development/Evidence/fleet5-compute-storage-contract-20261105-codex/hosted-proof-receipt.json`;
the raw ZIP and members are preserved beside it. The actual result elevates the
plain-phase problem from source observation to a reproduced native journal
failure, while remaining fixture evidence rather than live equipment acceptance.
The minimal standalone plain repair above is now the recommended first production
change **after** root's actual independent contract/source review.

The initial docs gate exit 1 is retained. Root explicitly authorized restoring
only the exact missing Low-closure History and its Evidence from
`d254fc6a511db108be351a3ba82645341748fea3`. Both were restored byte-for-byte and
verified with `git hash-object --no-filters`; their original wording is unchanged.
Receipt `scoped-dependency-restoration.json` binds source blobs and actual hashes.
No shared-board edit, broad old-document merge or Obsidian apply is authorized.

The bounded P0 field/ownership/failed-start/fault addendum is
[[2026-11-05_FLEET5_P0_plain_peer_phase_contract_detail_Codex]]. Root has actually
requested Claude review of fixed 5023 and has blocked expired-partial ladder work.
This stage awaits **actual P0 architecture review**. It does not send worker_done or authorize production
implementation. Next owner root/S1/Claude: assess tuple transaction, floor/CAS
ordering, plain compatibility, independent peer phases, recovery and exact archive
extension. Next Codex action follows the concrete review verdict in this branch.
