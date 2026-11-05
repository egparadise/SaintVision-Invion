# v5 unsigned derived-context proposal

Root chose the unsigned alternative in msg_c12b3f544036 after actual d2fab4a2
review: v4 Low closure ACCEPT is preserved; the signed cohort-set ABI was NOT
ACCEPTED for registration because of V4-M1. This v5 response remains DOCS-only.
No helper/API/runtime/registry/ADR/Node operation is implemented or authorized.
All actual target30/Root18/member/external trust bindings remain null/HOLD.
No real key/signature/RFC8032/Go/Engine/OS-lock/atomicity/equipment acceptance is
produced;40 future product cases remain NOT RUN. Actual separate code/native
evidence and all historical proposal verdicts remain unchanged.

## Classification, bytes and authority — V4-M1

`cohort-projection-set.schema.json` is a closed UNSIGNED record, not an envelope.
It has classification DERIVED_DIGEST and no body wrapper, signer, signature,
key, grant or producer-role field. Extra such fields are schema-rejected. It
is not an attestation, proof, trust anchor, lease or permission. There is no
aggregator signing role or signing-key custody. Root-fence retains only its
separately specified genuine mutation-fence/lease authority; in this scenario
only the three fence/lease records have that role. No root-fence key signs any
derived set or Node-produced state. The old v4 signed shape/domain is rejected,
not reinterpreted or registered as this new type.

The unique derived domain is ASCII
`saintvision/derived/migration-cohort-projection-set/v1` followed by ONE00 byte.
Digest = SHA256(domain || 00 || accepted strict C2 canonical record bytes).
The entire flat closed record is the body. No BOM/body newline, normalization,
float coercion or invalid UTF8/surrogate replacement. Transport newline is
outside the digest. C2 remains the accepted dedicated GoMarshal map encoding;
argv JSON/raw cmdline and all old signature protocols remain separate.
The digest never equals the plain envelope/data SHA256 definition by alias.
`derived-byte-ordering-vectors.json` publishes exact body/domain/message hex,
digests, key-order invariance and member-order/signature-field rejections.
Actual cross-language Go readers/verifiers remain future work, not run here.

## Producer, custody, verification and failure dataflow

The producer is any caller-side verification adapter operating under the
already authorized migration/renewal context. It collects separately
authenticated CURRENT member projections, the genuine operation lease/fence
context, and a separately verified fresh CP inventory-head readback. It then
computes this deterministic fingerprint locally. It does not ask a signing
service or expose any key. The bytes/digest may be cached or transported as
untrusted comparison data; neither producer identity nor storage confers trust.

A consuming verifier MUST independently obtain the expected registered cohort
and current sources from its original trusted configuration/context, before
deriving anything. Never use a supplied set to choose the Node, worker root,
daemon, tenant/epoch, signer key or authority to trust. For EACH complete member:
validate its original projection schema/domain/real signature and independently
registered Node/helper key-role-scope grant; verify exact current projection
head/history, plan/migration, owner/generation/lease, root/daemon/volume and
original immutable seal/authority context. Check both sources are current and
coherent at the owned/fenced snapshot. The current ordered PC2/PC4 scope vector
is fixed; missing, duplicate, third, reordered, stale, partial or ambiguous
member data BLOCKS. Do not choose a minimum sequence or a first member.

Verify the genuine lease/fence through its existing original authority and
current ownership context, including operation ID, epoch, exact lease bytes,
OS/logical ownership and phase. Verify the CP inventory head/readback through
its original pinned contract, authority and freshness; it is not authenticated
by this set. The record's inventoryHeadReadbackSHA256 is the exact external CP
source receipt ID from that independently verified input. The fixture uses
explicit untrusted receipt IDs also carried by the corresponding head proof
references; a real verifier must retrieve and authenticate those source bytes.
Missing source bytes/verifier/authority is BLOCK, even if a digest matches.

Only after those checks, construct the expected flat record from verified
sources, canonicalize and recompute its domain-separated digest. Compare every
context field/reference and the expected digest. A caller-supplied digest/set
is never sufficient evidence by itself, never a signature substitute and never
an authority shortcut. Signature or source/context/freshness/ownership failure
blocks before effects; no silent mirror, unsigned M2/normal-renewal fallback,
clock/claim/lock/window reset, old-binary restart, new issuer or offline ladder.
The unsigned view does not replace signed M2, signed original projections,
lease authority, CP readback, mTLS, guards or immutable plan pins.

## Complete context and API/journal use — V4-I1

