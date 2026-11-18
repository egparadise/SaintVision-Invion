---
doc_id: "ADR-PROPOSED-FLEET5-AUTHORITY-REPLACEMENT-R1"
title: "Proposed FLEET5 authority replacement and advance-renewal contract R1"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-18T22:10:00+09:00"
source_of_truth: "Git"
---

# Status

**PROPOSED / NOT_IMPLEMENTED / HOLD.** This contract releases nothing. It does not create keys, certificates, rows, policies or processes, and it does not change any live system. An operating release is a separate Root decision. That decision comes only after an independent security review, an implementation, hosted proofs and Root's private preflight.

- Task: Orca task_bbffe750d781 / dispatch ctx_578424c46777, branch `egparadise/fleet5-authority-replacement-20261118`.
- Base: Root544 `d81d40f824538a4ef553cc8ae4aa75f7c012e325` (progress index 1.0.544, Codex board 1.0.505).
- Author: Claude. Independent security reviewer: Codex (pending, not performed).
- This contract fills the `now >= A` branch of the R2 DAG: "CA expired / insufficient same-CA budget → AUTHORITY-REPLACEMENT workflow (out of scope; new trust authorization)" in [[Current three-Node pilot renewal preflight and recovery plan R1]].

Machine-checkable parts:

| Artifact | Path |
|---|---|
| Schema (JSON Schema 2020-12) | `contracts/proposed/fleet5-authority-replacement/fleet5-authority-replacement-v1.schema.json` |
| Cross-field checker and recovery decision | `tools/check_fleet5_authority_replacement.py` |
| Fixture generator (committed output, drift-gated) | `tools/generate_fleet5_authority_replacement_fixtures.py` |
| Real Nov18 fleet plan, HOLD | `contracts/proposed/fleet5-authority-replacement/instances/fleet5-nov18-ca-terminal-hold.json` |
| Positive and rejection fixtures, expected verdicts | `contracts/proposed/fleet5-authority-replacement/fixtures/` and `expectations.json` |
| Repository gate (collected by Core and Backend pytest) | `tests/core/test_fleet5_authority_replacement_proposal.py` |

## Source evidence (Root544)

These facts are read from committed Root evidence only. No new observation was made.

| Fact | Source |
|---|---|
| Original CA notAfter 2026-11-14T07:15:30Z, expired at read. CP client leaf expired 2026-11-09T07:15:30Z. State `CA_TERMINAL`. | `Evidence/fleet5-20261105-root/resume-20261118-and-completion-audit/root-current-state.json`, and the `authority` field of `user-transport-resilience-20261118/root-operation-receipt.json` |
| Terminal CA DER SHA-256 `b8d777ab…41c5a3`, tenant `97968b42…2205`, epoch `bcd581be…ed09`, CP URI form `…/control-plane/epoch/{epoch}` | `Evidence/fleet5-20261105-root/pc3-actual-cpu-pilot-r1/pc3-cpu-pki-r1/receipt.json` |
| Cohort PC2/PC3/PC4 NodeIDs, accounts and addresses. PC4 account is `inviz`. | R2 plan table |
| PC1 `inviz@192.168.45.13`, SSH exit 255 (public key rejected). It is not enrolled. | `user-transport-resilience-20261118/fleet-PC1.json` |
| PC2/PC3/PC4 reachable, prior Node containers running (unless-stopped). The Main DB Docker daemon is unavailable and the latest DB state has not been recovered. PC5 Node is not admitted. | `root-operation-receipt.json` |
| `tools/lan_pki.py` `ca_pair()` issues a 7-day CA. The fleet CA's 11-07 → 11-14 lifetime is consistent with that default. | source, `tools/lan_pki.py` |

Same-CA renewal, the expired-trust bypass, `init`/reset/re-pin and restarting under the old authority all stay forbidden (R2 and Root544).

## Scope boundary with the Codex custody/preflight card

The existing Codex worker owns retained-key custody and read-only preflight: `tools/recovery_preflight/*`, `services/node-agent/recoverycandidate/*`, `contracts/proposed/expired-policy-custody-*` and the matching tests on `agent/codex/fleet5-recovery-integration-readiness-resume-20261118`. This branch does not touch them.

