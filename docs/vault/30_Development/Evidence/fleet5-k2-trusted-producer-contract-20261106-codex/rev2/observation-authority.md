# Revision2 observation authority and attempt lifecycle

PROPOSED/HOLD; no deployed issuer, accepted new wire/domain/key, installation or
effect permission. Root choice msg_6df22674ff19 adopts necessary policy conditions
only. This closes the missing PRESENT-head rule in K2-M1 without changing K1.

## Separate parents and capabilities

K1 parentOperationId identifies a root-fence migration/restore operation in the
appropriate authenticated operation map. attemptId identifies one immutable
observation attempt under that parent and one exact registered Node scope.
normal3LeaseId is a separately typed common normal:3 operation lease after a
terminal migration; it is not a K1 MigrationOperationID. The original plan's
MigrationOperationID remains historical, regardless of either live parent.

CurrentView is derived data requiring PRESENT head plus two fresh ordered M2s.
It is not permission to issue a challenge or create/start an observer Exec.
An ObservationRefreshAuthorization is a separate proposed internal authenticated
permit for a named method/attempt. Until its closed issuer/body/mediation has an
actual independent review and installation, challenge issuance, replacement,
ExecCreate/Start and rotation refuse ERR[OBSERVATION_AUTHORITY_HOLD], even when
head is PRESENT. A121s-old/missing M2 is neither authority nor an implicit denial
of a future properly authorized refresh; it is a reason CurrentView is absent.

| Future mode | Mandatory independent predicates | What it may eventually produce |
| --- | --- | --- |
| MIGRATION_OBSERVE | Authentic PRESENT head and exact expected native declaration; actual current HELD migration operation/window/fence; installed policy/grants/current statuses and authenticated clock; exact owned root/daemon/container/volume/process/executable preimage; registered approved observer/Exec method and separately granted permission | One original M2 and owned Engine readback for the exact attempt; only a later independent K1 verification can derive CurrentView |
| TERMINAL_NORMAL3_OBSERVE | Exact immutable terminal migration seal; fresh COMMON normal:3 lease/window/fence; same ordered identity scope and owned runtime; installed trust/status/clock; exact method permission | Separately typed normal observation record; never casts the normal lease to MigrationOperationID or claims unchanged K1 can derive a normal CurrentView it cannot consume |
| ABSENT bootstrap | Original A36 requires held migration-owner lease and exact new-start intent; actual closed BootstrapPhaseAuthorization/transition evidence/permission is missing | No effect now; ERR[PREPUBLICATION_AUTHORITY_UNDECIDED] under strict D-PREPUBLICATION |

Every missing/mismatched predicate in an otherwise installed future mode refuses
ERR[OBSERVATION_PRECONDITION_FAILED]. Unaccepted/unprovisioned authority refuses
ERR[OBSERVATION_AUTHORITY_HOLD] first. Unknown effect outcome refuses
ERR[OBSERVATION_OUTCOME_UNKNOWN] and preserves the fence. A normal record requested
as a K1 current view refuses ERR[NORMAL3_K1_CURRENT_UNSUPPORTED]. There is no
generic allow-if-current-is-unavailable path. Normal rotation has its own future
effect authorization and cannot inherit observation permission.

## Closed proposed permit port, not an accepted signature format

Future authenticated CP common-cohort authority is the proposed protected port
for reading/committing permits and attempts. Root operator approval and existing
root-execution/root-fence grants are necessary authorization inputs. Their
existing kind/domain contracts are reused only where the exact frozen subject
and method actually express that use. The present root-execution-decision proof
is not assumed to encode the new attempt/mode/method fields. The missing
authorization attestation wire/issuer/domain registration is explicitly
PROPOSED/HOLD; no new accepted signer or protocol is invented.

Proposed immutable permit body is closed to: policy/installation version;
permitId; exact mode; named method (CHALLENGE_ISSUE, CHALLENGE_REPLACE,
OBSERVER_EXEC_CREATE_START, or RECONCILE_OWNED_ATTEMPT, never wildcard);
ordered cohort/scopes; typed parentKind/parentId/lease raw hash/fence;
PRESENT head/declaration raw hash, or the exact terminal seal for normal mode;
attemptId and immutable body hash; approved observer/executable/source/image/
runtime-lock identities; exact owned preimage/root/daemon/volume/container/
PID-start generation; issuer/subject permission reference; issue/expiry and
operator-window bounds; currentVersion/previous attempt version; and idempotency
key. Unknown fields or omitted required predicates refuse. Private keys and
caller-selected trust roots are not body fields. Actual IDs, anchors, wire,
permission and port bindings remain null/HOLD.

