---
doc_id: "HIST-FLEET5-B-CONTRACT-REV4-001"
title: "FLEET5 revision 4 selected-node approval and closed handoff proof contract"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Actual independent Claude whole delta review via Root pending"
updated: "2026-11-06T07:03:03+09:00"
source_of_truth: "Git"
---

# Scope, baseline and actual verdict

Owner Codex; task FLEET5-COMPUTE-STORAGE-CONTRACT-20261105,
`task_a8fd2969f0b3 / ctx_6f0f8253b8a7`, own branch
`agent/codex/fleet5-b-contract-rev4-20261106`. Proposal base is immutable
`e9932f306550a07e4893ab7a1a7dc6944b31e271`; accepted product source anchor remains
`72028cbac903c4415d9979f980a6e0f9948e914f`. Actual independent review
`638109ab211bdfab7646a07b375003a636b3a33b` says **REVISION REQUIRED** for
B3-M1/M2/M3 and L1..L6, not ACCEPT or partial freeze. Its 33 probes, including
false positives/failures, source census and actual verdict are preserved byte
for byte. All100f/02cf/15823/e993 and earlier errors remain immutable.

Root decision `msg_94ff5bb7a0e6` authorizes one narrow REV4 DOCS/schema/static
fixture delta only. No product code, migration, registry, ADR, keys, Node/PG/
Docker/VM operation or partial registration is authorized. Future hard
implementation owner stays Codex after actual whole-contract review. Latest
first-read Root boards Index421/Codex382 and exact hashes/KST/task/scope are in
revision-record.json. Canonical doc/skill versions remain in the original
source inventory; agent-delivery1.1.0/core-reliability1.0.0 apply. Shared boards,
source originals and registry remain untouched; no Obsidian apply. Separate
e50/K1/bootstrap delivery is not B acceptance. Existing48/VFCL statuses persist.

All real Node/VM/path/network/image/policy/key/provenance/deployment bindings stay
**NULL/HOLD**. No physical/private/remote/PKI/Node/PG/Docker/WSL/VM/trust/clock/
schedule/protected-state action, helper worker or cleanup occurs. Old PC2/PC4
pilot identities remain distinct and untouched. New real Go/crypto/PG/Linux
Docker/crash/concurrency/equipment evidence is **zero**, A1-A16 pending. Prepared
folders, startup/admission/ARM receipts and a healthy execution Node are not
active contributed-storage acceptance.

# Accepted direction carried forward

Rev3 R1-R7/L-a..h directions remain the proposal basis except the precise
corrections below. Fresh combined-role activation requires all five, four
independent Linux workers plus a CP-colocated **separate-kernel managed Linux VM**
with its own Linux Engine/native filesystem. WSL/Desktop/DrvFs/9P/remap is not
fallback or a fifth independent S05/S07 domain. Actual resources/contexts remain
unavailable/unmeasured, not positive capability. VM planning2vCPU/4GiB/20GiB plus
host2GiB memory and10GiB disk headroom stays planning policy, not a Node quota.

Default R4, plain floor:2/leaf:3, SF1/RS1 and B-MIG1 DESIGN-FIRST stay unchanged.
New role installation preserves identity/Node key/DER/shared C/epoch and exact
policy/R/root; a distinct leaf operation changes DER and SAME shared C+1, P+1
at CAS overlap and separately required final P+2, R unchanged. No separate
storage channel/counter. Node has owned RW state, exact default RW Docker socket
and one RO/nonrecursive/rprivate contribution. Workloads receive no host/state/
socket/contribution path or writeback. Closed HostConfig allowlist and actual
Linux enforcement remain required future tests. Docker socket implies trusted
Node guest-host-root power; readonly contribution is not a compromised-host
security boundary. Unknown flags/mounts, RW contribution, symlink/TOCTOU/mount
substitution, stale/channel-mismatched policy, reset or old restart fail closed.

# M1: expanded actual source census and supported entry plans

