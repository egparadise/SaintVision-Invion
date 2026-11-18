---
doc_id: "ADR-PROPOSED-FLEET5-AUTHORITY-REPLACEMENT-R2"
title: "Proposed FLEET5 authority replacement and advance-renewal contract R2"
version: "1.1.0"
status: "review"
author: "Claude"
updated: "2026-11-19T01:49:19+09:00"
source_of_truth: "Git"
---

# Status

**PROPOSED, NOT IMPLEMENTED. Activation NOT_AUTHORIZED.** R2 revises [[Proposed FLEET5 authority replacement and advance-renewal contract R1]]. It closes the five HIGH findings and the MEDIUM finding 6 of the independent Codex R1 review.

**Revision 2 (1.1.0).** The independent Codex review of R2 asked for changes. That review covered candidate `14ddc8e9` and evidence head `9a9bc90c`; its report is `docs/vault/30_Development/History/2026-11-19_FLEET5_Authority_Replacement_R2_Codex_Review.md`, held in the reviewer worktree `fleet5-independent-review-task723adb91` and not committed here.
- Revision 2 fixes these in place, in the order the review gave:
  - writer fencing on interrupted A1 (R2 review finding 4, high);
  - serving freshness and inventory (finding 3);
  - the E2 row representation (finding 4);
  - validity at reliance, settlement and handoff (finding 5, high);
  - manifest-scoped identities (the remaining opID question).
- The branch is `egparadise/fleet5-authority-replacement-r3-20261119`.
- Paths and the schema ID are unchanged. R2 was never accepted, so nothing consumes the earlier shape, and a document in that shape now fails the schema.
- The sections below describe revision 2. *Revision 2 changes* lists the deltas.

**The review report:**
- The report is `docs/vault/30_Development/History/2026-11-19_FLEET5_Authority_Replacement_R1_Codex_Review.md`.
- It sits in the reviewer's worktree `fleet5-ca-replacement-review-20261119`, sha256 `5c88dcf38f527a3ee98d85f88a44cdc9516691d987e0a6de28a06ec66ce2d829`.
- It is not committed on this branch.
- It reviewed proposal `12b67c01` and evidence head `bb6e028d`.

**R1 is preserved byte-for-byte.** R1's contract, schema, checker, generator, fixtures, handoff and 155-test gate are unchanged and still pass. R2 lives beside R1:

| Artifact | R2 location |
|---|---|
| Schema | `contracts/proposed/fleet5-authority-replacement-r2/fleet5-authority-replacement-v2.schema.json` |
| Expectations | `contracts/proposed/fleet5-authority-replacement-r2/expectations.json` |
| Checker, recovery decision and reference executor model | `tools/check_fleet5_authority_replacement_r2.py` |
| Generator | `tools/generate_fleet5_authority_replacement_r2_fixtures.py` |
| Gate | `tests/core/test_fleet5_authority_replacement_r2.py` |

**The corpus (revision 2):**
- 1 real HOLD instance.
- 49 positive fixtures, which together cover every one of the 20 recovery actions.
- 61 rejection fixtures, covering 31 rejection codes.
- 1 operator handoff.
- 1 human-readable full operation manifest.

This is still a planning contract. Passing every gate here authorizes no enrollment, CAS, policy publication, restart or cutover. Production stays **HOLD**. The production runtime has none of the mechanisms this contract requires (see *Runtime integration gaps*).

# What changed from R1

R1 accepted plan-supplied hashes and journal counters as truth. R2 replaces each of those with evidence that a test can falsify.

