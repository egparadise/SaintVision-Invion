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

The pre-existing public-path P02 provenance checks remain a **partial necessary consistency subset**. Missing
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
The PL-R1c candidate refuses pointee-changing conversions to underlying pointer
types: the operand must be untyped nil or a pointer with an identical element
type (`types.Identical` after alias/named-pointer resolution). An own defined
pointee name cannot launder a foreign pointer; slice-to-array-pointer conversions
are refused by this rule. Identity pointer and unrelated value conversions stay
allowed. PL-R1b-I1 remains explicit: writes into slice/map element storage and
append into backing arrays are generally unchecked, including a copied slice
header or a slice parameter. Walking a SliceExpr root is not storage ownership.
The PL-R1d candidate extends conversion targets to pointer-term type parameters:
it recursively collects pointer elements through constraint interfaces, embedded
interfaces, aliases/named pointers, and union terms. The same untyped-nil or
identical source/target element check applies to EACH collected pointer element;
slice-to-array-pointer operands still refuse. This is a bounded target-term
restriction, not a whole-program heap/type-set effect proof or a general generic
or storage audit.
These are precise source-defense rules for the reviewed closure and tested attack
classes, not arbitrary trusted-process isolation or a whole-program effect proof.
Implicit argument dispatch through allowed `json.Marshal` (MarshalJSON/MarshalText)
and argument ownership remain limits (PL-I4), not a general effect/isolation proof.
They do not install an authority, provider or positive authentication path. The
actual combined review closed interface class (a); accepted PL-R1b write forms
remain accepted, and PL-R1d/foreign-write class (b) closure remains subject to
actual independent narrow review. PL-I1 future factory
must call checkPolicyBindings before K1; PL-I2 operation-set authentication stays
with the future archive. No new producer, wire, current view or effect grant.


## D04 internal consistency candidate (Root msg_ccd8401cb2c5)

The NEW private `p02_*_internal.go` seam implements the bounded P02 Rev3
consistency contract accepted in review `6fa4c644` of design `84ee9b1b`.
The published R1 source is `08e0f56eabe7d46518e17b8c3d6d7e296df880ac`.
Root's actual isolated Go1.27.1 run passed23top-level/228subtests, with0fail/0skip
and unchanged source before/after. Its exact Docs42287667048 and hosted
Core42287980945 succeeded. Core's required jobs/steps succeeded; its declared
optional skips remain explicit in the attributed Root receipt. Actual independent
Claude CODE review `879aea64e6896d6014f1b10d4ab63fda0de6073c` returned narrow
`INTERNAL_CODE_ACCEPT`, with nonblocking Low D04-L1 and INFO I1-I4. That review's
earlier Core-pending observation and the earlier WIP NOT_RUN checkpoint remain
unchanged historical facts in their original Git/Evidence.

The separate R2 change (Root `msg_d42e405d8bd0`) rejects more than16signature
tuples BEFORE the general snapshot budget and deep freeze: exact private
`OWNERSHIP` / `01_ANCHOR` / `immutable-signature-table`, with an empty passed
prefix. The later exact tuple/context check and independent general budgets stay
unchanged. Root's unchanged observational probe actually reproduced R1's17tuple
refusal at `04_SIGNATURE`; that probe's command PASS was not contract PASS.
The new16/17boundary regression preserves the matching tuple and fingerprints;
its17tuple allocation check measures repeated evaluation of the same input.
R2 Go tests, R2 source gates, R2 Docs/Core and independent delta CODE review are
NOT_RUN at this WIP checkpoint. R1 results do not validate changed R2 bytes.
Gofmt parsing is not compilation, type-checking, a passing source gate or tests.

It adds a bounded lexical JSON codec with exact round-trip, fixed generated
validators from the three immutable Rev2 schemas, closed signed-width private
records, and a20stage pure evaluator. No json.Unmarshal/NewDecoder, runtime
schema loader, arbitrary marshaler, interface/function callback, dependency,
K1 import/callsite or source/schema pin is added. Intermediate codec nodes are
private; concrete prerequisites contain no `any` truth assertions. The final
legacy `policyData` scope algebra is populated only from checked closed scopes.

