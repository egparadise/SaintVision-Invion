# H1/H2 authority contract candidate

Status: PROPOSED_UNREVIEWED_CONTRACT. Root selected logical policies in
msg_10808c1899e9; actual external bindings are UNBOUND/HOLD. Owner Codex,
future independent Claude contract review through Root. This is one finite
DESIGN-only contract; it installs no authority and changes no product bytes.

## State and authority boundary

The five distinct states are SELECTED_LOGICAL_POLICY (Root choices1-5),
PROPOSED_UNREVIEWED_CONTRACT (this document), ACTUAL_UNBOUND/HOLD (all real
bindings), future separately authorized code, and actual installed/runtime states
requiring fresh evidence. Neither contract acceptance, CI, a typed value, file
ownership/mode/path, project IP, raw hash, role label nor a candidate's signature
bridges those states. No generic plugin/provider/callback or caller trust-update
option is introduced. Existing public TrustUnknown/default refusal stays fixed.

The external bootstrap TCB is ONE project/control-plane-scoped TrustProvisioner
boundary, independently selected by Root custody outside the candidate, package,
caller, installer artifact and registry signer. Its finite required binding is:
project/control-plane identity; provisioning authority identity and authenticated
delivery mechanism; provenance of public anchors; approved registry and locator
identity; authenticator/source-closure identity; and current-status/clock authority
identities. Every actual value is NULL. Naming this slot is not authenticating it.
The implementation must refuse while any binding or wire registration is absent;
it cannot learn them by reading the descriptor it is trying to trust.

The TrustProvisioner owns the independently authenticated policy release and
installation assertion. Root/custodian authorizes its binding and policy; H1
installer later implements delivery/readback under a separate grant. H2 owns the
fixed-purpose record verifier under that installed authorization. Status and clock
sources own their original authenticated assertions, not the registry response.
H3-EA remains a downstream origin/scope dependency, not redesigned here.

`authority-fields.json` is the closed field-origin matrix:26exact p02Capsule
members, every nested source member and23H2 policy slots. Every value has an
independent origin identity, authorizer, immutable origin and subject join.
Dynamic maps are complete authorized maps, not wildcards. All new sidecar slots
are proposed logical records, NOT added wire fields, accepted K1 roles or schemas.

## H1 custody, installation and refresh

Resolve an opaque installed locator only in the Root-bound project registry.
Never accept a caller path, endpoint, key, callback, source pin or bootstrap
version. The immutable delivery assertion must authenticate the independent
provisioner, project/component/registry subject, delivery ID and original capture/
publication identity/time, exact policy/capsule raw hash, generation, anchorVersion,
authorization raw identity, and intended installation readback. Its authentication
mechanism/public anchors are the finite external TCB binding, still UNBOUND.
It is not a signature authorized by a key copied from that same assertion.

Logical installation states: UNBOUND; AUTHORIZED_NOT_DELIVERED;
DELIVERED_PENDING_READBACK; INSTALLED_BOUND; INVALIDATED. Only INSTALLED_BOUND
with independent delivery-origin authentication AND exact subject/generation/raw
identity readback can be read as H1. The first three and invalidated states refuse.
All actual installations remain UNBOUND. This is a logical installer contract,
not permission for this task to create directories, receipts, keys or state.

A later independently authorized installer publishes a new immutable generation
and forward anchor version atomically under its own reviewed installation/fence
contract. It preserves old policy/delivery/capsule evidence and never overwrites
an old generation or accepts equal-version different bytes. H6 must authenticate
monotone minima; this reader never increments/resets a counter/floor. No automatic
refresh from a candidate, expired response or arbitrary file replacement. A real
policy/key/expected-verdict change requires a new authenticated delivery/generation;
current status may refresh for the SAME immutable subject under the status
source's original versioned publication. Original key intervals are never extended.

Registration has a distinct missing origin obligation: an independently
authenticated assertion must identify who captured and delivered the exact raw
registration, its original immutable publication/capture identity and ordering,
project/purpose/source/contract subject, and destination registry generation.
Current status must refer to that exact registration/delivery subject and version.
Existing a0/raw-byte equality supplies identity only, not this assertion. Actual
RD delivery stays HOLD and raw7 UNREGISTERED; no raw pin or normalization changes.

## H2 protocol and authorization parameters

The candidate remains format `fleet5-p02-registry-candidate:2`, purpose
`installed-policy-registry`, domain
`fleet5/p02/installed-policy-registry/candidate/v2`. Its signature message is
EXACT domain bytes || one NUL || existing canonical UTF-8 JSON({body,signer}).
Only proposed Ed25519 under independently authorized canonical DER-SPKI is allowed;
SPKI SHA256 hashes full DER, not32raw key bytes. Signature is64bytes. Candidate
format/domain/algorithm/key slot is PROPOSED/UNREGISTERED, not an accepted new wire.
No K1 root-plan/root-seal role inheritance is allowed. A signature cannot choose
its own purpose, key, algorithm, codec, scope, Root choice or bootstrap version.

