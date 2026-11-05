---
doc_id: "HIST-FLEET5-B-CONTRACT-REV2-001"
title: "FLEET5 B-FRESH1 contract revision 2 and B-MIG1 design boundary"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Actual independent Claude revision review via Root pending"
updated: "2026-11-06T03:45:16+09:00"
source_of_truth: "Git"
---

# Scope and decision gate

This is a DOCS/schema/fixture proposal. It implements no B runtime, database,
installer, ADR or device change. Owner Codex, task
`FLEET5-COMPUTE-STORAGE-CONTRACT-20261105`, Orca
`task_a8fd2969f0b3 / ctx_6f0f8253b8a7`, branch
`agent/codex/fleet5-b-contract-rev2-20261106`. The exact source and branch base is
`72028cbac903c4415d9979f980a6e0f9948e914f`, Root's accepted combined candidate;
Root reports all 8/12 checks SUCCESS and source/packet ACCEPT. Those are baseline
results, not B results. The optional Low test patch `f0af3077` is excluded from
72028 and this proposal. The original proposal `100f6f132132199d1204a76190f04712dd82de00`
and its expected red remain immutable. Actual independent review
`2bb959a3365c2b59c8818ed746480c9183b4c0fc` required revision; it was not acceptance.

Root decision `msg_fa19f6e8d717` selected B-FRESH1 plus B-MIG1 DESIGN-FIRST and
authorized only this revised proposal. Implementation/ADR/registry/NodeOps wait
for actual revision review and Root's subsequent concrete authorization. Root
will own frozen ADR/registry registration. Codex would own hard ABI, runtime,
CP/CAS and concurrency; a different Claude agent must review actual code.

Latest Root-vault first read: INDEX-PROGRESS-001 **1.0.415** and
WORKBOARD-CODEX-001 **1.0.376**, updated `2026-11-06T03:03:02+09:00`; exact bytes
and the canonical first-read/skill versions are recorded in `revision-record.json`
and the preserved initial source inventory. Skills agent-delivery 1.1.0 and
core-reliability 1.0.0 apply. No shared board, registry, ADR, source original or
Obsidian apply is edited. Existing 48/VFCL statuses remain unchanged.

All real Node/context IDs, paths, addresses, endpoints, image/executable hashes,
leases, deployment/archive bindings and physical acceptance are **NULL/HOLD**.
No guest/context is asserted to exist. Physical PC2/PC4 old pilot Nodes and their
identities remain untouched and distinct from the uninitialized new five-Node
fleet. No remote, Docker, WSL, enrollment, key, install or workload action is run.

# Existing contract and missing semantics

The exact 46-surface inventory and line anchors are rehashed against **72028** in
`source-inventory-72028.json`; no older Root checkout is used as runtime proof.

| Source | Existing supported behavior | Required explicit B contract |
|---|---|---|
| `deploy/lan/worker_workspace.py:70` | R4 refuses storage arguments and extra mounts | Default stays closed; separate exact opt-in role, never generic mount copying |
| `deploy/lan/worker_storage.py:163,178` | State plus one RO/nonrecursive/rprivate contribution, no socket | New role verifies exactly state, default socket, one contribution |
| `deploy/lan/worker_storage_bridge.py:19`, `worker_replace.py`, `worker_config.py` | Existing profiles and exact configuration ownership | New role-specific request/receipt/schema, wrapper and manifest bindings |
| `services/node-agent/cmd/inv-node/main.go:104,115` | Authority pins P before storage validates/pins; sampler and runner can coexist | Pure dual prevalidation, explicit partial pin phase and role observation |
| `services/node-agent/runtime/peer_floor_linux.go`, `deploy/lan/peer_policy_phase.py` | Plain floor :2 and leaf :3 explicitly reject contribution role | New floor :3 / leaf :4, no schema fallback or plain :2 claim |
| `services/node-agent/transport/storage.go:44,46,48` | Policy binds Node DER; channel hash is Go struct JSON; pins exact policy bytes | Leaf B requires same shared C+1 and exact authorized policy B |
| `services/node-agent/runtime/storage_policy.go:38` | Same-C changed hash and backward C/R rejected; old floors retained | Preserve this; no R bump, reset or floor deletion bypass |
| `packages/contracts-go/contracts.go:1349,1388` | Six-field storage ChannelProof is the execution channel | No independent storage channel/table/counter |
| `services/control-plane/src/inv/node_channels.py:104,151,205` | Current-row channel check, provision and revoke both increment C | B admission/fence and consistent writer lock order; revoke invalidates planned B |
| `services/node-agent/runtime/docker.go:256` | Checks Binds, Devices, ports and workload isolation | Also close HostConfig.Mounts, VolumesFrom and top-level Mounts (review L1) |