This contract **consumes** their results only as typed inputs:
- `checkpoint.readback.custodyState`
- `newAuthority.custody.custodyEvidenceRef`
- `roleKeys[].custodyEvidenceRef` for every `RETAINED` key
- the authenticated per-Node policy floors and channel versions read in A0

Until those inputs exist as reviewed evidence, the real instance stays HOLD.

# Contract

## C1. Independent new trust

| Rule | Checker code |
|---|---|
| A new Ed25519 CA key is generated fresh offline, with `pathLength 0`. The CA is never cross-signed by, chained to or a renewal of the terminal CA. | AR-SCHEMA |
| The new CA certificate, the new public key and the subject CN all differ from the terminal CA. A distinct CN prevents chain-building confusion. | AR-TERMINAL-REUSE |
| The terminal CA is `REFERENCE_ONLY`. It never appears in any anchor bundle. | AR-TERMINAL-ANCHOR |
| The anchor bundle is exactly `{new CA}` after A2. No other entry is allowed. | AR-ANCHOR-MISMATCH |
| This contract applies only when `terminal.notAfter <= observedAt`. Before that, the same-CA branches in R2 apply. | AR-TERMINAL-NOT-EXPIRED |
| A Root trust decision (`trustAuthorization`) and new-key custody evidence are both required before PROPOSED. Private material never appears in the repository or the plan. | AR-HOLD-REQUIRED, AR-SECRET-MATERIAL |
| At most one new CA per `planID`. If A1 is interrupted, the decision comes from custody readback. A second key is never generated "to be safe". | recovery `HOLD_CUSTODY_UNRESOLVED` |

## C2. Rotation and new enrollment are separate tracks

- **ROTATION** (PC2, PC3, PC4) keeps the existing DB identity: the same NodeID, the same Node key (re-attested custody), the same epoch URI and the same journal/floors. Only the issuer changes to the new CA.
  - A ROTATION identity must already be an existing row (AR-ROTATION-UNKNOWN-IDENTITY).
  - Its key must not change (AR-ROTATION-KEY-CHANGED).
- **NEW_ENROLLMENT** (PC1) mints exactly one identity that has never existed in the tenant:
  - a new NodeID absent from every existing row, including disabled or retired rows;
  - a fresh Node key absent from every existing key;
  - no prior key, an empty state directory, and counters starting at C 0→1 and P 0→1.
  - Violations raise AR-ENROLLMENT-REUSES-IDENTITY, AR-ENROLLMENT-COUNTER and AR-IDENTITY-COLLISION.
- **Identity is NodeID + Node key + SPIFFE URI, never account or host name.** PC1 and PC4 both use account `inviz`. That is valid, and fixture `p01` proves the checker accepts it. Copying PC4's share directory or NodeID to PC1 is rejected (fixture `r09`).
- **Ordering.** No enrollment phase may start before A7 (rotation settled). A PC1 row observed earlier is `HOLD_ENROLLMENT_BEFORE_ROTATION_SETTLED`.
  - Rotation can complete without any enrollment (fixture `p08`).
  - PC5 (Main Windows Node) is not in this cohort. Its enrollment is a later, separate NEW_ENROLLMENT plan.

## C3. Preserve the DB epoch and the monotone counters

- **Epoch.** Every Node and CP URI keeps the existing `inv.control_epoch` value: `spiffe://saintvision.ai/tenant/{t}/node/{n}/epoch/{epoch}` and `…/control-plane/epoch/{epoch}`.
  - Epoch replacement is not a recovery tool (AR-EPOCH-SPIFFE).
  - A readback epoch different from the preserved epoch is `HOLD_EPOCH_DIVERGED`.
  - PROPOSED requires the epoch from a DB readback, not historical evidence (AR-HOLD-REQUIRED).
- **Channel version C.** Rotation uses `C_after = C_before + 1` with `C_before >= 1`, through the existing `provision_channel` CAS (`expected_version`) and an audit row. No reset or decrement is allowed (AR-CHANNEL-NONMONOTONE).
- **Policy version P.** Rotation uses `P_after = authenticated floor + 1` with floor >= 1, the same rule accepted for d476 (AR-POLICY-NONMONOTONE). Floors come from Node-owned journals through the custody preflight. They are never inferred from C or from history.
- C and P are independent domains and must be safe integers.

