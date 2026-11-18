---
doc_id: "HISTORY-FLEET5-ABE0C971-RECOVERY-PREFLIGHT-FOLLOWUP-REVIEW-20261119-ORCA"
title: "Fleet5 recovery preflight R2-01/R2-02 followup independent review at abe0c971"
version: "1.0.0"
status: "review"
author: "Orca dispatched independent worker"
updated: "2026-11-19T01:41:36+09:00"
source_of_truth: "Git"
---

# Scope and verdict

Task `task_c541ff64ce81`, dispatch `ctx_199234462f04`, reviewed the exact source commit `abe0c971aad2ec3251c71a308e6ea44abb9e7c9f`. The implementation author is Codex; this dispatched worker is independent of that author. Root retains integration and operating authority.

Review checkout: detached `.work/review-task_c541ff64ce81`, initially clean at the requested SHA. The unrelated primary checkout modification `apps/web/public/auth-config.js` was neither read as review input nor changed. Read guidance: INDEX-PROGRESS-001 v1.0.400, WORKBOARD-ORCA-001 v1.0.1, GOV-AGENT-001 v1.1.3, GOV-CONTINUITY-001 v1.0.0, GOV-CONTINUOUS-001 v1.1.0, GOV-GIT-001 v1.1.4, agent-delivery v1.1.0 and core-reliability v1.0.0. This isolated task adds only this History; shared boards, registry and Obsidian are intentionally unchanged.

**Verdict: ACCEPT_SOURCE_CANDIDATE_ONLY_KEEP_INTEGRATION_AND_OPERATING_GATES. Mandatory blockers: 0.** R2-01 and R2-02 are closed for their original source/test-evidence acceptance scope. The unhosted short-read/ctime cases do not change that verdict. Production P1–P7 remain NOT_RUN; integration, production DB recovery, publication, migration, release, activation and PC1 enrollment are not accepted.

# Disposition

| ID | Disposition | Evidence and residual |
|---|---|---|
| R2-01 LOW | **CLOSED for source acceptance** | Both hosted runtimes attribute all 17 binding/database negatives to the intended guard and row count. The PostgreSQL privilege negative really withdraws PUBLIC/direct EXECUTE and is no longer marked not-applicable. New non-blocking R3-01 test-cleanup residual is below. |
| R2-02 LOW | **CLOSED for source acceptance, with INFO coverage residual** | Both hosted runtimes execute the unmodified `provisioned_reader()` through a private mount namespace: 24 cases (2 positive, 22 negative), all with the expected result/guard. Short-read and ctime-change cases are not hosted cases, but local synthetic probes confirm fail-closed behavior. |
| R2-03 INFO | **OPEN, unchanged** | First-slot image-anchor assurance remains bounded as previously reviewed. |
| R2-04 INFO | **OPEN, unchanged** | Launch-signer separation remains fixture-enforced rather than helper-enforced. |
| R2-05 INFO | **OPEN, unchanged** | Expired PREPARED still lacks a signed audited terminal transition; `cp.py` still emits `operationOutcome: UNKNOWN`. |
| R2-06 INFO | **OPEN, unchanged** | Procfs magic-link check plus `linkat` remains non-atomic within the documented trusted-custody boundary. |
| R2-07 INFO | **OPEN, unchanged** | This is still the PC2/PC3/PC4 three-member preflight; PC1 requires its separate NEW_ENROLLMENT path and issuer-chain/SPIFFE validation is outside these collectors. |
| R3-01 LOW (new, test hygiene) | **OPEN, non-blocking** | If `withdraw_control_privilege()` revokes ACLs but its final `held is False` assertion fails, it raises before returning the saved ACL. The caller's `control_acl` remains `None`, so its `finally` cannot restore the prior ACL. A mocked psycopg probe reproduced two REVOKEs and zero restoration GRANTs. This is confined to the disposable fixture and cannot produce a false green; it can only make an already failing test leave fixture residue. Normal success-path restoration is hosted-green. |

The diff `15384c36..abe0c971` touches only `.github/workflows/backend.yml` and the three preflight test/helper files. The R2-03/R2-04/R2-06 source files and R2-07's `common.py`/`join.py` are unchanged; R2-05's behavior remains present in `cp.py`.

# Hosted evidence

