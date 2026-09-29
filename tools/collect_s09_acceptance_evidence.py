"""S09-DB / S09-ST AC-09 acceptance evidence collector (immutable Context, RunRecord,
eval golden gate, diff/test/trace artifact pins, bounded approval loop).

At one fixed, committed code SHA and in one invocation this collector re-runs the
existing S09 real-PostgreSQL set (one pytest process per file, memory rule) and maps
every case of those five files to seven AC-09 evidence clauses:

* immutable Context (content stored once per tenant, item version survives the
  source, secrets refused and nothing stored, oversized refused not truncated,
  application role cannot delete snapshots, orphan-only collection);
* RunRecord seal immutability (no seal for an unfinished run, sealing twice returns
  the same record, a sealed record cannot be rewritten, one record per run);
* eval golden gate (a violation fails the gate however good the score, the database
  refuses a gate pass with violations, per-category scores, incomplete suite never
  passes, forbidden cases cannot be scored);
* eval executor conformance (adapter failure is error not fail, unredacted output
  is not stored, unpinned model refused by default, empty/partial/all-errored runs
  never pass, run row and report agree);
* diff/test/trace artifacts pinned by role (unverified cannot be pinned, a later
  overwrite is detected by the pin — S09-ST);
* bounded approval loop (request replay/scope immutable, quorum and direct-state
  bypass blocked, exactly-once decision races, revoked grants stop dispatch,
  review only for the authorized project reviewer, corrupt snapshot cannot be
  approved);
* RunRecord completion pipeline with real output bytes (``tests/integration/
  test_results.py``), which is environment-gated to a Linux private-storage host:
  on other hosts its cases are skipped and the clause is ``not_run`` with the gate
  named as the reason — never counted as pass, never counted as zero.

Rules applied from the start (Codex reviews of the S02/S03/S10 collectors, PRs #120,
#121, #127):

* fail-closed on every suite: any failed/error case (mapped or not), a non-zero
  pytest exit or a suite status other than ``complete`` makes the bundle FAIL, and a
  failure anywhere outranks an unavailable sibling suite (FAIL, never UNAVAILABLE);
  a clause is ``pass`` only if every mapped case passed in THIS run;
* nothing observed is never zero: an unavailable suite carries ``counts=null``, a
  clause that did not run is ``not_run`` with a stated reason, and the verdict is
  ``PASS_MEASURED_PARTIAL`` (with an explicit ``passScope``) when the only clauses
  that did not run are the environment-gated ones;
* provenance from ``tools.provenance.collect`` computed with the repository root as
  cwd, plus this collector's own content hash; a dirty working tree is refused by
  default (``--allow-dirty-tree`` is an explicit, recorded opt-out); the default
  label carries the SHA and a UTC timestamp, and an existing output with the same
  label is refused rather than deleted or overwritten;
* redaction contract (checked before every write, violations refuse the write):
  DSN values and passwords from ``INV_TEST_ADMIN_DSN`` / ``INV_AUDIT_DSN`` /
  ``INV_DATABASE_URL`` / ``INV_TEST_DATABASE_URL`` are refused; disposable database
  names (``inv_backend_test_``/``inv_rls_``/``inv_s03_`` + hex), UUIDs, every
  ``<prefix>_<26-char Crockford ULID>`` entity id regardless of prefix (the S09 ids
  are ``evs``/``evc``/``evr``/``art``/``apv``/``run``/``evd``/``wsp``/``usr`` among
  the ``saintvision.ids.PREFIXES`` and kernel sets) and ``IPv4:port`` are replaced
  by placeholders; ``--note`` passes through the same replacement; pytest failure
  messages are never kept (parameter-free case ids and counts only); paths outside
  the repository are recorded as ``<outside-repo>/<name>``.  This bundle is internal
  evidence, not a public artifact.

AC-09 itself ("Prompt 100건 유효율 99%, 코딩 과제 30건 성공률 70%, 누출 0") is a product
measurement that this collector does not perform: those three items and the real
external Provider adapters (CX-02) are recorded as ``UNMEASURED`` with no values.
``acceptanceClaim`` is always ``false``.

Exit codes: 0 PASS / PASS_MEASURED_PARTIAL; 1 FAIL; 2 UNAVAILABLE (no DSN, a suite
could not run, dirty tree without opt-out, or an existing output with the same
label); 3 NOT_RUN (nothing executed, or a mapped case skipped for a reason other
than the named environment gate).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
import xml.etree.ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.provenance import collect as collect_provenance  # noqa: E402

SCHEMA_VERSION = "s09-db-acceptance-evidence:1"
DEFAULT_OUT_DIR = REPO_ROOT / "docs/vault/30_Development/Evidence/s09-db-acceptance"

LINUX_PRIVATE_STORAGE_GATE = "linux-private-storage"

# One pytest process per file (memory rule).  ``gate`` names an environment gate the
# file itself declares (skipif) — its skips are recorded, never promoted or zeroed.
SUITES: list[dict[str, Any]] = [
    {"id": "context-eval", "postgres": True, "paths": ["tests/test_context_eval.py"]},
    {"id": "eval-execution", "postgres": True, "paths": ["tests/test_eval_execution.py"]},
    {"id": "approvals", "postgres": True, "paths": ["tests/integration/test_approvals.py"]},
    {"id": "approval-review", "postgres": True, "paths": ["tests/integration/test_approval_review.py"]},
    {"id": "results-linux-private-storage", "postgres": True, "paths": ["tests/integration/test_results.py"],
     "gate": LINUX_PRIVATE_STORAGE_GATE},
]

_CE = "tests.test_context_eval::"
_EE = "tests.test_eval_execution::"
_AP = "tests.integration.test_approvals::"
_AR = "tests.integration.test_approval_review::"
_RS = "tests.integration.test_results::"

AC09_CLAUSES: dict[str, dict[str, Any]] = {
    "immutable-context": {
        "title": "불변 Context(tenant당 1회 저장·버전 생존·비밀/초과 거부·snapshot 삭제 불가)",
        "cases": [
            _CE + "test_the_same_content_is_stored_once_per_tenant",
            _CE + "test_storing_the_same_content_twice_is_idempotent",
            _CE + "test_a_bundle_reproduces_its_items_in_order",
            _CE + "test_build_bundle_refuses_a_secret_and_stores_nothing",
            _CE + "test_bundle_hash_depends_on_order",
            _CE + "test_the_item_version_survives_the_source_changing",
            _CE + "test_an_oversized_item_is_refused_not_truncated",
            _CE + "test_orphan_snapshots_are_collected_and_referenced_ones_are_not",
            _CE + "test_the_application_role_cannot_delete_snapshots",
            _CE + "test_deduplication_ratio_is_reported",
        ],
    },
    "runrecord-seal-immutable": {
        "title": "RunRecord 봉인 불변(미완성 run 봉인 불가·재봉인 동일·재기록 불가·run당 1)",
        "cases": [
            _CE + "test_a_record_cannot_be_sealed_for_an_unfinished_run",
            _CE + "test_sealing_twice_returns_the_same_record",
            _CE + "test_a_sealed_record_cannot_be_rewritten",
            _CE + "test_only_one_record_per_run",
        ],
    },
    "eval-golden-gate": {
        "title": "eval golden gate(위반은 점수로 상쇄 불가·DB 거부·분류별 점수·불완전 suite 불통과)",
        "cases": [
            _CE + "test_a_suite_version_is_unique_and_hashed",
            _CE + "test_a_forbidden_case_cannot_carry_a_weight",
            _CE + "test_a_violation_fails_the_gate_however_good_the_score",
            _CE + "test_the_database_refuses_a_gate_pass_with_violations",
            _CE + "test_per_category_scores_are_reported_separately",
            _CE + "test_a_scored_forbidden_case_is_refused",
            _CE + "test_a_violation_on_a_scored_case_is_refused",
            _CE + "test_an_incomplete_suite_does_not_pass_the_gate",
        ],
    },
    "eval-executor-conformance": {
        "title": "eval executor/adapter 적합성(error≠fail·미redact 미저장·모델 pin·빈/부분/전부 error 불통과)",
        "cases": [
            _EE + "test_a_correct_adapter_passes_the_gate",
            _EE + "test_an_adapter_failure_is_errored_not_failed",
            _EE + "test_an_unverifiable_cancellation_is_recorded_as_unknown",
            _EE + "test_an_adapter_that_did_not_redact_does_not_get_its_output_stored",
            _EE + "test_an_adapter_that_cannot_pin_its_model_is_refused_by_default",
            _EE + "test_running_without_model_pinning_records_that_choice",
            _EE + "test_a_violation_fails_the_gate_however_well_everything_else_scored",
            _EE + "test_a_forbidden_case_declaring_nothing_forbidden_is_refused",
            _EE + "test_cases_run_in_key_order_so_two_runs_are_comparable",
            _EE + "test_the_reference_adapter_satisfies_the_executor",
            _EE + "test_a_run_in_which_every_case_errored_does_not_pass",
            _EE + "test_the_run_row_and_the_report_always_agree",
            _EE + "test_an_empty_suite_is_not_a_pass",
            _EE + "test_a_partial_run_is_not_a_pass",
        ],
    },
    "artifact-pin-by-role": {
        "title": "diff·테스트·trace Artifact 역할 pin(미검증 pin 불가·덮어쓰기 탐지, S09-ST)",
        "cases": [
            _CE + "test_diff_test_and_trace_artifacts_are_pinned_by_role",
            _CE + "test_an_unverified_artifact_cannot_be_pinned",
            _CE + "test_a_later_overwrite_is_detected_by_the_pin",
        ],
    },
    "tenant-isolation": {
        "title": "Context dedup·eval tenant 격리",
        "cases": [
            _CE + "test_deduplication_does_not_cross_tenants",
            _CE + "test_evaluation_is_tenant_isolated",
        ],
    },
    "bounded-approval-loop": {
        "title": "제한된 수정 루프의 승인·검토(replay/scope 불변·quorum 우회 차단·exactly-once·grant 회수·검토 권한)",
        "cases": [
            _AP + "test_request_replay_and_scope_are_immutable",
            _AP + "test_untrusted_or_weakened_policy_cannot_create_approval",
            _AP + "test_quorum_and_direct_state_bypass_are_blocked",
            _AP + "test_challenge_is_actor_bound_rotating_and_digest_bound",
            _AP + "test_expired_nonce_does_not_consume_vote",
            _AP + "test_same_decision_race_is_exactly_once_and_survives_store_restart",
            _AP + "test_distinct_voters_race_and_dispatch_race_emit_one_command",
            _AP + "test_revoked_grants_stop_dispatch_and_cannot_be_self_restored",
            _AP + "test_content_change_wrong_tenant_and_wrong_project_are_denied",
            _AP + "test_audit_failure_rolls_back_nonce_vote_dispatch_and_outbox",
            _AP + "test_rejection_is_terminal_and_audited",
            _AP + "test_expiry_closes_pending_or_approved_run_once",
            _AP + "test_cancelled_run_or_restored_epoch_invalidates_approval",
            _AR + "test_review_returns_exact_action_only_to_authorized_project_reviewer",
            _AR + "test_snapshot_is_immutable_and_request_replay_does_not_duplicate",
            _AR + "test_corrupt_or_legacy_snapshot_cannot_be_reviewed_or_approved",
            _AR + "test_cancelled_run_cannot_be_reviewed",
            _AR + "test_review_cannot_cross_project_even_with_project_grant",
        ],
    },
    "runrecord-completion-pipeline": {
        "title": "RunRecord 완료 파이프라인(실 출력 바이트·receipt·pin·epoch·mTLS stop→verifier) — Linux 사설 스토리지 게이트",
        "gate": LINUX_PRIVATE_STORAGE_GATE,
        "cases": [
            _RS + "test_released_resources_allow_only_prepared_verified_result_and_one_commit",
            _RS + "test_crash_after_reservation_has_one_attempt_and_cannot_reexecute",
            _RS + "test_missing_output_or_receipt_never_succeeds",
            _RS + "test_stop_before_prepare_cannot_introduce_late_output",
            _RS + "test_unconfirmed_or_failed_application_never_succeeds",
            _RS + "test_cancel_and_recovery_revoke_prepared_completion",
            _RS + "test_output_identity_scope_policy_and_fence_are_bound",
            _RS + "test_result_commit_failure_rolls_back_evidence_state_and_event",
            _RS + "test_preparation_rollback_does_not_leave_a_pin",
            _RS + "test_corruption_after_prepare_blocks_completion",
            _RS + "test_result_pin_has_database_guard_and_tenant_isolation",
            _RS + "test_epoch_change_rejects_old_prepared_result",
            _RS + "test_gc_and_result_prepare_serialize_without_dangling_pin",
            _RS + "test_real_mtls_stop_then_verifier_evidence_completion",
        ],
    },
}

EXTERNAL_WAITS: list[dict[str, str]] = [
    {"id": "AC-09-prompt-validity", "item": "Prompt 100건 유효율 99%", "owner": "product measurement; S09-BE/S09-FE"},
    {"id": "AC-09-coding-success", "item": "코딩 과제 30건 성공률 70%", "owner": "product measurement; S09-BE"},
    {"id": "AC-09-leak-zero", "item": "누출 0 (제품 실측)", "owner": "product measurement; S09-BE"},
    {"id": "CX-02", "item": "실제 외부 Provider adapter 실행/취소/collect", "owner": "credential boundary; S09-BE"},
]

_SAFE_NAME = re.compile(r"[A-Za-z0-9_]+")
_SAFE_CLASS = re.compile(r"[A-Za-z0-9_.]+")
_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\binv_(?:backend_test|rls|s03)_[0-9a-f]{32}\b"), "inv_disposable_<redacted>"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
     "<uuid:redacted>"),
    (re.compile(r"\b[a-z]{3,4}_[0-9A-HJKMNP-TV-Z]{26}\b"), "<id:redacted>"),  # any prefixed ULID
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b"), "<host:port:redacted>"),
]


def evidence_ref(path: Path) -> str:
    """Repo-relative POSIX path, or a placeholder when the file lives outside the repo (hosted CI /tmp)."""
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return f"<outside-repo>/{path.name}"


def safe_case_id(case: ET.Element) -> str | None:
    classname = case.get("classname") or ""
    name = (case.get("name") or "").split("[", 1)[0]
    if not _SAFE_CLASS.fullmatch(classname) or not _SAFE_NAME.fullmatch(name):
        return None
    return f"{classname}::{name}"


def parse_junit(raw: bytes) -> dict[str, Any]:
    """Counts plus per-case outcome (worst outcome wins across parametrized ids)."""
    root = ET.fromstring(raw)
    if root.tag not in ("testsuites", "testsuite"):
        raise ValueError("not JUnit")
    rank = {"passed": 0, "skipped": 1, "error": 2, "failed": 3}
    outcomes: dict[str, str] = {}
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    for case in root.findall(".//testcase"):
        if case.find("failure") is not None:
            outcome = "failed"
        elif case.find("error") is not None:
            outcome = "error"
        elif case.find("skipped") is not None:
            outcome = "skipped"
        else:
            outcome = "passed"
        counts[outcome] += 1
        case_id = safe_case_id(case)
        if case_id is not None and rank[outcome] >= rank.get(outcomes.get(case_id, "passed"), 0):
            outcomes[case_id] = outcome
    return {"counts": counts, "outcomes": outcomes}


def clause_status(outcomes: dict[str, str], cases: list[str]) -> dict[str, Any]:
    per_case = {case: outcomes.get(case, "missing") for case in cases}
    values = set(per_case.values())
    if values == {"passed"}:
        status, reason = "pass", None
    elif values & {"failed", "error"}:
        status, reason = "fail", "case-failed-or-errored"
    else:
        status, reason = "not_run", "case-skipped-or-missing"
    return {"status": status, "reason": reason, "cases": per_case}


def gates_skipped_here(suites: list[dict[str, Any]]) -> set[str]:
    """Environment gates whose suite ran (pytest reported) but executed nothing because every case was skipped."""
    result: set[str] = set()
    for suite in suites:
        gate = suite.get("gate")
        counts = suite.get("counts") or {}
        if gate and suite.get("status") == "not_run" and counts.get("skipped", 0) > 0 \
                and not (counts.get("passed") or counts.get("failed") or counts.get("error")):
            result.add(gate)
    return result


def evaluate_clauses(outcomes: dict[str, str], skipped_gates: set[str] | None = None) -> dict[str, Any]:
    """A gated clause whose every case was skipped by its named gate is not_run with that gate as the reason."""
    skipped_gates = skipped_gates or set()
    clauses: dict[str, Any] = {}
    for key, spec in AC09_CLAUSES.items():
        clause = {"title": spec["title"], "gate": spec.get("gate"), **clause_status(outcomes, spec["cases"])}
        if clause["status"] == "not_run" and spec.get("gate") in skipped_gates \
                and set(clause["cases"].values()) <= {"skipped"}:
            clause["reason"] = f"environment-gated:{spec['gate']}"
        clauses[key] = clause
    return clauses


def pass_scope(clauses: dict[str, Any]) -> dict[str, list[str]]:
    scope: dict[str, list[str]] = {"passed": [], "notRunEnvironmentGated": [], "notRunOther": [], "failed": []}
    for key, clause in clauses.items():
        if clause["status"] == "pass":
            scope["passed"].append(key)
        elif clause["status"] == "fail":
            scope["failed"].append(key)
        elif (clause.get("reason") or "").startswith("environment-gated:"):
            scope["notRunEnvironmentGated"].append(key)
        else:
            scope["notRunOther"].append(key)
    return scope


def run_suite(spec: dict[str, Any], junit_dir: Path, *, python: str = sys.executable) -> dict[str, Any]:
    junit_dir.mkdir(parents=True, exist_ok=True)
    junit_path = junit_dir / f"{spec['id']}.xml"
    junit_path.unlink(missing_ok=True)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    python_paths = [str(REPO_ROOT / "src"), str(REPO_ROOT / "services" / "control-plane" / "src")]
    if env.get("PYTHONPATH"):
        python_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    command = [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rs", *spec["paths"],
               f"--junitxml={junit_path}"]
    started = dt.datetime.now(dt.timezone.utc)
    completed = subprocess.run(command, cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    elapsed = (dt.datetime.now(dt.timezone.utc) - started).total_seconds()
    result: dict[str, Any] = {"id": spec["id"], "paths": spec["paths"], "postgres": spec["postgres"],
                              "gate": spec.get("gate"), "exitCode": completed.returncode,
                              "elapsedSeconds": round(elapsed, 3), "junitSha256": None, "counts": None,
                              "outcomes": {}, "status": "unavailable"}
    if not junit_path.is_file():
        return result
    raw = junit_path.read_bytes()
    result["junitSha256"] = hashlib.sha256(raw).hexdigest()
    try:
        parsed = parse_junit(raw)
    except (ET.ParseError, ValueError):
        result["status"] = "invalid-junit"
        return result
    result["counts"], result["outcomes"] = parsed["counts"], parsed["outcomes"]
    executed = parsed["counts"]["passed"] + parsed["counts"]["failed"] + parsed["counts"]["error"]
    if executed == 0:
        result["status"] = "not_run"
    elif completed.returncode == 0 and not (parsed["counts"]["failed"] or parsed["counts"]["error"]):
        result["status"] = "complete"
    else:
        result["status"] = "failed"
    return result


def overall_verdict(clauses: dict[str, Any], suites: list[dict[str, Any]]) -> str:
    # Fail closed first: any failure anywhere outranks an unavailable sibling suite.
    for suite in suites:
        counts = suite.get("counts") or {}
        if suite["status"] in ("unavailable", "invalid-junit", "not_run"):
            if counts.get("failed") or counts.get("error"):
                return "FAIL"
            continue
        if suite["status"] != "complete" or suite.get("exitCode") != 0 or counts.get("failed") or counts.get("error"):
            return "FAIL"
    scope = pass_scope(clauses)
    if scope["failed"]:
        return "FAIL"
    if any(s["status"] in ("unavailable", "invalid-junit") for s in suites):
        return "UNAVAILABLE"
    if not scope["passed"] or scope["notRunOther"]:
        return "NOT_RUN"
    # A non-gated suite that executed nothing is not evidence.
    if any(s["status"] == "not_run" and not s.get("gate") for s in suites):
        return "NOT_RUN"
    if scope["notRunEnvironmentGated"]:
        return "PASS_MEASURED_PARTIAL"
    return "PASS"


EXIT_BY_VERDICT = {"PASS": 0, "PASS_MEASURED_PARTIAL": 0, "FAIL": 1, "UNAVAILABLE": 2, "NOT_RUN": 3}


def build_evidence(*, provenance: dict[str, Any], suites: list[dict[str, Any]],
                   note: str | None = None) -> dict[str, Any]:
    outcomes: dict[str, str] = {}
    for suite in suites:
        outcomes.update(suite.get("outcomes") or {})
    clauses = evaluate_clauses(outcomes, gates_skipped_here(suites))
    scope = pass_scope(clauses)
    # Totals are only meaningful over suites that produced counts; unavailable ones stay unknown.
    counted = [s for s in suites if s.get("counts") is not None]
    totals = ({k: sum(s["counts"].get(k, 0) for s in counted) for k in ("passed", "failed", "error", "skipped")}
              if counted else None)
    verdict = overall_verdict(clauses, suites)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "task": ["S09-DB", "S09-ST"],
        "acceptance": "AC-09",
        "acceptanceClaim": False,
        "acceptanceScope": ("measured: the S09 real-PostgreSQL set at one code SHA mapped to seven AC-09 evidence "
                            "clauses; environment-gated: RunRecord completion pipeline (Linux private storage) "
                            "is not_run where the gate skips it; UNMEASURED: AC-09 product metrics (prompt "
                            "validity, coding-task success, leak count) and real external Providers (CX-02)"),
        "codeSha": provenance.get("commit_sha"),
        "provenance": {
            **{key: provenance.get(key) for key in (
                "commit_sha", "branch", "integration_ref", "integration_sha", "integration_check_mode",
                "working_tree_clean_status", "content_clean_diff", "modified_paths", "interpreter",
                "runtime_python", "timestamp_kst", "executor", "os_platform")},
            "collectorSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "dirtyTreeAllowed": bool(provenance.get("dirtyTreeAllowed", False)),
        },
        "environment": {
            "database": "disposable PostgreSQL database per pytest session from INV_TEST_ADMIN_DSN "
                        "(DSN, host, port, password not recorded)",
            "ci": bool(os.environ.get("CI")),
            "gatesSkippedHere": sorted(gates_skipped_here(suites)),
        },
        "suites": [{k: v for k, v in suite.items() if k != "outcomes"} for suite in suites],
        "totals": totals,
        "unavailableSuites": [s["id"] for s in suites if s.get("counts") is None],
        "clauses": clauses,
        "passScope": scope,
        "passScopeNote": ("PASS_MEASURED_PARTIAL means every clause that ran passed and the only clauses that "
                          "did not run are the environment-gated ones listed in passScope.notRunEnvironmentGated; "
                          "those clauses still need a host that satisfies their gate")
        if verdict == "PASS_MEASURED_PARTIAL" else None,
        "externalWaits": [{**item, "status": "UNMEASURED", "value": None} for item in EXTERNAL_WAITS],
        "verdict": verdict,
        "note": note,
    }


def render_markdown(evidence: dict[str, Any]) -> str:
    p = evidence["provenance"]
    lines = [
        f"# S09-DB/ST AC-09 acceptance evidence — `{(evidence.get('codeSha') or 'nogit')[:12]}`",
        "",
        f"- verdict (measured part): **{evidence['verdict']}** · acceptanceClaim: `false` · totals {evidence['totals']}"
        f" · unavailable suites {evidence['unavailableSuites']}",
        f"- captured: {p.get('timestamp_kst')} · executor: {p.get('executor')} · clean tree: {p.get('working_tree_clean_status')}"
        f" · dirty allowed: {p.get('dirtyTreeAllowed')} · collector sha256 `{(p.get('collectorSha256') or '')[:16]}`",
        f"- environment gates skipped here: {evidence['environment']['gatesSkippedHere'] or 'none'}",
        "",
        "| suite | gate | status | exit | counts | elapsed s |",
        "|---|---|---|---|---|---|",
    ]
    for s in evidence["suites"]:
        lines.append(f"| {s['id']} | {s.get('gate') or '—'} | {s['status']} | {s['exitCode']} | {s.get('counts')} | {s['elapsedSeconds']} |")
    lines += ["", "| AC-09 clause | status | reason | cases |", "|---|---|---|---|"]
    for key, clause in evidence["clauses"].items():
        cases = ", ".join(f"{name.split('::')[-1]}={state}" for name, state in clause["cases"].items())
        lines.append(f"| {clause['title']} (`{key}`) | **{clause['status']}** | {clause.get('reason') or '—'} | {cases} |")
    scope = evidence["passScope"]
    lines += ["", f"- passScope: passed {scope['passed']} · not_run(environment-gated) {scope['notRunEnvironmentGated']}"
                  f" · not_run(other) {scope['notRunOther']} · failed {scope['failed']}"]
    if evidence.get("passScopeNote"):
        lines.append(f"- {evidence['passScopeNote']}")
    lines += ["", "| external wait | status | value |", "|---|---|---|"]
    for item in evidence["externalWaits"]:
        lines.append(f"| {item['id']} {item['item']} ({item['owner']}) | UNMEASURED | — |")
    if evidence.get("note"):
        lines += ["", f"- note: {evidence['note']}"]
    return "\n".join(lines) + "\n"


def redact_text(text: str) -> str:
    for pattern, placeholder in _REDACTIONS:
        text = pattern.sub(placeholder, text)
    return text


def assert_redacted(text: str) -> None:
    for pattern, placeholder in _REDACTIONS:
        if pattern.search(text):
            raise ValueError(f"evidence would embed an unredacted identifier ({placeholder})")


def assert_no_secrets(text: str) -> None:
    from psycopg.conninfo import conninfo_to_dict

    for key in ("INV_TEST_ADMIN_DSN", "INV_AUDIT_DSN", "INV_DATABASE_URL", "INV_TEST_DATABASE_URL"):
        dsn = os.environ.get(key)
        if not dsn:
            continue
        if dsn in text:
            raise ValueError(f"evidence would embed {key}")
        try:
            password = conninfo_to_dict(dsn).get("password")
        except Exception:
            password = None
        if not password:
            match = re.search(r"://[^:/]+:([^@]+)@", dsn)
            password = match.group(1) if match else None
        if password and password in text:
            raise ValueError(f"evidence would embed the password of {key}")


def write_evidence(evidence: dict[str, Any], out_dir: Path, label: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    md_text = render_markdown(evidence)
    for text in (json_text, md_text):
        assert_no_secrets(text)
        assert_redacted(text)
    json_path, md_path = out_dir / f"{label}.json", out_dir / f"{label}.md"
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    return json_path, md_path


def existing_outputs(out_dir: Path, label: str) -> list[Path]:
    """Outputs that already exist for this label; they are never deleted or overwritten."""
    return [out_dir / f"{label}{suffix}" for suffix in (".json", ".md") if (out_dir / f"{label}{suffix}").exists()]


def collect_provenance_at_repo_root(executor: str | None) -> dict[str, Any]:
    """Provenance must describe the repository, not whatever cwd the caller happened to use."""
    previous = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        return collect_provenance(executor=executor)
    finally:
        os.chdir(previous)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    result.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    result.add_argument("--label", default=None,
                        help="file stem (default: s09-acceptance-<sha12>-<UTC %%Y%%m%%dT%%H%%M%%SZ>)")
    result.add_argument("--executor", default=os.environ.get("INV_S09_EXECUTOR") or "Claude")
    result.add_argument("--note", default=None)
    result.add_argument("--junit-dir", type=Path, default=REPO_ROOT / ".work" / "s09-acceptance")
    result.add_argument("--allow-dirty-tree", action="store_true",
                        help="explicit opt-out: run on a dirty working tree (recorded in provenance); "
                             "by default a dirty tree is refused because the evidence would not be reachable")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    provenance = collect_provenance_at_repo_root(args.executor)
    provenance["dirtyTreeAllowed"] = bool(args.allow_dirty_tree)
    sha12 = (provenance.get("commit_sha") or "nogit")[:12]
    label = args.label or f"s09-acceptance-{sha12}-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}"
    if existing := existing_outputs(args.out_dir, label):
        print(f"refusing to overwrite existing evidence: {[p.name for p in existing]}", file=sys.stderr)
        return 2
    if not provenance.get("working_tree_clean_status") and not args.allow_dirty_tree:
        print("working tree is not clean; evidence must come from a committed, reachable head "
              "(pass --allow-dirty-tree to record an explicit opt-out)", file=sys.stderr)
        return 2
    if not os.environ.get("INV_TEST_ADMIN_DSN"):
        print("INV_TEST_ADMIN_DSN is required (disposable PostgreSQL); nothing measured", file=sys.stderr)
        return 2
    note = redact_text(args.note) if args.note else None
    suites = [run_suite(spec, args.junit_dir / label) for spec in SUITES]
    evidence = build_evidence(provenance=provenance, suites=suites, note=note)
    try:
        json_path, md_path = write_evidence(evidence, args.out_dir, label)
    except ValueError as error:
        print(f"refused to write evidence: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"verdict": evidence["verdict"], "totals": evidence["totals"],
                      "clauses": {k: v["status"] for k, v in evidence["clauses"].items()},
                      "passScope": evidence["passScope"],
                      "json": evidence_ref(json_path), "markdown": evidence_ref(md_path)}, ensure_ascii=False))
    return EXIT_BY_VERDICT[evidence["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