Preparing a folder, a storage startup receipt, or a healthy execution Node is not
active contributed-storage acceptance. Existing sampling v1 verifies signed
bounded observations; it neither mounts contribution into workloads nor grants
writeback, durable capacity, replication or a disk quota.

# Closed role, manifest and deployment boundary

Proposed manifest version 4 explicitly selects `workspace-storage-ro-v1` with
existing execution profile `lan-workspace-v1`, role floor
`saintvision-node-peer-policy-floor:3` and new normal/batch leaf contract 4.
Plain manifest/profile/floor :2/leaf :3 remain externally unchanged. Role schemas
have closed fields and one exact spelling. Unknown fields/role/version, aliases,
single-dash flags, equal-form flags, duplicate options, mixed versions, stale or
tampered policies and channel mismatch reject before mutation. New generated
JSON/TS/Go schemas, bundle hash inventory and every consumer must agree; manifest
version alone cannot authorize a role. No fallback from a rejected B role to plain.

The proposed schema's manifest record is the closed **role-binding section**, not
the entire existing bundle manifest. `baseServingArgvSha256` binds the inherited
full serving arguments; `roleArguments` fixes their ordered role-critical projection
spelling (`--socket`, source main.go:45), including the new explicit
`--role-config /state/node-role.json`. This new protected file binds role,
context, operator release-verification public-key digest, generation policy and
operation schema. Its exact bytes/hash enter the manifest, signed intent and
actual raw-argv/config observation. It requires a new strict parser/contract;
an absent/unknown role config never silently enters B. No new arbitrary mount
is needed for public verification material. Complete product schemas and
cross-language signature/envelope vectors remain required implementation work.
Every option in the full argv appears exactly once; the projection is not an
argument list to append to an already complete argv. Existing storage policy
path remains `/state/storage-policy.json`.

The Node has exactly three approved mounts: the existing owned **RW state
volume**, the existing **RW** `/var/run/docker.sock` at that exact default path,
and the approved
contribution at `/contribution` with RO, nonrecursive and rprivate enforcement.
No arbitrary socket, DOCKER_HOST override, extra bind, RW contribution, mount
substitution, symlink component or unapproved volume consumer is allowed. State
keeps existing volume owner/identity, exclusive process lock and single live Node
consumer. Contribution never resides under state, credentials or an installer
temporary directory. Policy bytes reside in the protected state configuration;
the contribution source and R are immutable throughout a leaf cycle.

Host preflight opens source/ancestors without following links, verifies approved
containment and all ownership/mode/filesystem identities, and keeps descriptors
while comparing the path before create, after create, before start and after
signed observation. Node pins its opened root descriptor and rechecks path/FD
identity before and after sampling. Device/inode reuse alone is insufficient:
context boot/daemon/mount/source identity and the approved serving generation
must also match. Mutation, rename, mount replacement or inability to revalidate
is UNKNOWN/BLOCK. Real Linux adversarial race tests are mandatory; schema
fixtures do not establish TOCTOU resistance.

Workload containers retain their existing isolated execution contract: no Node
state/socket/contribution/host bind, no storage writeback and no automatic path
access from contribution registration. B must inspect **all** of Binds, Devices,
HostConfig.Mounts, VolumesFrom, top-level Mounts and ports; each unauthorized
surface must be absent/empty, including a malicious inspection reply. A workload
needing storage in a future feature needs a separately approved data-delivery
contract. Resource proposals (reservation, headroom, scheduling weights) are
separate from existing per-workload cgroup limits; this proposal promises no
aggregate CPU/RAM or contributed-disk hard quota.

The Node's Docker socket gives the trusted Node process guest-host root power.
The readonly contribution is a workload boundary and accident/race guard; it is
not protection against a compromised Node image, guest kernel, daemon or host
root. No signed receipt can remove that trust assumption.