source_census.py reads exact72028 Git objects, no application imports. It scans
all494 non-test/non-doc Python files, follows imported/local/self helper edges
and conservatively marks ambiguous method edges. It includes every caller of
lock_run/lock_resources/require_execution and their wrappers. Every DB/ORM method
candidate is recorded on **any receiver**, including query/scalar/scalars/refresh/
merge/execute/copy/with_for_update and aliases; no session-name filter hides a
call. Module-level/decorator scope is explicit. Known non-DB container/adapter
calls are marked only with source evidence. Unresolved static receiver edges
stay visible, not an empty list constructed as a completeness claim. An unknown
B authority writer blocks until resolved; known business/observe paths have
concrete canonical plans, not a blanket B refusal.

The independent638109 census anchors are inputs, including all ten missed CP
modules and credential_registry.py (the remaining module). NodeAuth.lock_current
at node_auth.py:108 and its nested public.nodes FOR UPDATE are recorded alongside
225. Per-function summaries contain actual lexical lock tables/modes/order,
helper edges, outer guards and discovery/reread plan. Lexical order is not a
runtime branch/PG trace. Removing a known build_preparations call, ORM row lock,
helper edge, helper import or alias binding must fail regeneration against Git.
The first development scan's decorator-owner error is preserved, then corrected
by explicit module scope; no source file was modified.

| Actual affected entry | Current source ordering hazard | Required B plan |
|---|---|---|
| build_preparations._claim | lock_run223 -> resource/storage budget rows -> lock_resources267 | Discover full candidate resources/Nodes without locks, owner scope locks Node prefix, then Run/plan/budget/resource rows; reread fit/membership |
| shards approval/reservation | shard_plans48 -> Run53 -> approval53+ -> resources65 | Discover whole selected member set; prefix before plan/Run/grant/resource, abort/replan changed set |
| runs/workspace_start | Run and require_execution wrappers | Prefix before Run/mutation, recheck execution gate under mandatory tenant guard |
| business_handoff/output_ingestion/shard_completion/result_view | indirect Run locks, stored source/receipt links | Discover linked Runs/Nodes first; prefix then ordered Run/evidence/claims, no Node I/O in transaction |
| build_execution_worker | runs212 FOR SHARE | Canonical parent scope then exact Run SHARE; external execution outside locks |
| credential_registry | require_execution plus registry/grant reads | Prefix before grant/resource authority use; no caller labels as approval |
| NodeAuth.lock_current108/public ORM aliases | public.nodes FOR UPDATE before observation UOW | Protected B scope/observation write procedures, exact current certificate and nonce, no direct authority UPDATE privilege |
| observe/reconcile and all new b_* writers | mandatory epoch/tenant plus dynamic target scope | Fixed owner procedures, complete sorted set, authoritative scope recheck, bounded transaction; keep observation usable |

Mandatory order is control_epoch first, tenant_controls next, then routing/fence,
sorted inv.nodes, sorted public.nodes/contributions, shared node_channels,
role/current, business/Run, operator grants/resources/claim/transfer/model,
nonce/evidence/ledger. Preserve500ms lock_timeout/2s statement_timeout, bounded
new-transaction retry and exact tuple/ledger reread. No Node I/O while row locks
are held, no starvation guarantee, no late lower-rank Node added from stale
hints. Plain semantics remain intact. Required future PG tests include all
transitive/ORM/FK/RLS paths and actual permission/lock traces.

# M2: protected per-Node approval renewal and only-time-expired reapproval

Frozen released cohort configuration is a historical description, not permanent
live authority or a requirement to refresh unrelated workers. Each Node has its
own current protected approval/release/delegation/admission chain. New approval
is immutable and signed under distinct APPROVAL purpose/domain
`saintvision/node-role-approval/v1` plus NUL. It binds priorApprovalHash, exact
Node/cohort/frozen configuration/epoch/C/R/root/image/executable/policy/floors,
fresh selected Node+independent host candidate, current operator grant/trust,
nonce and bounded new interval. Old approvals are never updated in place.

