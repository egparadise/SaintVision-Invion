---
doc_id: "HIST-20261007-CARD284-CODEX"
title: "Card 284 VF-CL reviewer blocker independent re-review"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-10-07T08:07:44+09:00"
updated: "2026-10-07T08:07:44+09:00"
source_of_truth: "Git"
---

# Card 284 VF-CL reviewer blocker independent re-review

## Scope and decision

- Review tree: train 62 candidate `59050d2aa125fad67a4734f271fea5c294296a1a`
  (`coord/train62a-ci-1059`).
- Reviewer-owned scope only: VF-CL-02, VF-CL-03 and VF-CL-04
  `independentlyReviewed`, the five open reviewer blockers, their closure evidence, and the
  manifest checks that prevent a prose-only closure. Implementation fields, acceptance state,
  `ciVerified`, and the old implementation-side `verifiedAgainst` record were not changed.
- Decision: all five requested blockers are closed. No product defect was found and no product,
  migration, contract, evaluator, target, or workflow file was changed.

## Independent findings

| Card / blocker | Current-tree finding | Fail-closed or mutation evidence | Verdict |
|---|---|---|---|
| VF-CL-02 / URI trailing and version slash | `pathsafe.py` still rejects `/` in a dataset/model version and rejects a trailing empty path segment. | Focused 6/6 passed. Disabling both guards caused exactly the two trailing-slash cases and the ambiguous-version case to fail (3 failures). | CLOSED |
| VF-CL-02 / `c75201af` model shard resolution | The original resolver was strengthened later: the product caller in `inv/model_uri_resolver.py` supplies a schema-checked, project-authorized execution observation; the business resolver checks model/version/project/authority and intersects every reported location/version/node with the restricted tenant/reader catalogue. The raw immutable-manifest seam remains an explicitly trusted unit seam, not the product HTTP boundary. | Direct injected `modelId` drift and `materialisable`/`readyNodes` disagreement were refused. Exact-head Core JUnit contains 7 PostgreSQL resolver cases and the HTTP cross-role/revocation case. | CLOSED |
| VF-CL-03 / `34791448` exact license adapter | `model_import.py` is unchanged since the reviewed commit: exactly `licensePolicy` and `classification`, byte-exact string equality, missing/non-string/extra keys refused, field names only in diagnostics. A match grants no execution authority. | Python 3.14 focused suite 37/37 passed. Replacing equality with `casefold()` made two case-drift tests fail. | CLOSED |
| VF-CL-04 / 0043 retained-replica pin | Migration 0043 is unchanged since `08ece3bc`: pinned replicas may be only `ready` or `stale`; downgrade refuses an unreviewed reversal. | Captured upgrade SQL admits pinned+stale and a ready-only mutant does not. Exact-head Core JUnit contains both real-PostgreSQL migration cases and the service-level pinned-departure case. | CLOSED |
| VF-CL-04 / `3e267b05` archive retention | The original plan remains, with later hardening: malformed/ambiguous label times refuse the plan; missing time becomes `UnknownAge` without mtime guessing; WAL starts at the minimum retained segment. | Focused 37/37 passed. Changing the boundary from `min` to `max` failed four safety/property cases. Exact-head Backend 3.12 and 3.14 succeeded. | CLOSED |

## Executed evidence

- `tests/test_vf_service_review.py -k "parser or builder"`: 6 passed; two-guard mutant:
  3 failed / 3 passed.
- `tests/core/test_registry_policy_exact_match.py`: 37 passed under the repository Python 3.14
  environment; case-fold mutant: 2 failed / 35 passed.
- `tests/test_pitr_archive_retention.py`: 37 passed; `min` to `max` WAL-boundary mutant:
  4 failed / 33 passed.
- `tests/test_vf_replica_migration.py`: local 2 skipped because
  `INV_TEST_ADMIN_DSN` is absent. This is not promoted to a blocker: exact-head Core run
  `37401903045` succeeded at the review SHA, and downloaded `core-tests.xml` records both cases
  as executed, plus all seven `test_model_uri_resolver.py` PostgreSQL cases and the HTTP resolver
  boundary case.
- Exact-head Backend run `37401900619`: Python 3.12 and 3.14 jobs succeeded.
- `tools/check_vf_cl_registry.py`: passes after the reviewer records and manifest checks are
  updated. No local Docker command was used.

## Residual boundary

VF-CL-04 remains `ciVerified: false` and none of the three cards becomes operationally accepted.
This review closes only the five stale independent-review blockers; it does not change the
registry's implementation/CI/acceptance claims.
