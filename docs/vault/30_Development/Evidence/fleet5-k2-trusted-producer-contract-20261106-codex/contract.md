# K2 trusted producers and effect boundary — proposal 1

Status: DESIGN_PROPOSAL_REVIEW_REQUIRED. Owner Codex. Independent reviewer is
future Claude through Root. This document grants no code, installation, key,
runtime or operational authority. All actual deployment bindings are null/HOLD.
Source for code statements is exact eb32b211ab3704935b9431747089ab0715582a74;
source-inspection.json pins the reviewed files, symbols and raw hashes.

## 1. Reverse goal and acceptance

Goal: a real application can authenticate every input it passes to K1, and no
effect can treat a successful offline verification as permission to mutate.
Acceptance requires independently provisioned public trust, original authenticated
history, independently acquired current state, current authorization and a fully
mediated effect boundary. Missing authority must produce a refusal with zero
effects, rather than a guessed default or a promoted fixture.

| Evidence required | Contract | Work / one owner |
| --- | --- | --- |
| Complete mapping of all73 declared fields in13 NewVerifier input types | producer-matrix.json and source-field inventory | K2A contract / Codex |
| Independent installation, grants, publication and history provenance | sections2–4; installed-bindings-HOLD.json | K2A-TRUST / Codex |
| Exact current cohort, version, head and two live witnesses | sections4–5 | K2A-CURRENT / Codex |
| Read-only adapter has no signer, nonce allocator, lock writer or Engine exec | section5 and static refusal fixtures | K2A-ASSEMBLY / Codex |
| Exact durable intents, mandatory fences and before/after readbacks | section6; no executable adapter here | K2B-EFFECTS / Codex after separate grant |
| Original A01–A40 red/green cases actually execute in an isolated test environment | future-runtime-A01-A40.json | Future implementation / Codex; currently all NOT_RUN |
| Independent contract verdict and exact target | One actual Claude review assigned by Root | Review / Claude; assignment decision / Root |

The static coverage check is not a live producer, crypto proof, installation or
runtime test. It does not alter the48-task/VFCL denominator or calculate a new
completion percentage.

## 2. What exists and what remains missing

At eb32, the sole non-test Go occurrence of NewVerifier is its definition in
migrationverify/trust.go. K1 is a pure verifier. It checks formatting, pinned
contracts, role/scope/key signatures, original consuming times and causal joins;
it cannot establish whether the application truthfully acquired its trusted
arguments. Neither a correct type, a file name, a hash, a role label nor a
self-issued test key installs trust.

Existing partial mechanisms are reusable within their actual scope:

* node_channels.py certificate_identity, NodeChannels.snapshot and assert_channel
  bind operator-provisioned channels to tenant/Node/epoch, DER fingerprint,
  enabled/version and validity. They do not implement a migration publication
  registry, all-role grant registry, CA revocation service or cohort fence.
* leases.py fences ordinary execution allocations. Its job/resource fences are
  not a registered root-fence migration authority and must not be cast as one.
* inv-node's exclusive --observe-peer-policy-floor dispatch precedes OpenJournal.
  transport.ObservePeerPolicyFloor uses the unchanged Node key internally,
  rechecks DER/key/floor/process/executable, and signs original M2 v2 bytes.
  This does not grant a migration operation or authorize Docker Exec creation.
* worker_config.no_migration refuses any terminal/nonterminal migration marker.
  worker_plain_rotation SF1 and RS1 implement narrowly bounded settled-state
  verification and same-stopped-container start. They are not a migration
  bypass, common cohort lease or new image installation permission.
* The v5 operation/API/head/common-fence documents are normative proposal inputs,
  not deployed endpoints. The older common-fence contract explicitly says
  NEW_CODE_CONTRACT_NOT_IMPLEMENTED_OR_ACCEPTED. No unaccepted B coexistence or
  rev6 protocol is a dependency of this K2 proposal.

producer-matrix.json separates each existing file/API from the missing producer,
its independent authentication, containing transaction, readback and refusal.
existing-proof-contract-catalog.json preserves all28 descriptors and their exact
producer/signer/domain/codec/freshness bindings. Twenty-seven normalized proof
contracts and the one original native codec remain unchanged; no new wire,
signer or signature domain is declared accepted here.