H1 expectedEffectiveVerdict is an explicit immutable policy parameter, with no
default. Its real value is NULL; no operational accepted literal is chosen.
Producer policy requires present string, nonempty printable ASCII1..128bytes.
Keep existing D04 malformed-type/literal diagnostic behavior and INFO I1/I2/I4/I5;
this normal producer constraint does not rewrite adversarial private DTO semantics.
Original review outcomes and H3-EA origin/current target remain separate. An
authentic nonapproval can authenticate successfully yet fail D04's approval join.

All existing numeric, interval, schema and lexical bounds remain. Capsule raw
bytes<=65536, registry record<=existing2MiB, no bool-to-integer/coercion. Existing
D04 general budget and16entry guard are unchanged; an H2-produced table contains
one exact verified tuple (no duplicate expansion). Producer/authenticator source,
codec/binary/stdlib closure and exact reviewed publication are independently
approved H1 policy subjects. Existing f2c1 CI proves code only; future H12 hashes
remain NULL until actual publication. A filename/green CI/arbitrary review JSON
cannot register those subjects or authorize bootstrap.

## Closed acquisition and first failure order

Universal admission precedes every gate: cap each external assertion at65536bytes,
capsule at65536bytes, record at2MiB and public SPKI at4096bytes; require exclusive
raw input ownership and freeze within the existing32MiB/100000node aggregate
budget before parsing/authentication. Reject overruns with no verification. This
admission is a resource check, not origin authentication; G02 then checks the
complete typed snapshot/freeze. Test cases require admission to pass.

Each call is read-only and has ONE acquisition attempt, ZERO automatic retries.
No I/O under held DB locks. Use immutable authenticated source checkpoints, then
short source readback operations, never claim a distributed lock/fence or immunity
to uncoordinated mutators. If sources cannot authenticate one coherent subject/
version-bound cut, refuse. Repeated identical immutable reads are idempotent and
consume no nonce/ticket; time or current-state changes may change the result.

| Gate | Deterministic obligation / private failure class |
| --- | --- |
| G00_BINDING | Require independently installed external TCB and purpose-registration binding. Actual absent -> UNBOUND. TEST_ONLY bound hypotheses are future isolated fixtures, never a runtime switch. |
| G01_ORIGIN_DELIVERY | Authenticate H1 policy/delivery origin under that external binding; exact independent project/component/registry/installation subject and immutable raw generation readback. Wrong/self-issued origin -> ORIGIN. |
| G02_OWNERSHIP | Exclusive input ownership, fixed byte/count budgets and freeze. No concurrent-mutation/isolation claim. Overrun -> OWNERSHIP. |
| G03_CAPSULE | Exact closed capsule bytes/typed policy, existing constraints and independently installed immutable policy equality. Do not infer expected verdict or policy from response. Invalid -> CAPSULE. |
| G04_AUTHENTICATED_SNAPSHOT | Read/authenticate original registration/delivery/status checkpoint, grant, ticket and clock-origin assertions; exact subject/raw-version joins, including specific RD origin. Authenticate assertions here; evaluate ACTIVE/expiry at G08. Wrong/missing exact source binding -> SNAPSHOT_AUTH/REGISTRATION_ORIGIN. |
| G05_H2_AUTHORIZATION | Independent grant exactly authorizes this purpose/format/domain/algorithm/DER-SPKI, selector/cohort and component; approved source/closure identities. An authentic foreign-purpose grant -> AUTHORIZATION. |
| G06_RECORD_CODEC | Freeze bounded candidate, exact existing canonical envelope/schema/signature encoding and fixed format/purpose. Parser failure is RECORD_FORMAT, never credited as a later semantic refusal. |
| G07_SIGNATURE | Parse independently supplied public SPKI as Ed25519, exact DER identity; verify exact fixed message/signature. Actual cryptographic failure -> SIGNATURE. A test label or tuple is no verification. |
| G08_STATUS_TIME | Current independently authenticated registration/nonrevocation for every exact H1 delivery/capsule/H2 grant/key/registry/record subject must be ACTIVE. Original grant issue interval and whole authenticated current interval must satisfy all bounds; otherwise STATUS/TIME/EXPIRED. |
| G09_VERSION_REPLAY | Exact immutable generation/anchor/capsule context; current stable record identity/version and protected min/floor, original scoped ticket/request/H5 digest joins. Lower/equivocating/foreign/replayed subject -> VERSION/REPLAY, no writes. |
| G10_FINAL_READBACK | Authenticate final SAME-subject version vector and compare it to initial; acquire approved final clock sample, preserve clock mechanism/epoch and monotonic bracket, re-evaluate every time bound. Changed subject/version or overrun -> READBACK/EXPIRED. No retry. |

These are proposed H12 internal failure classes, not new public/wire codes and
not a reordering of D04's20stages. Every failure maps to existing public
TRUST_UNKNOWN_OR_PIN_MISMATCH with zero output authority/effects; retain private
stage evidence only within the trusted application boundary.

