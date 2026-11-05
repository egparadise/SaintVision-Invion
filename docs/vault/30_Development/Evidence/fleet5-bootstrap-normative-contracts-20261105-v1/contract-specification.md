# Proposed binary bootstrap contracts v1

This is a closed normative **proposal**, awaiting independent contract review
and a separate Root implementation decision. It contains no commands for
execution. The accepted803 plan is unchanged. JSON Schemas fix shape/types/
bounds/keys; this specification fixes semantic and authenticated checks beyond
JSON Schema. BOTH are mandatory in any future implementation. Missing schema,
unsupported version, unknown key/state, duplicate JSON key, invalid Unicode,
unavailable referenced bytes, unknown trust, ambiguous ownership or failed check
means BLOCK before effects. A well-formed fixture is never authorization.

## Artifact encoding and trust

Every artifact schema is closed recursively through `common.schema.json`.
Objects require every declared property; optional lifecycle values are explicit
null only where their schema allows. No extension bags, implicit defaults,
unknown parameters or arbitrary shell/paths exist. Integers are wire integers,
never bool/float coercions; counters are0..2^53−1, positive generations1..2^53−1,
UID/GID0..2^32−1, PIDs1..2^31−1. Recovery epoch is an exact existing STRING,
matching Go Config.Epoch and M2 recoveryEpoch; it is never an integer or newly
generated value. Overflow blocks before arithmetic. Strings are
strict UTF8 Unicode scalars with no NUL, bounded per schema; no normalization,
case conversion or blanket ASCII restriction. IDs are exact opaque strings,
compared bytewise. Git SHA is40 lower hex, byte SHA256 is64 lower hex,
Ed25519 signature is128 lower hex. Image digests have literal `sha256:` prefix;
Docker object IDs do not. Docker Name includes its literal leading slash.
Absolute paths are registered Linux paths, never accepted just because their
syntax passes. Metadata timestamps are exact UTC whole-second RFC3339 `...Z`;
current time comes only from actual trusted clock, never a request override.

The outer object is exactly `{body,signer}`. `signer` has role, keySPKISHA256
and signatureHex. Roles are fixed per schema, not caller capabilities. Root
must register separate allowed public key SPKI hashes and role/scope grants
in a reviewed trust configuration bound by the plan's contract digest. Existing
Node leaf keys serve M2 only; none is recopied or used for Root seals/leases.
How authorized host-helper/Root/CP signing capabilities are provisioned is an
implementation prerequisite; a public fixture supplies no keys or permission.

`signature-domains.json` enumerates six distinct ASCII domains. Signature
message is domain + one00 byte + canonical body. Body contains every schema
field, excludes signer, has no newline/BOM. Canonical bytes equal strict Go
`encoding/json.Marshal(map)` C2 rules: sorted keys, compact, raw valid Unicode,
Go HTML and U+2028/U+2029 escaping; reject invalid UTF8/surrogates BEFORE Go can
replace them. No floats/NaN/Infinity, duplicate keys or alternate scalar types.
The exact toolchain must be recorded in future actual-Go cross-language tests
(B03 requires Go>=1.22; candidate go.mod1.23/CI1.27.1). This is a new-artifact
mapping; legacy v1, outer receipt and CP commit signatures remain unchanged.
`bodySHA256` and `envelopeSHA256` in the domain document are distinct. All artifact
references in these contracts are **envelopeSHA256** unless explicitly named
Raw/DER/config/argv. References must retrieve exact canonical bytes, verify
signature and trust, and verify expected scope/contract, not merely hex shape.

`proof` is a reference, not an untyped evidence object: contractSHA256,
artifactSHA256, scopeSHA256, signerKeySPKISHA256, observedAt and validUntil are
all required. contractSHA256 selects an independently reviewed closed evidence
schema/verifier pinned in the immutable plan contract set. Its exact bytes must
be available and authenticated; no arbitrary contract is dynamically loaded.
Scope is the canonical exact typed subject required by that verifier (Node,
daemon, volume, operation, nonce and relevant state). An absent or unregistered
referent BLOCKS. All proof timestamps must agree with signed referent bytes,
observedAt<=validUntil, and the fresh gate's trusted current time. A proof ref
alone proves nothing. Minimum verifier semantics are enumerated below; product
publication must close those evidence schemas before implementation acceptance.