## 3. Independent installation and publication authority

Proposed K2A LoadInstalledPolicy accepts an opaque deployment selector, resolved
only through a preprovisioned worker-root/CP registry. It accepts no caller path,
bundle-supplied trust root, runtime callback, alternate codec or trust-update flag.
Root must separately provision public anchors, exact role/SPKI/scope/interval
grants and the registry's authentic transport/storage authority through the
existing operator custody process. Custody, CA/offline policy, actual Root
readiness and installation receipt remain null/HOLD. A file owned by root is
necessary storage hygiene, not sufficient provenance or authorization.

The future installed record binds registry version/raw bytes, ordered old
PC2/PC4 identity scopes and public DER/CA, registered v5 graph/raw hash/NodeKinds,
all28 contract/schema/codec/verifier pins, and an exact verifier publication.
Registration cannot be learned from the plan being checked. Source pins preserve
design8874b2df, review6b12d3ab and Root registration raw SHA256
a0a05427c40499ac32e52c58982a84bceb4b4e833b68c601f9373d93d80aa562.
They are an implementation baseline; that hash alone does not authenticate an
installed registry or its owner.

Verifier publication acquisition must resolve the configured repository and
workflow path through an authenticated, independently configured provider.
It binds exact commit/head/ref/event/correlation/runAttempt/jobs/required steps,
original artifact ID/digest/bytes and compiled binary VCS/toolchain metadata.
It reads the actual independent review at its immutable commit, verifies its
target/scope/verdict through a separately granted reviewer identity, and binds
Root's actual source-choice decision. Arbitrary review JSON, a green workflow
name or an unsigned copy of a CI response is not permission. The future signed
attestation producer must issue the existing fixed proof contract only after
that acquisition; it cannot attest supplied metadata on demand.

For K1 specifically, actual Claude191b6f843a643ee4989ce28c9ebf1816963ffe28,
Docs42132923864 accepted corrected Go56651cba. Git byte comparison shows eb32's
only migrationverify change is README; its other non-document changes are the
reviewed rate test, proof helper and focused workflow. Root independently
accepted that delta and selected eb32 in msg_4f741ef0872c. Actual eb32 Core
42138733821/all2jobs SUCCESS and sourceDocs42137296076, qualified report f28fb41d
and its Docs42142783600, and bounded Root acceptance msg_f96802b15040 close the
K1 code/report axis only. K2 must authenticate the management decision's actual
published identity and scope, not trust these strings because a packet repeats
them. Source-inspection and K1-provenance-reference.json retain exact hashes.
The failed old56651 Core42126222201 stays FAILURE; its historical cause remains
unproven. No CI/proof/archive is rerun by this task.

The frozen e50 durable packet predates K1. Installing it cannot install or claim
eb32's verifier. Future packaging work must build a separately versioned K2
artifact from reviewed eb32 or a reviewed successor, bind executable/module
closure/image config/layers/platform/archive, preserve the five helper modules
plus launcher+lock seven-file closure, and register exact source/runtime-lock/
manifest/review/CI hashes. No archive is rebuilt/replaced here. Current CI
inv-node hash2aa70e1f42992790700a53b0989dfa1800785227021de9f7b0e13436be33fb8a
is an observed test artifact, not an installed/approved K2 target. The eventual
rollback contract must preserve data/floors and forbid automatic old-image
restart; a new post-pin recovery policy requires separate review.

The seven-file closure is the exact eb32 baseline, not permission to carry its
old hashes across changed or added K2 modules. Every later closure change needs
new reviewed pins/manifest/source provenance. Because K1 has no product caller,
an inv-node binary's eb32 VCS revision alone does not establish that a usable
K1/K2 application path is linked or installed. The future reviewed package must
include and test that actual integration entrypoint, then bind its own executable
and installation receipt; this task builds none.

Key grants are independently versioned role+exact C2 authority scope+DER-SPKI
bindings. Current registration status must be ACTIVE, with the original
NotBefore/NotAfter preserved. A historically valid signature can outlive that
signing interval if current independent registration still permits its history;
no current signing privilege is inferred. A revoked registration, unknown
authority or signature outside its original interval fails closed. Node leaf
grants also require exact DER, old Node URI/epoch, explicit ServerAuth and
DigitalSignature, and current certificate nonrevocation. A channel being enabled
is insufficient to prove all CA/leaf revocation facts.

