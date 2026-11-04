---
doc_id: "HIST-20261104-LEGACY-PR-SOURCE-AUDIT-CODEX"
title: "Legacy open PR source-head audit: thirteen remaining branches"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-11-04T14:06:00+09:00"
updated: "2026-11-04T14:18:00+09:00"
source_of_truth: "Git"
task_id: "task_fc87fbcb38e0"
---

# Legacy open PR source-head audit

Six heads are superseded by later source, five contain proposals excluded by later architecture
decisions, and two retain useful source/test deltas (#118 and #119). None of these thirteen exact
heads is an ancestor of either the assigned source or the pinned candidate. This audit does not
establish whole-project completion, PR acceptance, current CI success, or operational acceptance.

## Identity and boundaries

- Owner/executor: Codex dispatched worker; independent reviewer: coordinator pending.
- Orca run `run_e57ecd84a7bc`, task `task_fc87fbcb38e0`, dispatch `ctx_7cf31e3d629b`.
- Assigned source and direct local test SHA: `03e17c31cf535008d39534aaa80d3ae274bd75cc`
  (`origin/integration/all-agents-unified` at dispatch).
- Reviewed candidate: `fe69e300121edefe198a8a495ebc9abb08588667`, branch
  `agent/codex/supervision-integration-20261104`; this is a pinned observation, not its future tip.
- Report branch: `agent/codex/legacy-pr-audit-20261104`; checkout
  `D:/Project/SaintVisionI-Invion/legacy-pr-audit-20261104`; initial tracked/untracked status empty.
- Started 2026-11-04 14:06 KST. Report/evidence are the only authored changes. No product edits,
  shared-board/registry edits, Obsidian apply, PR mutations/comments, new workers, live Node/DB
  operations, Docker changes, or schedule changes. All old pilot namespaces and 69 anonymous
  volumes remain untouched. Active #401/#402/#406 were excluded.
- Dispatch scope overrides the normal shared-board update/export workflow: coordinator owns
  aggregation and any later forward-port assignment. No other agent's review is claimed.

Read guidance: INDEX-PROGRESS-001 v1.0.375 and WORKBOARD-CODEX-001 v1.0.337 at source;
the read-only shared Obsidian index is v1.0.376, updated 2026-10-29. GUIDE-001 v1.1.0,
ADR-INDEX-001 v1.37.0, GOV-AGENT-001 v1.1.3, GOV-GIT-001 v1.1.4,
GOV-CONTINUITY-001 v1.0.0, GOV-CONTINUOUS-001 v1.1.0,
INDEX-VIRTUAL-COMPUTER-001/ROADMAP-VIRTUAL-COMPUTER-001 v1.0.0, backend/DB/storage
plans v1.0.0, task registry v1.0.0 and verification catalog/canon were consulted.
Skills: repository agent-delivery v1.1.0/core-reliability v1.0.0 and version-matched
`orca skills get orchestration`. The assigned audit is a dispatch, not a new registry task.

## Thirteen-head verdict table

All rows: remote head revalidated with one `git ls-remote --heads origin <13 exact refs>` (exit 0),
full SHA in the inventory; ancestry checks returned 1 for both source and candidate. `git cherry`
reported `+` for every unique nonmerge commit: **no whole-commit patch equivalence is claimed**.
Identical current blobs and later semantic replacements are distinguished below.

| PR / verified head | Verdict | Current source or decision evidence at the pinned candidate | Missing delta / next owner |
|---|---|---|---|
| #390 `72934014` | Superseded recovery plan | `tools/lan_pilot.py` historical-expiry validator/private OOB authorization; `deploy/lan/worker_leaf_rotation.py`; Card295 recovery and Card296 isolated namespace implementation | No product delta from the old two-option memo; retain historical plan only, no live execution |
| #306 `9963f8a0` | Superseded caller memo | `build_execution.py` receipt/isolation/epoch checks and atomic completion; `build_product_runtime.py:configured_tenant_product_runtime`; `worker.py:consume_builds` | No old memo implementation to port; physical builder/isolation/cleanup acceptance remains separate |
| #265 `ecb43d4d` | Superseded design | Strict BuildRequest/BuildPlan/BuildReceipt in core schema; `build_governance.py`, `build_adapter.py`, `gpu.py:current_single_gpu_allocation`; `test_single_gpu_contract.py` | No blind design/board import; does not certify every design wish or physical GPU acceptance |
| #194 `c5d03f4a` | Superseded implementation | Business handler → shared `denial_recorder.record_denial`; canonical `problem.py` callback and kernel handler; audit_action source/test identical blobs | No missing recorder; focused current behavior verified, real PG not rerun |
| #148 `99f0efd5` | Mixed: result retained, inherited product stack excluded | Canonical S05 decision §§6–7; clean-base `run_s05_legacy_staircase.py`/workflow/tests preserve separate Card46 and Card47 provenance | No stack merge: legacy lane without semaphore already reconstructed; performance numbers are historical |
| #145 `9efc4dcc` | Decision superseded; inherited stack excluded | Canonical S05 decision §§6–7 explicitly names #115/#141/#145/#148 for reconstruction without semaphore product code | No missing decision; coordinator retains later decision |
| #141 `429e831c` | Conflicts with later measurement decision | Candidate hosted-wave arm depends on rejected semaphore tree; legacy-only staircase replaces accepted measurement need | Do not restore candidate-wave runner/workflow by merging the branch |
| #140 `9c02a89b` | Superseded storage design | `object_store.py:ObjectStore`, `s3_object_store.py:S3Objects`, shared `s3_client.py`, migration 0048, provider-bound result/checkpoint readers/tests | No old design-only import needed; operating vendor/DR acceptance remains separate |
| #119 `367ac339` | Still-needed read-only harness delta | Current `measure_s07_recovery.py:parser` has only synthetic measurement knobs; common registration helper has no transform callback; proposed-review S07 spec explicitly says CLI unimplemented | Codex narrow four-file forward port; Claude review; no disruption or operational promotion |
| #118 `c149f8df` | Still-needed evidence-runner delta | All three runner/test paths absent; current individual approval/control/outbox tests and later operational collectors cover different scopes | Codex narrow three-file forward port; Claude review; fresh disposable PG evidence required |
| #115 `08f4a6a9` | Conflicts with later accepted decision | S05 decision §§6–7: `NO_DEGRADE_THROUGH_50_CLOSE_SEMAPHORE_LINE`; process-local permits and root-transaction lifecycle deliberately excluded | Do not restore semaphore product code/flag |
| #35 `39d8c238` | Superseded implementation | Envelope/WorkloadSpec tests, requirements, AGENTS and five integration files identical blobs; provisioning has later narrower exception handling; catalogue callers remain in InvFileExplorer | No missing old fix identified; focused source tests pass |
| #14 `e491ec73` | Mixed: retained fixes, rejected experimental architecture | Eval executor/tests and many kernel blobs identical; current shared `gate_passed` rejects all-error runs; ADR050–052/064–065 require explicit binding/identity and canonical migration graph | Do not merge old gateway/handoff, automatic epoch initialization or renumbered migration chain |

Paths without a directory in this table are under `services/control-plane/src/inv` unless explicitly
identified as tests/tools. Full path/symbol/SHA references and per-path blob comparisons are in
`docs/vault/30_Development/Evidence/2026-11-04_legacy_pr_source_audit_Codex.inventory.json` and
the corresponding raw `.json`. “Superseded” is a source disposition, never an acceptance score.

## Missing deltas and exact reproductions

### #118: unified HTTP/PostgreSQL evidence runner

The following paths exist at `c149f8dff4df36aa8918ea8d2bb45fb200cc0d03` and each returns exit 128
from `git cat-file -e fe69e300121edefe198a8a495ebc9abb08588667:<path>`:

- `tools/run_s04_db_evidence.py`
- `tests/core/test_s04_db_runner.py`
- `tests/integration/s04_db_runner_case.py`

The branch runner executes exactly four report cases: HTTP create/cancel replay, approval quorum
and expiry, publisher crash/republication, and consumer rollback/dedup. Physical delivery resumption
stays UNMEASURED. The current approval/control/outbox regression files and
`collect_s04_kernel_approval_evidence.py`/`collect_s04_s08_operational_evidence.py` are valuable,
but do not provide this unified executable four-case report. This is a missing harness feature,
not evidence of a production failure. Port those three paths with current fixtures, inspect stale
comments/clock dependence and report validation, then measure against a new disposable database;
do not import the branch's old green JSON/XML as today's candidate evidence.

### #119: S07 registration-only dry-run adapter

Parser-only reproduction (no database, artifact, or Node is touched):

```text
python -c "import runpy; p=runpy.run_path('tools/measure_s07_recovery.py')['parser'](); print(p.format_help()); p.parse_args(['--adapter','five-node-lab','--inventory','synthetic.json','--dry-run','--json-out','unused.json'])"
```

Direct exit **2**: help omits adapter/inventory/dry-run, and current required synthetic
`--nodes`, `--repetitions`, `--liveness-timeout-seconds`, `--junit-out` prevent that command.
`git show 4d322156 -- tools/measure_s07_recovery.py tools/five_node_lab_preflight.py` (exit 0)
shows the absent parser/projection/transform implementation. Minimal scope adds the two associated
test files: `tests/core/test_s07_recovery_measurement.py` and
`tests/integration/test_five_node_lab_preflight.py`.

The current S07 spec is **proposed-review**, explicitly records this command as unimplemented,
and keeps disruption/repair/JUnit acceptance out of scope. Therefore this is pending source,
not a regression in an advertised completed feature. An early coordinator note loosely called
the spec accepted; this record corrects that status. Preserve shared inventory validation,
read-only transaction proof, CP-colocated exclusion and current synthetic behavior when porting.

## Why the other heads must not be blindly merged

- **S05 stack:** canonical `S05 bounded admission 후속 결정 제안.md` §§6–7 explicitly rejects
  importing #115/#141/#145/#148 product code. Card46 run 36362386530 measured the old semaphore
  tree with its flag off; Card47 run 36363327477 measured the later clean integration tree.
  Current legacy runner preserves `mayReplaceCanonicalDecision=false`. Neither historical run
  was repeated here or promoted to current CI evidence. Reintroducing process-local permit
  machinery because its exact head is unreachable would reverse the documented decision.
- **PR14:** `Codex 업무 binding과 실행 커널 연결 계약.md` ADR-051 explicitly excludes its
  experimental 0019→0025 migration graph and auto-stamping. Current `business_handoff.py`,
  `business_auth.py`, `workspace_api.py` and 0021/0026+ canonical history use explicit identity,
  authority intersection and immutable actual-execution bindings. Current epoch initialization is
  operator/bootstrap responsibility; migration must not invent live authority. The eval and
  node-test-inventory fixes survive independently; their identical blobs are recorded.
- **Design memos:** #390's options are overtaken by implemented fully expired recovery and isolated
  bootstrap; #140's SPI/shared signer/provider-byte path is implemented; #265's direction has
  strict build/GPU contracts and guards. #306's missing caller observation is historical: a
  product loop and authenticated-receipt service now exist. Its configured reference transport
  still refuses unsupported physical dispatch; that boundary is retained rather than called done.

## Verification and handoff

Direct focused execution on source `03e17c31cf535008d39534aaa80d3ae274bd75cc`, Windows,
`D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe` **3.14.7**, pytest **9.1.1**:

```text
python.exe -m pytest -q -p no:cacheprovider tests/core/test_canonical_denial_audit.py tests/core/test_audit_action.py tests/core/test_credential_provision_cli.py tests/core/test_evidence_envelope_serving.py tests/core/test_workload_spec_input_anchors.py tests/test_eval_execution.py
```

**Exit 0; 68 passed, 13 skipped, 0 failed/errors, 0 deselected.** All thirteen skips are
PostgreSQL eval-execution cases because `INV_TEST_ADMIN_DSN` is absent. In particular the
DB-backed all-error gate case was not executed; its source is present. This run verifies local
denial/refusal/envelope behavior only, not real PG, browser, physical Node, GPU or hosted CI.
`PYTHONDONTWRITEBYTECODE=1`, `PYTHONUTF8=1`, and PYTHONPATH included this checkout's src,
control-plane/src and root. Raw subprocess argv/start time/exit/stdout/stderr are retained.
The tree was dirty only with these new report/evidence files. Candidate differences were
inventoried; these results are not relabeled as a full candidate run.

Documentation gate returned **0** (24 original hashes, 1,166 versioned documents, 48 tasks,
12 outcomes); ontology gate returned **0** (RDF/SHACL, 48 task mappings, four invalid-fixture
rejections, four competency queries); sync check returned **0** (2,077 managed, 12 pending exports,
zero conflicts, no writes). Each was invoked through the recorded subprocess wrapper with the
absolute 3.14.7 interpreter. The sync command was `tools/sync_obsidian.py --check --conflicts-out
docs/vault/30_Development/Evidence/2026-11-04_legacy_pr_source_audit_Codex.sync-conflicts.json`;
no conflicts file was needed. Exact gate argv/timestamps/exits are in the raw evidence.
Push is conditional on all three returning 0. Sync is read-only, with no apply.
Hosted CI for this new report: not run; independent report review: pending; operational acceptance:
not run. Completion here means delivery of this bounded audit, never whole-project done.

Intermediate findings were sent to the coordinator in Orca message `msg_d9b5a14db56d` (exit 0).
Next owner: coordinator records these dispositions and assigns the #118/#119 narrow ports to
Codex with Claude review. Do not merge historical branches wholesale, close PRs, change shared
scores, or infer equipment availability from this audit.
