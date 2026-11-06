---
doc_id: "HISTORY-FLEET5-20261106-PREP-RATE-CLOCK-CODEX"
title: "FLEET5 deterministic preparation rate window test"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Root Codex pending independent test and README delta review"
updated: "2026-11-06T09:27:06+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "56651cba697f2ab6fcd7166ca4e6ea11eac28113"
task_ids: ["FLEET5-CORE-PREP-RATE-CLOCK-20261106"]
tags: ["fleet5", "codex", "test-reliability", "postgres"]
---

# Scope and accepted boundaries

Owner Codex, independent test/documentation reviewer Root Codex. This is the
sequential ready card from `msg_03792925724e`, under existing Orca
`task_38393b5d1865` / dispatch `ctx_ceecb3824e33`, not a new author/task/process.
The factual failed-Core report a413c0c2e9a6d070321480f9c216b8aa07e5fd74 and exact
Docs42133327925/job127615152751 completed SUCCESS before this card started.
Root accepted that report as failed-CI evidence only. Its original Core failure
and default sync3 remain preserved.

Orca created branch `agent/codex/fleet5-prepare-rate-clock-test-20261106` from
exact56651, worktree `fleet5-prepare-rate-clock-test-20261106`, setup skipped,
without a helper agent. Root Index1.0.429/Codex1.0.390 were read at start.
AGENTS, agent-delivery1.1.0, core-reliability1.0.0 and the narrow Root scope apply.
The original scope was the preparation integration test, unique test-only helper,
owner History/Evidence and README R1. Root later explicitly added the one fixed
CI workflow below. Product, Go/tests/testdata/schema/source28pin/wire/graph,
existing workflows and dependency bytes stay56651.
No boards, registry, Card150, PKI/private configuration, equipment, clock or
Obsidian apply action. No whole Core dispatch until Root chooses a reviewed
combined source.

Actual K1 review is191b6f843a643ee4989ce28c9ebf1816963ffe28, exact
Docs42132923864/job127613767272 SUCCESS, received in `msg_b56d7fd0b616` and read
from public Git. Verdict ACCEPT applies to the56651 IMPLEMENTATION delta only;
M1/M2 and L1-L5 are closed. R1 is README wording and is added to this card's
scope. R2-R6 Info remain: K2 cross-migration fencing/independent producers,
offline backdating limits,30-second historical skew, current-method concurrency
coverage limits and unused semantic fields. No stronger guarantee is asserted.
Core42126222201 remains FAILURE; K2/runtime40/physical acceptance remain NOT RUN.

# Source investigation and actual CI failure

`BuildPreparationService._reserve`373-416 opens the real Database transaction,
checks the request grant and idempotency record, reads DB `clock_timestamp()`,
floors to a minute and increments real rate rows. PREPARE_LIMITS are subject5,
project30 and tenant-project60. This short transaction commits before later
failed work; the6th over-budget reservation rolls its attempted increment back.
Database.transaction preserves runtime non-owner/NOBYPASSRLS, tenant settings,
recovery epoch, tenant barrier and commit/rollback. BoundDatabase shares that
transaction for nested grant checks.

The old test includes the FIRST charge inside `_setup_prepared_build` then four
failed-work attempts and the6th expected429. No clock binds their minute bucket.
Current actual failure was GRAPH-0003/409/false instead of RES-0007/429/true.
Minute rollover is a source-consistent counterexample hypothesis, not proven
historical-run clock evidence. Product and test were byte-identical to c6f;
no runtime fix or blind CI rerun is authorized.

The test design will bind only the exact `_reserve` rate-clock SELECT through a
scoped test service/transaction connection adapter. It must return a real
parameterized PostgreSQL timestamptz row and retain real transactions, grants,
epoch/RLS checks, idempotency, UPSERT and rollback. Other clocks and SQL remain
untouched. Values stay within the35-day retention interval. Same-minute seconds
must differ so lost rounding creates multiple rows and fails assertions.

# Actual resource state

Main Python3.14.7 `-B`, psycopg available. At start INV_TEST_ADMIN_DSN is absent,
CI is unset and psql/pg_ctl/postgres are not on PATH. No DB connection, install,
container/WSL/remote/Node action was attempted. Real PG is **NOT RUN**, not PASS.
The existing integration fixture creates a unique inv_test_UUID and inv_app_UUID,
uses real Alembic/inv_kernel/NOBYPASSRLS and audits integrity before dropping only
its own resources. It requires a verified disposable PostgreSQL16+ server.
`workspace_http` also imports the synthetic mTLS Node/workspace execution fixture
family documented for Linux; resource validation must include that full harness.

