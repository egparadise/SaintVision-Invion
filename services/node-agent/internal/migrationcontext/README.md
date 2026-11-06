# K2A read-only boundary and refusal slice

This revision follows Root `msg_f4259ea0de6b`, choice A. It does **not** implement
positive production authentication. Independent provisioning and purpose-specific
attestation contracts/anchors are missing. All five production ports are null,
and every unregistered record refuses even when hashes, role labels, DER, times,
source/CI/review strings and a self-issued signature are internally consistent.
There is no accepted new proof format, domain, key, registry or verifier ABI.

`NewService()` takes no arguments. Service fields, provider methods/records and
opaque policy/history bindings are private. No production constructor issues an
`InstalledPolicy` or `History`. JSON, a zero value, a foreign service, a changed
version or changed frozen data cannot create a valid opaque input. Provider
interfaces are closed internal contracts, not caller-supplied callbacks. No
entrypoint or provider implementation is installed by this package.

The actual public first-failed-gate behavior is:

| Entry | Executed boundary in this revision |
| --- | --- |
| `LoadInstalledPolicy` | Locator syntax, registry availability/read, then mandatory unregistered-registry refusal; no issued policy |
| `ReadHistory` | Service-bound policy, scoped exact query, archive availability/read, then mandatory unregistered-archive refusal; no issued history |
| `ValidateHistory` | Service-bound policy, exact original history/selector, running-code availability/read, then mandatory unregistered-running-code refusal; no issued report |

Later publication/certificate/clock acquisition gates can be tested independently;
an all-null public call reports only its first failure. Null/unregistered registry,
archive, publication, certificate, clock and running-code sources map respectively
to `TRUST_UNKNOWN_OR_PIN_MISMATCH`, `HISTORICAL_BINDING_UNKNOWN`,
`PUBLICATION_UNKNOWN_REVOKED_EXPIRED_OR_BACKDATED`,
`CERTIFICATE_STATUS_UNKNOWN_REVOKED_OR_EXPIRED`, `CLOCK_UNTRUSTED`, and
`INSTALLATION_OR_RUNTIME_CAPABILITY_UNKNOWN`. A missing interval mechanism is
`CLOCK_MECHANISM_UNPROVEN`. No raw provider/K1 diagnostic becomes authority.

Private pure functions check necessary bindings and freeze maps, slices, JSON
values and exact bytes. The JSON algebra rejects arbitrary structs, aliases,
callbacks/custom marshalers, invalid numbers/UTF-8 and size/depth overruns before
encoding. Callers exclusively own inputs during copying; this is not concurrent
mutation safety. Registry graph, contract/source/publication pins, exact review
target/scope and CI run membership, actual executable versus archive identity,
receipt/runtime-lock/linked-closure joins, ordered old two-member scopes and exact
DER/Node URI/Ed25519/grant C2 joins are consistency conditions, not authentication.
K1 retains its full original signature, contract/recipe, SPKI, consuming-time
grant/lease/challenge and certificate checks. Unknown real bindings stay HOLD.

Original history selects the exact original migration operation, HELD hash/fence,
plan body and authenticated containing-epoch facts. It may be expired and absent
from live operations. No live map exists here to substitute for it. The original
semantic `current` values and seal aliases are retained. Current independent
publication/certificate nonrevocation remains necessary at the real observation
time in any future positive integration.

The private interval evaluator freezes one input and evaluates unchanged K1 at
L, U and t0. It compares the complete report, including all counts and digest keys.
Pure envelope checks reject zero/non-UTC/inverted/zero-crossing intervals, an
out-of-bracket t0, overrun, changed versions or uncertainty above one second.
Its monotonic observations, mapping and stdlib/closure pins are **structured
synthetic inputs only** here. It does not observe elapsed time, authenticate a
clock, obtain a final live sample or implement actual TOCTOU readbacks. No physical
clock or production clock mechanism is claimed. Future authenticated acquisition
and post-evaluation readbacks must close those obligations before public success.

Only `k1_bridge.go` imports/calls K1 and constructs its trusted inputs. It supplies
historical operations/challenges plus independent status and explicit time. It
does not supply live operations/challenges or a current projection. There are no
current APIs/placeholders, effect APIs, locks, journals, nonce allocation, signing,
process/file/network/database/Engine/SSH/issuer operations, or physical clock reads.

Tests deliberately construct private **already-bound synthetic fixtures** to
exercise downstream checks. The public ephemeral crypto fixture is generated from
immutable eb32 test helpers in an isolated scratch copy, without changing K1. It
contains public keys/certificates and signed history, **no private keys**. Its
source/export command/hash are recorded in the unique task Evidence. Its JSON
decoding is a test-only authentication bypass, not a producer authenticator,
installed policy, runtime observation, or A01–A40 execution.

