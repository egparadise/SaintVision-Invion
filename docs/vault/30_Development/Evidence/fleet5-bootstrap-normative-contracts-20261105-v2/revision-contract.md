# Normative proposal v2: trust, proof slots and retained history

This is a NONEXECUTING contract proposal. v1/f932 remains an immutable
REVISION REQUIRED historical proposal;803 plan ACCEPT remains plan-level only.
This v2 directory is the complete proposed revision, not a registration,
implementation, signer provisioning, migration command or permission to operate.
Every actual target30/Root18/member envelope and out-of-band deployment binding
stays null/HOLD. This document task ran0 actual Go/crypto/Engine/lock/atomicity/runtime cases,
and40 future product cases remain NOT RUN. Synthetic policy and key hashes are
explicit document dummies, with no generated keys or verified signatures.
Root's separate P0 native proofs remain their own evidence; they are not
erased, rerun here or reused as acceptance of these proposed contracts.

## External authentication bootstrap — M1

Before accepting a plan, locate the installed reviewed helper/CP trust policy
and worker-root registration through a trusted external installation/registration
boundary. It pins exact trust anchors, allowed key roles and scope grants, all
supported artifact schemas, slot table, proof contracts and verifier source/
artifact/CI/review digests. Neither a plan nor its bundle can create, replace,
extend, revoke or select a different trust bootstrap. A caller cannot supply a
worker root, key, registry, plugin/verifier or bypass option. A process cannot
use unverified plan bytes to discover its own plan authentication key.

Authentication order is fixed in `trust-bootstrap-contract.json`. Verify the
external policy/registration and exact installed reviewed verifier bytes first.
Absent/unavailable/unregistered/mismatched/untrusted means BLOCK before plan
authentication, reserve, logical lease, journal intent or effects. Then strict
parse and verify the plan with the externally pinned root-plan key. The plan's
canonicalContractSHA256 can only select an exact already allowed registry
within that policy; matching a self-authored bundle registry is insufficient.
Each signing role includes externally authorized identity/scope grants, not
just a label or a matching hex hash. Node-leaf grants come from the unchanged
registered old cohort CA/identity, not a plan-created issuer. Other roles and
new signing capabilities remain unprovisioned here. Actual deployment policy,
anchors and registry bindings are null in `trust-bootstrap-contract.json`.

## Closed proof slots and scope derivation — M2

Generic `common.$defs.proof` is now false. Artifact/API schemas specialize every
proof reference with literal slotId, contractId, signatureDomainASCII,
producerRole, signerRole and a closed tagged typedSubject. No generic evidence
shape, dynamically loaded contract or attacker-chosen discriminator is allowed.
The external reviewed registry maps each slot to exact contract bytes and the
required reviewed verifier. Contract/source/artifact hashes in that installed
registry must match; proposed IDs in this directory do not register them.

`proof-slot-registry.json` is exhaustive:53 artifact paths plus24 method-specific
API paths =77 normalized slots. Every raw v1 ref is covered. Arrays use literal
`*` at each index; nullable proof is one slot; allOf refinements do not create
new slots. API method is part of the slotId, so another method's inventory-head
proof cannot be silently treated as the receiver's reference. This expands
beyond the review's56 phrase without omitting any underlying path. Empty or
optional event evidence has a standalone slot fixture too. Event member-progress,
effect-readback and event-evidence are three fixed contracts, with closed
subjects and reviewed state-specific verifier dispatch; they are not extension
bags or arbitrary acceptance of any evidence. Required stop/readback proof
cannot be substituted by an unrelated signed event note.

For each reference, retrieve the exact referenced bytes; parse its externally
pinned closed contract, verify strict signature/domain/key role and scope, and
recompute typedSubject using the slot's recipe and authoritative source below.
Compare ALL fields to the expected subject, then require
scopeSHA256 = SHA256(C2(typedSubject)), including its literal kind tag. The hash
alone is not a subject comparison. A maliciously changed subject with a newly
computed hash still fails. Metadata fields must equal authenticated referent
fields; metadata never adds authority that its signer did not prove.

Recipe aliases have exact meanings. `component` selects the containing product
object at its schema path; acceptedP0 and inventory.target both map to canonical
component `node-agent`. Other components are plain-migration-helper,
agent-mutation-fence, runtime-inventory-api, schema3-helper and renewal-guard.
`component.CI` is the containing coreCI/backendCI object. `image` is the plan's
accepted image or inventory image, with exact equality to the plan. `scope`
is the exact corresponding member input/seal/memberState/API arguments.slot,
matched by registered Node and slot, never a default first member. `plan` is
the authenticated exact final successor plan selected by request digest.
`request` is the exact authenticated IPC request bound by operation ID, current
lease and idempotency digest. A typed inventory-head subject derives presence,
envelope hash and registered cohort from the authenticated CP readback, with
both API expected-head copies required equal. Missing context is BLOCK.