Schemas do not prove trust, provenance, freshness, filesystem identity, image
lineage, process liveness or absence of side effects. Structural VALID synthetic
examples are deliberately UNTRUSTED. Production readers must reject them.

## Populated successor plan and immutable bindings

`successor-plan.schema.json` defines a future populated plan, not a mutation
of the constant-null803 plan. Every product record requires real source SHA,
artifact hash, build provenance, exact Core/Backend CI repository/workflow/ref/
event/head/run/attempt/artifact/attestation and independent ACCEPT for that same
source/artifact. Reviewer must differ from author and be authorized for the
subject. CI heads must equal product source; no Docs-as-Core substitution.
To avoid self-reference, planSubjectSHA256 hashes the canonical plan body with
exactly planSubjectSHA256, independentPlanReview and rootPublicationIntent
excluded. The two approval proof contracts authenticate THAT subject plus their
role/decision, not the final envelope hash. All other fields, including targets,
members, windows and contract set, are in the subject. Actual reserve execution
decision is external and binds the full final signed plan envelope. No approval
ref may refer to a different subject or be reused after any subject change.
Root's actual plan/publication decision and plan review are authenticated refs,
never a boolean. Plan expiresAt>createdAt and every future effect revalidates
plan validity, deadlines, positive measured budget and maintenance/operator
window. The future renewal window is separate and cannot authorize early leaf
renewal. Candidate4a, old2fb, review b59 and this report are distinct subjects.

Image identity fields are separate: local imageId, index-or-manifest digest,
platform manifest, config, ordered diffIDs, authenticated archive, executable
bytes, inherited Config and build recipe. Registry or authenticated offline
distribution proof must bind all to the accepted source/platform; no unsigned
archive, missing RepoDigest guess or host mirror. An index is not a platform
manifest and neither is a Docker imageId. Image Env/Entrypoint/Labels/User/
WorkingDir and remaining inherited runtime Config must match the old image,
using the same reviewed scratch/COPY/ENTRYPOINT recipe. Container overrides
cannot hide a new inherited difference. The inheritedConfigSHA256 is over the
closed canonical compared-image-Config projection selected by the inspect
contract, not a local image name. Unknown field/delta blocks.

Exactly two unique member inputs are ordered PC2 thenPC4, with their original
registered tenant/Node/epoch. These are fixed old-cohort slots, not new Node IDs
or permission to map hardware. Every baseline field binds the stopped/fenced
capture that will be validated; no Root unsigned historical snapshot satisfies
it. Old runtime image and immutable ID/daemon/name, exact Config/mounts/resource/
security/observe args, owned existing volume and full protected tree digest,
P/H/journal identity, C/cert/enabled/endpoint and authorities are fixed. A preplan
may refer to inspected running originals; the later fenced capture must prove
protected equality and the explicitly allowed lifecycle deltas. Exactly one
consumer is allowed before preservation. Historical containers not mounting
this exact volume are context; an extra consumer of it blocks regardless of
label. Existing shared volume is never copied, replaced or recreated.

Cmd preserves `--image` workload/permit semantics. The runtime image may change
only to the accepted target. Legacy CP agentImage/manifests remain frozen as
historical records; new typed inventory is current runtime truth. Cmd/Entrypoint
JSON array hashes and full argv JSON hashes use compact ordered raw-UTF8 JSON,
no Go HTML escaping; raw cmdline hash uses UTF8 elements joined by NUL plus
ONE final NUL. They are separate domains. Preserve empty arguments; reject NUL,
surrogates, shell entrypoint or a different full PID1 argv. Exact direct
Entrypoint `/inv-node` plus Cmd is required for this proposal.

The30 target and18 Root binding names in803 remain null. The successor schema
binds known inputs through typed product/image/authority/timing/approval fields;
future-derived fields (new containerId, post-start M2/mTLS, predecessor/seal/
inventory hashes) are **outputs in events**, never invented preplan inputs.
Before an output exists its schema slot is null or absent only as explicitly
allowed by its phase. It must exist before any consuming transition. No plan
is published READY by filling future outcomes with predictions. Actual
`actual-bindings-HOLD.json` contains no populated successor envelope.

## Lease, common fence and ownership

