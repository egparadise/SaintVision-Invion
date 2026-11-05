# Nonexecuting v3 Low delta

This proposal inherits the immutable cb3/v2 design accepted by actual Claude
b47371c386c4786223acdad08fa7bd28d2d8ddba, with conditions N-L4/N-L5 and N-I1–I3.
The v1/f932 REVISION REQUIRED verdict, v2 proposal ACCEPT and803 plan ACCEPT
are preserved historically. v3 has no independent verdict yet. This is still
documentation: no registered product contract, implementation, signer/key,
equipment action, automation change, actual runtime proof or permission to run.
All target30/Root18/member/deployment trust bindings remain null/HOLD. Separate
P0 source/native evidence is neither erased nor used as contract registration.
This task ran0 Go/crypto/Engine/OS-lock/atomicity/equipment cases;40 future
bootstrap product cases remain NOT RUN.

## N-L4: prior and target rules are schema constraints

The v3 schema files are closed overlays of the exact immutable v2 schemas.
Inherited schemas retain all unknown-key/type/phase/signature-role/proof-slot
constraints. Offline validation must register the entire exact dependency
closure; the `.invalid` IDs are resource labels, never network trust discovery.
Unavailable/unregistered/digest-mismatched dependency BLOCKS. Actual future
deployment must pin these bytes outside the plan as required by M1; this
publication does not fill those deployment pins.

For each v2 method table row, an intent/readback priorPhase must be in that
row's priorPhases. An effect outcome requires priorPhase equal to the method's
intentPhase; a no-effect outcome uses priorPhases. Unsupported method/record
combinations remain forbidden by v2. Prior enum membership is a schema check;
the actual signed predecessor, its exact sequence/digest, ownership and effect
history remain mandatory verifier checks. Schema VALID never establishes them.

For a member effect (kind other than none), top-level targetSlot=PC2 requires
effect.targetSlot=PC2 and likewise forPC4. Cohort effects remain target=null.
No-effect member capture/verify records can name a member at the top level
while effect.targetSlot stays null. The supported API argument slot must match
the top target and exact registered scope in the semantic reader; schema does
not compare a different document's arguments. The published28 table-case
positives are schema/recipe cases, explicitly not complete signed histories.
577 off-table prior/target mutations are rejected at the schema layer.

## N-L5: executable recipe data and containing-source joins

`recipe-definitions.json` closes the declarative subject derivation language:
exact named-source JSON pointers, literal const, sha256C2 and sha256ArgvJSON.
Unknown operator/source/path or missing context BLOCKS. Every kind tag is literal
and included in scopeSHA256. The runtime verifier must obtain authenticated
referent/source bytes through the externally pinned verifier registry. These
document recipes are not executable helper code or a dynamically loaded plugin.

For every embedded reference, compute typedSubject from these sources and
compare every field, then recompute scopeSHA256. Do not compare to a stored
proof template. A changed subject plus recomputed hash remains invalid if the
containing source differs. `crossartifact-recipe-results.json` records87
embedded checks spanning all77 slots, and `recipe-negative-fixtures.json`
publishes501 altered-field cases with recomputed hashes. Actual cryptographic
verification, live source observation and full event-history replay are not run.

Context selection is deterministic. An inventory proof under members/i uses
that exact member's slot/currentContainer/volume and the same-slot plan input.
A member-progress proof under memberStates/i uses that exact memberState and
same-slot plan/current bindings. A terminal seal uses its own slot/body and the
same inventory member. An API proof uses arguments.slot and that exact registered
member; quiescence oldContainerId comes from arguments and must separately
equal the plan's exact old immutable ID. API newContainerId must equal the same
slot's current immutable ID. An effect proof uses the event's top-level target.
If a Node-specific recipe lacks one of these contexts, BLOCK; a first-member
default cannot supply missing identity. Cohort-only recipes do not read an
arbitrary Node alias.

