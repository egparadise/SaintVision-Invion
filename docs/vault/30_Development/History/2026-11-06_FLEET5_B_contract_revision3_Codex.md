---
doc_id: "HIST-FLEET5-B-CONTRACT-REV3-001"
title: "FLEET5 narrow revision 3 authority lifecycle lock and VM contract"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Actual independent Claude delta review via Root pending"
updated: "2026-11-06T05:36:58+09:00"
source_of_truth: "Git"
---

# Scope and supersession

Owner Codex, task FLEET5-COMPUTE-STORAGE-CONTRACT-20261105,
`task_a8fd2969f0b3 / ctx_6f0f8253b8a7`, own branch
`agent/codex/fleet5-b-contract-rev3-20261106`. Parent DOCS proposal is
`02cfd260437e1d592cb4bf67e5d6764c4260363a`; immutable accepted source anchor is
`72028cbac903c4415d9979f980a6e0f9948e914f`. Root's latest board records separate
e50 testdelta/final checks in progress; no results are borrowed as B evidence.
Root-vault first read Index418/Codex379 and exact hashes/KST are in
`revision-record.json`; canonical first reads and skill versions remain in the
preserved Rev2 inventory (agent-delivery1.1.0/core-reliability1.0.0).

Actual independent review `ac9182c3e3d606ec027c0be2e90e049ff50d54f1` found R1-R7
and L-a..h; verdict is **REVISION REQUIRED, NOT ACCEPT/FREEZE**. Its actual
adversarial failures and audit are preserved in this evidence directory. The
original 100f/02cf proposals and reviews remain immutable. Root decision
`msg_f7caf4c96b16` authorizes only this narrow DOCS/schema/static fixture delta,
with no partial CP-schema/phase freeze. This document supersedes conflicting
Rev2 authority, expiry, replay, admission ordering, fence order and WSL clauses.
It does not register an ABI, modify product code or authorize NodeOps.

All real identities, addresses, host/VM/context bindings, paths, images, policies,
keys/provenance, leases and deployment bindings remain **NULL/HOLD**. The new
fleet is not initialized; old PC2/PC4 pilot identities remain distinct and
untouched. No remote/private/physical/PKI/Docker/WSL/install/trust/clock/schedule/
protected state operations or Obsidian apply occur. Shared boards, registry,
ADRs and source originals remain unchanged. Existing 48/VFCL statuses persist.
Actual Go/PG/Docker/crash/concurrency/physical B evidence is **zero**.

# R1: protected release authority and delegated request keys

The Node's protected role-config pins a **distinct operator-release verification
anchor**. It reuses no CA, enrollment, root-fence, Node TLS/signing or CP TLS key.
Protected release signing is outside ordinary runtime and online verifier/use
issuer custody and is never on the per-request path. No key is created/read in
this task. `authority-abi.json` specifies custody, principals and grants.

The protected signer approves a Node-visible RELEASE object binding exact
approved tenant/Node/cohort/operation, config, contribution/R, policy, shared C,
epoch, root/image/executable/floors, generation, approval interval and a specific
per-Node/per-release use-key public hash. A DELEGATION binds that release hash,
use key, authenticated CP caller class, allowed purposes, node/generation and
validity wholly inside release/approval/trust/certificate bounds. Release and
delegation are both signed by the protected release authority; the online use
key cannot sign either. Runtime has neither signer credentials nor key files.
Node validates anchor -> RELEASE -> DELEGATION -> signed role-use chain against
its actual gate ID, generation and config, never just a release ID label.

The online use issuer owns only the delegated request key. Its separate mTLS
service interface authenticates the CP service identity, loads the authoritative
current tuple/active admission/release/delegation from its own bounded DB pool,
checks purpose against that caller's grant and the exact business permit/body,
and signs only that loaded tuple. Caller-provided generation/config/purpose
labels are not authority. MODEL versus EXECUTION on the same Node execution
path is decided by authenticated CP caller + issuer permit classification;
Node verifies the signed scope but cannot infer model semantics from the path.
Unknown service/purpose fails. The verifier has no release-signing key and
cannot approve a changed generation, config, expiry or fence.