The repository boundary test inventories all tracked first-party Go files in both
modules, including platform files, plus this new package before its first commit.
It rejects new K1 imports, dot/blank aliases, constructor aliases, unchecked DTO
references, public injection/opaque issuers and effect/bypass imports/selectors.
It separates unchanged K1 definitions from new callers. The whole-package census
parses and type-checks **all twelve** non-test K1 files with actual dependency
export data and no source/type stubs. It recursively describes full underlying
named/alias/map/slice/function/interface/generic input types with deterministic
cycle references. Working source is compared to exact eb32 using the same actual
toolchain, separately from raw source pins. G01–G08 and type-correct R01–R03 named
map/slice/function mutations after simulated raw repins must be detected.

These gates constrain the reviewed program. Opacity does not defeat malicious
same-process code, and a source gate is not cryptographic authorization. The next
production dependency is a separately closed/reviewed independent provisioning
and attestation-verification contract **per purpose**, actual registered anchors
and ports, and a future explicit implementation grant. No actual binding, clock
mechanism, installation, D-COHORT, D-OBSERVATION, prepublication/current authority,
K2B effect execution, or five-PC acceptance is completed here.

The P02 provenance checks are a **partial necessary consistency subset**. Missing
joins remain explicit HOLD obligations for the future independently provisioned
and reviewed attestation contract: actual review VERDICT and exact target/scope;
CI event, correlation, run attempt, required jobs and every required step's
conclusion; artifact ID/digest/bytes; binary VCS/toolchain/module/helper closure;
and Root's exact reviewed source choice/equivalence decision. Existing CIRef,
CIWorkflow, CIAttempt and CIJobID presence checks do not verify those facts. No
arbitrary review JSON, green workflow name, source filename/hash or role label
authenticates them. This revision adds no new P02 proof format, fields, verifier
ABI, registered producer, accepted wire or production positive factory. All
public unregistered authentication paths still refuse and issue no opaque input.


The reviewed Low revision strengthens the source gate with actual package
Go/types resolution: exact current pure function/method objects are allowed,
independent of import alias. Resolved references/calls are checked against that
closed policy, including own interface and instantiated constraint dispatch.
There is no strings/time wildcard. Ambient clock/timer functions, signing/key
creation, certificate Verify/system roots, unresolved function-value callbacks,
native linker sources, bodyless functions and linker directives are refused.
Native inputs are checked in both reviewed production packages. The gate is
source defense in depth, not protection from hostile same-process code.

The census now derives actual explicit AND inferred K1 bridge objects, including
NewVerifier, Verifier.Verify, Packet, Report and CanonicalJSON. It describes full
transitive underlying types/signatures/variadics/receivers and sorted named plus
pointer method sets. The original13/73/0 input metric remains a separate baseline;
it does not describe the size of the larger complete object graph. New type-correct
Packet/Report map/slice, CanonicalJSON variadic and value/pointer MarshalJSON
mutations are detected after simulated raw repins; declaration-order controls
stay equal. Existing raw K1 source pins remain frozen, with no automatic repin.


The PL-R1a candidate limits own interface/constraint dispatch to unexported OWN
method objects, and refuses exported methods or foreign interface embeddings,
including aliased/transitive embeddings. Concrete own methods are a separate
reviewed class. Foreign package-level variable reads permit only the resolved
current time.UTC binding; taking a foreign package variable address is refused.
The PL-R1b candidate checks write targets in assignments (tuple/select-case
included), range clauses with `=` (not definitions with `:=`), and increment or
decrement. Direct foreign package variables resolve by object identity, including
parentheses and dot imports. Targets walk selector/index/slice/parenthesis roots and
explicit or implicit pointer dereferences, including promoted field paths.
Pointee writes require an unaliased named type declared in this package; foreign,
builtin, unnamed or unresolved pointees are conservatively refused even through
a local pointer, helper parameter or an allowed pure call. Own named pointee
types and local value/range mutations remain allowed. This type restriction is
not proof of storage ownership or whole-program pointer/alias provenance.
These are precise source-defense rules for the reviewed closure and tested attack
classes, not arbitrary trusted-process isolation or a whole-program effect proof.
Implicit argument dispatch through allowed `json.Marshal` (MarshalJSON/MarshalText)
and argument ownership remain limits (PL-I4), not a general effect/isolation proof.
They do not install an authority, provider or positive authentication path. The
actual combined review closed interface class (a); PL-R1b/foreign-write class (b)
closure remains subject to actual independent narrow review. PL-I1 future factory
must call checkPolicyBindings before K1; PL-I2 operation-set authentication stays
with the future archive. No new producer, wire, current view or effect grant.