M2 typed subject is derived from the actual signed floor body, certificate,
and fresh verifier nonce only. The Node's existing signature does NOT gain
container/daemon/plan fields: those joins require the separate owned runtime
inspection/ExecID slots. M2 schema/domain/servingExecutableSHA256 and raw
servingProcessSHA256 remain exactly v2 ABI; no wire change is implied here.
The actual serving PID must be1, actual journal UID must match, executable must
be the serving same executable, and no OpenJournal or sideloaded observer.

The two plan approval subjects have different kind tags and constant contracts:
independent-plan-review versus root-publication-intent. Both contain the exact
recomputed planSubjectSHA256, which still excludes exactly itself and those two
approval references. They cannot be swapped even though swapping does not
alter the subject digest. G2 planning-policy has its own fixed selection,
cohort digest and pretrusted registry digest, not a circular planSubject.
Reserve's root-execution-decision contains the FINAL signed plan envelope hash,
operationId and first migrationId. It is external to that envelope, not an
approval over the reduced plan subject. Cross-kind, cross-node, cross-epoch,
cross-component, stale-nonce, different-operation, different final envelope or
recomputed-foreign-subject reuse fails before effects.

Every row records producer and signer roles, constant domain plus00, exact
closed subject fields, freshness mode, permitted phases and required verifier.
Fresh proofs require actual observedAt<=validUntil, current trusted time within
the validity interval, age<=min(plan maxEvidenceAge,120s), future skew<=30s.
Immutable provenance is verified at its authenticated event time and against
current accepted publication/revocation state, not treated as a fresh live
measurement. Historical seal/inventory reads may authenticate old evidence
without satisfying a new operation's freshness gate. New renewal/restoration
requires a new nonce/current M2 and lease. No request clock override exists.
Plan review, publication intent and G2 selection are validity-bounded approvals:
their authenticated subject, nonrevocation, current validUntil and plan expiry
are mandatory; they are not fabricated live observations merely to meet120s.
Reserve's final-envelope execution decision and operational observations remain
fresh proofs. Neither approval mode can satisfy a current Node/process check.

Actual contract/verifier/source/CI/anchor bindings remain null. Unregistered
proof contract means BLOCK; the document fixture mock registry is not usable
as installation trust. Proof slot fixture tests check shape, fixed metadata,
typed subject and hash consistency against explicit dummy expected values;
they do not perform cryptographic or live verification.

## Stop outcome and method table — L3/L4/I3

`state-machine.json` is the normative closed method/prior/intent/outcome/effect
table. OLD_RESTART_NO means the exact original container still may be running.
stopOld durably records OLD_STOP_INTENT before the stop effect, then requires
actual process/descendant quiescence and exact stopped ID/daemon/volume/lease
readback before OLD_STOPPED_QUIESCENT. captureFenced accepts only that exact
stop-outcome predecessor and matching quiescence proof. Restart=no, a generic
OLD_FENCED label, heartbeat absence or a stopped boolean alone cannot qualify.
Both old restart=no readbacks precede the first stop; PC2 verification precedes
PC4 stop; first-member failure blocks second-member cutover.

Create, inventory, seal and restore now also have named intent phases. Event
method, recordKind, priorPhase, phase, top-level targetSlot and effect.kind are
bound by schema/table. Member effects' target must match the top-level target
and exact API argument slot; cohort effects have target=null. The no-effect
capture/verify methods still bind their top-level member target. Effects require
durable exact prior intent; effect outcomes require the authenticated receipt
and intent digest. Intent has neither its own digest nor a predicted receipt.
No-effect records have no effect receipt or effect intent hash.

Inventory refs are null before actual inventory publication. Seal refs are
null before actual sealing. Published-history flags require exact hashes and
must equal authenticated predecessor history, never caller declarations.
Early phases cannot set them true. A failure from any phase becomes
BLOCKED_FORWARD_ONLY or QUIESCENCE_UNKNOWN; a repeated failure observation may
remain in that blocked phase. This is explicitly recordKind=failure, never an
intent/outcome or replayed effect. Same-phase intent/readback allowances do not
exclude a failure record or permit arbitrary advancement. The exact table and
verified predecessor, not one enum field, authorize a transition.

