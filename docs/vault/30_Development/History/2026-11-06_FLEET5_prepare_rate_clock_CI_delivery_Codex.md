---
doc_id: "HISTORY-FLEET5-20261106-PREP-RATE-CLOCK-CI-CODEX"
title: "FLEET5 preparation rate clock real PostgreSQL evidence"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Root Codex pending actual test README workflow review"
updated: "2026-11-06T09:37:45+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "eb32b211ab3704935b9431747089ab0715582a74"
task_ids: ["FLEET5-CORE-PREP-RATE-CLOCK-20261106"]
tags: ["fleet5", "codex", "test-reliability", "postgres", "ci"]
---

# Immutable source and scope

Owner Codex, independent test/README/workflow reviewer Root Codex. This continues
Orca `task_38393b5d1865` / dispatch `ctx_ceecb3824e33`. Root scope messages
`msg_03792925724e`, `msg_b56d7fd0b616` and `msg_2f135030b23c` authorize the bounded
test-only clock seam, README R1 and one focused hosted workflow. No helper agent
or new author task was created. This separate Orca report branch
`agent/codex/fleet5-prepare-rate-clock-report-20261106` starts at exact source
eb32b211ab3704935b9431747089ab0715582a74 and changes owner History/Evidence only.
Source branch stays frozen; report product diff is0. Root Index1.0.430/Codex1.0.391,
AGENTS, agent-delivery1.1.0/core-reliability1.0.0 and Orca1.4.248 apply.

Source eb32 has parent56651. Product/Go/testdata/schema/pins/migrations/dependencies
and existing workflows remain56651; README R1 is the sole K1 package delta.
Its package tree is56f11475c85e2b9018b627b6c8ca5962a5b94fb3, changed only by README.
Actual191b K1 implementation acceptance remains distinct from test validation,
full Core and K2/physical acceptance. Old Core42126222201 FAILURE and qualified
a413 report/Docs42133327925 remain immutable; no prior result is replaced.

# Exact first-run results

The first ordinary source push created focused run42137053588, event `push`, exact
eb32 head/ref/path/title, workflow `Preparation rate clock real PG`, job127627763128.
It completed SUCCESS. Exact source Docs42137296076/job127628586662 also completed
SUCCESS with its unique correlation. No workflow rerun/cancel, whole Core dispatch,
local PG/Docker/VM/install, hardware, production DSN or physical clock action.

Hosted tools were actual Python3.12.16, Go1.27.1 linux/amd64 and PostgreSQL16.15
(server_version_num160015), with the dedicated job's invdev/invowner service.
The actual test fixture allocated unique inv_test_UUID/inv_app_UUID resources,
used real Alembic, tenant/epoch/grant/RLS checks and audited cleanup. No fake rate
counter, guard monkeypatch or global approval/SQL/OS clock was used. Source
[[2026-11-06_FLEET5_prepare_rate_clock_test_Codex]] describes the scoped adapter.

| Real-PG evidence | Actual result |
| --- | --- |
| Exact original56651 function, same controlled minute |1 passed,0 failure/error/skip, subprocess0 |
| Exact original function, exact next-minute6th attempt |1 intended assertion failure,0 error/skip, subprocess1; control checker0 |
| Entire affected integration file |30 passed,0 failure/error/skip,0 deselected, subprocess0 |
| Source-local core unit file |29 passed,0 skip/failure/error; unit-only, not PG evidence |
| Earlier source-local PG prerequisites |0 passed,2 resource skips; preserved as NOT RUN |

The red control verifies actual `(GRAPH-0003,409,false)` against the unchanged old
expectation `(RES-0007,429,true)`. Its expected failure is checked separately and
cannot hide a failed positive suite. The same-window control independently passes.
This establishes a deterministic source counterexample; it does **not** establish
the cause or clock values of the original historical Core failure.

Independent parsing of actual XML and structured traces confirms6 real clock
SELECTs in each original control,3 scope rows count5 in one minute, then6 rows
across two exact minute buckets5->1 under forced rollover. Fixed positive traces
confirm5 first charges, exact next-minute bucket1, then5 and sixth-request429;
there are11 actual clock reads and two buckets, each with all3 real scopes.
Nonidentical seconds, exact window timestamps and idempotency/counter assertions
detect omitted clock binding, unrounded per-request buckets and lost guard/count
behavior. No sleep-until-minute, retry, skip, xfail, limit increase or relaxed
409-or429 expectation was added.

# Artifact integrity and publication

Downloaded original artifact13466003560 once,13,493 bytes. SHA256 matches the
remote digest:
`cb6ac1002ff5fe785a12186d26b891a4895ba105ea9c4c4fb67f0fc726925a62`.
Opaque ZIP/raw logs/JUnit remain GitHub/ignored scratch only. Public evidence is
parsed counts, exact source/job/event/ref/tool provenance, real counter traces and
raw hashes under `Evidence/fleet5-prepare-rate-clock-ci-20261106-codex`.

Actual XML raw hashes:

- same-window:4df75b576c364d35e00dc6646096c7af47cd4fe878a438032b04d5060210a9ec
- forced rollover:045a0317d39a547d9fbc5f0d438793fd76c62061b6f12ed318a00c76820bdc92
- full file:8976c7bd39be85fc04692f3b9d0b3bc08ae36009bb680f17a0b12c1a0690907f

The observer's initial preflight assumed REST `name` was the static workflow name.
It actually contains dynamic run-name. That assertion failed before any Docs
dispatch; exact workflow path/title/head/ref/event validation replaced it. Source
Docs was dispatched once afterward. This was metadata observation correction,
not a test/CI rerun. The source and all first-run results remain unchanged.

# Remaining gates and first next action

Root independently reviews immutable eb32 TEST+README+YAML and these actual results,
then chooses an exact combined source and authorizes one fresh full Core/Docs.
The focused PG lane does not clear failed42126222201, and no full-Core acceptance,
K1 worker_done, K2/runtime40 or whole five-PC acceptance is claimed here.
Codex publishes this documentation-only report with required local gates and its
own exact Docs. Root's actual independent verdict and combined-source decision
are still required; no generic approval or unrequested whole-Core rerun.

All10 required local report gates exited0 at09:36:42-09:37:43 KST. The official
read-only sync check used Root's current canonical state; before/after SHA256
both1a4bf31dd6f03e8ce2c41f97548d27836950329d744f58a3b6d11a2bafe4d64c.
No apply/adopt/resolve/state write occurred. Exact commands/exits/times are in
`report-source-gates.json`; the report source/runtime/test/workflow diff is0.