Production RELEASE/DELEGATION use the closed signedEnvelope schema; the signed
body schema is selected by kind, with duplicate/unknown fields rejected. Role-use
retains exactly `v1.<unpadded-base64url canonical payload>.<lowercase hex128 signature>`
in one bounded header. Public Ed25519 use-key bytes are carried in the protected
DELEGATION, and their decoded32-byte SHA256 must equal both release and delegation
key hashes. Domains are the exact ASCII `saintvision/node-role-release/v1`,
`saintvision/node-role-delegation/v1`, `saintvision/node-role-use/v1`, and
`saintvision/node-role-safety/v1` respectively, each followed by single NUL and
canonical decoded payload bytes. Signature verification and valid public-key
encoding/algorithm checks are mandatory future real crypto tests, not established
by the symbolic fixture signer labels.

Root rotation is an explicit protected operation binding old/new anchors and
config; no online self-rotation or arbitrary key discovery. Per-release delegated
key rotation needs a new protected delegation and bounded overlap inside the
same release; exact retired-key IDs become locally invalid. Authenticated
protected gate invalidation atomically changes the Node's in-memory active gate
under the business gate mutex, denies new business and cancels/drains existing
streams; local gate identity is bound in every token. The signed invalidation
also has a bounded durable local gate-generation record before acknowledgement,
so a crash cannot reactivate an invalidated gate. It is not a P/C/R reset.
Unknown/lost invalidation acknowledgement remains fenced; CP denial is immediate
at current-row commit, Node remote revocation is bounded by acknowledged gate
invalidation or remaining token/delegation expiry. Do not claim instant network
atomicity. On Node restart no gate is active until a fresh generation-bound
protected release/readmission is verified, even if old files remain.

# R2: independent observe/reconcile and safety lanes

All lanes require exact existing TLS1.3/mTLS chain, current control-peer policy,
Node identity/epoch and endpoint/body contract checks. Raw method is POST, exact
ASCII path, no RawPath alias/query/percent-encoded alternative. Release or
business-token expiry/fence does not exempt these checks. There is no generic
unauthenticated diagnostic exemption.

| Exact raw Node path | Lane and authorization | Permitted effects |
|---|---|---|
| `/v1/heartbeats` | OBSERVE, current authenticated CP + nonce/epoch | Existing scoped liveness reply; not eligibility |
| `/v1/snapshots` | OBSERVE, same checks | Bounded telemetry; no resource reservation |
| `/v1/roles/observe` (new) | OBSERVE, same checks + fresh nonce | Actual process generation/root/config/floor proof without an old business grant |
| `/v1/roles/gate` (new) | CONTROL, CP auth + protected release authority signed exact gate action | ARM an exact release or invalidate exact gate; no business/key delegation self-approval |
| `/v1/executions/receipts` | RECONCILE, existing CP auth + exact existing signed permit/hash/epoch | Existing Runner.Observe: get durable receipt or reconcile recorded intent; never create/start unseen command |
| `/v1/executions/cancel` | SAFETY, existing signed permit + separately typed protected safety authority | Exact command stop/tombstone/receipt only, no execute/restart |
| `/v1/builds/quarantine` | SAFETY, separate scoped safety authority + existing request identity/epoch | Durable reconciliation obligation, no claim of repair/physical stop |
| `/v1/executions` | BUSINESS EXECUTION or MODEL | Existing kernel permit plus full delegated role-use chain |
| `/v1/objects/read` | BUSINESS TRANSFER | Existing bounded object request + role-use |
| `/v1/terminals/frame` | BUSINESS TERMINAL | Existing terminal spec + stream/frame role-use |
| `/v1/storage/sample` | BUSINESS STORAGE_COLLECT | Existing storage-v1 signed challenge + role-use; CP issue/commit separately gated |