Inputs are exclusively owned for a bounded sizing pass and deep freeze. No
concurrent-input mutation, hostile same-process isolation or general heap effect
proof is claimed. The evaluator accepts only already-authenticated PRIVATE
prerequisite hypotheses. It does not establish who authenticated them. Exact
verified signature tuple DATA must match the independent key, full domain+NUL+
canonical body/signer bytes, signature bytes, purpose/format, capsule, generation,
scope/selector, versions and request binding. No hash-only or role-label substitute
is accepted and no signature verification/signing/key operation is performed.
All actual producers/anchors/custody/H1-H7/H3-EA remain NULL/HOLD.

Effective verdict is checked against the private capsule exact expected literal
at05_REVIEWS; no accepted literal is defaulted. The printable-ASCII capsule codec
is at01_ANCHOR (design-review INFO I1), so present control/non-ASCII values refuse
there. Empty array/object expectations and integer/bool/null/empty-string/129byte
expectations can reach05; nonempty array/object contents cannot be represented
by the private expectation and fail the raw/typed capsule equality at01 (CODE
review INFO I4). Printable bounds and literal mismatches are checked at05.
Effective publication differs from every independently bound original/part review
identity, including unused originals; equality with the SOURCE SHA is not itself
a refusal (design-review INFO I2). Original targets/scopes/verdicts are preserved.

CODE-review INFO I1 remains: when both H5 and clock are missing with a present
ticket, Go reports TIME before the design's INSTALLATION. The general snapshot
budget also precedes a missing-capsule refusal. R2 changes neither multi-missing
source order nor that independent general budget. CODE-review INFO I2 records
additional Go-only fail-closed predicates: positive floor; clock/lifecycle/ticket/
H5 integer domains; nonempty ticket ID, H5/coverage evidence and artifact; full
subject-bound readback tokens; Root-choice digest over actual supplied bytes;
and the C2 printable-ASCII check after schema validation. These are explicit
precision limits, not a claim of complete design/Go diagnostic equivalence.
R2 updates the current README (CODE-review INFO I3) without rewriting old reports.

Eight component hashes derive from the exact checked payload/C2/raw component
bytes. Exact CI run metadata and independently required/optional steps, review
coverage, archive versus executable, lifecycle/head/floor/ticket/expiry/H5,
zero-weight H5 echo/request and final readback joins precede projection. Raw
H3-EA evidence digests are computed over the supplied exact already-authenticated
bytes; authentication of those bytes and their binding to the typed statement is
still the missing producer's obligation, not supplied by this evaluator. Source
tree-to-partition origin and fully subject-keyed H4 status remain producer
obligations; typed consistency checks are not those authentications.

The result contains ONLY existing private policyData41leaf and separate
runningData5fields. Approved receipt/runtimeLock/link Provenance comes from H3;
RunningExecutable plus all five measured fields comes from H5. The H3-approved
Verifier source/executable remain expected counterparts. Deterministic epoch
projection uses ONLY the newly allowed exact `time.Unix` and `time.Time.UTC`
objects; no ambient clock/timer API or time wildcard is granted. Alias-aware
regressions and all existing effect/source/public-refusal/opacity/K1 baseline
gates remain required on the final code. The unchanged checkPolicyBindings is
still a future consumer before K1; this seam performs no X509/Ed25519 check.

No public service method calls this seam. It issues no InstalledPolicy, History,
policyBinding or historyBinding; all public null/unregistered paths keep refusing.
No producer, port, loader, acquisition/current view, real clock, installer,
lock/journal/effect, hardware or five-PC acceptance is added. RD registration
byte equality is fact-only and HOLD for actual delivery/origin authentication.
Raw7 remains UNREGISTERED; A01-A40 remain NOT_RUN. New private implementation types
are reported separately and do not change K1's immutable13types/73field baseline.