The product alias is its containing acceptedP0/migrationHelper/commonFence/
runtimeInventoryAPI/schema3Helper/newRenewalGuard/target object, with the exact
canonical component mapping retained from v2. CI is its containing coreCI or
backendCI. `head` is the containing expectedInventoryHead or previousInventoryHead;
the publish API's arguments.expectedPriorInventoryHead uses that exact argument.
Both expected-head declarations must agree with the authenticated current head.
Plan/image are the exact final authenticated plan and accepted image. Progress
is the exact memberState, not a different Node's current stage. Event method,
recordKind, sequence, operationId, plan hash and effect fields come from that
same containing event. No old placeholder plan hash is retained in evidence.

The two approval references bind the reduced subject as before. The reserve
execution decision and all event/API/inventory/seal plan references bind the
actual final signed plan envelope hash. Inventory publishes both member records
under one metadata CAS. Both seal fixtures reference that exact inventory and
their own bootstrapVerifiedEvent/member/volume/current/backup. A restore lease
references both exact seals, has a new operation ID and fence epoch, and the
post-seal projection retains its exact lease digest. The post-seal unknown
projection follows the published predecessor by its exact envelope digest,
sequence21→22, with original seal origin20 retained. Sequence/order/digest joins
are static fixture checks; missing older complete signed chain is not accepted
as a real execution proof. All fixtures remain untrusted.

`synthetic-authoritative-facts.json` is explicit dummy producer-observation
input, separate from proof subjects. In production these sources must be
actual authenticated native/Root/Engine/nonce/process evidence under registered
contracts, not plan-selected expected values. Its fixture flag denies production
trust. Per-Node exec ID and serving container/daemon are distinct. Observer
commandSHA256 is derived from the published fixture observerArgv using the
ordered raw-UTF8 JSON-array encoding, distinct from C2 HTML escaping and raw
NUL cmdline hashes. The argv contains dummy paths/identities and is not an
operator command or a binary-bootstrap instruction. Runtime inspection derives
containerId/daemon/image/config/mounts from the containing currentContainer;
M2 derives scope/floor/authority from that exact member plus the explicit nonce
and accepted executable. It still gains no Node-signed image/container fields.
Node-floor signer key hash must equal that member's registered public SPKI;
code-review signer key must equal its containing reviewer's pinned SPKI. No
keys, certificates or private configuration were read/generated/recopied here.

The fixture policy's registered cohort/scopes must equal the containing cohort
and ordered plan scope vector. Actual trust is loaded outside the plan; the
synthetic policy is explicitly untrusted and cannot register anything. Missing
registered sources/verifiers always BLOCK before reserve or effects.

## N-I1–I3: operation, failure receipt and identifier semantics

A RESTART_RESTORE operation requires sealedHistory=true and one of the explicit
sealed/restore/blocked phases. At SEALED or RESTART_RESTORE_INTENT it requires
HELD lease. Unknown/failure retains the original seal and operation lease and
grants no effects. MIGRATION cannot have lease NONE/RELEASED; non-failure
migration stages require HELD, and blocked/unknown stages can retain HELD or
UNKNOWN. A released operation uses NONE and never clears the migration marker.
No restore is permitted in an early migration phase. The original retained
history predicate, fresh M2/mTLS and no-second-migration rules remain mandatory.

A failure record's effect receipt, if present, is an observed unknown/failed/
not-attempted receipt, never a successful outcome. Its typed outcome is exactly
unknown, known-failure or not-attempted. It cannot advance stage, authorize
retry, publish success or release ownership. Effect outcomes require
known-success; the actual prior intent/receipt/owner/history must still verify.
The failure fixture has an unknown receipt and remains QUIESCENCE_UNKNOWN;
a known-success substitution is schema-rejected even with a recomputed hash.

typedSubject containerId/oldContainerId/newContainerId/execId are strict64 lower
hex, like their corresponding IDs. Inspection point is literally before-M2 or
after-M2 according to kind. cohortId is a bounded opaque registered identifier
(1..256 Unicode scalars, no NUL), compared byte-for-byte with the externally
registered cohort; it is not reinterpreted as a container hex ID, case-folded,
or replaced with an arbitrary same-shape string. Tenant/Node/epoch stay the
original exact registered strings. Strict lexical/time readers, UTF8, domains,
RFC8032, external trust, all legacy denial/fence/retained-backup and G1–G10
requirements from v2 remain unchanged. No old binary restart, automation
reenable, floor/claim/lock/window/clock reset or offline-ladder expansion follows.
