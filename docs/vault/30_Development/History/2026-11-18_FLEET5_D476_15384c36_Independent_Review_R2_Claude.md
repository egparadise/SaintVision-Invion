---
doc_id: "HISTORY-FLEET5-D476-15384C36-INDEPENDENT-REVIEW-R2-20261118-CLAUDE"
title: "Expired-policy candidate 15384c36 independent review R2 (F1-F6 and read-only preflight)"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-18T23:20:00+09:00"
source_of_truth: "Git"
---

Task FLEET5-D476-15384C36-INDEPENDENT-REVIEW-R2-20261118 (Orca task_5898fc185b22, dispatch ctx_6943350be96a) started 2026-11-18 22:40 KST.

| Item | Value |
|---|---|
| Candidate (author Codex) | `15384c36f184ec7e2008329bc5c221aa1595d5f7` |
| Base | `d47630d730278aa9e49b15a63cd221696da8dc00` (prior review: [[2026-11-08_FLEET5_Expired_Policy_D476_Source_Security_Review_R1_Claude]]) |
| Scope | 7 commits, 19 non-evidence files, +1950/−93 |
| Reviewer branch | `egparadise/fleet5-d476-15384c36-review-20261118` |
| Record | `Evidence/fleet5-d476-15384c36-review-20261118-claude/review.json` |

**Roles:**
- Claude performed this independent review. Codex is the author. Root owns integration and every operation.
- No Codex file was changed. No live credential, SSH, DB, Docker, key or certificate access was used. Nothing was synced canonically or activated.

## Verdict (source only)

**ACCEPT_SOURCE_CANDIDATE_ONLY_KEEP_INTEGRATION_AND_OPERATING_GATES. Mandatory blockers: 0.**

This accepts the source candidate only. Integration, adapter work, DB recovery, publication, migration, release and operation are not released, and P1–P7 production integration stays NOT_RUN. PC1's unique enrollment is outside this candidate and still outstanding.

Two items are recommended before integration: R2-02, then R2-01.

## Prior findings F1–F6

| ID | Prior | Now | Evidence at 15384c36 |
|---|---|---|---|
| F1 uppercase signature hex | LOW | **CLOSED** | `wire.go:35`/`:125` check `^[0-9a-f]{128}$` before decode. Python does the same at `proposed_expired_policy_recovery.py:131`. Hosted controls `signature-encoding-{uppercase,odd,whitespace}` (×3) all refuse with `RECOVERY_SIGNATURE`. |
| F2 role-key hashes unbound | LOW | **CLOSED** | See below. |
| F3 absolute-path opens | LOW | **CLOSED** | See below. |
| F4 dev/ino above 2^53 | LOW | **CLOSED** | `supportedFilesystemNumber` (`custody_linux.go:29`) is applied before the cast (`:198`). Python has a wire refusal test. `node.py` records dev/ino as strings and holds when they are out of range (`node.py:164`). |
| F5 fixture launch-signer = operator | INFO | **CLOSED for the fixture** | The fixture uses a distinct key and asserts it differs from every other role; `launchSignerSHA256 e47d4190…` is in the artifact. Helper-side residual: R2-04. |
| F6 expired PREPARED has no terminal state | INFO | **PARTIAL** | An expired PREPARED operation now refuses with the typed `EXPIRED_PREPARED_REQUIRES_FORWARD_RECONCILIATION` in prepare, commit and reconcile (`:361`, `:397`, `:423`). A signed, audited terminal transition is still missing: R2-05. |

**F2 evidence:**
- The v2 proof and checkpoint bind `authorizerSHA256` and `operatorSHA256` (`custody_linux.go:276`, `:310`), and `ownHistory` checks them (`:122`).
- Python expects the same fields (`:253`, `:275`, `:385`).
- The v2 domains (`wire.go:25`, `:27`) leave v1 history on HOLD.
- The empty-history first slot is anchored by an image-baked `recovery-authority.json` (`authority_linux.go:50-75`).
- Hosted controls `foreign-first-slot-authority`, `absent-image-authority` and `overmounted-authority` (×3).

**F3 evidence:**
- Children are opened with `openat2` using NO_XDEV, NO_SYMLINKS and BENEATH (`authority_linux.go:20-31`). It fails closed off amd64/arm64 and on kernels without openat2.
- Directories are walked from `/` one component at a time with O_NOFOLLOW, and the FDs are held (`custody_linux.go:52`).
- Child mount IDs must match (`:42`), and aliases among the four roots are rejected (`:181`).
- The root directories are re-validated before the proof and before the checkpoint.
- Records are published by O_TMPFILE plus `linkat`, with no named temporary (`:132-163`).
- `TestPinnedParentSurvivesRename`, plus the hosted controls `identical-inode-file-mount-alias` and `host-bind-parent-replaced`.

## New findings