Receipts remain usable while fenced or discovering generation, without an
EXECUTION/MODEL token. Source `server.go:281`, `runner.go:343`,
`node_transport.py:79`, `dispatch.py` observation path establish the current
reconcile contract. Observe may reconcile/stop/remove an already owned ambiguous
intent and persist its actual receipt; it is not a pure read. It cannot create
an unseen execution, fabricate success or mark a storage check healthy. CP
receipt acceptance/ack only stores verified actual outcome and releases claims
when the existing stop/receipt invariants permit. It does not grant B admission.

Gate control is POST at exact `/v1/roles/gate`, with separately closed
ARM_EXACT_RELEASE or INVALIDATE_EXACT_GATE action/body/generation/nonce/expiry,
signed by the protected release authority (domain
`saintvision/node-role-gate/v1` plus NUL). Neither online use issuer nor safety
key can arm a business release. Before activation, Node may acknowledge ARMED
release/generation without admitting business. The target per-release private
use key is provisioned to the online issuer only after the protected delivery
controller confirms the exact committed CP activation ledger/fence release.
This custody handoff is an explicit future provisioning requirement, not a claim
that any key/service exists. No target key is available to the online issuer
before that commit; old keys cannot authorize the new generation/gate. Node
needs the full chain and actual matching ARMED gate for every business request.
Lost delivery or acknowledgement remains UNKNOWN; replay only the exact frozen
key reference/public hash, never generate a replacement silently. An immutable
key-delivery/possession receipt is checked in computed eligibility; ACTIVE DB
rows alone are not operational success. Fresh all-five release waits for all
five final proofs/gate acknowledgements; per-Node readmit touches only that Node.
All Node/control/key handoff I/O is outside DB row locks, followed by canonical
current-row/evidence rechecks. These steps do not claim distributed atomicity.

The CP typed OBSERVE/RECONCILE scope must also avoid a bootstrap circularity:
`NodeChannels.snapshot` currently requires online/fresh state, and a partial
renewal may serve target DER B while the shared CP row is still at A/C. A narrow
`b_read_observation_scope` loads either the recorded identity/current DER or the
exact protected frozen-intent target DER/epoch, checks the mandatory current
control-epoch/tenant guards and scoped observation permission, and returns a
non-business ObservationScope. It may observe a fenced/offline/revoked business
member, never mint a ChannelProof eligible for dispatch/storage commit. Phase
proofs are stored as candidates against the exact intent/current tuple. B callers
cannot use ObservationScope as a business grant or skip current-row rechecks.
If historical epoch/trust credentials are not valid under the existing Node
checks, observation returns AUTHORITY_UNAVAILABLE and recovery remains reviewed;
no TLS/status/certificate repair is inferred. Receipt commit keeps existing
verified outcome/stop/claim invariants; changed authority that cannot satisfy
those invariants retains raw diagnostic evidence and quarantine rather than
fabricating an acknowledgement or freeing a claim.

Safety has its own protected verification anchor/key and least-privilege grant,
distinct from release/use keys and ordinary business service. It binds exact
Node/epoch/command or quarantine obligation, purpose/body hash/nonce/short
expiry. It remains available when B approval/lease is unavailable; its own
operator containment grant and existing authentication must still be valid.
The use issuer cannot mint safety authority. Read-only generation discovery and
same-permit reconciliation need no safety-key round trip. If epoch/trust itself
is invalid, return AUTHORITY_UNAVAILABLE, preserve evidence and enter the
separate reviewed recovery gate; no cross-epoch TLS bypass or invented recovery.
A local stopped-process probe is separately scoped operator observation, not a
business-start exception. No Node I/O occurs while DB row locks are held.

# R3/R4: leases, per-Node readmission and acyclic admission