Every record binds exact final plan envelope, migrationId, registered cohortId,
operationId, fenceEpoch, genuine lease envelope, current inventory head/readback,
sequence and the exact ordered COMPLETE two-member projection references with
their original scopes. These are identity/CAS comparisons, not independent
authority. The record after release explicitly names the genuine RELEASED
epoch1 fence even though member ownerLease fields are null; restore records
name the new HELD epoch2 lease and PRESENT inventory/readback. No context is
inferred from a null owner reference or supplied aggregate.

The proposed bootstrap API is now version2, with explicit distinct fields:

- Member request: expectedNodeProjectionEnvelopeSHA256 is that Node's signed
  projection envelope; expectedCohortProjectionSetDigestSHA256 is null.
- Cohort request: expectedNodeProjectionEnvelopeSHA256 is null;
  expectedCohortProjectionSetDigestSHA256 is the locally recomputed unsigned
  derived fingerprint. Only genuine both-journals-absent genesis inspection
  can have no prior set; all active cohort requests need the complete set.
- Responses likewise distinguish nodeProjectionEnvelopeSHA256 from
  cohortProjectionSetDigestSHA256. They remain transport data, never permission;
  sideEffectPermitted stays false. Block/conflict/initial read-only responses
  can lack a projection as the closed response schema specifies.

The old ambiguous expectedPriorProjectionSHA256/projectionEnvelopeSHA256 fields
are rejected by API:2; no version/shape fallback. Current journals keep their
own previousProjectionSHA256 and latestEvent as original signed Node history;
those fields never accept a derived set digest. Members inside a derived set
also reference original Node projection ENVELOPES. No PC2 stand-in for a cohort,
no unsigned object presented as a Node attestation. This is a proposed wire
revision before any registration/implementation, not a live API migration.

`scenario-objects.json` regenerates the full195-object/36-event scenario with
kind-aware digests and explicit context. The record after release is ordered
after the release fence dependency; its former signer rule is absent. Full
graph coverage and source-proof recipes are recomputed.432 context/lease/head/
epoch/member omission/duplication/reordering/cross-node cases fail even after
all dependent fields/hashes are rebound.44 old-field substitutions fail schema.

## Synthetic signer policy — V4-I2

The CURRENT scenario has115 signed-SHAPE envelopes (0 actual signatures
verified),44 transport messages,36 unsigned derived records, and112 structured
untrusted proof references (not112 verified signed proofs). Every explicit
current outer signer and proof-reference key/role matches
`dummy-signer-policy.json` and its Node/role/code scope. The derived records
have no entry in signing assignments or trust-role grants.

PC2/PC4 host-helper, Node-leaf and Node-scoped seal keys/identifiers are distinct.
Outer dummy signature bytes are distinct for every artifact/role/scope. They
are deterministic labelled bytes, NOT Ed25519 signatures; key hashes are dummy
identifiers, not invented production key provenance. The test mapping has
actualTrust=false/keysAreReal=false. It cannot provision or grant any real role.
Node projection/helper roles, genuine fence/lease roles, CP inventory/readback
roles and original Node leaf roles remain separate. Controller/cohort helper
log scope is explicitly distinct from a Node scope; it does not sign this
derived set.342 key/role/Node metadata swaps fail under recomputed hashes.
Actual RFC8032/key-custody/issuer verification remains a separate future gate.

## Original pre-prune evidence — V4-I3

The original v4 pre-prune synthetic seed DID survive as an immutable staged
Git blob. Recovery addressed only that self-authored synthetic content, without
an object-store scan/private-material search. Git blob
b8c66b46bf4c431c0d59b79941d2da868f2c523d was actually retrieved; its61973 bytes
hash to the recorded SHA256
51c0370462d40b021d46f906dbe362dcf5ac2ebdc4c1117083c402619d744c3e.
`preprune-recovery-audit.json` records the targeted commands and exact identity;
`recovered-original-preprune-seed.json` preserves the retrieved bytes. It is
HISTORICAL ORIGINAL v4 evidence, not a v5 signer-policy-positive or a production
configuration. Its old signer/aggregate mistakes are deliberately not edited.

`preprune-equivalence.json` compares all102 consumed input paths against the
published final v4 seed and publishes equal value hashes. This closes the
earlier unpublished-bytes limitation without labelling a guessed recreation
original. The v5 seed intentionally changes policy/context and is not covered
by that old equivalence. Validation/regeneration of final graph bytes/hashes is
separate from seed provenance and from actual cryptographic/runtime evidence.

All old reports, errors and actual closed Low results remain immutable. Source2fb
and all real state/keys/schedules/guard parameters/physical identities are
untouched. Root must review this exact revision, freeze/register only an actually
accepted canonical derived contract/domain/role separation, and separately
issue concrete code scope. No implementation or NodeOps follows from Docs CI.