| R1 | R2 |
|---|---|
| Label hashes for keys, leaves and roots | Real public DER for every certificate and CSR, from publicly derivable Ed25519 fixture keys. The checker parses and verifies signatures. |
| Prior IDs and key hashes kept in separate arrays | One authenticated tuple (`nodeID`, `status`, `publicKeySHA256`, `channelCertificateSHA256`) per DB row, bound to a prior leaf the prior CA signed |
| Readback of presence, C, leaf hash and P | Exact pre- and postimages, audit and journal operation IDs, a fresh challenge per process and member, loaded anchor digests and handshakes |
| Phase enum per resumption | Immutable operation manifest. Each operation gets PENDING, COMMITTED, CONFLICT, ABOVE_PLAN or UNVERIFIED, plus explicit apply and acknowledge lists. |
| E1–E3 enrollment | Fenced reservation, then E1 reserve → E2 row admit → E3 channel provision → E4 policy publish → E5 settle |
| Deadlines compared against `observedAt` | Deadlines evaluated at `checkpoint.resumeAt` from measured phase budgets and the actual certificate validity |
| A terminal-only transition | `mode` is TERMINAL_REPLACEMENT or ADVANCE_RENEWAL. Cutover is TERMINAL_SINGLETON, DUAL_ANCHOR_OVERLAP or QUIESCED, and dual overlap requires a retirement proof. |
| A ceremony whose outputs were required before A1 | A1 is the ceremony. Its outputs are forbidden before A1 is attempted and required once A1 is durable. |

**Phases.** The rotation phases are:
- A0_PREFLIGHT_READ
- A1_NEW_TRUST_AUTHORIZED
- A2_ANCHOR_STAGED
- A3_ROTATION_LEAVES_INSTALLED
- A4_CHANNEL_CAS
- A5_POLICY_PUBLISHED
- A6_CP_CONTEXT_SWITCH
- A7_ROTATION_SETTLED

The enrollment phases are E1_ENROLLMENT_RESERVED through E5_ENROLLMENT_SETTLED. Enrollment still starts only after A7.

**Recovery actions.** R1 had 11 recovery actions. R2 adds seven, for a total of 18:
- HOLD_RESERVATION_MISMATCH
- HOLD_WRITER_FENCE
- HOLD_MANIFEST_MISMATCH
- HOLD_DUPLICATE_EVIDENCE
- HOLD_ANCHOR_STAGING_UNVERIFIED
- HOLD_SERVING_EVIDENCE_INCOMPLETE
- HOLD_DEADLINE_INSUFFICIENT

Revision 2 adds HOLD_PROCESS_INVENTORY_CHANGED and HOLD_VALIDITY_LAPSED, for a total of 20. Rollback to the terminal CA is still not representable.

# Revision 2 changes

| R2 review finding | Revision 2 |
|---|---|
| 4 (high): interrupted A1 returned RESUME before the live fence was compared; the executor then signed | The live fence is checked before every custody, ceremony, abandon, resume and COMPLETE decision after a mutation was attempted. The checked fields are token, holder plan digest, monotonic `generation` and a fresh `readAt`. Missing, transferred and stale fences all HOLD_WRITER_FENCE. The executor model also refuses to sign or apply without the fence. |
| 4: log validation skipped when no outputs and no signed entries, executor dereferenced the absent log | A1 in flight with a key in custody always validates. An absent log, a CA key count other than 1, or a key the plan never recorded is HOLD_CUSTODY_UNRESOLVED. |
| 4: rowPresent=false placeholder counted as pending, then ROW_ADMIT appended a duplicate row | Absence is omission. `rowPresent` is removed, so a placeholder fails the schema. The executor refuses ROW_ADMIT when any row for the NodeID exists. |
| 3: challenge issuance age never bounded | Challenge issuance is bounded by `challengeLifetimeSeconds`. Every answer carries a trusted CP receipt time (`receivedAt`). Challenges are one-use: the journal records `consumedChallengeNonces`. |
| 3: extra live process IDs ignored at settlement | An authoritative `liveInventory` from the CP process registry must equal the frozen inventory. Otherwise HOLD_PROCESS_INVENTORY_CHANGED. A readback from a non-live instance is not evidence. |
| 3: 120 s / 15 s windows need fleet measurement | The windows are measured plan inputs under contract caps. Null is AR-HOLD-REQUIRED; wider is AR-SERVING-WINDOW. |
| 5 (high): policy start time unchecked | A planned policy must be valid at resume time. |
| 5: COMPLETE returned before any validity check | COMPLETE is judged at the final observation; otherwise HOLD_VALIDITY_LAPSED. The handoff re-checks validity at its own time. |
| 5: prior leaves and installed policy unbudgeted in advance renewal | Still-serving prior leaves are budgeted. The installed prior policy is budgeted through `installedPolicyNotAfter` validity readback. |
| 5: dual overlap is conditional | DUAL_ANCHOR_OVERLAP requires `overlapRuntimeEvidenceRef`, or the plan is HOLD. QUIESCED keeps its own quiesce evidence. |
| Question: opID from pre-ceremony inputs; bare opID across manifests | The opID is the digest of the canonical operation body under the plan digest. Audit and journal rows are keyed by `{manifestDigest, opID}`. The same opID under another manifest is CONFLICT. |

