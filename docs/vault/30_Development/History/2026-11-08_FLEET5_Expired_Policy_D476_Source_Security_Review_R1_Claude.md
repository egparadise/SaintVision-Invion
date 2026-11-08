---
doc_id: "HISTORY-FLEET5-EXPIRED-POLICY-D476-SOURCE-SECURITY-REVIEW-R1-20261108-CLAUDE"
title: "Expired-policy D476 candidate source and security review R1"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-08T11:12:30+09:00"
source_of_truth: "Git"
---

Task FLEET5-EXPIRED-POLICY-D476-ACTUAL-SOURCE-SECURITY-REVIEW-R1-20261108 (Orca task_d0227890bfe9, dispatch ctx_21e17eefef82), started 2026-11-08 10:59 KST.

**Roles:**
- I am the actual independent Claude source and security reviewer.
- The author is Codex (ctx_e55b82334c37 / task_cc9b52d7dd35, exited).
- Root is the sole owner of canonical APPLY, SSH, private preflight and operations.

**Inputs:**
- The candidate is [d47630d7](https://github.com/egparadise/SaintVision-Invion/tree/d47630d730278aa9e49b15a63cd221696da8dc00) on agent/codex/fleet5-expired-authority-recovery-contract-r1-20261108.
  - It has four commits from base b8c839d1daf28677a0587af115cbea496626d5ea: ec2a9d2b, dad956b1, 5275a3fb and d47630d7.
  - It changes 38 paths: 3 existing paths (two workflows and the Codex board) are modified and all others are added.
  - All 13 source-map pins match the committed blobs exactly.
- The report base is Root541 94f5b3da807ed64bf6a0234300c27139d02a3a7a (Docs 42436392665, 19/19).
- I read boards Index 1.0.541, Codex 1.0.502, History 1.0.150 and Claude 1.2.131.

## Verdict

**ACCEPT_SOURCE_CANDIDATE_ONLY_KEEP_INTEGRATION_AND_OPERATING_GATES**, with 0 mandatory blockers.

Findings: 4 LOW and 2 INFO, all non-blocking and all handed to the author for the integration card.

- Accepted: the source candidate only.
- Not accepted: no integration, adapter, production DB, publication, migration, budget, release or operating action.
- Still NOT_RUN: P1–P7.
- Still null/HOLD: B_Rpolicy and B_Rleaf. Both must include the recovery's own serving-binary migration.

## Method and scope

- **Static review only.** On Main Windows I used Git, JSON, AST and hash reads of immutable objects at the full candidate SHA. I did not check out, import or run any product code. I ran no Go, pytest, Docker, crypto, SSH, DB or live action.
- **Hosted evidence.** The runtime and crypto results come from Root's exact hosted evidence, not my own execution:
  - Core [42431918918](https://github.com/egparadise/SaintVision-Invion/actions/runs/42431918918): job 128582562798 has 52 steps, 6 of them declared skips; job 128582562899 has 16 steps.
  - Backend [42431943920](https://github.com/egparadise/SaintVision-Invion/actions/runs/42431943920): the py3.14 job has 21 steps, including 2 declared conditional mutation-step skips. The MLflow job has 9 steps and the py3.12 job has 21.
  - Docs [42431921203](https://github.com/egparadise/SaintVision-Invion/actions/runs/42431921203): 19 steps.
  - I re-read the ids, attempt 1, head SHA, step counts and skips with `gh run view`. They match the brief.
  - Skipped steps are declared skips, not passes.
- **Gap check.** No substantive gap needed an independent runtime repro.

## What I checked and found sound

- **Canonical wire.** Both languages accept only a closed subset and agree byte-for-byte:
  - ASCII 32..126 except `<>&`;
  - safe integers only;
  - duplicates and trailing data refused;
  - depth ≤16, arrays ≤128, objects ≤65536 B;
  - exact re-marshal equality.
  - Code: [wire.go L41-L109](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/wire.go#L41-L109) and [Python verify L128-L131](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/control-plane/src/inv/proposed_expired_policy_recovery.py#L128-L131).
- **Domains and roles.** There are five NUL-terminated signature domains.
  - The authorizer and operator keys are pinned by argv SHA256. The helper refuses if the authorizer, operator and retained Node keys are not all distinct ([custody L127-L129](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/custody_linux.go#L127-L129)).
  - The CP verifier also requires every role key to differ from the CA, the CP TLS key and every Node key.
- **Command boundary.** The command accepts exactly nine flags and no positional arguments ([main.go L29-L41](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/cmd/inv-recovery-custody/main.go#L29-L41)).
  - The request path is fixed, the process must run as euid 1000, and the roots are fixed.
  - Errors are content-free.
- **Custody is a real exclusion.** The helper takes a non-blocking `LOCK_EX` on the existing journal `.lock` ([custody L46-L54](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/custody_linux.go#L46-L54)).
  - That is the same inode the unchanged daemon locks at OpenJournal ([lock_linux.go](https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/services/node-agent/runtime/lock_linux.go)).
  - It also takes a separate custody lock ([custody L111-L112](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/custody_linux.go#L111-L112)).
  - Both locks are held through the checkpoint. The locked dev/ino must equal the operator-attested values.
  - The assurance is honestly labelled "not hardware".
- **File hygiene** ([custody L27-L45](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/custody_linux.go#L27-L45)).
  - Opens use O_NOFOLLOW. Each file must be a regular single-link file with the same UID, a private mode and a stable fstat.
  - Mounts must carry the expected RO/RW flags.
  - Records are written durably with O_EXCL and link-no-replace, with an fsync of the file and directory fsyncs ([custody L91-L106](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/custody_linux.go#L91-L106)).
  - Residue, foreign files and partial files are HOLD. Nothing is deleted.
- **Only the policy-expired, leaf-valid state is accepted.** The helper uses only the real wall clock ([wire.go L134-L153](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/wire.go#L134-L153), [custody L165-L175](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/custody_linux.go#L165-L175)). Refusals are typed:
  - CA expired → TERMINAL_CA_EXPIRED;
  - leaf expired → TERMINAL_LEAF_EXPIRED;
  - an unexpired policy, including a fractional expiry after the current second → POLICY_NOT_EXPIRED.
  - More than the budget plus 660 s must remain on each leaf.
  - The budget must be 1..60 s.
- **Generations and floor** ([custody L132-L175](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/custody_linux.go#L132-L175)).
  - The cohort must be exactly 3 sorted members, with a digest equal to the argv value.
  - P = floor + 1 is checked against the actual `.peer-policy` journal, and C + 1 is bound.
  - Only the idle journal layout and the never-started scenario are accepted. Partial scenarios are HOLD before any proof write.
- **History chain** ([custody L67-L90](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/custody_linux.go#L67-L90)).
  - Both the proof and the checkpoint are verified with the Node key.
  - The counter must equal i + 1, and each previousCheckpoint must be the hash of the prior record.
  - Tenant, epoch and Node scope are checked on every historical body (the d476 fix).
  - A replay needs an identical requestDigest and is labelled historical, not fresh custody.
- **Proof and checkpoint** ([custody L180](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/custody_linux.go#L180), [L186-L197](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/custody_linux.go#L186-L197)).
  - The proof is fixed to serving false, servingPID null and activationAllowed false.
  - The ack wait is bounded and rechecked.
  - All files and the lock inode are rechecked under the locks before the checkpoint is written.
- **CP verifier and reference ledger** ([proposed_expired_policy_recovery.py](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/control-plane/src/inv/proposed_expired_policy_recovery.py)).
  - Trust comes out of band, and every proof field is bound to the authorization and operator attestation.
  - All five client sites must be present or absent at the current generation.
  - The scope digest pins the tenant, epoch, CA, CP, authorizer, operator and nodes.
  - Only one operation can be PREPARED at a time, and nonces must be unique.
  - The commit is a C/P CAS with rowcount 1 and full rollback, plus an idempotent replay.
  - activate() always refuses, reconcile is read-only, and main() refuses.
- **Schema** ([expired-policy-custody-v1.schema.json](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/contracts/proposed/expired-policy-custody-v1.schema.json)).
  - The shapes are closed. activationAllowed, publicationAllowed and serving are const false, and servingPID and productionBudgetSeconds are null.
  - No live or serving mode can be expressed.
- **Tests and harness** ([run_expired_policy_candidate.py](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/tests/proofs/run_expired_policy_candidate.py)).
  - Each of the 37 negative controls asserts the exact typed refusal.
  - The harness also asserts that:
    - the ordinary M2 verifier rejects the candidate proof;
    - the original state hashes are unchanged;
    - replay is identical;
    - the audit count is 6;
    - activation is refused.
- **Workflows** ([core.yml](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/.github/workflows/core.yml), [backend.yml](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/.github/workflows/backend.yml)).
  - The changes only add steps. There is no continue-on-error, and no existing step is weakened.
- **Isolation.** The candidate packages are not imported by inv-node, the M2 observer, app/worker composition or node_transport.

## Findings (all non-mandatory)

| ID | Severity | Finding | Impact | Request to author |
| --- | --- | --- | --- | --- |
| F1 | LOW | Go Verify decodes signature hex with `hex.DecodeString` and accepts uppercase ([wire.go L121-L126](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/wire.go#L121-L126)). The ADR and the Python verifier require lowercase. | Divergence in envelope encoding only; the payload and key do not change. Where the outer bytes are hashed the result fails closed. | Check `^[0-9a-f]{128}$` before decoding, and add a cross-language refusal test. |
| F2 | LOW | The Node-side proof, checkpoint and history do not bind the authorizer or operator key hashes ([custody L180](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/custody_linux.go#L180), [L195](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/custody_linux.go#L195)). | The CP side still pins the authority, so a record made under foreign pins cannot commit. On the Node it only holds a counter slot and causes a later HOLD (availability). | Add authorizerSHA256 and operatorSHA256 to both bodies, and check them in ownHistory. |
| F3 | LOW | Files are opened by absolute path with O_NOFOLLOW on the last component only, not openat on root dirfds. | A same-UID actor could swap a parent directory between checks. The fixed mounts mitigate this, and the ADR already lists it as an assumption for P2. | In the P2 adapter, use openat or openat2 with RESOLVE_BENEATH and RESOLVE_NO_SYMLINKS. |
| F4 | LOW | The lock dev/ino are cast from uint64 to int64 and must be safe integers ([wire.go L54-L58](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/services/node-agent/recoverycandidate/wire.go#L54-L58)). | Values above 2^53 cause a WIRE_NUMBER HOLD: fail-closed, but a portability limit. | Encode them as decimal strings, or record the inode range in P2. |
| F5 | INFO | The fixture's launch-signer.pub is the operator public key ([run L89](https://github.com/egparadise/SaintVision-Invion/blob/d47630d730278aa9e49b15a63cd221696da8dc00/tests/proofs/run_expired_policy_candidate.py#L89)). | Affects fixture realism only. | Use a distinct key. |
| F6 | INFO | Once a PREPARED operation's challenge has expired it can never commit, and there is no abort or expire transition. | Correct HOLD, but under one-PREPARED-at-a-time it blocks the next operation. | Define a signed, audited ABORTED transition in the production DB adapter (P5). |

## Integration gaps (not defects)

- Revocation comes only from the authorizer's revoked list.
- Only the idle journal layout is supported.
- Only a single CA with pathLen 0 is supported. Authority replacement after the CA terminal at 2026-11-14 16:15:30 KST is a separate, unimplemented workflow.
- The five-site inventory and the CID/image values are operator claims.
- Production DB, publication, serving migration, transport readiness and release are not implemented. P1–P7 are NOT_RUN.

## Preserved state

- Releases: Node 1efea494, API 96afd799, schema 0068, UI abb7074e.
- Expiries: policy 2026-11-08 16:15:30 KST, leaf 2026-11-09 16:15:30 KST, CA 2026-11-14 16:15:30 KST.
- Run run_01M6VXSMM9SV8MAB7K4B1YCRX8 is awaiting_approval/v4/attempt0. Approval apr_01M6VXSPZ0252M2SJ8ZA5E11QE has expired.
- Hosts: PC1 key 255; PC5 RAM 94.58%, unadmitted. GPU, storage, manual, all-5 and reboot checks have not run.
- Still in place: Original19HOLD, discharges0, runtimeB0, A1-A16, H1-H7, H3EA, RDNULL_HOLD, raw7UNREGISTERED and A01-A40NOT_RUN. wholeProgramComplete is false.

## Next first action / owner

1. Root verifies and publishes this verdict.
2. Codex (owner) closes F1–F4 in the next integration card: restricted serving migration, a current-profile M2 producer, and an expired-policy custody/forward-publication adapter. That card needs an actual Claude review.
3. Until then, no Node restart, reboot or migration under the unchanged authority.

The evidence is in `docs/vault/30_Development/Evidence/fleet5-expired-policy-d476-source-review-r1-20261108-claude/`: review.json, read-pins.json, local-gates.json and sync-state-comparison.json.