# D1 / B1: homogeneous five and the CP Linux execution context

Fresh B requires **five** combined-role Nodes: four independent Linux workers
and a fifth in the CP physical failure domain. ADR100 independent S05/S07 counts
remain four; a CP VM/guest does not create a fifth independent physical domain.
Plain PC5 is not an allowed fallback. If any context cannot satisfy this contract,
the entire fresh five-member cohort remains BLOCK/HOLD.

Only native Linux daemon filesystems are eligible. The CP physical Windows
machine needs a separately provisioned, dedicated Linux VM or WSL2 ext4 guest
with its **own supported Linux Docker Engine**, default socket and Linux-native
contribution. CP role tooling runs in that exact guest. Windows Desktop engines,
DrvFs, 9P, host-drive remaps, `/run/desktop/mnt/host`, uncertain translations,
network/removable filesystems and an inherited default WSL distro are rejected.
This is a design/provisioning prerequisite, not authorization to install or an
assertion of readiness. The old Desktop/r5 containers and the recorded physical
API1.41 blocker are unchanged.

The proposed `executionContext` record binds an opaque approved physical-domain
reference, context kind/identity, guest machine-ID hash and boot ID, daemon ID,
default-socket identity, fixed launcher/probe artifact digests, approved source
containment and endpoint. The role validator requires Linux, negotiated API1.45
for B plus an actual capability probe, ext4/xfs/btrfs source, no-link parents and
root, approved UID/mode, dev/inode/fs and mount metadata. This stricter B proposal
does not change the plain client's API negotiation. Filesystem names alone do
not prove native containment: measured mount ancestry must exclude every host
drive/network/remap ancestor. Unsupported/unknown values block.

The launcher adapter is selected by an approved context ID, explicit guest/VM or
distro identity and execution UID. It invokes a fixed reviewed Linux probe via
a bounded stdin/stdout protocol; no user shell, ambient environment, default
distro, path interpolation or Windows-to-Linux path conversion. Adapter and
probe hashes are frozen before provisioning. It reports actual guest/daemon/
socket/source/Engine/API/endpoint measurements. The operator checks host-side
Docker inspection source-to-root correspondence independently of Node echoes;
the Node signs its actual root descriptor, serving PID/UID/start time/raw argv,
executable bytes, namespace and floor state. Host dev/inode/fs in that SAME
guest kernel must correspond to the Node root. Mount IDs and namespace IDs are
recorded with their namespace, **never compared for equality across namespaces**.
Guest boot/daemon changes invalidate admission. An absent adapter, mismatched
guest daemon, unsupported Engine/API, unreachable mTLS endpoint or unmeasured
source is BLOCK. Provisioning requires a concrete separate reviewed plan before
execution; no private physical binding is copied into this public evidence.

# D2 / B2: persistence, authority and admission

`persistence-abi.json` proposes a new role-attestation ABI, not a second channel.
`inv.node_role_admissions` is immutable signed evidence, keyed by admission ID,
with a uniqueness tuple `(operation,node,serving-generation,nonce)`. It binds
tenant/Node/epoch, **shared C**, contribution/R, DER and exact policy hash, image,
actual executable/config/raw-argv hashes, serving CID/PID/UID/start/boot/nonce,
context and root identity, actual peer/storage floor hashes, observation and
expiry, nonce/proof, immutable approval/operation references. A guarded current
pointer selects the latest independently verified incarnation; history cannot
be adopted as current. There is no independently mutable `success` flag.

Durable cohort/operation, immutable member/target, approval/grant and member-CAS
ledger records accompany admissions. Operation/member targets and policy A/B
bytes are frozen by authorized operator planning. A member CAS ledger is written
in the **same CP transaction** as that member's channel CAS; a matching tuple
without its matching ledger is never inferred to be this operation's success.
Cohort state/fence and current-pointer changes are guarded transitions, not
runtime-authored attestations. `inv_kernel` may read/lock these records and use
existing business-authorized APIs; it cannot INSERT/UPDATE/DELETE admissions,
assignments, grants, targets or fences. Any required lock-sentinel privilege is
constant-only and cannot change authority fields. A runtime connection/GUC,
HTTP request, Node's own signing key or arbitrary operator SQL is not a grant.