Scope classes remain K1's exact COHORT (cohortId plus ordered complete members),
NODE (tenantId/nodeId/recoveryEpoch), and COMPONENT identities. Outer kind roles
stay root-plan, host-helper, root-seal, root-fence and cp-inventory as pinned in
verify.go; proof roles/domains remain the28 catalog entries. DER SubjectPublicKeyInfo
hashes are not raw public-key hashes. K2 must acquire scope and grant before
accepting a signer identity, rather than use a valid signature to register itself.

## 4. History, current publication, clock and replay

HistoricalContext must come from an authenticated append-only operation/challenge
archive whose entries bind the original HELD lease raw hash, identity, migration,
operation, cohort fence and acquired/expiry interval. Original nonce issuance,
scope hash and issue/expiry survive release. RELEASED state does not cause an
ended epoch to be fabricated as a current operation. History reads grant no new
lease. Missing archived entries are UNKNOWN/HOLD, not reconstructed from packet
fields or fresh signatures.

Consuming times remain K1-derived from original signed records/events:
plan.createdAt; migration-event.recordedAt; inventory.publishedAt; seal.sealedAt;
HELD.acquiredAt; the earliest exact signed API request event; the journal's exact
latest event; or the exact RELEASED release-outcome event. All signatures and
causal graph joins must authenticate. K2 supplies no alternate consuming-time
override and does not backdate Now or increase age. A copied historical M2 is
AUTHENTICATED_ORIGINAL_NATIVE_HISTORY_NOT_FRESH_PROOF, not a current witness.

Offline signatures cannot prove that an authorized key did not backdate a new
signature. The residual remains explicit. K2 adds independent current grant/
publication/certificate status and historical time anchors from the authentic
publication/operation/event ledgers. PublicationStatus binds exact raw referent
hash, subject hash, authentic original PublishedAt and current CheckedAt/ExpiresAt.
The ledger must preserve independently anchored publication/commit order and
graph-time joins; a signer-provided date alone is insufficient. Without that
independent authority, even well-formed signed history remains HOLD for use.
Retired/revoked/missing records cannot be re-created as accepted publications.

Current facts are acquired independently of packet contents at a real current
clock observation. Existing K1 maximum evidence age is min(plan age,120s), with
its existing30s proof skew; strict expiry is exclusive. Current publication and
certificate status cannot be future-checked, older than120s or expired. Current
M2's effective end is the minimum of observation+allowed age, certificate end,
plan end and current HELD lease end. The Node did not sign this derived end.
Current challenges must be issued no later than realNow and expire strictly
after it; the original signed nonce and Node/cohort/operation/fence must match.

Proposed TrustedClockSource reads only an independently installed approved time
authority and local monotonic bracketing. An arbitrary OS UTC value or caller
Now is not authenticated time. The snapshot carries an uncertainty interval and
clock source/version; collection restart, rollback, discontinuity or disagreement
refuses CLOCK_UNTRUSTED. Proposed maximum uncertainty is1s, pending Root decision
D-CLOCK; it is not borrowed from30s proof skew. K2 must conservatively validate
the entire realNow interval against every lower/upper bound and freshness limit,
then pass the actual UTC observation to K1. It cannot choose an optimistic past
endpoint to keep a proof alive. Accepted clock source/bound is null/HOLD until
provisioned and reviewed. No clock is changed in planning or implementation tests
outside explicit synthetic fixtures.

Fresh challenge allocation, reservation and nonce consumption are authority
writes and belong to K2B's control path, not a read-only K2A acquisition. K2A
reads already authenticated issuance rows. Repeating a read returns the same
content/version or STALE_SNAPSHOT, with no new nonce, counter or timestamp that
pretends to extend validity. A challenge is bound to operation/scope/fence and
one bounded observation attempt; using its signed witness in another operation,
generation, slot, expiry window or effect intent is REPLAY_OR_SCOPE_MISMATCH.
Effect replay is additionally controlled by durable idempotent intent state.

## 5. K2A acquisition, snapshot assembly and current derivation

Proposed internal interfaces are typed service boundaries, not new wire formats:

* LoadInstalledPolicy(selector) -> AuthenticatedInstalledPolicy or TRUST_UNKNOWN.
* ReadHistory(scope, hashes, versions) -> AuthenticatedHistorySnapshot.
* ReadCurrent(scope, expectedVersion) -> AuthenticatedCurrentSnapshot.
* Assemble(policy, history, current, clock) -> verifier inputs + SnapshotToken.
* ValidateHistory(packet, snapshot) -> HistoryReport; no effect capability.
* DeriveCurrent(packet, snapshot) -> CurrentView + SnapshotToken, or refusal.

Untrusted requests may nominate an object/scope already allowed by policy; they
cannot create any of these authenticated DTOs, inject Now, install keys, override
version checks or supply the verifier implementation. Constructors stay behind
the future reviewed K2A package. DTO ownership is exclusive while copying; callers
must not mutate maps/slices during construction. K1's defensive copy does not
prove safety of concurrent uncoordinated mutations.

SnapshotToken is a proposed non-authorizing internal value containing installed
registry/grants/publication/certificate versions, cohort key, currentVersion,
active migration/operation/HELD hash/fence/maximum sequence, head and two ordered
member hashes, node process/container generations, challenge versions, clock
interval and a digest of the authenticated input bytes. A digest is a change
detector, not a signer or capability. No such DTO/API is deployed at eb32.

Proposed acquisition sequence: read authenticated control snapshot V0 in a short
read transaction; finish/close it; perform permitted bounded immutable/public
reads without DB locks; read fresh independent current statuses/clock; read V1
in another short transaction. V0 and V1 must match every monotone version and
identity binding. Otherwise discard the assembled candidate and return
STALE_SNAPSHOT, without silently retrying or recategorizing stale evidence.
No network/SSH/Engine/signing/filesystem traversal occurs behind held DB row
locks. Read-only adapters cannot reserve names, allocate nonces, create locks or
temporary files in runtime state, call OpenJournal/pin, sign, or start Docker
exec. Already recorded original native bytes can be acquired and authenticated;
obtaining a new witness via Engine Exec requires separate K2B authority.

Current requires the independently authenticated PRESENT inventory head/readback,
exact current HELD lease and its real window, latest authenticated sequence and
two original ordered PC2/PC4 member projections. Both current native witnesses
must match independently measured, currently owned executable/PID/UID/argv/
journal identity/floor/policy/certificate scope and the current issued nonce.
Expected native state comes from the authenticated head's declaration and
typed recipes; recipe values do not become measurements. M2 cannot itself prove
its host root, daemon, Engine ExecID, container/image/config/layers or CP head.
Those require separate owned before/during/after inspections, exact ExecCreate
ID before start, ExecInspect completion/exit0 and stable PID/start generation.
Read-only K2A consumes those authenticated records; it does not run their producers.
The future typed per-Node runtime inventory API remains missing. Global CP
state.agentImage and CLI --image are not proof of the installed Node runtime
image; the latter is the allowed workload image. No producer may silently
rewrite either value to hide that missing typed inventory/consumer contract.

R2: K1 latestCurrent compares authenticated history within one migration/plan.
K2 must independently read the common cohort's current migration, maximum fence
epoch and sequence, including other migrations, from one authoritative registry.
Its key is the complete ordered tenant/Node/recoveryEpoch vector and cohort,
not migrationId alone. A higher epoch, RELEASED owner, different active migration,
changed head/sequence/grants/identity or partial member causes a refusal. Generic
execution leases do not supply this registry. An uncoordinated writer cannot be
made safe by merely reading twice; every permitted mutator must participate in
the same mandatory fence and operator mediation.
The sequence is the maximum for the selected active operation, qualified by
cohort fenceEpoch, migrationId and operationId. Sequence numbers from different
operations are not compared as one unqualified global counter; the cohort epoch
and currentVersion establish supersession across migrations.

### ABSENT bootstrap boundary and named decision D-PREPUBLICATION

K1 current derivation with ABSENT head is closed, even if an old signed witness
is relabeled fresh. There is no authenticated head declaration of expected
native state. K2A can read public installation metadata and authenticate history
without producing a current view; it must return NO_CURRENT_HEAD for a request
to derive one.