One Root-authorized cohort lease reserves both exact registered scopes before
any effect. Both host OS locks plus durable logical fence are held for the full
operation and all children. A lease signature or one-shot precheck alone grants
no access. The Root coordinator performs ordered reservations PC2 thenPC4; if
the second reservation fails before effects, append a signed release of the
first after proving no effects/children. No cutover begins on a partial cohort
reservation. Lease fields bind operation/plan/migration, monotonic fenceEpoch,
prior fence digest, live owner principal/UID/GID/host boot/PID/start/generation,
registered worker roots, daemon/volume identities, allowed entrypoint digest,
descendant registry and exact inventory. Secret random token is transmitted
only through authenticated protected IPC; public records contain its hash.
Never derive it from PID or age. Held OS locks and exact live owner generation
must match at every nested call and before/after each effect.

Fence epoch advances only by durable compare-and-publish against the previous
authenticated fence after proven release and process/descendant quiescence;
expiry, dead PID, elapsed age, session loss or absent socket alone never allow
reclamation. Unknown ownership records BLOCKED_UNKNOWN and quiescence unknown;
no lock/marker/token deletion or force parameter. An interrupted authorized
same-plan owner handoff requires explicit Root decision, old owner and all
children proven quiescent, new generation/epoch and append-only handoff proof;
otherwise BLOCK. This is a future transition requiring product tests, not an
offline recovery mode. Fixed workerRoot registration, not caller directory,
chooses `agent-mutation-fence.json` and `agent-binary-migration.json`.

Any migration marker, terminal or not, denies generic legacy mutations. This
includes prepare/finish/start/repair PS+shell, credential publication, workspace
upgrade/rollback, storage helpers, controller prepare/stage/commit/retire and
all old rotation paths. Explicit scheduler denials cover
Register-LeafRenewalTask.ps1, Invoke-ScheduledLeafRenewal.ps1 and
tools/scheduled_leaf_renewal.py, including new task registration outside the
three disabled IDs. New managed entrypoints call the common fence themselves,
including direct Python public APIs; wrappers use a hash-bound runner. No
`rotation_publication=True`, force/skip or alternate path substitutes for lease.
Unpatched raw privileged scripts are not magically fenced. Root must exclude
all reachable old launch surfaces and in-flight descendants, else G9 HOLD.

## State, journaling, atomicity and reconciliation

`state-machine.json` enumerates allowed states. DRAFT_HOLD is documentary only;
PROVENANCE_LOCKED is the first event after authenticating the populated plan.
Each immutable event binds request/idempotency/operation, sequence, exact prior
event digest, plan, fence epoch/lease, both member states and explicit effect.
Sequence1 has prior=null; later sequences require sequence−1 and exact existing
envelope hash. Unknown/partial/prepared/staged/switched leaf state blocks a new
migration. Exact same-plan reentry reads evidence; it never starts a second
attempt or overwrites an earlier state. Same idempotency key and same canonical
request return recorded outcome without replaying effects. Same key/different
request is conflict. New key is not authority to redo an ambiguous effect.

Every effect has a durable signed intent event BEFORE the action and a durable
verified outcome afterward. The effect kind/target must match the fixed method
and transition; no arbitrary advance. Restart-no intent is FENCE_INTENT;
stop intent remains OLD_FENCED until quiescence receipt; rename intent is
PUBLICATION_INTENT; create intent follows OLD_PRESERVED; start intent is
NEW_START_INTENT; inventory/seal/restore have separately recorded intents at
their preceding state. An event at the same phase is allowed only as that
method's intent or exact readback receipt, never as a second mutation. Event
phase for member methods equals target member resulting phase; the other
member state is unchanged. Cohort publication methods require both member
states at the named precondition. The projection phase is its own member's
state, not inferred from the other member or a high-water cohort value.

Both old containers must read back restart=no before the first stop. PC2 is
processed beforePC4; PC4 may keep running restart=no until its turn. First-member
failure prevents second cutover. Root-owned Engine inspect plus process/exec/
mount-consumer proof must establish old process and descendants actually stopped
before protected full-tree scoped double read. UID/GID/mode/type/content,
cert/key/CA/policy/state/journal/floors remain equal. The trusted capture receipt
is explicitly unsigned Node-wise, fenced and authenticated by the host adapter;
it is not a substitute for normal M2. No credential recopy or OpenJournal.