The future unexported permit factory authenticates the installed port and exact
authorization before constructing this DTO. JSON unmarshalling into the body,
a body hash, caller role or root-owned file does not authenticate it. K2B
re-acquires this authority immediately before admission, without trusting a
caller-supplied SnapshotToken or K1 report. K2A only consumes already produced
authenticated records; all issuance/permit signing/archive/Engine writes are K2B.

## One current challenge slot; immutable attempt archive

K1 Challenges is keyed parentOperationId + NUL + C2(Node scope) hash. Therefore
exactly one current observation attempt may own that slot. The new proposed
attempt archive is keyed independently by immutable attemptId and preserves all
raw challenges, original M2s, permits, intents and outcomes append-only.

| Request/state | Required behavior |
| --- | --- |
| Same attemptId and same complete bytes | Return the ORIGINAL issued challenge/times/outcome. Never mint another nonce, move timestamps, increment versions or repeat Exec |
| Same attemptId with changed bytes/mode/method/parent | ERR[OBSERVATION_ATTEMPT_COLLISION] before any new write |
| New attempt while old is pending/running or lacks terminal proof | ERR[OBSERVATION_ATTEMPT_NOT_TERMINAL] |
| Prior exact attempt is terminal-known, no Exec/descendant in flight, parent still valid, fresh specific authorization | Atomically append new immutable attempt, replace CURRENT challenge slot and advance currentVersion; keep prior raw data |
| Prior outcome may have occurred, reply lost, restart/recovery sees pending intent | ERR[OBSERVATION_OUTCOME_UNKNOWN]; no new challenge, Exec, owner or lease takeover until protected reconciliation establishes exact outcome/quiescence |
| Parent expires before replacement | Refuse the current operation; expiry alone is not takeover. After proven quiescence, any new operation/fence requires its own reviewed authorization |
| Old witness/SnapshotToken after replacement | ERR[CURRENT_CHALLENGE_REPLACED]; old immutable history remains history |

Durable substeps are authorization validation -> challenge issuance -> ExecCreate
intent -> recorded actual ExecID -> ExecStart intent -> observed running -> exact
terminal/readback verification. All writes happen only under separately granted
K2B authority, mandatory common cohort reservation and owned OS guard. Any
possibly executed substep becomes UNKNOWN/forward-only; a timeout never proves
exit. A repeated request cannot execute an uncertain substep again.

Replacing a CURRENT slot must NEVER rewrite K1's original History.Challenges or
any historical packet. K1's historical map also has one slot per operation/scope:
if adding a new durable historical consuming record would require two different
original challenges in the same K1 historical slot, unchanged K1 cannot represent
that combined history. Refuse rather than merge it; a separately authorized new
parent operation/fence or reviewed contract revision is required. A fresh current
NativeWitness outside the retained packet can use the replaced live slot while
the packet's original historical challenge remains immutable.

Restart reloads durable intent/attempt/owner state. It cannot reset the slot,
clear a journal, unlink a lock or restart an old image. Protected reconciliation
is itself a separately authorized method; its readback must establish actual
process/descendant/Exec quiescence before any transition or new owner. No broad
offline recovery or lease-expiry bypass is added.
An UNKNOWN/possibly executed attempt in EITHER cohort member holds the common
cohort fence and forbids new challenge issuance/replacement, new Exec and new
owner across BOTH scopes. Only the separately authorized exact reconciliation
path may inspect/settle that attempt under the retained owner; a healthy other
member cannot release the ambiguity or publish all-cohort readiness.

## Exact original A36

The exact original red/green strings from design8874 are reproduced in
future-runtime-A01-A40.json, case A36, and their UTF8 hashes are checked against
the original Git bytes. Its bootstrap branch requires the held migration lease
plus exact new-start intent; its later-normal branch requires the immutable
terminal seal plus fresh common normal:3 lease. Neither necessary condition
is a deployed authority or sufficient permission by itself. Both branches remain
NOT_RUN, and their green production belongs to K2B/Node producers, never K2A.

<!-- original-A36 -->
```json
{
  "id": "A36",
  "red": "Bootstrap M2 demands terminal inventory before it can be produced, or later normal:3 requires a dead migration-owner lease forever",
  "green": "Held migration lease plus exact new-start intent admits bootstrap observation only; immutable terminal seal plus a fresh common normal:3 operation lease admits later observation/rotation; generic terminal helpers stay denied"
}
```