Proposed default: all pre-publication K2 effects, including reserve, challenge
issuance, new-start and observation ExecCreate, remain BLOCKED pending
D-PREPUBLICATION. The older A36/operation-lease/new-start-intent proposal suggests
a separate phase-scoped authority, but it is not an existing implemented grant.
Root must choose and independently review its closed contract before K2B:
exact installed trust + root-plan/execution authorization + ordered two-scope
reservation + original HELD migration lease + exact new-start intent/preimage +
mandatory common fence + owned generation/permission. Its result must be named
BootstrapPhaseAuthorization, valid only for the specified next bootstrap method;
it is never CurrentView and cannot authorize normal renewal or inventory publish.
The initial expected state/counter/set and phase transition evidence must be
specified separately without weakening K1 or extending its schemas. A method
whose required evidence has not been decided remains BLOCKED; no generic
allow-prepublication boolean is proposed. This proposal does not invent the
missing approval or recursively require the head that bootstrap will create.

## 6. K2B effects, durable intent and failure behavior

There is no K2B implementation or effect grant in this task. Proposed interfaces:
AuthorizeEffect(method, immutableRequest, SnapshotToken, independentCapability)
and ExecuteOwnedIntent(intentID). Their error/result types distinguish
REFUSED_NO_EFFECT, INTENT_COMMITTED, EFFECT_OUTCOME_UNKNOWN,
READBACK_VERIFIED and BLOCKED_FORWARD_ONLY. A bool, successful digest or history
report cannot be cast to an independentCapability. The exact method and plan,
caller permission/custody scope, owning root/daemon/volume/Node generation and
source/helper/guard/runtime publication must be authorized independently.

Before any effect: re-acquire current authenticated state and realNow, reverify
K1 current where available, compare every SnapshotToken version, acquire the
mandatory shared cohort reservation and owned OS locks in fixed PC2 then PC4
order, verify all launch surfaces are fenced/excluded, and check capability
expiry/operator window/safety budget. If the method is prepublication, only the
separately approved D-PREPUBLICATION authority can replace the unavailable
current view for that named method. No permission is inferred from source CI.

Proposed durable intent binds method, operation, cohort fence, scope, exact
request digest, expected currentVersion/prior event, preimage and expected
postimage, owned object IDs/names/generations, original publication decision,
deadline, actor and idempotency key. Commit intent and version CAS in one short
authority transaction before issuing any side effect; fsync the private owned
local intent chain before host effects. Preserve original hashes/receipts.
An intent ID reused with different bytes is IDEMPOTENCY_COLLISION. A completed
same-byte intent may return its immutable recorded outcome after current safety
checks; a pending/ambiguous intent may only reconcile the exact owned attempt,
never automatically execute again. No blanket exactly-once external-effect claim.

Release DB locks before Engine/SSH/issuer/host/file I/O; keep the mandatory
logical owner and local OS guard through effect and readback. Immediately before
the actual adapter admission, recheck permission, fence/window/clock and owned
preimage/current generation. Every mutator and child must enforce the same
capability/fence; bypassable raw/unpatched launch paths keep HOLD. A lease timeout
alone never transfers ownership while an in-flight or unknown intent exists.
Root-mediated reconciliation must establish actual quiescence before takeover.
Stale generations cannot publish a result under a new owner.

After an effect, re-read exact owned postimage/process/volume consumers and
authenticated current authority. Commit the chained outcome and version CAS
only on matching readback. REFUSED_NO_EFFECT means before the first authority,
intent-journal or external write. After intent commit, even a proven adapter
refusal retains INTENT_COMMITTED and the original durable record; it cannot be
reported as zero writes or silently executed again. A failure before any write
preserves REFUSED_NO_EFFECT;
timeout, crash, lost response, partial readback or changed owner after possible
effect preserves EFFECT_OUTCOME_UNKNOWN/BLOCKED_FORWARD_ONLY. Do not blindly
retry, clear a lock/phase, delete a Node/volume/backup or restart the old image.
Old backup remains retained, stopped and restart=no. Restoration of the new
container's unless-stopped policy requires actual mTLS+fresh M2+unchanged authority
and a separately authorized exact method/readback. New-image running/heartbeat
alone is insufficient.