Preserve old container with a reserved literal Name and immutable same ID,
restart=no, stopped, plus frozen **post-stop/rename** inspect. Never delete it
or any failed/new container, volume, backup, cert/key/journal/receipt. New create
uses exact old inspect, same owned volume and preserved args/config/resources/
mounts/endpoint; only reviewed runtime image and explicitly enumerated lifecycle
ID/name/restart/Engine ephemeral fields may differ. No new marker label is
needed. New ID is read from owned daemon response and inspected, never guessed
or prefilled. Rename/name collision, duplicate/third/unknown consumer or image
pull/import ambiguity blocks. An Engine request with unknown result remains
unknown until exact operation-bound daemon/process evidence resolves it.
Never retry create/start by name or start an old backup as rollback.

Starting new Go may pin state and is a forward-only barrier. Stable running or
heartbeat is insufficient. Post-start protected-tree equality, actual unchanged
mTLS, owned runtime image/process inspections and fresh signed M2 v2 must all
match before BOOTSTRAP_VERIFIED_RESTART_NO. Owned ExecCreate receipt records
the exact actual ExecID before ExecStart; prior ExecIDs must be empty, during/
after sets must equal the frozen Engine-specific expectation for that ID only,
with exact ExecInspect container/argv/UID/exit0. Missing or foreign ID blocks;
no generic volatile-field ignore. Same-executable UID/live PID1 and actual
journal/executable proofs are mandatory. Never sideload a new observer against
an old running Go process or assume the old image accepts the flag.

The projection journal is a signed CAS index into immutable events, not sole
evidence. Trusted roots are registered outside the Go volume; private owned
parents0700 and files0600, no-follow/open-dir-relative, regular single-link,
UID/GID and expected device/inode/parent identity checks hold before/after.
Prepare bounded bytes privately; flush file, publish immutable event/seal by
exclusive no-overwrite name, fsync parent, then CAS projection against exact
prior digest using same-filesystem atomic replace and parent fsync. Existing
name with different bytes BLOCKS; identical bytes are verified idempotently.
Projection replacement preserves previous canonical bytes in immutable history.
No overwrite of an archive. Required persistence primitives unavailable ->BLOCK.
Reader checks bounded full event chain/gaps/signatures and projection consistency.
Maximum one event1MiB, plan/inventory4MiB, proof ref payload64KiB, chain4096
events per first migration; exceeding bounds BLOCKS with evidence preserved.

Crash after intent/before outcome is not success or permission to repeat. Same
plan/owner reconciliation inspects exact IDs and effect receipt. Proven no
effect permits exact method continuation; proven complete effect permits only
append outcome/readback; conflicting/partial/unknown outcome appends
BLOCKED_FORWARD_ONLY or QUIESCENCE_UNKNOWN and stops subsequent effects.
No floor/claim/lock/window/latch reset, old-binary restart or automatic downgrade.

## Inventory publication, seals and normal renewal

Both new members verified precede one CP inventory metadata CAS over expected
prior inventory, global legacy state digest and exact unchanged channel vector.
The typed expectedInventoryHead is ABSENT with envelopeSHA256=null only for
an authenticated scoped not-found readback from the registered inventory API,
or PRESENT with the exact current envelope hash. readbackProof is mandatory
in either case. ABSENT is compare-and-INSERT, PRESENT compare-and-replace;
neither accepts an empty/default/guessed digest. This distinguishes an initial
new inventory collection from unknown state without inventing old inventory.
It atomically publishes both runtime records, or neither; transport timeout is
resolved by publicationId plus exact payload digest readback, never blind retry.
The inventory target/image matches plan, current IDs match journal, backups
match frozen post-fence inspections, authorities/volume/argv match capture.
The current inspected container runtime image may differ from preserved permit
image deliberately. Global legacy agentImage and C/certs/enabled/endpoints stay
unchanged; inventory publication is not channel/leaf commit authority.