# Contract

## D1. First admission (finding 1)

- A NEW_ENROLLMENT carries a reservation. Its digest binds tenant, epoch, PC, NodeID, CSR SHA-256, plan digest, writer fence token and the existing-rows readback SHA-256.
- The reservation also carries a verified `nodeStateEmpty` proof. Node-owned state left on the machine means the enrollment is not a first admission.
- The existing-rows readback must include RETIRED and DISABLED rows (`includesRetired: true`). NodeID and key uniqueness is checked against every historical row.
- Admission is split into journaled operations: RESERVE (E1), ROW_ADMIT (E2), CHANNEL_PROVISION (E3), POLICY_PUBLISH (E4) and SETTLE (E5, a fresh authenticated handshake and heartbeat).
- A row present without C=1 is no longer automatically a foreign writer. During E2 it is the acknowledged ROW_ADMIT, provided its reservation digest matches. It holds otherwise.
- A row or channel created under any other reservation or fence holds with HOLD_RESERVATION_MISMATCH.
- An account name or inventory IP is never ownership evidence. PC1 and PC4 share the account `inviz` in the fixtures on purpose. Ownership comes only from the Node-signed CSR.

## D2. Authenticated identity and authority (finding 2)

**CSR proof of possession.**
- The CSR is an Ed25519 key with a valid self-signature.
- The subject CN equals the NodeID, or `control-plane` for the CP.
- For ROTATION and RETAINED CP keys, the CSR key must equal the prior key.

**Prior binding.**
- The prior leaf must be signed by the exact prior CA certificate. That certificate's SHA-256, SPKI and CN must match the recorded values.
- The prior leaf must carry exactly the member's planned SPIFFE URI.
- Its key and fingerprint must equal the ACTIVE DB row's tuple.

**New root profile.**
- Self-signed Ed25519.
- `CA=true` with path length 0.
- keyCertSign set and digitalSignature clear.
- Validity equal to the plan.
- Not cross-signed. Neither its certificate, its key nor its CN equals the prior CA's.

**New leaf.**
- Signed by the exact new root, with the issuer equal to the root subject.
- SPKI equal to the CSR key.
- One SAN URI equal to the planned tenant/node/epoch URI.
- An IP SAN equal to the inventory address for Nodes and none for the CP.
- EKU serverAuth for Nodes and clientAuth for the CP.
- Non-CA, with digitalSignature only.
- Validity exactly `leafValidity`, inside the root.
- `plannedLeafSHA256` equal to the DER hash.
- No two members share a leaf.

**Role separation.** The prior CA, new CA, CP client, every role key and every Node key are pairwise distinct (AR-ROLE-SEPARATION).

**Signer continuity.** A RETAINED signer needs all of the following (AR-ROLE-CONTINUITY):
- continuity verified for its own scope;
- custody evidence;
- Root's affirmative decision AFFIRMED_NOT_COMPROMISED.

UNDETERMINED keeps the plan HOLD. A REPLACED signer carries no continuity claim.

## D3. Serving evidence (finding 3)

**Process inventory.**
- The CP `processInventory` lists every process that constructs a `NodeTLSClient`, including replicas and the separately invoked storage-check CLI (INVOKED_CLIENT).
- It must cover all five sites: observer_worker, delivery_worker, workspace_runtime, build_product_runtime and storage_check_collector.