An operator principal with a scoped provisioning grant invokes guarded writers;
the grant binds operation, five exact members, role/context, expected current
rows, target hashes, expiry and reviewer-approved operation reference. Dedicated
operator attestation credentials validate Node-signed observations and independent
host measurements. They may refresh a still-approved SAME generation/tuple
within its lease, never invent a new image/root/generation/C/R or restore a
revoked grant. Database owner, operator signer and guest root remain trusted.
Proposed new migrations/GRANTs/functions are design-only and require actual
PostgreSQL permission/concurrency tests before inclusion.

Effective eligibility is computed under locks from current control epoch, Node
status/heartbeat, public Node and contribution ownership/status/R, shared channel
enabled/C/DER/endpoint/certificate expiry, current approved assignment, current
serving generation/context/image/executable/config/root/policy/floor hashes,
fresh one-use nonce/proof, approval/grant revocation/expiry and a released,
stable all-five cohort. Missing/stale/mismatched/currently fenced means UNKNOWN
and deny. Observation-only snapshots, startup receipts, capacity rows and old
admission history cannot substitute. Refresh failure never falls back to an older
admission. All business authorization is rechecked after a network reply and
before committing evidence/resources.

Serving generation includes boot ID, actual PID start ticks and a random process
nonce signed by the Node; restart cannot reuse an old generation grant. A new
typed role-use authorization envelope binds the frozen cohort release, current
admission/generation, shared channel, purpose, request nonce/hash and bounded
expiry. It accompanies existing transport authorization; it changes neither
the storage-sample-v1 body/domain nor kernel permit semantics. Only the operator
release authority can authorize a new generation/cohort; runtime cannot mint
such a release. Node business endpoints validate this envelope against their
actual role/generation and reject plain/diagnostic proofs for B requests. CP
checks current rows and one-use nonce again at commit. This closes the restart
gap between a CP cached observation and a different serving process. The ABI
addition requires generated contracts and actual Node/CP tests; it is not
implemented by the fixtures. Node-side release expiry is at most 120 seconds;
distributed revocation has bounded propagation, not instantaneous cross-machine
atomicity. CP current-row joins deny a revoked channel immediately at commit.

This generation closure adds a **new Node wire ABI**, beyond a CP schema change.
Proposed `X-Inv-Node-Role-Use` carries exactly one bounded signed role-use
envelope; duplicate headers, unknown/ambiguous framing and oversized/noncanonical
payloads reject. Its domain is `saintvision/node-role-use/v1` plus NUL and its
header value is exactly `v1.<unpadded-base64url-canonical-payload>.<lowercase-hex-Ed25519-signature>`
with a 65536-byte total token limit. Decode/re-encode equality, unique JSON keys,
canonical body equality and actual signature verification are required in
addition to the schema's token-shape check. Its
payload uses the same explicitly specified C2 canonical rules. It binds exact
POST path, body SHA256, purpose, current ChannelProof, release/admission/config,
serving generation, nonce and <=120-second expiry. Node consumes the nonce in
its existing identity/epoch-bound journal; a retry may recover only the same
recorded request/result under existing permit idempotency, never start a second
execution. The operator attestor independently checks current release/rows when
issuing it. Diagnostics/cancel/quarantine use their separate typed safety
authorization and never obtain a business envelope. Placement/storage issue/
commit are CP-only purposes; if they need a Node RPC, its endpoint-specific
purpose must match (TRANSFER for object read, TERMINAL for frame,
STORAGE_COLLECT for sample, EXECUTION or MODEL for execution). A closed
purpose/path matrix rejects all other combinations. This interface is proposed,
not present in source 72028, and needs Root's explicit contract freeze after
independent review. It cannot be silently delegated as ordinary CRUD.

The all-five stable snapshot is required at activation and throughout an active
fenced operation. After S9 release, current eligibility checks the selected
business Nodes and their current rows against the immutable cohort release;
an unrelated offline worker does not invalidate healthy selected workers.
Missing/changed generation or expired admission denies that Node. It cannot
reuse an old grant after restart. A new operation affecting cohort authority
again globally fences all five. Readmission of a changed generation requires a
new explicit operator-bound observation/release transition; it is never inferred
from a heartbeat. This preserves the four independent-worker S05/S07 failure
domain intent; a fifth CP guest is still excluded from those counts.