To avoid cyclic hashes: inventory references each BOOTSTRAP_VERIFIED event,
not a future seal. Each terminal seal binds that event, inventory envelope,
fixed old backup/current IDs/volume, final protected tree and M2/mTLS. The
terminal event then binds the seal, and projection points to that event/seal.
Seal publication uses no-overwrite per Node/migration path and an explicit
Root-seal signer. A missing one of the two seals or a partial terminal CAS
keeps cohort HOLD. Exact existing inventory/seal is reconciled read-only; no
new migration ID/target can replace, rotate, append or clear predecessor state.
Inventory and seal are immutable even when later normal leaf rotation changes
the shared volume. Seal floor/cert/state hashes describe bootstrap history,
not a permanent requirement that active leaf generation stay frozen.

Post-migration typed predecessor recognition allows exactly current container
and one recorded stopped backup as owned-volume consumers, in the exact
daemon/registered scope and frozen backup inspect. No label-only, workspace-only,
unknown or third consumer. Current Config/identity/runtime must match inventory.
During bootstrap M2, the held migration lease plus NEW_START_INTENT or
NEW_STARTED_UNVERIFIED supplies the preterminal path. Later normal:3 requires
immutable terminal seal/inventory and a **new** held common-operation lease;
the expired original migration lease is not reused. Current P/H/C/leaf/state
are validated from fresh signed M2/approved normal plan, not equated to old
migration hashes. Generic mutators remain denied even with terminal seal.

Restore only NEW container original unless-stopped after both actual M2/mTLS,
unchanged authorities and separately explicit Root restore decision; otherwise
keep restart=no. Old backup always restart=no. Desired restart changes require
intent, exact ID readback, fresh capability and final readback. READY means
ready for a separately reviewed normal renewal plan, never implicit permission
to run it or enable an old scheduler. No second binary migration is supported.

Replacement normal renewal requires new reviewed schema3 helper, new guard,
immutable plan pins, same old two-cohort keys/CA/epoch/identities, new capability
checks and actual current validity deadlines/windows/budget. P+1 overlap/P+2
final and C+1 have overflow guards; two consecutive completed normal cycles
prove P+4 and C+2 with distinct batch/leaf hashes. No fresh-five issuer, unsigned
fallback, historical receipt replay, old plan reuse, clock change, claim/window
or lock bypass. Unknown or missed deadline BLOCKS; separately reviewed offline
recovery is a separate decision, never a ladder added here.

## Required consumers, proof producers and acceptance

`api-ownership-acceptance.json` lists every proposed API, owner boundary and
red/green seam. This is a task proposal only. Fixed request schemas exclude
arbitrary argv, command, caller worker root and force/skip controls. Actor
authentication/role/scope, live lease/OS locks, readback and idempotency are
checked in each public function, including nested adapters and children.

Required readers are new worker_peer_floor target/observe/context,
worker_plain_rotation target/floor/install/finalize, new leaf normal3 dispatch/
restart, new guard, CP inventory current-runtime endpoint and supported wrappers.
Each must read the exact new typed inventory/journal/fence/seal and check its
operation context or BLOCK. Legacy manifest/global agentImage fallback is
forbidden. Public candidate ABI support alone does not implement these readers.

Minimum closed proof contracts required before product acceptance are build/
image/source provenance; CI/attestation; reviewer authorization/verdict; Root
plan/execution/restoration authority; schedule/all-launch/in-flight descendant
readback; old/new no-write compatibility; volume-consumer/process quiescence;
protected-tree double-read/equality; owned Engine inspect/ExecID receipt; M2v2;
unchanged mTLS; CP inventory CAS/readback. Their schemas/verifiers must be
published and pinned in the future plan's canonicalContractSHA256 set, with
exact identity scope, signer role, byte encodings, freshness and test seams.
Absent any such contract is an explicit implementation/publication blocker,
not an opaque generic proof accepted by this proposal.

Green document fixtures prove structural schema behavior and explicitly named
static predicates only. Actual trust/signatures, OS locks, Engine effects,
filesystem atomicity, old/new Go no-write, mTLS, signed live M2, deadlines and
normal cycles are FUTURE NOT RUN. Red fixtures include wrong versions/roles,
unknown fields, second migration, overflow, UID/name/argv mismatch, missing
provenance, failed CI, wrong head, self-review, unsafe backup/lease and ambiguous
state. Source review/candidate hashes are not production evidence. Root's first
decision after independent review is whether to accept these contracts and
assign implementation; it is not a decision to execute on equipment.