Protected approval/release/delegation lifetime is separate from short leases.
Proposed durable approval maximum is 24 hours and always bounded by explicit
operator expiry plus Node/CP certificate/trust validity (30-second skew budget).
No real lifetime is assigned here. Release/delegation cannot outlive that bound.
A Node admission lease is at most **300 seconds**; a per-request role-use token
is at most **120 seconds**, further bounded by admission/delegation/release/
approval/certificate expiry. All new time fields are exact integer Unix UTC
seconds; expiresAt > issuedAt. Plain :2 existing time formats remain unchanged.

After whole-five fresh activation, steady-state lease refresh is per Node.
`REFRESH_SAME_GENERATION` verifies a fresh Node proof and independent host proof,
unchanged frozen tuple and no mutation fence, then calls a narrow lease-refresh
procedure. It changes neither approval, release, delegation, generation nor
config. An unrelated offline member is not a refresh dependency. If the online
verifier is unavailable, the affected Node's admission eventually expires and
business denies; do not silently extend it. Receipt reconciliation remains usable.

`READMIT_SAME_CONFIG` handles an actual process restart or expired observation.
Discover generation via OBSERVE, independently measure the host/root, and
verify SAME frozen epoch/C/R/root/image/executable/config/policy/floors plus
unrevoked approval and certificate/trust. The protected release authority signs
a new per-Node readmission release/delegation for that fresh actual generation.
The canonical commit checks no cohort mutation fence and exact unchanged rows,
then atomically activates that Node's new admission/current pointer. Other
members and their leases are untouched; there is no all-five refresh or short
release expiry dependency. Changed config/epoch/C/R/root/floors or genuinely
expired/revoked approval is **not** same-config readmission. Deny that Node;
a new protected approval is an explicit external authority boundary, not an
inferred offline recovery. During active cohort mutation this lane is blocked.

Admission ordering is acyclic: (1) verified candidate observations, not eligible
admissions; (2) protected RELEASE references immutable candidate evidence;
(3) one closed CP activation transaction INSERTs committed release/delegation
records, INSERTs ACTIVE admission with a real existing release FK and updates
its current pointer. Fresh activation does this for all five and releases the
fence in the same CP transaction. Per-Node readmit does it for one Node only
while mutation fence is absent. No dangling fake planned release or circular FK.
Online verifier/issuer cannot perform protected activation by arbitrary DML.
Lost response: read exact operation/activation ledger + rows in a new canonical
transaction; matching tuple alone is UNKNOWN. Engine, filesystem and DB are not
one atomic transaction.

Selected sets are nonempty unique actual Node-ID strings and a subset of the
released cohort/eligible selected Nodes. Reject empty, duplicates, foreign IDs,
integers, indexes and out-of-range values before iteration/output. All-five
stable evidence is required only for fresh/cohort activation or explicit cohort
mutation. Four independent Linux workers remain the independent S05/S07 domains;
CP-colocated Node never adds an independent fifth domain.

`authority-abi.json` names NOLOGIN table/procedure owners, protected operator,
online verifier, online use issuer, safety service and ordinary business pools,
with exact grants and prohibited memberships. Authority rows are read/lock-only
to ordinary runtime; narrowly granted business nonce/evidence procedures are
separate writes. There is no runtime/attestor SET ROLE path to operator/owners,
no shared credentials and no caller GUC as approval. SECURITY DEFINER has fixed
pg_catalog search_path, fully qualified relations, forced tenant RLS, explicit
session identity/service binding and exact grants. All new B tables must join
`tools/rls-table-census.json`, collector/ratchet and pinned aggregate evidence
in the future migration; this proposal changes none of them.

# R5: all partial invalidation states remain closed

`phase-authority-matrix.json` enumerates pre-intent and k=0..5 member CAS states,
independent P=101/C=7/R=2 fixture bases, peer/storage pins, current CP C/DER,
operation/approval/delegation/admission/token windows, epoch and fence. P/C/R
remain independent; renewal changes P by2, SAME shared C by1 and R by0.