**Live inventory (revision 2).**
- Every post-A1 decision reads the authoritative live inventory from the CP process registry. It is answered under the challenge and lists `(site, processID, kind, instanceID)` for each process.
- It must equal the frozen inventory on `(site, processID, kind)`. These all hold with HOLD_PROCESS_INVENTORY_CHANGED, because the frozen manifest cannot cover them and the plan must be re-made:
  - a started replica;
  - a stopped or moved process;
  - a changed kind;
  - a trust readback from a process the plan does not list.
- A trust readback counts only for the instance that is live now. A process restarted under the same ID after its readback is UNVERIFIED until it is read again.

**Fresh readback (revision 2).**
- The challenge is issued by the CP and is one-use.
- `challengeIssuedAt` (CP clock) must be at most `challengeLifetimeSeconds` before `resumeAt`.
- A nonce in the journal's `consumedChallengeNonces` decides nothing. The executor consumes the challenge it acted on, and a re-decision needs a fresh challenge (modelled by `observe()`).
- Every row, process observation, handshake and the live inventory must echo the nonce and carry `receivedAt`, the CP receipt time. Each answer must satisfy all of the following:
  - `challengeIssuedAt ≤ receivedAt ≤ resumeAt`;
  - `resumeAt − receivedAt ≤ observationFreshnessSeconds`;
  - the responder clock (`observedAt`) within `clockSkewSeconds` of `receivedAt`.
- The windows are measured plan inputs (`measuredBudgets`) under contract caps: freshness 120 s, heartbeat 15 s, challenge lifetime 300 s. They are placeholders until the fleet is measured, and the real instance keeps them null.
- Each process reports `trustGeneration`, `loadedAnchorDigest` and `clientLeafSHA256`.
- Each member's handshake reports:
  - the peer leaf;
  - the anchor digest;
  - the CP client URI;
  - the policy digest;
  - a heartbeat within `heartbeatFreshnessSeconds` (at most 15 s).

**Completion.**
- COMPLETE, and settlement of A7 or E5, require every inventoried process and every member to show fresh evidence under the new pins.
- Missing, stale or old-pin evidence holds with HOLD_SERVING_EVIDENCE_INCOMPLETE.
- An unplanned peer leaf is a foreign writer.

**Duplicates.** Duplicate rows, processes, handshakes, reservations or ceremony entries are never collapsed. They hold with HOLD_DUPLICATE_EVIDENCE.

**Staging gate.** A3 stays behind A2 staging that is verified on every member. Unverified staging holds with HOLD_ANCHOR_STAGING_UNVERIFIED, and a half-staged bundle is a foreign writer.

**Binary migration.** Serving under new trust requires `servingBinaryMigration.status = REVIEWED`. The Node binary loads anchors at startup, so anchor reload belongs to that separately reviewed migration.

## D4. Same-phase retry after a committed effect (finding 4)

**The manifest.**
- `expected_manifest()` deterministically derives an immutable operation manifest from the pre-ceremony plan inputs and the ceremony output.
- Each operation records the opID, phase, kind, target, epoch, expected version, endpoint and the exact `pre` and `post` images.
- The opID is `op_` followed by the first 24 hex digits of the digest over the plan digest and the canonical operation body: phase, kind, target, epoch, expected version, endpoint, `pre` and `post` (`operation_id()`). It is computed before the manifest is hashed. Two manifests whose ceremony outputs differ never share an opID for the same phase, kind and target (revision 2).
- The plan and the durable journal store only the pin {planDigest, digest, operationCount}.
- Any change to an input changes the pin (AR-MANIFEST). A journal pinned to another manifest holds (HOLD_MANIFEST_MISMATCH).
- One full manifest is committed for human review at `contracts/proposed/fleet5-authority-replacement-r2/manifests/p02-operation-manifest.json`.

**Operation states.** An operation's readback state is one of:

| State | Meaning |
|---|---|
| PENDING | Exact preimage and no audit. The old fingerprint is compared, not only the version. |
| COMMITTED | Exact postimage and exactly one audit or journal entry keyed `{manifestDigest, opID}` for this manifest. Policy bytes and the policy validity readback are compared, not only the floor. |
| CONFLICT | Anything else (the NODE-0034 analogue). This includes this opID audited under another manifest, at the preimage or the postimage. |
| ABOVE_PLAN | A floor above the planned P |
| UNVERIFIED | Missing or stale observation |