## C4. Phase journal and the irreversibility point

| Phase | Effect | Reversible? |
|---|---|---|
| A0_PREFLIGHT_READBACK | Root read-only: epoch, rows, C/P, terminal CA public read, custody state | yes (read-only) |
| A1_NEW_TRUST_AUTHORIZED | Trust decision recorded; new CA key and certificate created in offline custody | **no**: key fate now matters |
| A2_ANCHOR_STAGED | New anchor bundle published to the Node config and to every CP site | forward only |
| A3_ROTATION_LEAVES_ISSUED | Node-signed same-key CSRs → new-CA leaves, same epoch URI | forward only |
| A4_CHANNEL_CAS | `C → C+1` per rotation member with the planned leaf fingerprint | forward only |
| A5_POLICY_PUBLISHED | `P = floor + 1` per member | forward only |
| A6_CP_CONTEXT_SWITCH | All five CP context sites rebind to the new CP leaf (R2 F3 barrier) | forward only |
| A7_ROTATION_SETTLED | Fresh authenticated heartbeats under the new trust; floors equal the planned P | — |
| E1 → E3 | PC1 enrollment authorized → admitted (row, C=1) → settled | forward only |

A2 (Node side) needs Node CA roots to be reloaded. Node roots load once at startup (R2), and the deployed binary cannot serve this profile. Node-side anchor staging therefore happens **inside** the separately reviewed serving-binary/container migration handoff. This contract does not authorize a restart.

## C5. Interrupted migration and recovery decision

`recovery_action()` takes the durable journal position, the in-flight phase and outcome, and a fresh Root readback. It computes the **only** permitted next step. Every enum value has a positive fixture.

| Condition (first match wins) | Action |
|---|---|
| Nothing durable and nothing in flight | NOT_STARTED |
| Last durable ≤ A0 and A1 not attempted, or A1 attempted with custody `NO_NEW_KEY` | ABANDON_BEFORE_NEW_TRUST |
| DB not readable | HOLD_DB_READBACK_REQUIRED |
| Readback epoch ≠ preserved epoch | HOLD_EPOCH_DIVERGED |
| A1 reached and custody is not `NEW_KEY_PRESENT_MATCHES_PLAN` | HOLD_CUSTODY_UNRESOLVED |
| A row that is neither planned nor pre-existing | HOLD_UNPLANNED_ROW |
| Enrollment row before A7 | HOLD_ENROLLMENT_BEFORE_ROTATION_SETTLED |
| C outside {before, before+1}; C+1 with a non-planned leaf; durable A4 but C back at before; floor below its preserved value; missing rotation row | HOLD_FOREIGN_WRITER |
| Floor above the planned P | HOLD_POLICY_ABOVE_PLAN |
| Final phase durable | COMPLETE |
| Otherwise | RESUME_FORWARD at the in-flight phase (exact replay of the same planned bytes and expected versions), else at the next phase |

`ROLLBACK_TO_TERMINAL_CA` is not representable (fixture `r27`). Fresh nonces never rewrite prior evidence. Every HOLD needs Root readback and a new reviewed decision. A retry loop is never a substitute.

## C6. Advance renewal (so CA_TERMINAL cannot recur)

All values are in seconds. The checker enforces every inequality. `safety = 630` and `skew = 30` are fixed.

| Rule | Formula |
|---|---|
| Leaf lifetime | `60 <= leaf <= 518400` (existing six-day cap); leaf notAfter <= CA notAfter |
| Overlap | `630 < overlap <= 21600` |
| Leaf renewal lead | `leafLead >= B_N + overlap + 660` and `leafLead < leaf` |
| Policy renewal lead | `policyLead >= B_N + 660`, `policyLead < policy`, `policy <= leaf` |
| Successor CA lead | `caSuccessorLead >= leaf + B_CA + overlap + 660`. The successor anchor is staged and every leaf re-issued before the current CA expires. |
| Warning | `caWarningLead > caSuccessorLead` (alert before the successor deadline) |
| CA lifetime | `caLifetime >= 2 × caWarningLead`; the new CA must not be born inside its warning window |