Preflight requires all authority validity to cover the bounded 600-second
operation plus30-second skew, valid B NotBefore and exact A/B policy bytes. A
failure before intent preserves current container/journal. Once durable intent
exists, the entire cohort is fenced before live exposure. Revoke/C jump, epoch
change, operation approval/grant/release expiry or unknown/lost authority after
k=0..5 CAS keeps **QUARANTINED** mixed monotonic evidence. B-FRESH1 blocks a new
ordinary intent, automatic re-enrollment, reset, policy regeneration or old
restart from that state. The distinct **B-RECOVERY1 reviewed authority
reconciliation gate** is design-first outside this contract: exact mixed-state
inventory, protected current authority, explicit Root review and recovery proof
are prerequisites. No ordinary renewal/readmit endpoint can enter it.

Same-intent forward replay is allowed only while the exact frozen authority,
bytes, current tuples/ledger and operation windows remain valid. Changed or
expired authority blocks replay; no new approved ordinary intent is inferred.
S4a still means P-first fsync succeeded, storage C still old; two pins are not
atomic. Half-copy/before-copy/unknown/restarted stays BLOCK. All old/history
floors remain byte-preserved; extras require approved immutable history or block.
Receipt reconciliation and narrowly authorized containment remain available.
Ordinary request-token expiry alone permits a new token only under unchanged
valid release/current tuple and **no mutation fence**. It cannot extend approval,
lease or delegation, admit an expired Node, or reopen business while fenced.

# R6: mandatory epoch/tenant guards and semantic callsites

Rev2 fence-before-epoch is withdrawn. Canonical order preserves the mandatory
`Database.transaction` outer guards: **control_epoch FOR SHARE first**, then
existing tenant_controls SHARE (UPDATE for containment writers, selected at
entry without upgrade), then routing/mutation-fence SHARE for ordinary use or
UPDATE for operator mutation, sorted inv.nodes, sorted public.nodes then
storage_contributions, shared node_channels, role/current rows, business/run,
operator grants, resource/claim/transfer/model/terminal, nonce/evidence/CAS ledger/
audit. Every class's exact mode is in the callsite inventory. Epoch writers take
control_epoch UPDATE first, then the same remaining order; operator fence writers
use the same guarded entry and may not bypass epoch or tenant checks.

When membership/scope is not yet known: lock-free discovery is a hint only;
enter the guarded transaction, acquire canonical locks, then reread/revalidate
all membership/authority. Changed scope aborts/replans in a new transaction.
Never authorize on discovery or add a lower-rank lock later. In particular
leases.py Run-before-Node, containment operator-grant-before-Node, observation's
all-online Node loop and lan_pilot channel-before-Node must be reordered for B.
Unknown B writers refuse; required observe/business paths receive explicit
ordered entry plans rather than being disabled wholesale. Public ORM writers
use the same guarded B procedures or refuse B before acquiring an incompatible
outer ORM lock. Plain visible contracts and epoch/tenant guards remain intact.

No Node/attestor/host probe I/O while DB row locks are held. Persist a bounded
permit/fence, commit; perform external work/quiescence; then reacquire canonical
locks and recheck exact tuple/evidence before committing outcomes. Existing
Database bounds500ms lock_timeout/2s statement_timeout remain the default B
bounds; operator maintenance uses the same limits in bounded batches. A timeout,
40P01/40001/55P03/57014 or lost commit response rolls back the whole transaction,
retains prior committed quarantine, and retries at most three times with bounded
jitter in new transactions and exact tuple+ledger reads. No fairness/starvation
guarantee is claimed. Maintenance writers may need a planned quiescent window;
contended work yields RETRYABLE/HOLD without changing authority. Real PostgreSQL
concurrent writer/deadlock/abort/lost response/implicit FK/RLS tests are future.