| ID | Severity | Where | Finding |
|---|---|---|---|
| R2-01 | LOW (test evidence) | `cp.py:36-52`, `:69-72` (preflight collector, in the candidate tree only) | The wrong tenant and all four binding negatives collapse into one `OPERATOR_VISIBILITY_UNKNOWN` code, because `observe()` catches every exception. The hosted proof therefore shows refusal but not which predicate refused. For example, `wrong-project` is rejected only by the Python binding/descriptor equality, before any DB query. **Fix:** add a test-only sub-reason, or unit-test each `verify_reader` predicate with all other fields valid. |
| R2-02 | LOW (coverage) | `cp.py:16-33`, `:70` | `provisioned_reader()` is the production binding source in `main()`, and it has no test: nothing in tests/tools/.github references `recovery-reader.json`. A defect there would fail closed, giving an unplanned HOLD during the live run. **Fix:** add a Linux test with an injectable root, with positive and negative cases for owner, mode, symlink and hardlink. |
| R2-03 | INFO | `authority_linux.go:50-75`; `custody_linux.go:167` | The first-slot anchor proves only that the file is in the read-only image root. The image ID is operator-claimed and never verified, and the proof does not carry `authorityBindingSHA256`, so the CP cannot see which anchor was checked. The assurance is image custody plus the helper hash, as the source comment states. |
| R2-04 | INFO | `custody_linux.go:206`, `:216` | The helper checks only that `launch-signer.pub` is 32 bytes, not that it differs from the authorizer, operator or node keys. Only the fixture enforces that separation. |
| R2-05 | INFO (F6 residual) | `proposed_expired_policy_recovery.py:361/397/423`; `cp.py:105`; `join.py:28-31` | An expired PREPARED operation wedges the reference ledger until a forward reconciliation that the source does not define. `cp.py` always reports `operationOutcome: UNKNOWN`, so join's expired-PREPARED branch can only be reached with injected test data. This fails closed. |
| R2-06 | INFO | `custody_linux.go:132-163` | The `/proc/<pid>/fd` check and the `linkat` are two separate steps, not one atomic operation. The procfs magic check and the openat2 no-xdev open limit the residual risk to an operator who can mount a foreign procfs, which this model treats as trusted custody. |
| R2-07 | INFO (integration boundary) | `common.py:55`; `join.py:12` | The preflight is fixed to the 3-member rotation cohort (PC2/3/4). PC1 is a NEW_ENROLLMENT and must not be appended to it, which matches C2 of [[Proposed FLEET5 authority replacement and advance-renewal contract R1]]. The collectors hash CA and leaf DER only; they do not validate the issuer chain or the SPIFFE epoch. |

## Checked with no finding

- **Identity bindings:**
  - tenant/epoch/node plus the authorizer/operator hashes in the v2 proof and checkpoint;
  - a closed `identity.json` and the policy scope;
  - a single CP fingerprint;
  - fixture tenant and epoch are now UUIDs and node IDs use the `nod_` format.
- **Counter durability:**
  - O_TMPFILE write and fsync, then an exclusive `linkat`, then a directory fsync;
  - the node record is emitted only after the durable write;
  - the SQLite ledger uses `synchronous=FULL` and a CAS on the prior C/P;
  - history checks counter i+1 and the `previousCheckpoint` chain.
- **False zero and RLS:**
  - A zero count under a foreign tenant is refused (`OPERATOR_VISIBILITY_UNKNOWN`), never reported as a fact.
  - RLS is checked per table: enabled, forced, not the owner, and exactly one PUBLIC permissive `tenant_isolation` policy whose qualifier text matches exactly (deparsed under `search_path pg_catalog`).
  - Superuser and BYPASSRLS are refused, and `session_user` must equal `current_user`.
  - `runs.state` and `execution_deliveries.phase` are NOT NULL (migrations 0001 and 0007), so the `NOT IN` and `<>` filters cannot drop NULL rows.
- **Read-only proof:**
  - REPEATABLE READ READ ONLY with no assigned XID and 0/0/0 tuple changes;
  - the channel-row checksum (including `xmin`) is equal before and after.
- **Secret hygiene:**
  - `node-key.pem` is opened with O_PATH only, and its hash is never computed or emitted;
  - the DB connection string arrives on stdin.
- **Workflow:** `backend.yml` adds only a PG preflight step with a fail-closed artifact (`test -s`, `if-no-files-found: error`). The existing Tests step is unchanged.

## Verification performed

| Check | Result |
|---|---|
| Hosted exact-SHA runs | Core 44309388161, Backend 44309650079, Docs 44309649837 and ac11-security-scan 44309650022 all succeeded at 15384c36. |
| Hosted Go candidate tests (Core log) | All 7 named tests passed; the log has 0 `--- FAIL` lines. |
| Candidate proof artifact 14429357295 | `result.json` sha256 `1bdf934a…`. 61 negative controls, none exited 0. Status `CANDIDATE_COMPONENT_PROOF_PASSED_KEEP_INTEGRATION_HOLD`. Three read-only node observations show 0 changed files. |
| PG artifacts 14430495520 (3.12) and 14429517726 (3.14) | Hidden count 0 → `OPERATOR_VISIBILITY_UNKNOWN`; 4/4 binding negatives refused; `openRuns` 1; tuple changes 0/0/0; before and after rows equal. These match ROOT-READY. |
| Local Python 3.14.0 (Windows, scratch venv, git-archive copy of 15384c36) | `test_readonly_cohort_join.py` + `test_proposed_expired_policy_recovery.py`: 49 passed, 5 failed. The 5 failures are platform-only: the reference ledger needs `os.O_NOFOLLOW`/`os.geteuid`, which Windows lacks. Hosted Linux passes them. |

I did not run the Go linux-tagged tests or the PG/Docker proofs locally. Their evidence is hosted only.

Root's ROOT-READY and the board addendum are untracked working copies in the Codex worktree. I pinned them by working-copy sha256 (`abaf481f…`, `1a6cb54c…`), not as Git objects.

## Next

1. Codex (author): R2-02, then R2-01, before integration. R2-03 to R2-07 are recorded residuals.
2. Root: integrate the source candidate only. Keep the integration and operating gates. PC1 enrollment follows the separate NEW_ENROLLMENT path.
