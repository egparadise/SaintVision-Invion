# Historical selectors, Go boundary and running-code identity

Revision2 normative proposal. Source is pinned eb32; actual review5623 identified
the old P12 error. No product Go or K1 pin changes are made here.

## Original plan operation, not current authority

TrustedContext.MigrationOperationID comes from the independently authenticated
ORIGINAL PLAN/HISTORY producer. It must equal the original semantic
facts.migrationOperationId and resolve to that exact original HELD lease hash,
migration, scope/fence and time interval in History.Operations. It may have
expired and be absent from live Operations. Live Current.OperationID, its
fence/currentVersion and the normal:3 lease ID remain separately typed/current.
Substituting one of them, omitting original history, or changing only the facts
selector refuses ERR[ORIGINAL_PLAN_OPERATION_MISMATCH] in the future factory,
before K1. K1 source diagnostics remain ERR[K1_VALIDATION_REFUSED] at its bridge.

The new focused scratch source check uses K1's existing in-memory fixture only:
original epoch1 is expired/absent live, epoch2 is current; Verify and Current
both pass in control. Current-ID substitution, missing History.Operations and
facts-only mismatch both refuse. This is source semantics evidence, not a K2
implementation, producer/installation proof, runtime case or completed CI rerun.

## Analogous fallback audit at immutable eb32

| Actual source selector | Required producer/time classification |
| --- | --- |
| recipes.go recipeSources: containing body.operationId, else ctx.MigrationOperationID | Explicit original signed record operation; missing plan-level operation uses ORIGINAL plan/history selector, never latest live owner |
| proofs.go proofOperationAt: use.live false versus true | false resolves History.Operations; true resolves independently current Operations. Names do not select the map |
| recipeSources slot: containing member/memberState, body.slot, arguments.slot, targetSlot | Exact authenticated containing artifact/member/method, then registered ordered scope; no first-node fallback |
| facts.nodes[slot], effectOutcomes[operation+sequence], eventSlots[recordID] | Independently authenticated ORIGINAL semantic/outcome archive for the exact consuming epoch/event; labels are not fresh measurements |
| containers[slot].current fallback when no containing current member | Original semantic snapshot bound to that proof's containing signed artifact. Do not overwrite it with live runtime state merely because it says current |
| aliases.currentSealEnvelopeSHA256 | Exact unique authenticated terminal seal for registered slot/scope in the packet; despite its name it is not a floating live registry lookup |
| component/product path selection | Exact containing acceptedP0/helper/fence/API/guard/target component publication and actual review scope |
| SemanticInputs.plan for freshness versus packet plan/body for recipes | Future factory must bind them to the SAME authenticated original plan body/version; no alternate expiry or evidence-age policy |
| currentNativeWitnesses expected subject | Authenticated PRESENT head declaration plus unchanged typed recipes; fresh actual measurement is separate, never invented to match a recipe |

All opaque any fields need explicit authenticated construction with the correct
containing epoch: KeyGrant.AuthorityScope, MemberIdentity.Scope,
TrustedContext.SemanticInputs and CurrentProjectionContext.InventoryHead.
Historical ValidateHistory still requires real current clock/publication/
certificate status; it is not a status-free offline privilege.

## Concrete future Go enforcement (not implemented)

Proposed trusted application package is services/node-agent/internal/migrationcontext.
Authenticated DTOs have unexported types/fields and unexported factories. A factory
constructs them only after actual installed provider checks; JSON unmarshal,
hand-built RPC DTOs, hashes or booleans never construct authentication. The future
reviewed bridge file k1_bridge.go alone may import migrationverify and construct
InstalledTrust/TrustedContext. The future registered integration entrypoint calls
the internal service API, with no direct hand-built K1 context path.

A standard Go AST/types import/callgraph gate must enumerate all production
imports, aliases/dot-imports, NewVerifier calls and InstalledTrust/TrustedContext
construction. Only that reviewed bridge plus its registered integration path is
allowed; tests are enumerated separately. New callers/constructors or indirect
unchecked RPC/JSON construction fail the gate. Existing exported K1 constructors
remain exported; the application/build boundary mediates their permitted use.
Unsafe/reflection/plugin bypasses are forbidden by the reviewed trusted closure,
not magically prevented by a type. Opacity is not cryptographic protection from
malicious code already executing inside the trusted process.

K2B NEVER accepts caller Report/digest/SnapshotToken as a capability. It obtains
fresh authenticated facts/current clock/permission/fence itself and verifies the
separate effect/observation permit before durable intent and admission.

The standard Go census here resolves the ACTUAL NewVerifier signature through
go/parser and go/types. It records canonical field types, named/alias/pointer
edges, embedded/exported fields and signature parameter shape. Eight mutations
after a simulated legitimate raw-source repin detect embedded values/pointers,
Now->any, aliases, new fields/types, map value types and pointer signature changes.
No regex field census is the future semantic gate. Private result-only types are
opaque stubs solely in this source census; no input or function body is stubbed.

Static V06–V09 limits remain explicit: a typed census cannot prove historical
placement, correct refusal meaning, completeness of effect exclusions or English
policy semantics. Targeted structured invariants/negative examples catch the
specific reviewed mistakes; independent source/contract review and later executed
implementation tests remain mandatory. Labels or a passing validator do not
prove those meanings in general.

## Actual running entrypoint versus an authentic unrelated artifact

VerifierPublication.ArtifactSHA256 MUST equal a measured hash of the ACTUAL
RUNNING verification/integration entrypoint executable, not an archive, image
digest, argv0, caller-selected path or another inv-node binary. It must also match
an independently approved sealed installation receipt/registry publication,
source/CI/actual review/scope, compiled Go closure and the linked K1 call path.
PublicationX plus runningY refuses ERR[RUNNING_VERIFIER_IDENTITY_MISMATCH].

Future v1 Linux self-measurement uses a held /proc/self/exe descriptor, its actual
PID/start generation and OS file identity, bounded exact bytes/hash and repeated
ownership/type/mode/link/metadata/identity checks across measurement and use.
The proc descriptor link is intentional; ordinary caller symlinks/paths are not
equivalent. Changed/deleted/unapproved code identity refuses. Bind the verified
installation receipt to that same held executable identity, and recheck TOCTOU
before returning a snapshot or admitting an effect. No measurement is performed
by this planning task. Other platforms require a separately reviewed equivalent
held executable/process-image identity path or ERR[UNSUPPORTED_SELF_MEASUREMENT].

Packaging ZIP/platform/image config/layers/runtime lock/helper/source hashes remain
separate typed provenance joined to executable bytes. Never compare a ZIP digest
to executable bytes. The current eb32 inv-node has no K1 import/call path; VCS=eb32
therefore cannot satisfy this installation requirement. Future entrypoint must
actually LINK/CALL K1, be tested/reviewed/published, and then independently installed.
All actual running-code/installation/registry/clock port bindings remain null/HOLD.