Proposed lifetimes in the real instance:

| Item | Proposed value |
|---|---|
| CA lifetime | 365 d |
| Successor lead | 30 d |
| Warning lead | 45 d |
| Leaf lifetime | 6 d |
| Leaf renewal lead | 3 d |
| Policy lifetime | 2 d |
| Policy renewal lead | 1 d |
| Overlap | 4 h |

`B_N` and `B_CA` stay **null** (not invented), so the instance is HOLD. A 7-day CA cannot satisfy these rules (fixture `r18`). The successor CA is a later plan of the same schema whose anchor bundle is staged while the current CA is valid. That later plan is a normal rotation, not this terminal path.

## C7. CP client and role keys

- The CP client leaf is re-issued under the new CA with the same epoch URI. `RETAINED` key continuity requires custody evidence. A `FRESH` key must be new.
- All five context sites are listed: observer, delivery, workspace, build-product and storage-check (R2 F3).
- Role keys (launch signer, policy signer) are either `RETAINED` with custody evidence or `REPLACED` under the trust decision. They are distinct from every Node key, the CP key and the new CA key.

## C8. PC1 first-enrollment operator handoff

`enrollment_handoff()` runs only for a plan that passes every check and whose recovery action is `COMPLETE` (E3 durable). It produces `contracts/proposed/fleet5-authority-replacement/handoff/pc1-first-enrollment-handoff.json` from fixture `p05`, pinned by the plan's SHA-256. Fixture `p14` is the concrete PC1 first enrollment just before E1.

| Handoff part | Content | Who consumes it |
|---|---|---|
| `newIdentity` | PC1 NodeID, SPIFFE URI with the preserved epoch, fresh Node key hash, new-CA leaf DER hash, C=1, P=1 | Root operator, DB readback comparison |
| `publicCAEvidence` | New CA certificate/key hash, CN, validity, anchor bundle (= new CA only), trust decision ref, excluded terminal CA hash | Node anchor bundles and the A6 CP contexts |
| `fiveNodeInventory` | Inventory exactly as `tools/five_node_lab_preflight.py` `validate_five_node_inventory` accepts it (revision computed), one entry per member with `certificateSHA256` = planned leaf | the existing five-node verifier |

The existing five-node verifier compares `nodeId`, `ip` and the leaf `certificateSHA256` with `inv.node_channels`. It does **not** check the issuer chain, the SPIFFE URI/epoch or the absence of the terminal CA. Those guarantees come only from the anchor bundles and CP contexts, and the handoff says so in `verifier.doesNotCheck`. On the real fleet, API96/portal/observer run on PC3, so Root must declare `controlPlaneHostId` for real. A CP-colocated Node is then excluded from the timed waves (`cp-host-colocation`). The synthetic handoff uses a separate `host-cp`.

# Verification and handoff

- The local gates, the hosted runs and their exit codes are recorded in [[2026-11-18_FLEET5_Authority_Replacement_Contract_R1_Claude]].
- Fixture set: 1 real HOLD instance, 14 positive fixtures, 30 rejection fixtures and 1 handoff. Each rejection carries its exact expected code set.
- The pytest gate (155 tests) adds three kinds of check:
  - expiry-boundary tests: terminal expiry at equality and at +1 s, leaf cap, overlap, leaf/policy/successor-lead floors, warning lead, CA lifetime ×2, and new-CA birth inside its warning window;
  - an interruption sweep: every phase in flight resumes at itself, including when its effect already landed; every durable boundary resumes at the next phase; rollback after a durable CAS holds; custody doubt holds;
  - handoff tests.

Questions for the independent security review:
- whether the five-site context list is complete;
- whether the anchor bundle should allow the successor CA during advance renewal (currently a later plan);
- whether role-key `RETAINED` is acceptable for the launch signer after a CA_TERMINAL event;
- whether A3 leaves may be issued before A2 settles on all members.

**Next first action and owner:**
1. Codex performs the independent security review of this contract.
2. The Codex custody/preflight card supplies the typed inputs.
3. Root performs the DB recovery readback and the PC1 non-secret diagnosis.
4. Only then is a PROPOSED instance revised.

Implementation, the operating release, production activation and canonical sync apply are all not authorized here.
