---
doc_id: "CONTRACT-FLEET5-P0-PLAIN-PEER-PHASE-DETAIL-001"
title: "FLEET5 P0 plain peer phase field ownership and failure contract"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude task_3529eefa626c through root pending"
updated: "2026-11-05T20:12:00+09:00"
source_of_truth: "Git"
---

# P0 bounded detail for the pending architecture review

Card `FLEET5-COMPUTE-STORAGE-CONTRACT-20261105`, owner Codex, branch
`agent/codex/fleet5-compute-storage-contract-20261105`. Source lifecycle is accepted
2fb; native proof code is fe7ebeff and actual result/report is 5023ce7d. The root
reply `msg_4a1bc0c5516e` requests this addendum while actual Claude review
`task_3529eefa626c / ctx_ba275b06ce0c` assesses the fixed 5023 P0 subsection.
This addendum is not that review verdict or implementation permission.

Read guidance/versions and historical base are recorded in
[[2026-11-05_FLEET5_compute_storage_contract_Codex]]. The main proposal and actual
Linux failure evidence are in [[2026-11-05_FLEET5_compound_lifecycle_B_contract_Codex]].
No production Go/Python/helper, workflow, runtime, key, container or policy is
changed in this addendum. Root's expired-partial disposition is **BLOCKED under
separately reviewed offline recovery**. No new CAS ladder or trigger/version jump
is part of urgent P0.

## Proposed P0 field contract

Use new strict normal proposal/batch schema `:3`; retain legacy normal `:1` and
offline `:2` meanings for exact historical verification/replay only. New normal
preparation must not emit a legacy schema containing new semantics. Old readers
reject `:3` before file/container/journal/channel mutation. Current Go peer floor
and same-version/different-hash rejection stay unchanged.

| Field | Source of truth and validation |
|---|---|
| tenantId / nodeId / recoveryEpoch / endpoint | Existing Node journal identity, owned container arguments and locked current DB channel; exact agreement required |
| rotationId / batchId / proposalDigest | Existing immutable proposal/cohort identity and exact raw manifest digest; no reuse across changed bytes |
| currentChannelVersion C / targetChannelVersion C+1 | Current DB channel CAS and existing +1 trigger; independent of peer phase versions |
| currentPeerPolicyVersion P / currentPeerPolicySHA256 | Actual current durable `.peer-policy` entry from the owned state volume, bound to its exact current policy bytes; never inferred from C, a bundle flag or worker-root JSON alone |
| overlapPeerPolicyVersion P+1 / overlapPeerPolicySHA256 | Generated exact overlap bytes with old+new CP fingerprints and valid bounded expiry |
| finalPeerPolicyVersion P+2 / finalPeerPolicySHA256 | Generated exact final bytes with new CP pin only and valid bounded expiry; never same-version bytes as overlap |
| floorObservationSHA256 | Digest of the exact protected observation described below, including journal identity, volume/container/consumer provenance, version/hash, nonce and capture state |
| current/nextNodeCertificateDER_SHA256 | Parsed actual DER fingerprints, exact key/SAN/EKU/time/CA binding; separate PEM byte hashes remain in file digest inventory |
| current/nextControlCertificateDER_SHA256 | Parsed public CP DER and exact overlap/final pin lists; no request-selected key |
| predecessorArchiveSHA256 / predecessorJournalRawSHA256 | Settled 2fb original-byte predecessor proof and actual current journal; reject predecessor `.next` before successor intent |
| installer/source hashes / stateVolume evidence | Reviewed exact helpers plus actual named volume, node label, current container ID/config/image, consumers, protected-file hashes and metadata |

P, P+1 and P+2 must be genuine positive integers within canonical schema range;
overflow, bool coercion, duplicate JSON keys, unknown fields and ambiguous argv
refuse before mutation. Any observed floor hash that differs from current policy
bytes is **inconsistent state**, not permission to choose a convenient new P.
Existing already-inconsistent legacy partial finalization needs separately
reviewed forward recovery; P0 does not rewrite it, reset a floor or merge identities.

The closed proposed shapes are in
`docs/vault/30_Development/Evidence/fleet5-compute-storage-contract-20261105-codex/proposed-plain-peer-phase-v3.schema.json`.
This is a reviewed-artifact candidate, not an installed canonical schema. Its
shape check does not authenticate an observer or replace the semantic checks here.

The installation receipt must add exact peer phase version/hash and the observed
post-start floor, not merely restartObserved=true. CP stage/commit, finalization,
Node attestation, canonical CP retirement and successor verification bind these
fields under the new schema. Keep original 2fb manifest/receipt/journal bytes and
signatures immutable; do not append unsigned fields to an old signed receipt.

## Floor observation ownership and authenticity

The floor is in the **Docker named volume**, not necessarily in the host-side
worker directory. The actual Go process holds the journal flock. Existing
`readPrivate` checks regular file/mode/size but does not itself establish container
ownership or bind a copy exported by a helper to a particular Node. A host path
string, caller-supplied version, unsigned ready file, PID or certificate date is
not sufficient evidence.