Before expiry, protected b_append_approval may append
APPROVAL_RENEW_SAME_CONFIG with bounded interval overlap. After **only** approval
time expiry, REFRESH/READMIT remain denied until protected REAPPROVE_SAME_CONFIG
appends a new approval using independent observation and a **current valid**
operator grant/cert/trust. The expired approval supplies lineage/history, not
permission. Max24h per new approval, bounded by current grant and cert/trust.
No online verifier/use issuer can sign/append approval or change its time.
No clock override. Explicit revocation, containment/quarantine, mixed/unknown
partial operation, changed epoch/C/R/config/root/policy/floors, expired cert/trust
or active cohort mutation fence blocks these lanes. B-RECOVERY1/explicit reviewed
mutation remains separate; no automatic enrollment or new intent from mixed state.

Each selected Node is observed and canonically checked independently. Offline or
expired unrelated members remain denied individually and do not gate renewal.
Fresh/cohort-mutating activation still requires all five. Same actual generation
may renew approval and replace its gate; READMIT requires a genuinely changed
trusted generation, and same-generation lease renewal is REFRESH. A new approval
for static scope does not itself activate a changed generation: protected
release/readmission must bind its actual new generation and quiescence proof.

| Per-Node phase | Current pointer / Node / receipt state | Failure or expiry |
|---|---|---|
| Observe selected | Fresh Node+host candidate, old pointer unchanged | No change; affected Node unavailable if authority expired |
| Append protected approval | New immutable A1 references A0; A1 not current | No in-place extension or business grant |
| Pause selected issuance | Durable expected-current operation intent; only selected Node pauses | Unknown retains intent/claims; unrelated Nodes continue |
| Invalidate/drain old gate | Protected exact g0 command, Node-signed durable INVALIDATED ack, actual quiescence | No ARM based on helper boolean; old tokens/streams cannot survive acknowledged switch |
| ARM replacement | g0 invalidated -> g1 ARMED CAS (or trusted restart NONE -> g1); exact current generation | No business before activation/delivery; lost ack requires exact Node record/proof |
| CP activation/current CAS | Real release/delegation FK -> ACTIVE admission/current/ledger same transaction, expected prior pointer+scope checked | Unknown commit rereads exact ledger/current, no tuple-only inference |
| Postcommit key handoff | Protected challenge -> use-key PoP -> consumed ledger -> protected final receipt | Any loss/expiry unavailable/UNKNOWN; fixed key/challenge state only |
| Eligible selected Node | Current protected chain, lease, actual g1, exact final delivery receipt | No old gate restoration or claim release by timeout |

Approval interval overlap is not privilege overlap on an invalidated gate. A
restart defaults to no gate; old process generation tokens fail. Quiescence,
actual stop/outcome/claims are independent of ARM ack. No Engine/Node/DB/key
atomicity claim. A partial node switch cannot silently start another ordinary
renew/reapprove operation; it needs exact still-valid intent plus current ledger
and Node evidence or explicit reviewed recovery when authority is no longer valid.

# M3: closed signed gate, delivery and observation artifacts

contract.schema.json plus mandatory strict decoder/semantic validators define
all shapes. Gate command hierarchy explicitly lists ARM_EXACT_RELEASE and
INVALIDATE_EXACT_GATE as protected operator-release purposes, never use/safety
keys. Registered Node leaf signs gateAck under
`saintvision/node-role-gate-ack/v1` plus NUL: exact tenant/Node/certificate,
action/command/request hashes, release/delegation/use-key hashes, prior/new gate,
current generation/epoch/static tuple, nonce/time/validity and durable local
record identity. Ack only follows that exact durable transition. Helper ARMED,
wrong leaf, absent record or stale generation cannot produce accepted evidence.
ARM ack before CP activation confers no business permission.

Proposed node_role_gate_acks and b_record_gate_ack accept evidence only from
protected operator or narrowly authenticated verifier, with actual Node crypto
verification, expected scope and fresh nonce/current leaf checks. Evidence insert
has no approval authority; runtime has no direct DML. Pre-release ack binds raw
hashes/candidate/operation, not a circular FK to an uncommitted release. Active
admission later has real existing release/delegation/ack references.