The closed purpose enum separates placement/execution/transfer/terminal/model/
storage issue/collect/commit from diagnostics and containment stop. Diagnostic
reads and narrowly typed safety kills can operate while fenced; they cannot
reserve resources, dispatch work, sample storage as accepted evidence or mint a
business proof. Every actual channel reader/writer and transitive caller is
classified in `caller-lock-graph.json`; `observation_only=True` is **not** a
business exemption. Unknown/new callers fail the inventory gate until classified.

Admissions bind a reserved `plannedReleaseId` before activation; they do not
foreign-key an already existing release. The activation transaction creates the
immutable release from those final admissions, and effective eligibility then
joins the matching planned ID and member evidence. This avoids circular FK or
premature-release authority. The operator attestor is an unattended, narrowly
granted service within the approved operation; no repeated human approval is
required for same-tuple proof refresh. It cannot authorize a changed tuple.

# Policy A/B and signed storage observations (L3/L4)

P remains an independent peer-policy version up to 9007199254740991. B shared C
and contribution R remain 1..2147483647 because current Python sampling v1 has
that effective bound; a renewal needs C <= 2147483646 and P <= max-2. No separate
storage C exists. Leaf renewal preserves tenant/Node identity, signing key,
endpoint, epoch, contribution ID/R and root identity, while Node DER A becomes
DER B and the **same shared channel increments exactly once** C to C+1. A fresh
role install keeps its approved identity/DER/C/epoch; changing role is not a leaf
renewal. New image/config/role is bound to a separate explicit operation.

Authorized operator planning freezes the exact current ChannelProof/A and exact
target C+1/B DER. It deterministically renders policy B from that target and the
unchanged contribution/R/root, using the existing closed root-config fields;
the signed intent and operator approval bind raw policy A and B bytes/hashes.
Runtime only verifies those bytes and cannot generate or silently repair policy.
Original A bytes are archived exactly. JSON reformatting is not byte preservation.
The storage channel hash is **Go json.Marshal(NodeStorageChannel struct)** in
field order tenant_id,node_id,recovery_epoch,version,endpoint,certificate_sha256
with Go escaping/no final newline; it is not P0's sorted-map C2 encoding. Policy
hash uses original file bytes; role signed canonicalization gets separate
cross-language Unicode vectors. No common serializer assumption is safe.

The new role floor :3 uses domain `saintvision/node-peer-policy-floor/v3` plus a
terminal NUL, a closed canonical payload and a detached Ed25519 signature. Its
canonical JSON follows P0 C2's Go sorted-map/HTML/U+2028/U+2029 escaping with no
body newline, while the outer receipt keeps its own established framing. It
binds actual PID/UID/start/boot/raw argv (including terminal NUL), executable
descriptor bytes, opened contribution root and current peer/storage floors.
Configured channel/context hashes are identified as configuration claims;
independent host proofs establish daemon/source correspondence. No unsigned
host-provided value is relabeled a measured Node fact. Unknown fields, duplicate
keys, overlong tokens and noncanonical bodies reject. Full real Go/Python
signature and Unicode vectors are still pending implementation.

Revoke also advances shared C and disables it. A revoke/C jump/epoch change,
different target tuple or expired approval invalidates the old intent and policy
B and retains cohort quarantine. Runtime never regenerates B, skips a C, bumps R
to bypass a pin, resets P/C/R or adopts a new grant. A new reviewed operator
intent is required for any changed authority tuple. Same Ed25519 key across
DERs is expected, so rejection of old challenges depends on exact current C,
DER/channel hash, nonce, expiry and CP row recheck, not key separation. Old signed
envelopes may remain cryptographically valid and still be unauthorized.

Storage collection retains existing v1 scope, nonce, clock/expiry, exact
certificate DER, relative-path/openat no-link checks, bounded reads and signed
observation verification. Role admission and current shared channel gate issue,
collect and commit. Actual storage observation and coverage/mismatch/unsampled
results stay distinct from installation/admission and operational acceptance.
No response upgrades a startup receipt to a successful storage check.

# D3 / B3: pure prevalidation and explicit two-pin startup