Minimal P0 can use a **trusted local operator state observation**, without adding
a new public Node HTTP endpoint or changing the storage wire. Its trust is the
existing pinned helper and authenticated operator/daemon context, not remote
hardware attestation. The receipt must say
`writerKind=local-operator-container-state-observation`, never node-attested or
cryptographic proof that the host cannot lie. A hash binds bytes, not their origin.

The observer must establish all of the following before its output can supply P:

1. The configured local daemon and exact Node container ID/image/name/ownership
   label match the approved manifest and current operation. Exact `/state` mount
   is the expected named RW volume with matching node label and approved consumers.
   Custom daemon/socket, arbitrary state paths, extra consumers or replaced volume
   refuse. Plain P0 introduces no contributed root/path mapping.
2. The live inventory snapshot is **provisional**. Before active credential/policy
   installation, maintenance ownership must establish no owned work, stop the
   exact container, verify it is stopped, and exclude all other RW consumers.
   The stopped container preserves its state volume and identity; no process lock
   is stolen or journal initialized for the observer. The complete selected cohort
   must have consistent quiescent observations before any authority file/pin/CAS
   mutation. Controlled stopping is explicitly recorded as maintenance, not
   mislabeled a read-only preflight. If zero-stop preflight were required, a new
   in-process authenticated observer would need separate contract review.
3. Read the existing journal directory through a bounded Docker archive from the
   exact container ID, without following links, extracting into host paths,
   creating missing entries or reading Node private-key files. Validate root
   directory metadata and bounded entries; reject absolute/traversal/duplicate
   names, symlink/hardlink/special files, wrong UID/GID, broad modes, truncation or
   archive errors. `/state/journal` must be a real private directory owned 0:0;
   `identity.json` and `.peer-policy` must be regular 0:0, mode0600, nonempty and
   within limits. Decode the identity and floor strictly with exact expected fields.
   Existing bounded archive helpers are source patterns, not proof these extra
   ownership/strictness conditions are already implemented.
4. Read exact active `/state/peer-policy.json` and public certificate bytes using
   the same no-follow/bounded metadata rules. Its version/hash must equal the
   durable floor, and scope must equal actual journal identity/current channel.
   Check actual DER/CA/key identity through the existing verification path without
   exporting the key. Preserve all unrelated journal files; log only fixed IDs,
   metadata and hashes, never raw journal/workload content or credentials.
5. Repeat the bounded observation and container/volume/consumer inspection under
   the operation ownership; require identical identity/floor/policy bytes and
   metadata, same stopped container ID/config/mounts and same volume provenance.
   Any race or unavailable observation is unknown, not zero/no-floor. Missing
   `.peer-policy` on an already enrolled current Node refuses rather than calling
   OpenJournal to create it. A newly initialized Node must first have a real
   accepted startup; that separate initialization is not part of this worker task.
6. Bind root-issued operation nonce/request digest, exact observer/helper SHA,
   capture sequence, container/volume/journal provenance and raw observation hash
   in the immutable preparation packet. Root receives it through the existing
   authenticated operator channel and verifies freshness against that outstanding
   request and current DB channel. Do not accept an arbitrary uploaded JSON copy
   or a self-declared writer identity. Local operator/daemon compromise is outside
   this trust model and is stated explicitly.

The request digest is the root's **preflight request** digest, fixed before the
observation exists. Observation binds that digest; final proposal binds observation
SHA; final raw proposal digest is computed last. Do not create a circular digest
by putting the final proposal digest into its own floor-observation input.

The new helper must not pretend that two archive reads provide kernel-level
hostile-admin protection. Quiescence, no other volume writers, strict provenance
and trusted operation ownership are the reason this observation can supply P.
If those facts cannot be proved, stop as unknown. The unmodified real Go journal
remains the final enforcement boundary and must independently reject any mismatched
version/hash at actual startup.

## P0 phases and failed-start rollback

| Durable helper phase | Required boundary and recovery |
|---|---|
| prepared | Exact raw proposal + observed P/hash + predecessor fixed; no authority mutation; repeat checks before apply |
| stop-intent / stopped | No owned work; exact current container only; fresh quiescent floor observation; no other writer |
| installing | Backup exact old public bytes once, preserve original container/config/volume; durable intent precedes each active copy |
| installed / start-intent | All candidate bytes and expiry/CA/SAN/EKU/key/peer tuple prevalidated; copied into stopped exact container; no policy-copy into a running Node |
| start-unknown | Any start/restart exception, timeout, missing listener or receipt; first assume possible target pin, then quiesce exact owned container and inspect actual floor |
| overlap-started | Real Go acknowledgement + observed P+1/hash exact; forward-only even before any CP CAS |
| channel-staged / switched | Existing C→C+1 CAS and bounded CP overlap/switch; same peer generation tuple bound in receipts; no old restoration |
| final-start-intent / final-unknown | Install exact final P+2 bytes only at permitted barrier; target floor may already be P+2 even if restart/listener fails |
| finalized / retired | Actual final P+2/hash + exact original-byte signed archive/CP retirement; successor starts from this real P+2, not C+1 |
| rolled-back | Allowed only with demonstrably unchanged old floor and old CP CAS, valid old authority, no new work and unchanged owned state; exact restoration proof required |