Root was notified in `msg_93d9c14acdbc` of the exact resource need and target file.
Source/test/README preparation continues independently; symbolic or unit work
will never be called real-PG evidence. First next action is to validate a Root-
identified test-owned harness, then preserve forced-rollover red and same-window
green, implement/assert exact GRAPH and429 behavior and real scope/window rows,
run focused/full impacted-file checks, publish one test source/own Docs and obtain
Root's independent review before any fresh combined Core.

# Implemented test seam and local checks

The private test service activates its connection adapter only inside `_reserve`.
It intercepts only exact unparameterized `SELECT clock_timestamp() AS now`,
executing real `SELECT %s::timestamptz AS now` and returning that real cursor row.
Database.transaction remains the actual delegate; all other SQL, including the
identical SELECT later in prepare/approval and retention's clock, stays unchanged.
The test instance is synchronous and exclusively owned. No production injection
surface, fake counter, bypassed grant, fake guard or limit change was added.

The first setup charge and later attempts use differing seconds within one minute.
The same-window case asserts exact GRAPH failures2-5, sixth429/retryable, real3
scope rows count5, unchanged counters on idempotent replay and rollback of refused
idempotency. The companion proves first bucket5, exact next minute new bucket1,
then bucket5 and sixth429, with only two minute buckets and unchanged actual SQL.
Observed timestamps/real test-database identities/window rows are emitted as
structured fixture evidence. Removed rounding, missing clock interception and
lost increment/guard would violate these actual error/row/count assertions.

Local source ASTs pass. Existing core-unit file:29 passed,0 skip/failure/error,
exit0. The two focused PG cases:0 passed,2 skipped because the actual DSN is absent;
this is **NOT RUN**, never a real-PG pass. Opaque logs/JUnit stay in ignored scratch;
`local-prerequisite-checks.json` records exact argv/exits/counts/raw hashes.

# Explicit hosted resource scope

Root `msg_2f135030b23c` found no verified local test PG and reported insufficient
local memory. No local PG/Docker/VM/install action is permitted. It authorized
one new `.github/workflows/preparation-rate-clock.yml` plus the minimal fixed
test proof `tests/proofs/run_preparation_rate_clock.py`, in this same author/card.
Existing Core/Backend/other workflows remain unchanged. Harness source trace is
workspace_http -> synthetic mTLS Node/LocalObjects/private workspace -> actual
integration postgres fixture; it needs the existing scratch Node/probe/supervisor
image and embedded Git, not product ObjectStore/BuildKit or unrelated suites.

The new lane runs only on pushes to this exact test branch and exact workflow/
test/helper paths, read-only repository permissions, no inputs/deployment/SSH/
production secrets, no cancel-in-progress,20-minute maximum. Hosted Ubuntu uses
the existing pinned Python3.12/Go1.27.1/requirements-test and ephemeral PG16 with
fixed CI-only credentials. Real fixture allocation uses unique databases/roles,
real Alembic/RLS/grants/epoch and audited own-resource cleanup. Strict prerequisites
and zero-skip/error gates prohibit a mock or missing-resource green result.

The control helper compiles the exact original56651 test function. Its same-window
run must pass; its forced exact-minute rollover must fail only with the intended
GRAPH409 versus expected RES429 assertion, with real window rows and no skips or
teardown errors. It records a deterministic source counterexample, not historical
CI clock evidence. The entire affected file then runs independently, even if a
control fails, and must collect/execute both positive cases without failure/skip.
Always-upload artifacts include opaque logs/XML, versions/provenance, structured
control outcomes and positive counts. Raw artifacts remain outside Git/vault.

These hosted results are PENDING the first immutable source push. The focused
lane is not full Core and cannot clear failed42126222201. Root independently
reviews actual test+README+YAML/results, then alone chooses a combined SHA and
authorizes one fresh full Core/Docs. No new whole Core is dispatched here.

For subsequent read-only sync, Root explicitly authorized the actual canonical
Git state path, not the obsolete429 snapshot; the official check must exit0 with
before/after state hashes unchanged. No apply/adopt/resolve/state writes or stale
branch export is authorized.

At09:25:13-09:26:31 KST all10 required local source/document gates exited0.
Canonical-state official check used the exact Root-authorized state path; SHA256
before/after both `1a4bf31dd6f03e8ce2c41f97548d27836950329d744f58a3b6d11a2bafe4d64c`.
No apply/adopt/resolve/state write occurred. `local-source-gates.json` records
exact argv/time/exit/logs. Local checks do not turn the pending hosted PG run into
a pass. Prompt scope is the cited Root messages, harness Orca1.4.248/main Python
3.14.7, context429/390 and skills1.1.0/1.0.0. K1 source191b review accepts only the
unchanged implementation; its README boundary is the sole package delta here.