## Retain seals through post-seal failure — M3

The projection carries sealedHistory and sealOriginEvent. Once authenticated
history contains a SEALED event, sealedHistory remains true, original
terminalSealEnvelopeSHA256 and sealOriginEvent are required and must remain
byte-identical in every later projection, including blocked/unknown states.
Schema checks shape/conditional presence; the history verifier compares original
values and rejects a fabricated false flag, replaced seal, dropped history or
new migration. The current protected state may later evolve only under an
approved normal3 plan; no requirement equates current floor/cert to bootstrap.

operationKind is MIGRATION, RESTART_RESTORE or NONE. leaseState HELD/UNKNOWN
requires the exact active operation lease digest; NONE/RELEASED requires null.
UNKNOWN retains the original lease reference but grants no permission to mutate.
NONE cannot claim HELD/UNKNOWN. A terminal migration journal does not require an
eternal held migration lease. A separately approved restart-policy restore has
a NEW operation lease and can fail after seal while preserving that seal.
Quiescence/ownership uncertainty blocks; no old-owner/lease/token/marker reset.
Normal3 uses a new common lease referencing immutable original seals; it does
not overwrite or turn the first migration into a second migration.

## Strict readers, time and signatures — L1/L2/I2

Before schema evaluation, all new protocol readers enforce strict UTF8, reject
duplicates/surrogates/nonfinite values and inspect numeric TOKENS. Only lexical
`0` or `-?[1-9][0-9]*` is an integer token; specifically reject -0, decimal point
and exponent even if mathematically integral:1.0,1e0,1E2. Then apply bounded
typed field checks; a bool is never an int. Python parse_int rejects -0;
parse_float/parse_constant always reject, with duplicate-aware object parsing
and exact type checks. Go uses Decoder.UseNumber, validates each json.Number
against that token grammar BEFORE ParseInt/range conversion, rejects duplicate
keys via strict token reader and checks EOF. Never decode through float64 or
rely on JSON Schema integer semantics for lexical type. Strings containing
numeric-looking text remain strings and must satisfy their typed field.

Every timestamp requires real strict RFC3339 parsing AND exact UTC whole-second
roundtrip, not only a regex or a Draft2020 format annotation. Go time.Parse
plus exact Format roundtrip and Python strict datetime parse/roundtrip enforce
valid calendar days/hours/minutes/seconds, reject leap seconds, invalid dates,
offset aliases and rollover. Runtime freshness uses actual trusted clocks;
fixtures use only explicit synthetic fixture instants, never a live override.

Ed25519 verification is strict RFC8032 pure Ed25519, no prehash/context variant:
32-byte public key,64-byte signature, canonical compressed A/R encodings,
on-curve prime-order nonidentity points, S<L with no modular normalization,
strict verification equation and no accepted small-order/noncanonical points.
Use a separately reviewed strict verifier and actual cross-language adversarial
tests before product acceptance. Hex shape is not verification. envelopeSHA256
covers exact signature bytes; another encoding/altered signature never aliases
an existing event or wins no-overwrite publication. Conflicting bytes fail
closed, preserving both observed evidence and original immutable publication.
No keys or signatures are generated by this documentation task.

## Lock order and fixture scope — I1/L5

After external authentication, acquire both registered OS locks PC2 thenPC4
in fixed daemon/worker-root order, then durable logical lease CAS against the
exact prior fence while locks remain held. No mutation until both are held and
read back. On conflict, prove no effects/children before releasing only this
attempt's newly acquired locks. Release stops new children, proves all child
quiescence, writes durable RELEASED logical CAS under the locks, then releases
OS locks PC4 thenPC2. A crash/unknown owner grants no takeover.

Nested calls use only trusted in-process/child context with matching live
operation, owner generation, token hash, OS-lock registry and reference count.
They do not reacquire, upgrade, steal or accept a caller's owned=true assertion.
Different owner or order inversion blocks. Public direct entrypoints revalidate
the same context; legacy raw paths remain excluded under G9.

Positive seal/inventory fixtures now have the same daemon for old/current,
distinct IDs and literal Names, old backup restart=no, current accepted image,
same exact volume and authority, and consistent slot/scope. The document checker
verifies these concrete S05 bindings against the fixture plan/inventory/seal,
not only restart policy. It cannot prove actual runtime/crypto/provenance and
labels that boundary explicitly. All real deployment bindings remain null.