Key delivery has **two distinct proofs**. Protected controller outside runtime/
use-issuer custody first loads exact committed activation ledger, current tuple
and actual Node ARMED ack. It prepares an unpredictable32-byte single-use
challenge, bound to delivery/challenge/ledger IDs+hashes, Node/cohort/epoch/gate/
generation/static tuple, release/delegation/key hashes, registered issuer service/
TLS identity, nonce and bounded expiry. No precommit delivery. The recipient
signs exact challenge/context under `saintvision/node-role-key-possession/v1`
plus NUL using the delegated use private key. PoP alone is not a release, delivery
receipt or authority. Authenticated recipient identity and the protected
challenge must match; caller labels never set the issuer/TLS context.

Controller verifies raw PoP/key/domain/context/current committed rows outside
and across canonical reacquisition, consumes the one-use challenge, records an
exact consumption ledger, then signs its own closed keyDeliveryReceipt under
`saintvision/node-role-key-delivery-receipt/v1` plus NUL. Receipt binds challenge/
PoP/ledger/ack/release/delegation/key/issuer hashes, exact prior/current state,
current pointer and validity. Only protected b_record_key_delivery commits final
eligible rows; issuer cannot sign the controller receipt or write them. Controller
publishes that receipt only after exact final-record commit is confirmed. Lost
response reuses the same frozen key/challenge/ledger state, never silently
regenerates it. Expired or indeterminate state remains unavailable pending exact
proof or reviewed resumption. A new challenge is never inferred from a timeout.

B business authorization transports the protected receipt with delegated role-
use proof (or exact cached signed receipt/hash bound to the actual armed release).
Node verifies the protected receipt, local gate/current generation and full
approval/release/delegation/use chain; CP separately checks committed current
rows/lease/receipt. Wrong gate, restart NONE, wrong PoP/domain/key/issuer/TLS/
ledger/hash, replayed challenge, expired receipt and precommit delivery deny,
including attacks with dependent hashes rebound. Signatures in the fixture model
are explicitly SYMBOLIC role-labelled digests, not crypto or custody evidence.

ObservationScope is a CP-local typed nonbusiness result, never a signed bearer
business grant or ChannelProof factory. AVAILABLE identifies authoritative current
or exact protected frozen-intent target DER/epoch provenance, member/intent/
current tuple, allowed literal POST observation paths, challenge and expiry.
AUTHORITY_UNAVAILABLE/SCOPE_DENIED/EXPIRED/UNKNOWN_SCOPE refusal cannot return an
eligible target/admission/ack. Fixed b_read_observation_scope validates principal,
Node/intent/current guard scope; no caller SQL/table/DER/identity substitution.
Receipts/role observation remain independent of expired business approval while
existing CP mTLS/control-peer/epoch/trust checks remain valid. Invalid trust is
unavailable, not repaired. Reconcile does not create execution/storage success.

# L1/L2: CAS aliases, full tuples and resolved lost responses

phase-cases.json includes every not-yet-CASed member revocation at k1..4, not
just node0. Revocation from old C7 to8 can equal renewal target8 while DER staysA
and channel is disabled. C alone never means done: exact operation ledger, DER,
full current tuple and fresh valid frozen authority decide; conflicting aliases
refuse and preserve monotonic evidence/quarantine. Matrix P102 is **overlap P+1**;
final P103 remains separately required, R2 unchanged.

UNRESOLVED_AFTER_EXACT_LEDGER_REREAD replaces the ambiguous lost-response label.
RESOLVED_EXACT_COMMIT_FORWARD requires exact committed ledger/current tuple,
valid authority and freshness. Missing ledger alone says nothing about external
Node effects; recorded intent and actual Node outcome must be observed before
an exact forward attempt. Conflicts/unavailable/indeterminate stay quarantined;
matching ledger never waives revoke/expiry/freshness or permits reset/old restart.

# L3/L4/L6: typed writers and lock-only rights

authority-matrix.json types every table -> ALL writer procedures -> EXECUTE
principals/NOLOGIN owner/verbs/columns. Separate fixed lock-only SECURITY DEFINER
procedures give ordinary runtime/online principals **no authority-table UPDATE,
INSERT, DELETE or lock_sentinel privilege**. Remove that sentinel path, including
key_deliveries wording. No SET ROLE to owner/operator/legacy inv_kernel/app that
would inherit those rights. B pool grants are explicit; plain external behavior
is preserved. Mandatory epoch+tenant guards execute first through fixed owner
lock operations, not bypassed or relaxed. No arbitrary SQL/table/lock-mode input.
Owner is non-super/non-bypass, qualified SQL/search_path pg_catalog, FORCE RLS
and session/service/tenant/selected-set checks. Each new B table joins actual RLS
census/collector/ratchet/aggregate pin in the future migration. Direct SELECT
only where required; durable nonce/evidence writes remain narrow procedures.
Actual PG tests must reject direct runtime DML/SET ROLE while authorized locks
work; static rights fixtures cannot establish enforcement.