`callsite-locks.json` replaces the previous heuristic completeness claim. It
records actual SQL/ORM call expression, function/line/hash, current mode and
semantic B entry plan, including app route and remote/workspace Git consumers.
DDL FK/RLS, outer guards and operator wrappers are explicit assets, not filtered
out by suffix. Static evidence cannot establish dynamic reachability or actual
PostgreSQL implicit lock acquisition; unresolved discovered callsites are
reported, never erased by an empty list constructor. The implementation gate
requires resolving every reachable callsite and actual PG coverage.

# R7: production CP context is a separate-kernel managed Linux VM

Production selects a managed **separate-kernel Linux VM with its own supported
Linux Engine/default socket**. WSL2/shared-kernel alternatives need a separate
review and are not fallback. No Desktop/DrvFs/9P/remap/interop/automount source
path is accepted. VM identity (hypervisor UUID/machine identity) is distinct from
current guest kernel boot identity; Node's measured kernel boot must correspond
to that exact guest, and source dev/inode/fs/context must match independent host
probe. Mount IDs are namespace-local and never compared across namespaces.
Linux identity encodes device-major and minor as lowercase uint32 hex8 each,
inode as lowercase uint64 hex16, plus exact supported fs/context identity.
No Windows file-ID equals Linux inode claim is permitted.

`capability.schema.json` specifies RAW measured host/VM CPU counts/allocation,
physical and commit memory bytes, disk capacity/free/backing filesystem, Linux
native contribution root, virtual network/interface/routes, TCP/TLS endpoint
reachability and reserved-port ownership, producer/version/artifact/nonce/proof
and observedAt. Booleans/hash alone do not establish capability. Fresh independent
producer evidence and operator-approved budget are required, with source-to-
daemon/Node correspondence. No measurement runs in this task. Root's reported
host99percent/125MB-free observation is a blocker context, not a fresh worker
measurement or permission to provision. Unsupported OS/hypervisor, insufficient
memory/disk/CPU/network or unknown capability is RESOURCE_UNAVAILABLE/BLOCK.

Planning defaults are guest2vCPU/4GiB RAM/20GiB disk, plus host2GiB physical and
commit-memory headroom and10GiB disk headroom. Actual budgets and bindings stay
NULL until a measured reviewed plan approves them. Budget predicates compare
raw available host physical/commit memory against guestRAM+headroom and host
free disk against guestDisk+headroom; guest allocation/capacity/free native
contribution space and route/port/TLS measurements must satisfy the explicit
approved plan. These are provisioning/resource-policy checks, not Node workload
hard quotas or a claim that a guest exists. No install/elevation/private host
read or protected old Desktop/r5 operation is authorized.

# L-a..h: byte/time/Unicode/replay/workload closure

All hashes/hex fields have exact byte length and explicit ASCII alphabet. JSON
Schema uses min/max length and a real end assertion, Python fullmatch/byte checks,
Go length+byte-loop equivalents; no shared '$'-only assumption. New times are
exact integer Unix seconds, reject bool/float/exponent/string/overflow, require
strict positive windows and the nested expiry bounds above. Existing plain :2
fields are not reinterpreted. IDs/paths/protocol fields are ASCII with per-field
alphabets and fixed endpoint paths. Strict UTF8 decode and recursive no-surrogate
checks precede Go encoding; never accept replacement U+FFFD for invalid input.
NUL/C0/DEL is forbidden in strings. Legitimate Unicode displayLabel alone may
contain U+2028/U+2029 and combining sequences; C2 escapes those and HTML, uses
UTF8 without NFC, sorted keys and no LF. Signature bytes are exactly
ASCII(domain) || single0x00 || decoded canonical payload bytes, with no newline.
Unknown/duplicate JSON fields, aliases and noncanonical encodings reject.