Automatic exception handlers and outer wrappers must use the **same guard** as
explicit rollback. `restartObserved=false` does not permit restoring old files.
The failure classification is concrete:

- Failure before active copy: preserve state and existing start/stop status;
  restore a deliberately stopped old container only after identity/old-floor/CAS
  recheck. Never discard the preparation record to start a different plan.
- Failure after copy but before a target peer pin, with exact all-old floor/CAS
  proved in a quiescent observation: restore exact old public bytes and original
  container configuration under the fence, start only valid old authority, then
  verify actual old floor/DER. Preserve backups and an explicit rollback record.
- A failed Go start can have pinned P+1 **before** expiry/TLS/listen checks. If the
  actual floor is P+1, or its persistence cannot be determined, no old byte copy,
  old container restart, floor deletion or automatic rollback is allowed. Resume
  the exact next tuple forward, or remain blocked with the evidence intact.
- At finalization, observed P+2 forbids restoring overlap P+1 as well as old P.
  If final start fails, retain final bytes and replay forward; no same-version hash
  exception. A still-date-valid old cert does not reverse this barrier.
- CP stage/CAS/switch, foreign container/consumer/root or unproved state always
  refuses old restoration. A lost CAS response requires existing current-channel
  reconciliation, never guessing from a helper phase or a timeout.

Do not copy new peer policy into a still-running container and then call restart:
current Go TLS/Authority reads live files, so an incoming request could pin new
bytes before the helper records restart. Stop/fence before copies, and treat every
wrapper's fallback as potentially crossing the first-floor barrier. No wrapper
may silently downgrade or claim ready on exception.

## Native proof and fault test matrix for the implementation review

| ID | Meaningful required test / exact acceptance |
|---|---|
| P0-01 | Preserve native baseline fe7/42014770700 red and ZIP digest; setup errors are not that proof |
| P0-02 | Actual Python new-schema generation and unchanged real Go Journal/Authority/TLS complete **two NORMAL cycles**, same journal/key/identity: peer P→P+1→P+2→P+3→P+4 and channel C→C+1→C+2 |
| P0-03 | Go post-start floor bytes equal exact generated phase bytes/hash at every boundary; no mock pin/restart, alternate module, GOOS or file-mode bypass |
| P0-04 | Actual floor source is named volume: wrong container/volume/consumer, stale request nonce/helper hash, worker-root-only fake floor, forged JSON, changed second archive, symlink/hardlink/bad owner/mode/duplicate/oversized/missing floor all refuse |
| P0-05 | Candidate expiry/CA/SAN/EKU/key/DER/identity/tuple failure is caught before active install where possible; existing real pin-before-expiry negative retained and failure classified as advanced/unknown, never unchanged |
| P0-06 | Kill after every host public-file write and container copy, before/after durable helper intent, before Go start, after actual peer floor sync/rename/directory-sync, before listener/ack and after lost start response |
| P0-07 | Both direct rollback and automatic failed-start catch path: before target pin exact old restoration succeeds; callback/process fails **after real PinPeerPolicy** and before receipt, old restoration is refused without copying old bytes or resetting floor |
| P0-08 | Final P+2 pin then failed start forbids rollback to overlap; exact final retry succeeds; same-version altered hash/lower P remain rejected by actual Go |
| P0-09 | CP stage conflict/lost response, CP switch crash, old date-valid cert after CAS, stale/partial cohort and concurrent operation lock ownership preserve evidence and refuse unsafe rollback |
| P0-10 | New `:3` on old helper rejects before mutation; legacy `:1` original-byte archive verification remains strict; changed peer fields/hashes or unsigned additions fail signature/digest checks |
| P0-11 | Exact 2fb `.next` predecessor refusal, original journalRaw/manifest/receipt bytes and canonical CP retirement survive two cycles; replay only retires exact verified predecessor duplicate |
| P0-12 | P0 refuses storage-policy/contribution configuration and other unsupported mounts **before mutation**; full B/storage remains unimplemented; no dropped sampler to make plain tests pass |
| P0-13 | Expired-partial normal state is BLOCKED under separate offline recovery; test no CAS ladder, trigger bypass, version jump, reset, old pilot touch or automatic fallback |

Root's actual architecture verdict is still required before authoring these
production changes. The plan does not claim these future tests are executed.
Only the preserved native baseline failure and existing local/publication checks
have actually run. Physical/all-five acceptance and contributed storage stay false.