Preserve P-first then storage-pin order, but validate **both** complete configs,
peer policy, DER chain/key/scope, future NotBefore/expiry, exact policy B, expected
current/target floors, source FD/context and operation before **any journal
creation or pin write** on the role path. Existing pure readers cannot open a
write-producing journal as prevalidation. Trusted CP/operator clock is used;
proposed skew budget is 30 seconds, B NotBefore <= now-30 and expiry >= now+630
for a 600-second operation budget. Clock uncertainty, expiry during operation or
insufficient validity rejects; no host-clock mutation or backdating workaround.
Revalidate at each destructive transition and before activation.

Then open/own the expected state volume and pin P+1, fsync; pin storage C+1,
fsync; only then expose a business-gated listener and role observation. Two files
are not atomic. **S4a = (P+1, storage C)** is an explicit quarantined crash state.
Only the identical approved operation, full recorded B config/policy and target
tuple can replay monotonically to (P+1,C+1,B). A crash after the second pin can
replay that same tuple. Half-copy, changed/unknown files, before-copy and generic
`restarted` remain BLOCK. No original config start, old leaf restore, P decrement,
storage-floor erase or rollback to A after a pin. After forward completion the
final peer P+2 uses the same B policy and storage C+1.

Only the exact current contribution's storage floor can authorize admission.
Historical `.storage-<id>` floors are preserved byte-for-byte; each extra must
match an explicitly approved immutable archive floor/hash and recorded retired
identity, or startup blocks. No deletion, automatic selection/adoption or
"all floors are active" rule. Unknown temporary/floor/.next markers block. A
fresh empty journal has separately approved absence; no legacy journal is
inferred to be fresh (L2).

# D4 / B4: cohort phases, failure, replay and activation

`phase-table.json` closes the P/C/R/DER/pin/fence/admission tuple for each phase.
The global durable intent and all-five fence commit **before the first live
file exposure, Docker create/copy/start, pin or channel CAS**. Once that intent
exists, unchanged members, already-CAS members and members still at A are all
quarantined. A fresh cohort has no workload admission at provisional A; it must
complete the coherent B cycle before first release. Per-member CAS is not an
atomic five-member transaction.

Before exposure, the fence also blocks issuance of new business role grants.
Existing bounded grants must expire (including the trusted skew allowance), and
all five must provide fresh quiescence evidence: no execution/transfer/terminal/
sampling in flight, no active resource lease and no second state consumer.
Unreachable or nonquiescent members block exposure; a CP fence alone does not
stop an already dispatched request. A typed diagnostic/safety stop may assist
only under its existing authority, followed by actual quiescence proof. No
file/copy/start/pin/CAS transition can race a still-valid old business grant.

| Phase | Peer/storage floor | CP shared channel / Node DER | Admission |
|---|---|---|---|
| S0 pre-intent | P / C | C / A | Only a previously released approved cohort; fresh none |
| S1 pure preflight | unchanged | unchanged | No new permission; failure preserves current container/journal |
| S2 fenced intent | P / C | C / A | All five deny |
| S3 file/install transition | P/C or incomplete copy | C/A or staged B | All deny; incomplete/unknown block |
| S4a first pin | P+1 / C | C / B | All deny; exact frozen replay only |
| S4b both pins | P+1 / C+1 | C / B | All deny |
| S5 staging k of five | each P or P+1 / C or C+1 | k at C+1/B, rest C/A; R unchanged | All deny, including CAS-complete members |
| S5 staged | all P+1 / C+1 | all C+1/B; CP client may still A | All deny |
| S6 switching/switched | all P+1 / C+1 | C+1/B; CP actual client switch verified | All deny |
| S7 final observations | per member P+1 or P+2 / C+1 | C+1/B | All deny until all five final |
| S8 activation transaction | all P+2 / C+1 | all C+1/B, exact R/root/policy B | Stable all-current recheck; release evidence created atomically in CP |
| S9 released | all final and fresh | exact current tuple | Computed current admission only; mismatch/expiry/fence denies |
| abort/lost/unknown | last committed monotonic tuple | no assumed write success | Fence retained, exact forward recovery or BLOCK |