**Recovery positions.**
- **Durable phases:** every operation must be COMMITTED.
- **The in-flight phase:** PENDING operations are applied and COMMITTED ones acknowledged.
- **The next phase with nothing in flight:** a COMMITTED operation is a foreign writer, except a SETTLE observation.
- **Later phases:** operations must be PENDING or UNVERIFIED.

**Writer fence (revision 2).**
- The plan freezes the fence `token` and `generation` (in the plan digest).
- Once a mutation was attempted (A1 in flight or later), every decision first reads the live fence row. This covers the abandon, custody, ceremony, resume and COMPLETE decisions.
- The fence is held only when token, `holderPlanDigest` and `generation` all equal the plan's, and `readAt` is within the freshness window of `resumeAt`.
- Otherwise the plan holds with HOLD_WRITER_FENCE. A higher generation means the fence was re-acquired after this plan took it, so the fence is stale even when the token is unchanged.
- The executor model raises `ExecutorConflict` if it is ever asked to write without the fence.

**Row representation (revision 2).** A readback row exists only for a row the DB returned; absence is omission. There is no placeholder. The executor never creates a second row for one NodeID.

**Ceremony log.** The log must show:
- exactly one CA key;
- every signed leaf equal to its planned leaf.

The resulting decisions:

| Readback | Decision |
|---|---|
| A second CA key | HOLD_CUSTODY_UNRESOLVED |
| A second or extra leaf | HOLD_FOREIGN_WRITER |
| A1 interrupted with the planned key present, fence held, log present with exactly one key, CA key recorded in the plan | RESUME at A1 by deterministic re-signing. Ed25519 makes the leaves byte-identical. |
| A1 interrupted with a key present but no log, zero keys, or a key the plan never recorded | HOLD_CUSTODY_UNRESOLVED (revision 2) |
| A1 interrupted under a missing, transferred or stale fence (key present or not) | HOLD_WRITER_FENCE (revision 2), never re-signing or abandon |

**Reference executor model.**
- `apply_op`, `execute_resume` and `journal_durable` model the executor.
- `execute_resume` applies only the decided operations and raises `ExecutorConflict` on a moved preimage.
- The gate proves that a second execution mutates nothing, including audit writes and leaf issuance.

## D5. Expiry during a pause, and advance renewal (finding 5)

**Deadline check.** `deadline_insufficient()` runs at every resumption at `resumeAt`. The work end is `resumeAt + Σ measured phaseSeconds of the remaining phases + safety + clock skew`. The plan holds with HOLD_DEADLINE_INSUFFICIENT when any of these is true:
- the new CA is not yet valid;
- the new CA's remaining life after the work end is inside its warning lead;
- the leaves are not yet valid;
- the leaves' remaining life after the work end is under the leaf renewal lead;
- any planned policy is not yet valid at `resumeAt`, because publication may happen now (revision 2);
- any planned policy's remaining life after the work end is under the policy renewal lead;
- in ADVANCE_RENEWAL before A7 settles, the work end is past the prior CA's notAfter;
- in ADVANCE_RENEWAL before A7 settles, the work end is past the overlap's `mustEndBy`;
- in ADVANCE_RENEWAL before A7 settles, the work end is past the notAfter of any still-serving prior leaf, for a Node or for the CP client (revision 2);
- in ADVANCE_RENEWAL up to A5, a member still on its prior policy has a validity readback (`installedPolicyNotAfter`) that ends before the work end (revision 2). A missing or stale validity readback for that dependency is HOLD_SERVING_EVIDENCE_INCOMPLETE.

**Settlement and handoff validity (revision 2).**
- COMPLETE is judged at the final observation (`resumeAt`), never from the journal alone. The new CA, the leaf validity and every planned policy must already be valid, with more than safety + skew left before notAfter. Otherwise HOLD_VALIDITY_LAPSED, for example after a pause.
- A committed policy publication reads back the planned policy's validity.

The overlap is never extended. Unknown budgets keep the plan HOLD.