Every table writer and procedure EXECUTE list is tested causally, not prose regex
on1/17 tables. Removing any writer/grant or adding runtime approval permission
fails policy validation. Safety binds action, Node/epoch/permit/body/nonce/expiry
AND literal POST method/path; no query/percent aliases. Context-budget approval
uses a **distinct protected planning budget role/key/purpose**, external planning
trust pin, domain `saintvision/context-budget/v1`. It binds measured cohort/context/
VM spec/resources/headroom/probe hashes/validity and cannot sign a Node release
or authorize business. No actual key/provider/provenance is claimed.

# L5 and information carried honestly

Raw host AND guest clockOffsetMillis are signed exact integers vs trusted CP,
with nonnegative uncertaintyMillis, sync source/method/producer/evidence,
observedAt and same context/nonce. Require abs(offset)+uncertainty <= minimum of
approved budget and30000ms, authenticated fresh measurement. Unknown, stale,
untrusted or overbudget blocks capability. No request clock override or host
clock adjustment. Physical/resource capability is still unmeasured/HOLD.

JSON Schema integer can accept lexical2.0: strict UTF8/no-surrogate/duplicate/
float decoding and exact integer checks are normative before schema/Go encoding.
Plain :2 times remain unchanged. displayLabel limit is128 Unicode code points
and separately512 raw UTF8 bytes, no NFC; canonical escaping has its own bounded
payload size. Terminal Sequence/Nonce are protected transitively by exact frame
bodySHA and must also pass frame sequence/replay/expiry checks. Signature input
is ASCII registered domain || single0x00 || decoded canonical C2 bytes, no LF.

**300s CP admission lease is not a Node-enforced compromised-use-key bound.**
Node bound is delegation/release/approval/cert expiry plus acknowledged local
gate invalidation. CP denies expired lease immediately at current checks; no
instant distributed revocation or shorter delegation guarantee is invented.
Per-restart protected signer/key-custody availability remains a future operational
prerequisite, not an already running service.

# Evidence and next owner

Schema positives/negatives cover gateControl/safety/observeInput/signedEnvelope/
roleConfig/gateAck/keyDeliveryReceipt/ObservationScope and all required fields.
Stateful chain inputs include real synthetic approval intervals, actual model
gate records, challenge/PoP/controller receipt/current ledger rather than ARMED
booleans or NOW+4000. READMIT(old,old) rejects; REFRESH handles same generation.
All reviewer33 historical probes and earlier failures remain preserved. Actual
Go/crypto/PG/Docker/crash/concurrency/equipment0 and A1-A16 pending. Unmodified
72028 R4 probe still has exact expected exit1 when coexistence is required.

The current source capture scans494 files and expands185 files into2933
candidate DB/ORM expressions,615 helper edges and823 assignment/context/parameter
alias bindings. These are explicit source records, not a claimed complete
runtime count;1374 static receivers remain explicitly unresolved/not proven DB.
They are not silently called nonlocking. Required known business/observe entries
have supported canonical plans; any actual unknown B writer must resolve before
implementation inclusion. Five source-census causal CLI mutations return exact
exit1 CENSUS_MISMATCH (expected), while source regeneration passes. The stateful
schema/rights fixtures currently pass476 cases, all SYMBOLIC/static only.

Commands, exits, KST, hashes and publication gates are captured in this unique
evidence directory. Normal delivery is commit/push/exact Docs then **one actual
whole Rev4 delta review**. No partial freeze or B code before Root accepts that
review and grants concrete bounded implementation/ADR/registry scope. Task stays
open; next owner Root dispatches that review at the final published SHA/Docs.