Read-only GitHub API queries found Backend Build [44328610405](https://github.com/egparadise/SaintVision-Invion/actions/runs/44328610405) successful at the exact requested SHA, with `backend (3.12)`, `backend (3.14)` and `mlflow-live` all successful. The same branch run listing reported Core Build 44328634603, Documentation Build 44328619118 and ac11-security-scan 44328626036 successful at that SHA; their logs were not independently re-executed or parsed for this review.

The earlier Backend run 44325507061 at parent `a2ddbade` was cancelled after its preflight step and showed why the final ACL change was needed. It is not used as final acceptance evidence.

| Runtime | Artifact | GitHub ZIP digest verified locally | Focused JUnit result |
|---|---|---|---|
| Python 3.12 | 14438187885, `fleet5-readonly-pg-3.12-abe0c971…` | `7a1632eec245163a7ae0f334adeefe1c02097cf68bb83afed8f883a004c89151` | 3 tests, 0 failures/errors/skips |
| Python 3.14 | 14439105438, `fleet5-readonly-pg-3.14-abe0c971…` | `3d75db05c1da740496246cfc229393e26be5c8cd73972e2f59fe296ba242db2f` | 3 tests, 0 failures/errors/skips |

Both `observations.json` receipts pin the exact source SHA, 17/17 public `OPERATOR_VISIBILITY_UNKNOWN` refusals and the expected `bindingNegativeGuards`. `control-privilege-revoked` is `control-function-privilege` with `guardRows: 1`; `controlPrivilegeWithdrawnFrom` is `{public: true, direct: false}`. Both retain no assigned transaction ID, 0/0/0 tuple changes, equal before/after channel checksums and `activationAllowed: false`.

Both `provisioned-reader.json` receipts pin the same SHA and `cp.observe(..., binding=None) -> cp.provisioned_reader()`. All 24 cases have `sameInode: true`; trusted and owner-only-0600 complete, and the other 22 refuse with the expected guard while exposing only `transactionReadOnly` as a fact. `hostDescriptorPresent` and `activationAllowed` are false.

A local named-assertion validator checked these artifact invariants and exited 0 for both runtimes. Two preliminary validator drafts exited 1 from reviewer mistakes (an incorrect expected count of 25, then a set-to-dict comparison), not from product assertions; the corrected validator compares the actual 24-case set explicitly.

# Short-read/ctime acceptance decision

`tools/recovery_preflight/cp.py:29-30` performs one bounded read, requires `len(raw) == st.st_size`, re-stats the same descriptor and requires unchanged `st_ctime_ns`; `:32-33` maps every failure to `OPERATOR_VISIBILITY_UNKNOWN`. The hosted matrix has no explicit short-read or ctime-change case, although `recovery_guard_trace.py` already names that guard `descriptor-read-stability`.

Using Python 3.10.11 on Windows and only mocked local file descriptors, the unmodified function accepted a stable synthetic `{}` descriptor, rejected a one-byte read of a two-byte descriptor, and rejected a ctime change after a complete read. Both negatives returned `OPERATOR_VISIBILITY_UNKNOWN`; all mocked descriptors were closed in all three cases. This validates control flow, not real Linux filesystem race behavior.

**Decision: non-blocking INFO residual, not an acceptance regression.** The original R2-02 failure effect was an unplanned HOLD, not unsafe acceptance, and both branches fail closed. Add explicit short-read and post-read-ctime cases to the hosted private-namespace matrix before relying on this as production race evidence; do not reinterpret the mocked probe as such evidence.

# Local verification boundary

- Interpreter: `C:\Users\inviz\AppData\Local\Programs\Python\Python310\python.exe`, Python 3.10.11, Windows `win32`.
- Synthetic probes only: mocked file descriptors and mocked psycopg; no real credential, production DB, SSH, Docker, host `/etc` write, mount or activation.
- No local PostgreSQL/private-namespace run and no full local suite. Hosted Linux evidence is kept distinct from local synthetic results.
- The first ACL-probe draft had a reviewer Python syntax error; the corrected mocked probe exited 0 and reproduced R3-01.
- Product/test implementation changes by this reviewer: 0. Local commit, push, new CI dispatch and Obsidian apply: not performed. Existing exact-SHA hosted evidence was read only. Operational acceptance: not performed.

Documentation gates on this report: `python tools/check_docs.py` exited 0 (24 original hashes, 1297 versioned documents, links/tasks/DAG PASS); `python tools/check_ontology.py` exited 0 (RDF/TTL/JSON-LD, SHACL and query PASS); `git diff --check` exited 0. Obsidian `--check`/`--apply` were not run because this is an isolated review-only addendum; no sync is claimed.

# Remaining production phases and next owner

Every production phase remains explicitly unexecuted by this review:

| Phase | Status at abe0c971 | Required next evidence |
|---|---|---|
| P1 | NOT_RUN | Separate reviewed production integration execution and receipt |
| P2 | NOT_RUN | Separate reviewed production adapter execution and receipt |
| P3 | NOT_RUN | Separate reviewed production integration execution and receipt |
| P4 | NOT_RUN | Separate reviewed production integration execution and receipt |
| P5 | NOT_RUN | Production DB/publication procedure and evidence, including expired PREPARED reconciliation |
| P6 | NOT_RUN | Separate reviewed production integration execution and receipt |
| P7 | NOT_RUN | Separate reviewed production integration execution and receipt |

1. **Root coordinator (next owner):** may integrate this source candidate only, preserving every integration/operating gate and P1–P7 as NOT_RUN. Do not activate or treat PC1 as part of this cohort.
2. **Codex (followup author):** add permanent short-read/ctime negative cases and make ACL withdrawal restoration failure-safe. These are non-blocking test hardening, not conditions for the source-only verdict.
3. **Root/production owners:** execute and independently review P1–P7 separately; PC1 remains NEW_ENROLLMENT outside this candidate.