**Modes.**
- TERMINAL_REPLACEMENT requires an expired prior CA (AR-TERMINAL-NOT-EXPIRED), a TERMINAL_SINGLETON cutover with no overlap (AR-MODE), and staged and final bundles that are the new CA only (AR-TERMINAL-ANCHOR).
- ADVANCE_RENEWAL requires a currently valid prior CA with at least the successor lead remaining. Its overlap must be no longer than the successor lead (AR-ADVANCE-WINDOW).

**Dual-anchor overlap.**
- In DUAL_ANCHOR_OVERLAP, A2 stages {prior, new}.
- A7 adds ANCHOR_RETIRE and CP_ANCHOR_RETIRE operations, which together form the retirement proof.
- COMPLETE requires every member and process to report the final new-only bundle.
- A retirement observed before its phase is a foreign writer.

**Quiesced cutover.** QUIESCED is an explicit singleton cutover. It requires its own runtime proof of quiescence (`quiesceEvidenceRef`).

**Dual overlap is conditional (revision 2).** DUAL_ANCHOR_OVERLAP stays a conditional design until independently verified runtime evidence exists for anchor reload, retirement, timing and interruption. A PROPOSED plan needs that evidence in `overlapRuntimeEvidenceRef`, otherwise it is AR-HOLD-REQUIRED. TERMINAL and QUIESCED plans carry none (AR-MODE).

## D6. Handoff scope (finding 6)

- The PC1 handoff is built only from a COMPLETE plan whose verdict is clean.
- Its schema is `fleet5-authority-replacement-enrollment-handoff:2`.
- Its inventory places the CP on PC3 (`placement.controlPlaneHostPC`). PC3 is declared co-located with `exclusionReason: cp-host-colocation`, and PC5 is excluded.
- It carries `acceptance.scope = FOUR_MEMBER_MIGRATION` and `fiveNodeReadiness = NOT_ESTABLISHED`.
- Passing `validate_five_node_inventory` does not establish fleet readiness, DER issuer or a fresh handshake.
- **Revision 2:** `enrollment_handoff(..., at=)` re-checks validity at the handoff time, which defaults to `resumeAt` and is never earlier. It refuses a lapsed credential or policy. It records `validity.evaluatedAt`, `validUntil` and `renewalDueBy`. A consumer re-checks validity at use, because the handoff proves validity only at `evaluatedAt`.

# Finding → closure → tests

The gate is `tests/core/test_fleet5_authority_replacement_r2.py`. Its test names carry the finding prefix.