P is peer-policy generation, H its exact policy hash, C channel generation and R
the old Node recoveryEpoch. Binary-only bootstrap preserves P/H/C/R/keys/CA and
the storage-free runtime profile. Later accepted plain normal-v2/schema3/M2
renewal uses P -> P+1 overlap -> P+2 final and C -> C+1 for each cycle, then
P+3/P+4 and C+2 for the next; equal-version different-hash is refused and R never
changes. Migration fenceEpoch is distinct from P, C and R. SF1 does not permit
image/profile migration; RS1 permits only the same stopped owned container and
never promotes its unsigned volume read to a fresh witness. None is an offline
CA ladder, rollback-floor reset or lease/window bypass.

## 7. Implementation dependency graph and red/green evidence

Every work item is PLANNED and requires an explicit later implementation scope.
Owner is singular; reviewers do not manufacture the owner's evidence.

| Item | Depends on | One owner | Deliverable / gate |
| --- | --- | --- | --- |
| D-ROOT | Actual Claude contract verdict | Root | Decide D-PREPUBLICATION, D-CLOCK, trusted registry/custody/source installation and mandatory fence authority; missing stays HOLD |
| K2A-TRUST | D-ROOT read-only grant | Codex | Independently authenticated installed-policy/publication/grant/history readers; no signer/effect |
| K2A-CURRENT | K2A-TRUST | Codex | Authenticated current statuses, cohort-wide versions/head, clock and recorded original witnesses |
| K2A-ASSEMBLY | K2A-CURRENT | Codex | Closed non-forgeable input assembly, read snapshots, TOCTOU refusal, K1 integration and negative tests |
| A-REVIEW | Exact K2A code/CI | Claude | Actual independent read-only code verdict; no effect scope implied |
| K2B-PHASE | A-REVIEW + D-PREPUBLICATION + separate effect grant | Codex | Closed phase authorization, nonce allocation/reservations/intent authority and all mutator mediation |
| K2B-EFFECTS | K2B-PHASE | Codex | Exact owned adapters, durable intent/readback/reconciliation and crash boundaries |
| B-REVIEW | Actual effect code/isolated evidence | Claude | Actual independent effect boundary review |
| INSTALL | B-REVIEW + actual resources/custody/operator readiness | Root | Separate reviewed packaging/trust provisioning and operational acceptance; not granted here |

future-runtime-A01-A40.json preserves all original IDs and original red/green
texts from design8874's acceptance-matrix.json and adds explicit dependency,
mutant purpose and future isolated permissions. Every case remains NOT_RUN with
null execution evidence, including cases with previously reported component
subproofs. Planned tests must kill the original red alternative and execute its
paired green without skips; static success cannot satisfy them. Additional K2A
normative examples cover unknown trust, revocation, expiry/backdating, replay,
wrong artifact/review scope, cross-migration fence, ABSENT head/current witness,
clock uncertainty and TOCTOU. They are symbolic decisions, not crypto vectors.

Future isolated test permissions must be scoped to synthetic tenant/Node IDs,
ephemeral fixture keys, owned temporary PG/Engine resources and fixture clocks;
no production DSN/private PKI/host writes. A runtime test report must bind exact
code, fixture identities, service versions, permissions, before/after state,
artifact hashes, exit and executed red/green results. Existing K1 CI is not
rerun or borrowed as the new K2 implementation's CI.

## 8. Operational HOLD and concrete next action

Engine capability remains API>=1.45 versus reported Docker5 API1.41. Do not silently
negotiate below the required capability. A separate-kernel Linux VM is
RESOURCE_UNAVAILABLE under the reported97%/482MiB snapshot; no current resource
remeasurement or VM grant is inferred. PC1/PC3 authentication/group readiness
remains unknown until actual feedback. Old two-Node identity scopes remain the
old cohort, never new all-five issuer identities. Historical leaf deadlines
must be remeasured privately by Root before operations; unknown/elapsed windows
block and require separate offline review, never clock/claim/lock bypass.

Next: Root assigns one actual Claude review of this immutable proposal and exact
Docs. No K2 code grant is implied. After the actual verdict, Root chooses the
named decisions and grants a small read-only implementation scope first; the
effectful stage requires its own reviewed contract/code grant. Physical five-PC,
B contract acceptance and whole-program100% remain incomplete.