Before CP switch, stage/staged/switched all retain quarantine. CP client switch
needs evidence of the **actual** B client used by every registered business
adapter, with nonce-bound Node witnesses of the TLS client DER, not just files
on disk. Final P+2 rejects old CP A. All five final role observations, member CAS
ledgers, exact DER B/C+1/R/policy B, host/context proofs and actual CP switch
evidence must be fresh and stable before activation. Network measurements occur
outside DB transactions; commit locks/rechecks the exact immutable evidence and
all current rows. Fence release creates an immutable all-five release record;
eligibility is still computed, never an unqualified active boolean. This is a CP
transaction boundary, not an Engine/filesystem/network atomic transaction.

For a lost member-CAS response: end the failed/unknown transaction, open a new
ordered transaction and read both committed channel tuple and operation ledger.
Old expected tuple + absent ledger permits exact CAS retry; exact target + exact
matching ledger permits idempotent replay. Any other combination is UNKNOWN/
BLOCK. A target tuple alone, timeout, deadlock or partial batch is not success.
Abort retains the global fence and intent. There is no per-member readmission,
automatic cancellation, old container restore or policy regeneration. Failed
pure preflight does not create intent or alter container/journal. Once fenced,
failures preserve the current container/journal and durable intent for exact
forward recovery; cleanup is a separate reviewed operation.

# D5 / B5: lock graph and all callers

Every B-touching transaction uses this order, with stable ascending IDs inside
each class: (1) operation/cohort fence and membership-routing guard rows;
(1b) `inv.control_epoch` under the already acquired fences; (2) `inv.nodes`;
(3) `public.nodes` status rows, then
`public.storage_contributions`; (4) `inv.node_channels`; (5) assignment/current
admission rows; (6) ordered business rows (run, approval/grant, resource/claim,
transfer/model/terminal); (7) nonce, immutable evidence, member-CAS ledger and
audit rows. The ABI graph fixes the suborder. No outer channel or run lock may
precede this prefix. In particular `_channel_row(lock=True)` cannot wrap
`provision_channel` for B, and storage `_scope`/receipt paths cannot take a run
lock first. Every mutator reaching B must use the canonical gate or **REFUSE B**.

Callers first read nonauthoritative hints to discover the full Node/cohort set,
end that transaction, then lock routing guards/fences and the full sorted set
before any business lock. Recheck membership/hints and business predicates under
those locks. A changed set aborts and replans in a new transaction; do not add a
new Node/cohort lock after later locks. Routing guard rows cover plain and B
Nodes so an observed-plain path cannot race role assignment; generic paths
lock/recheck the guard before deciding plain vs B. Fresh cohort membership is
immutable; B-MIG1 registration is prohibited. Epoch/global writers lock all
affected fences before the sorted rows or refuse when B exists.

The outer `Database.transaction` epoch check must therefore have a new B-aware
entry that acquires the routing/fence prefix first; wrapping its existing epoch
lock around a later fence is forbidden. Generic outer transactions without this
prefix refuse B. The shared epoch read is rechecked after fences and before
Nodes, and an epoch writer takes every affected fence first or refuses B.

Provision/revoke/renewal, enrollment/epoch/recovery, Node status/quarantine,
contribution CRUD, storage issue/collect/commit, model delivery, transfer,
terminal, resource reservations and all reachable CLI/wrapper/direct SQL writers
are included. Public ORM contribution/node changes must call the guarded writer
or refuse B, including path/owner/version/status mutations. Database privileges
and B-aware guarded functions/triggers prevent a direct generic writer from
bypassing the gate; an untrusted session variable is insufficient. Plain APIs
retain their visible contract, but internal routing/lock acquisition may change.
The exact implementation migration cannot land until the writer/permission
matrix is reviewed. Diagnostics and safety kills are typed exemptions from
eligibility, not exemptions from lock order when writing Node/channel state.

Proposed per-transaction lock_timeout=2s and statement_timeout=5s bound lock
waits. Deadlock 40P01, serialization 40001, lock timeout 55P03 or transport loss
roll back the entire transaction and preserve the already committed operation/
quarantine. A bounded retry starts a **new** transaction, rereads tuple plus
ledger, and follows the exact frozen operation; no inferred CAS, version reset,
skipped member or silent reauthorization. Actual PostgreSQL concurrent writer,
deadlock-victim, abort and commit-with-lost-response tests are mandatory. The
source lock graph and predicate fixtures are not evidence those races passed.