Role-use replay is generation-bound **in-memory**, not terminal-frame fsync.
A cryptographically fresh per-start nonce plus measured kernel/PID start identity
makes the generation unique. Consume nonce under the business gate mutex before
effects; expiry GC uses exact expiry+skew, capacity4096 live tokens fails closed
(no live eviction). A new valid retry token can only retry the existing kernel
permit under its durable idempotency. CP business nonce/evidence commits stay
durable. Terminal opener and each frame use their own scoped nonce and monotonic
sequence/body hash under the existing approved stream ID; no privilege-bearing
frame after token/lease expiry or gate change. New token renewal cannot extend
stream beyond its approved spec; quiescence waits for streams/requests to close.
No old-generation token survives restart; observation does not consume business
replay entries. Safety has a distinct bounded replay namespace.

The workload HostConfig decoder is a closed allowlist, including CapAdd,
capabilities/security options, every namespace/runtime/sysctl/volume/cgroup/device/
network field. Unknown fields reject unless an exact neutral value has been
explicitly frozen and tested for the approved Engine/API profile. All bind/
Mounts/VolumesFrom/top-level Mounts/host path/socket/contribution/state access
remains forbidden to workloads. Allowed tmpfs/cgroup and exact GPU requests are
bound to the existing permit. `workload-allowlist.json` lists required fields,
neutral fields and nested values; actual Linux Docker enforcement remains future.
Trusted Node's Docker socket still equals guest-host-root power; readonly bind
is no defense against a compromised Node/daemon/guest root. No RW contribution,
arbitrary mount, stale/tampered policy, symlink/TOCTOU/substitution, counter reset
or generic mount copying is accepted. Policy A bytes/R/root stay exact; leaf B
changes DER and SAME shared C+1. R4 default guard, plain :2/:3, SF1/RS1 and B-MIG1
DESIGN-FIRST remain unchanged.

# Evidence and next gate

The preserved Rev2 adversarial failures are not relabeled PASS. Rev3 negative
fixtures rebind dependent hashes/signature-input digests after changing attacks,
so rejection is attributed to authority/scope/time/current state rather than
an incidental stale hash. Signers are explicitly SYMBOLIC fixtures, not actual
keys, Ed25519 verification or custody evidence. Source/schema/model tests are
not actual Go/PG/Docker/physical acceptance. The existing unmodified72028 R4 gap
still has expected exit1; raw original red and 46-surface source proof remain
available unchanged through02cf. A1-A16 real-system tests remain pending,
including actual key chain crypto/canonical vectors, lane reconciliation during
fence, per-Node restart readmission, grant separation/RLS, every partial invalidation,
PG concurrency and Docker read-only/nonrecursive/rprivate/workload decoder.

Local proof uses main Python3.14.7 with -B and records242 schema/static/symbolic
checks. The source ledger contains602 expressions in65 files,27 explicitly
resolved dynamic/helper expressions and138 FK/RLS/schema assets; eight named
entry plans specify lock modes. verify_source_ledger.py independently rechecks all602 AST expressions/65 file hashes
and138 schema anchors against72028 with zero mismatches. It does not claim actual SQL trace completeness
or PostgreSQL lock behavior. Initial five positive-schema failures are preserved
in initial-fixture-red.json; nested root/tuple schema copies were replaced by
canonical $refs and the rerun passes. Commands/exits/raw log hashes and final
publication gates are captured alongside this record. Root governance scope1.1.0
at7ec1af26 and exact decision source are preserved; separate bootstrapv5/K1
acceptance is not B evidence.

A final static grant check found that the first published Rev3 packet15823c2a
named b_record_key_delivery as the table writer but omitted its operator EXECUTE
entry. The expected static failure is preserved in key-delivery-grant-expected-red.json;
the narrow follow-up adds that explicit grant plus protected operator/safety
observation-scope access, and the new consistency fixture passes. No actual DB
grant or production change was applied; independent Rev3 review remains pending.

Normal delivery is unique commit/push/exact Docs plus actual independent delta
review; no repeated user approval or partial freeze is requested. Next owner
Root obtains one actual review of the published Rev3 SHA, resolves the coupled
authority/lifecycle/lock contract, and only then may register ADR/registry and
grant bounded Codex implementation. This task is not complete while that gate
is pending; no worker_done or physical/storage acceptance is claimed.
