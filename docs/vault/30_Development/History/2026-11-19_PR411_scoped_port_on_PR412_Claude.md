---
doc_id: "HISTORY-PR411-SCOPED-PORT-PR412-20261119-CLAUDE"
title: "PR 411 scoped preflight followups ported onto accepted PR 412 head"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-19T05:18:11+09:00"
source_of_truth: "Git"
---

# Scope

Orca task task_6139460918f8. Claude ported the scoped PR 411 followups onto the independently accepted PR 412 head `3f3defb16d10d9bada75df653225daf74d7e40b7`. The branch is `agent/claude/pr411-scoped-on-412-3f3defb1`. The stacked PR targets `agent/claude/pr411-precursor-unified-15384c36`, because unified `59f0a3c2` does not yet contain the precursor. Source only: no merge, deployment, live activation, fleet contact or migration was performed.

# Lineage

Cherry-picked with `-x`, in order, from `15384c36..abe0c971`:

| Source | Content |
|---|---|
| `b4c16254` | R2-02 private-mount-namespace harness `tests/integration/recovery_reader_namespace_harness.py`, R2-01 guard tracer `tests/integration/recovery_guard_trace.py`, cohort preflight assertions, and the Backend `provisioned-reader.json` receipt check |
| `a2ddbade` | `ENOTDIR` expectation for a symlinked descriptor directory |
| `abe0c971` | Real withdrawal of `pg_control_system()` EXECUTE for the control-privilege negative |

`2598d3c0` (PR 411 tracking) is not cherry-picked. Its shared-board edits are left out, as in PR 412. The stacked-integration note describes the older 15384c36 base. The independent review it introduced is carried unchanged (see below).

# Deviations from reviewed abe0c971

Comparing `abe0c971` with this branch for the three ported test files shows exactly one class of change:

- `tests/integration/test_recovery_cohort_preflight.py`: the module docstring and the two receipt `fixture` labels read `schema0067` instead of `schema0068`. This keeps PR 412's unified 0067 exact pin (`9e8846cf`). `tools/recovery_preflight/common.py` is untouched and still pins `SCHEMA = "0067_audit_reader_revoke"` with exact equality. No `0068` string remains in the ported files.
- `tests/integration/recovery_guard_trace.py` and `tests/integration/recovery_reader_namespace_harness.py` are blob-identical to `abe0c971`.
- `.github/workflows/backend.yml`: the only change on top of `3f3defb1` is the one PR 411 line `test -s dist/recovery-readonly-pg/provisioned-reader.json`. The full "Prove read-only cohort observation on disposable PostgreSQL" step and its upload step match `abe0c971` line for line.

The one conflict, in the receipt block of `b4c16254`, was resolved by taking the PR 411 side (`write_receipt`, which keeps the `SV_PREFLIGHT_PG_RECEIPT` gate) and relabeling it to 0067.

# Preserved review tracking

These review files are carried from their review commits:

- `2026-11-19_FLEET5_abe0c971_Recovery_Preflight_Followup_Review_Orca.md` from `2598d3c0`, byte-for-byte (blob `c8ff4d45`). This is the independent source review of the ported code.
- `2026-11-19_PR412_independent_review.md` from `58f61b2c`, byte-for-byte (blob `43e0dae5`). This holds the PR 412 fixture findings.
- `2026-11-19_PR412_independent_rereview.md` from `ae58e3d0`, the independent re-review that accepted `3f3defb1` and closed the CX01 blocker. The original frontmatter failed `tools/check_docs.py`: `doc_id` was not JSON-quoted, and `title` and `source_of_truth` were missing. Only the frontmatter was changed: `doc_id` is quoted, and `title: "PR 412 independent re-review"` and `source_of_truth: "Git"` are added. The body after the closing `---` is byte-identical to `ae58e3d0`, with SHA-256 `3288d3636cff91151de00dd47a8954349d4b18dbffb4ef544c9f1996af3c4148` on both sides.

The review verdicts are unchanged. This note adds no review disposition of its own.

# Verification

Local, Windows, owner venv Python 3.14.7: targeted pytest over `tests/test_core_workflow_cx01.py`, `tests/core/test_recovery_preflight_schema_pin.py`, `tests/core/test_readonly_cohort_join.py`, `tests/integration/test_recovery_cohort_revision_pin.py` and `tests/integration/test_recovery_cohort_preflight.py` gave 23 passed and 13 skipped, exit 0. The 13 PostgreSQL cases skipped because this host has no reachable PostgreSQL (Docker daemon stopped, no service). `py_compile` of the three ported files and a YAML parse of `backend.yml` and `core.yml` passed.

Real disposable PostgreSQL on Python 3.12 and 3.14, and the private-namespace provisioned-reader cases, run only in hosted Backend. Hosted run IDs and artifact receipts for the exact final head are recorded in the stacked PR description, not here, so that this note does not cite a candidate SHA.

# Remaining

- An independent Codex review of this port is needed: the 0067 relabel and the conflict resolution.
- R2-03 through R2-07, R3-01 (failure-safe ACL restoration), and hosted short-read/ctime cases remain open, as recorded in the abe0c971 review.
- Production P1–P7 remain NOT_RUN. Activation stays off. PC1 requires separate enrollment. Coordinator owns integration sequencing.