| Finding | Fixtures | Gate tests |
|---|---|---|
| 1 First admission | p14, p15 (E2 row landed: ack), p16 (E3 missing: apply), p17 (foreign reservation); r09–r11, r14, r41–r44 | `test_f1_*`: every E-phase boundary landed or not; every reservation field bound; fence, digest and channel holds; shared account is no proof |
| 2 Identity and authority | r12, r13, r26–r40 | `test_f2_*`: seven leaf mutations (impostor root, other node URI, other epoch, client EKU, no IP SAN, extra IP SAN, validity); key swap; hash-only rejected; prior tuple per PC; row status; prior CA identity; 10 pairwise role collisions; signer decision, scope and REPLACED |
| 3 Serving evidence | p26–p31; r45–r47 | `test_f3_*`: each of six processes missing; handshake field mutations; heartbeat and freshness boundaries at ±1 s; duplicate collections; A3 staging per member; binary gate; five-site inventory |
| 4 Retry after commit | p04, p09, p18–p25, p30, p31; r48–r51 | `test_f4_*`: full drive from A1 to COMPLETE with crash-before-journal and duplicate delivery at every phase (second run: zero mutations, one audit per operation); every prefix of every multi-op phase; moved preimage; 0 or 2 audits; old fingerprint; policy bytes; effect of an un-journaled phase; fence and manifest; manifest sensitivity; A1 deterministic re-signing |
| 5 Expiry and advance | p32, p33, p34–p39; r52–r58 | `test_f5_*`: policy deadline boundary ±1 s; leaf deadline from the actual certificate; successor validity at use time; independent notBefore checks; overlap deadline ±1 s; dual staging then retirement; early retirement; terminal still rejects dual; successor-lead start boundary ±1 s |
| 6 Handoff scope | handoff from p05 | `test_handoff_*`: four-member scope, PC3 co-location, PC5 excluded; refuses unsettled or rejected plans |
| R2 review 4: fence on interrupted A1 | p03 (fence held), p40 (transferred), p41 (log absent), p42 (stale generation) | `test_r2f4_*`: 8 fence faults × key present/absent; fence boundary; fence at A4, COMPLETE and E2; executor refuses without fence; 4 log states × outputs recorded or not; unrecorded key |
| R2 review 4: E2 row representation | p15–p17 regenerated | `test_r2f4_*`: placeholder fails schema; no second row; interrupted E2 resumes to exactly one row |
| R2 review 3: freshness and inventory | p43 (unplanned live replica), p44 (consumed challenge), p45 (issuance too old); r59 | `test_r2f3_*`: issuance age ±1 s; receipt before issuance, after resume, responder skew, other challenge for row, process, handshake and live inventory; skew bound; tighter measured window; window caps; one-use challenge; 7 kinds of inventory churn × 3 positions; restarted instance; registry source; duplicate live entries |
| R2 review 5: validity | p46 (COMPLETE after pause), p47 (policy not yet valid), p48 (installed prior policy lapses); r60, r61 | `test_r2f5_*`: COMPLETE validity ±1 s; six dependencies independently; policy start; handoff at later time, at bound, before settlement; prior leaf for PC2, PC4 and CP; installed-policy readback missing, short and stale; replaced policy no longer a dependency; committed policy validity; conditional overlap |
| R2 review: manifest-scoped identity | p49 (audit under other manifest) | `test_r2id_*`: different ceremony outputs give different opIDs (R2 collision shown); opID = body digest; foreign-manifest audit at postimage and preimage for both journals; unrelated history ignored; bare opID fails schema |

**Mutation check.** The checker gets 23 single-fault mutants: each one removes one F1–F5 safeguard. The gate kills all 23, and the checker hash is restored afterwards. Section *Verification* in [[2026-11-19_FLEET5_Authority_Replacement_Contract_R2_Claude]] has the record.

**Revision 2 mutation check.** 29 further single-fault mutants each remove one guard added in revision 2. The gate kills 28. The 29th (`ID-exact-key-not-required`) is equivalent: the schema limits an audit key to exactly `{manifestDigest, opID}`, and any entry with this opID under another manifest is already CONFLICT. Matching the opID alone therefore means the same thing. The record is in [[2026-11-19_FLEET5_Authority_Replacement_R2_Revision_Claude]].

# Runtime integration gaps

The production runtime does not yet implement any of the following. Each gap is a separate implementation card. That card needs hosted integration evidence on a disposable transactional DB with real ephemeral PKI. Until then this contract cannot be executed.

1. **Fenced first admission.** `tools/lan_pilot.py:919` creates the node row with conflict ignored. `tools/lan_pilot.py:1294` reuses a certificate on public-key equality. There is no reservation column, no writer fence with a monotonic generation, and no journal of ROW_ADMIT or CHANNEL_PROVISION. The runtime must also verify the reservation against the frozen plan when it commits the row and the channel.
2. **Exact-preimage CAS and audit opIDs.**
   - `services/control-plane/src/inv/node_channels.py:178` compares only `expected_version` and returns NODE-0034.
   - It does not compare the old fingerprint.
   - Its audit row has no operation ID and no manifest digest, so COMMITTED cannot be proven from the runtime.