# D6: file ownership, rollout, rollback and B-MIG1

`source-inventory-72028.json` covers all 46 original helper/wrapper/generated
binding surfaces. Coordinated new work also reaches all rows of the caller
census: Node transport/generation/role observation/startup, generated contracts,
manifest producer/validators, Linux launch adapters, storage/workspace installers,
normal/batch renewal, guards/finalization, CP migrations/permissions/gates/CAS,
placement/resource/terminal/model/transfer/storage callers and readiness tools.
Codex owns hard contracts, runtime and concurrency; Root may assign exact
nonoverlapping manifest/CRUD/fixture files only after freezing the contract.
Each file has one owner and an actual different-agent reviewer.

Rollout is design -> independent revision review -> Root ADR/registry freeze ->
schema/ABI implementation with default R4 unchanged -> red/green per layer ->
real Go/PG/Linux Docker CI -> exact combined candidate full CI and independent
code review -> separate reviewed private provisioning plan -> authorized new
five-member context preparation/admission/storage+execution acceptance. An old
plain candidate can remain running while B preflight fails. It is not promoted
to B or counted as contributed storage. Missing CP Linux context blocks fresh B.

Rollback before intent is no-op, preserving original bytes/container/journal.
After intent/pin/CAS, automatic rollback to old credentials/config/container is
forbidden; preserve state and quarantine and resume only the exact recorded
forward operation. A code rollback unable to interpret the new role/floors must
refuse, not start plain against B state. Operator recovery needs separately
reviewed evidence and authority; no reset/migration exception is implied.

B-MIG1 remains a separate **design-first** contract for any legacy/plain or
settled-P0 predecessor. It requires a common global fence, exact predecessor
identity/profile/source/policy/volume/consumer/floor inventory, frozen cohort
membership, separate role/config/image lease and truthful predecessor evidence.
Only a new proof can authorize conversion. Existing plain SF1/RS1 remain exact
plain-only contracts; no broadening, generic restart, arbitrary retained mount,
in-flight conversion or old active pilot identity adoption. This revision
implements no migration and admits no legacy member.

# Proof and acceptance ledger

`review-resolution.json` maps B1-B5/L1-L4 to this contract and the A1-A16 matrix.
Schema/negative fixtures run only against synthetic values. The unchanged-source
gap probe is rerun on 72028: default structural proof expects exit 0;
`--require-coexistence` expects exit 1 from the preserved R4 guard. That expected
red is evidence of the real gap, not a failed worker task. Exact commands,
exits, environment, hashes and document gates are in the evidence directory.

New B real Go, actual PostgreSQL, Linux Docker enforcement, crash/rollback and
physical five-PC evidence counts are **zero**. Future required tests include
two complete shared-C/DER renewal cycles, S4a crash after each pin, every partial
CAS/batch/switch state, malformed/extra floors, same-key stale challenge denial,
all caller gates, lost replies and concurrent provision/revoke/commit, Docker
RO write failure/nonrecursive/rprivate/source substitution, malicious workload
Mounts/VolumesFrom and no second state consumer. No mock-only pass can close
those rows. P0 evidence and Root's 72028 CI remain separately attributed.

Local verification uses main-repo Python 3.14.7 with `-B`: 181 schema/predicate/
static checks pass, no runtime mocks are presented as real-system evidence.
`proof-checks.json` records the unchanged guard's exact 0/expected-1 exits and
raw log hashes. Seven publication gates (docs, ontology, sync check only,
contract bindings, frontend integrity, single-source ratchet and freshness
report) record exit codes in `publication-gates.json`. The exact 46-source
inventory is unchanged from the original frozen 4f bytes at accepted 72028;
90 related source/schema/fixture files include 32 direct-channel files, all
classified. Eleven additional generated/transport/journal surfaces are listed
in `additional-contract-bindings.json`. This static closure is not a dynamic
execution/concurrency proof. The initial census BOM parse failure and its
source-preserving correction are recorded in `tooling-resolution.json`.

Next owner Root: obtain actual independent revision review of the published
exact proposal SHA and decide whether to freeze this contract for bounded
implementation. Until then Codex keeps B production and real operations gated.