A snapshot assertion is authenticated by the independently provisioned snapshot/
status authority at its named containing checkpoint/read transaction. It binds
all `snapshotVector` subjects in the matrix, original raw assertions and their
versions. Initial and final assertions must authenticate the SAME vector and
original snapshot identity. An opaque version/hash string alone proves nothing.
`revision` later carries the original authenticated snapshot ID, not a fabricated
successful token. Time samples are allowed to advance within the same approved
clock mechanism/epoch; they are separately authenticated, not equality-compared
as raw bytes. Current status/raw policy subjects and the externally bound trust identity/version
(including provisioner/status/clock authority identities) must remain stable.
Current authorization/nonrevocation includes those authority grants, not only
the registry key; the current bootstrap mapping is supplied by the independent
Root-bound boundary, never by a key attesting its own authority. At G10 compare
authenticated origin/subject first, then vector equality, then approved clock
mechanism/epoch/bracket, then the final time predicates. A changed authority
mapping invalidates this read; zero automatic retries.

At BOTH initial and final clock intervals [L,U], require0<=L<=U<=existingMaxEpoch,
U-L<=1second; original keyNotBefore<=record.issuedAt<keyNotAfter and
keyNotBefore<=L<=U<keyNotAfter. Original status.checkedAt<=L, U<status.expiresAt,
U-status.checkedAt<=120seconds. Original ticket.issuedAt<=record.issuedAt<=L,
U<ticket.expiresAt, U<record.validUntil and U-record.issuedAt<=120seconds.
H5.observedAt<=L, U<H5.expiresAt and U-H5.observedAt<=120seconds remain downstream
requirements; any tighter independently authorized bound also applies. Final
validity ends at the minimum relevant exclusive expiry. Missing trusted clock,
discontinuity/rollback/epoch change or an unproven bracket refuses; no ambient OS
UTC, supplied Now, optimistic endpoint, backdating or wider age.

A readback mismatch/expiry returns refusal. A later caller must start a separate
fully fresh acquisition under current authenticated policy; no internal fallback,
reusing an old successful token, authority write, fresh challenge allocation or
expired-ticket reset. Offline signatures still cannot prove that an authorized
signer did not backdate a newly made signature. Independent current registration
and original delivery/publication ordering/time anchors remain necessary; this
contract does not erase that residual with a version token or authenticated Now.

## Exact D04 handoff and downstream boundaries

Only after all H1/H2 gates pass could a future separately authorized assembler
freeze exact H1 capsule/raw bytes and one13field verified signature tuple for
existing p02Inputs. Every tuple field/message/signature comes from the checked
record and independently bound key/context. This is neither an InstalledPolicy
nor a History. The capsule and tuple are necessary data, not a trust token.

H12 alone does NOT produce H3 source/CI/reviews/coverage, H4 lifecycle/ticket/
clock, H5 measurement, H6 floor or H7 linked entrypoint evidence. Those sources
must independently authenticate the same subject/version. In particular, H12
cannot synthesize p02Inputs.before/after: all existing token fields (including
original ticket and actual H5 digest) require authenticated whole acquisition
and final readback. If unavailable, leave the public path refusing. D04 then
checks all20stages; unchanged checkPolicyBindings(policy,running) must precede
any future K1 constructor. No public Service hook or opaque issuer is added.

Dependency DAG: this contract -> actual Claude contract verdict + Root binding/
code choices -> separately granted smallest H2 crypto-only code -> actual reviewed
H1/H2 origin/status acquisition -> H3/H3-EA provenance and exact authorized tree
partition, H4-H6 status/clock/measurement/floor -> H7 versioned linked packaging/
installation trust -> separately reviewed positive K2A assembly -> separately
granted K2B phase/producers/effects and original runtime A01-A40. Existing accepted
normal-v2/M2/SF1/RS1 boundaries remain; no unaccepted B coexistence protocol,
ABSENT-head current view, fabricated ended-epoch current operation, plain-floor
raise, automatic downgrade, new CA ladder or crossmigration concurrency claim.

`acceptance-cases.json` specifies exactly H12-C01..C10 with full earlier
preconditions. All are PROPOSED_NOT_RUN and not original A01-A40 or crypto/runtime
proof. Later-purpose/revocation/version/readback failures cannot be credited to
parser, bad signature or unrelated missing sources. `next-code-proposal.json`
names one smallest code scope and the exact current guard incompatibility. It
proposes only a pure mathematical check returning private tuple DATA/boolean;
actual custody remains absent/default-refusal. No code is implemented now.

All actual H1-H7/H3EA/expected-verdict custody/RD remain NULL_HOLD; raw7 is
UNREGISTERED; A01-A40 NOT_RUN. K1's13types/73fields and28contract/schema pins,
product/source-inclusion/runtime/whole-K2/FIVE acceptance remain unchanged.