3. **Trusted-root leaf verification.** `services/control-plane/src/inv/node_channels.py:58` parses DER and checks URI, usage and time but takes no trusted root. Chain-to-exact-root, EKU-per-role and IP SAN checks exist only in this checker.
4. **Policy bytes, validity and journal readback.** No API reads back the installed signed policy digest, its validity, or the policy journal keys per Node.
5. **Per-process trust readback and live inventory.** `services/control-plane/src/inv/node_transport.py:67` loads trust into an SSL context at construction. There is no readback of trust generation, loaded anchor digest or client leaf for the five construction sites, replicas or the invoked storage-check CLI. There is also no authoritative process registry with instance IDs that a decision could compare with the frozen inventory.
6. **Fresh-challenge mTLS observation.** No tool issues a CP-clock challenge nonce, records the trusted receipt time of each answer, or journals consumed challenges. None records a per-member handshake with the peer leaf, anchor digest, CP URI, policy digest and heartbeat.
7. **Node anchor reload.** `services/node-agent/transport/trust.go:103` verifies at connection time, but anchors load once at startup. Staging, dual overlap and retirement need the separately reviewed serving-binary migration. Dual overlap also needs independently verified reload, retirement, timing and interruption evidence (`overlapRuntimeEvidenceRef`). Quiescence needs its own runtime proof.
8. **Measured budgets and windows.** No phase has a measured duration, and the freshness, heartbeat and challenge windows are unmeasured. The real instance keeps `measuredBudgets.source = UNKNOWN` and the windows null.
9. **Deterministic ceremony tooling.** `tools/lan_pki.py` issues a 7-day CA with random serials. There is no offline ceremony that produces the planned root, leaves, policies and bundles, or a ceremony log, from the frozen plan.
10. **Executor.** `execute_resume` is a reference model over JSON readback, not an executor. A real executor must apply only the decided operations, under the live fence (checked again at commit), with the DB transaction as the commit point. It must consume the challenge it acted on.

# Real instance

The instance is `instances/fleet5-nov18-ca-terminal-hold-r2.json`, the real Nov18 plan from Root544 evidence. It records:
- `status HOLD` and `fixture false`;
- `dbAvailable false` and custody NOT_READ;
- historical epoch and rows;
- every key, CSR, leaf, counter, budget, serving window, fence token and generation, and process inventory left null;
- signer compromise decision UNDETERMINED;
- binary migration NOT_REVIEWED;
- placement PC3 with PC5 excluded.

Its recovery decision is NOT_STARTED, and promoting it to PROPOSED is rejected with AR-HOLD-REQUIRED.

# Verification and handoff

The local and hosted evidence is recorded in [[2026-11-19_FLEET5_Authority_Replacement_Contract_R2_Claude]].

**Questions for the independent reviewer (Codex), R1 round.** The R2 review answered these. Its finding 1 covered the endpoint, finding 3 the clocks and finding 5 the overlap.
1. Does the operation-state classification (PENDING, COMMITTED, CONFLICT, ABOVE_PLAN, UNVERIFIED) together with the position rules leave any readback state that could be acknowledged or applied wrongly?
2. Is the opID derivation (plan digest + phase + kind + target) sufficient? Should the operation's pre/post images also be bound?
3. Are the freshness and heartbeat windows (120 s and 15 s) right for the fleet's clocks? Should `challengeIssuedAt` be bounded by the CP's clock rather than by `resumeAt`?
4. Is a dual-anchor overlap bounded by `mustEndBy`, with retirement as A7 operations, an acceptable advance-renewal transition? Or should ADVANCE_RENEWAL be QUIESCED-only until the binary migration lands?
5. Should the reservation also bind the Node endpoint, or is the CSR key sufficient?

**Questions for the independent reviewer (Codex), revision 2:**
1. The fence check now precedes custody, so a lost fence also blocks ABANDON_BEFORE_NEW_TRUST. Is HOLD the right answer there, or may a plan abandon its own journal under a lost fence?
2. Any change in the live set of `(site, processID, kind)` forces a re-plan, while a restart under a new instance ID only forces a re-read. Is this split right? Should a replica that merely scales down also force a re-plan?
3. `consumedChallengeNonces` lives in the plan's journal. Should one-use instead be enforced by the CP challenge store, with the journal only as a record?
4. Prior leaves and the installed prior policy are budgeted to the end of all remaining work, not to the phase where each stops being relied upon. Is this conservative bound acceptable?
5. COMPLETE requires validity with only the safety + skew margin, not the renewal leads. `renewalDueBy` is reported in the handoff. Should COMPLETE instead hold inside a renewal lead?
