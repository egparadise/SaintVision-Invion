"""S03-DB AC-03 acceptance evidence runner (restricted execution, denial, reclaim, evidence id).

At one fixed code SHA and in one invocation this runner:

* runs the existing S03 test files that the S03-DB review package maps to AC-03,
  one file per pytest process (memory rule), each with its own JUnit report, and
  maps their cases to the four AC-03 clauses (allowed execution succeeds;
  forbidden path/command blocked; resources reclaimed after exit; evidence id and
  output hash enforced);
* runs the existing ``tools/collect_container_evidence.py`` lanes unchanged: the
  DB lane (C1..C4: lease reclaim provenance, evidence/output-hash consistency) and
  the container lane (P1..P4: byte-exact stdout/stderr with SHA-256, rootfs-write
  denial, network isolation, uid/caps) -- and copies their verdicts as measured
  or UNMEASURED exactly as the collector reported them;
* bundles everything into a redacted JSON/Markdown pair with provenance.

Honesty rules:

* a clause is ``pass`` only if every mapped case passed in THIS run; a skipped or
  missing case makes it ``not_run``;
* a lane the collector could not measure stays ``UNMEASURED`` (never pass).  On a
  host without a product run ledger the DB lane measures an empty disposable
  database and is therefore UNMEASURED; on a host without a Linux Docker socket the
  container lane is UNMEASURED.  Passing the tests alone yields
  ``PASS_MEASURED_PARTIAL``, never ``PASS``;
* the 24 integration files that need a real Linux Docker runtime are listed as
  ``not_run_here`` with no numbers;
* ``acceptanceClaim`` is always ``false``; outputs never contain a DSN, password,
  tenant id or failure text (parameter-free case ids and counts only).

Exit codes: 0 PASS / PASS_MEASURED_PARTIAL; 1 FAIL (a clause failed or a lane
reported violations); 2 UNAVAILABLE (no DSN or a suite could not run); 3 NOT_RUN.
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

SCHEMA_VERSION = "s03-db-acceptance-evidence:1"
DEFAULT_OUT_DIR = REPO_ROOT / "docs/vault/30_Development/Evidence/s03-db-acceptance"

# One pytest process per entry (memory rule).  ``select`` narrows a large file with -k.
SUITES: list[dict[str, Any]] = [
    {"id": "pgfree-state-and-sandbox", "postgres": False,
     "paths": ["tests/test_run_state.py", "tests/core/test_sandbox_contracts.py",
               "tests/core/test_workload_spec_input_anchors.py"]},
    {"id": "execution", "postgres": True, "paths": ["tests/test_execution.py"]},
    {"id": "tool-admission", "postgres": True, "paths": ["tests/integration/test_tool_admission.py"]},
    {"id": "reservation-aborts", "postgres": True, "paths": ["tests/integration/test_reservation_aborts.py"]},
    {"id": "postgres-reclaim", "postgres": True, "paths": ["tests/integration/test_postgres.py"],
     "select": "expiration_and_cancellation_do_not_release_capacity or recovery_blocks_until_stop_and_old_checkpoint_cannot_win"},
    {"id": "containment-stop", "postgres": True, "paths": ["tests/integration/test_containment.py"],
     "select": "running_kill_preempts_network_call_and_releases_only_after_real_stop"},
]

# Review package (card 5, §B-1) mapping, case ids are "<module>::<test>".
AC03_CLAUSES: dict[str, dict[str, Any]] = {
    "allowed-execution-succeeds": {
        "title": "허용 실행 성공(상태 전이·exit)",
        "cases": [
            "tests.test_execution::test_complete_run_writes_state_evidence_and_event_together",
            "tests.test_execution::test_success_is_refused_from_any_state_but_verifying",
            "tests.test_execution::test_cancel_is_idempotent",
            "tests.test_execution::test_cancelling_a_finished_run_is_refused",
            "tests.test_execution::test_a_terminal_state_without_a_reason_is_rejected",
            "tests.test_run_state::test_the_happy_path_is_walkable",
            "tests.test_run_state::test_the_approval_path_is_walkable",
            "tests.test_run_state::test_illegal_transitions_are_refused",
        ],
    },
    "forbidden-path-or-command-blocked": {
        "title": "금지 경로·명령 차단",
        "cases": [
            "tests.core.test_sandbox_contracts::test_sandbox_contract_rejects_host_access_or_isolation_downgrade",
            "tests.core.test_sandbox_contracts::test_profile_limits_block_unapproved_execution",
            "tests.core.test_sandbox_contracts::test_profile_executable_allowlist_is_canonical",
            "tests.core.test_sandbox_contracts::test_shell_metacharacters_are_literal_container_arguments",
            "tests.core.test_workload_spec_input_anchors::test_sandbox_compile_rejects_workload_before_profile_access",
            "tests.core.test_workload_spec_input_anchors::test_tool_claim_rejects_workload_after_command_before_runtime_access",
            "tests.test_execution::test_a_dataset_mount_cannot_be_writable",
            "tests.test_execution::test_output_ref_must_be_an_inv_uri",
            "tests.integration.test_tool_admission::test_forged_outbox_content_has_no_execution_effect",
            "tests.integration.test_tool_admission::test_unverified_or_incomplete_runtime_is_denied",
            "tests.integration.test_tool_admission::test_changed_execution_context_is_rejected_before_first_claim",
        ],
    },
    "resources-reclaimed-after-exit": {
        "title": "종료 후 자원 회수(lease)",
        "cases": [
            "tests.integration.test_reservation_aborts::test_cancel_before_claim_returns_reservations_without_fabricated_node_receipt",
            "tests.integration.test_reservation_aborts::test_cancel_racing_admission_never_releases_a_possible_execution",
            "tests.integration.test_reservation_aborts::test_issued_claim_still_requires_authenticated_node_proof",
            "tests.integration.test_postgres::test_expiration_and_cancellation_do_not_release_capacity",
            "tests.integration.test_postgres::test_recovery_blocks_until_stop_and_old_checkpoint_cannot_win",
            "tests.integration.test_containment::test_running_kill_preempts_network_call_and_releases_only_after_real_stop",
        ],
        "lane_rules": ["C1", "C4"],
    },
    "evidence-id-and-output-hash-enforced": {
        "title": "Evidence ID·출력 hash 강제",
        "cases": [
            "tests.test_execution::test_the_database_refuses_a_success_without_evidence",
            "tests.test_execution::test_a_failure_after_evidence_rolls_the_evidence_back_too",
            "tests.test_execution::test_evidence_is_append_only_for_the_application_role",
        ],
        "lane_rules": ["C2", "C3"],
    },
}

LINUX_DOCKER_ONLY = [
    "tests/integration/test_node_runtime.py", "tests/integration/test_dispatch_node.py",
    "tests/integration/test_node_delivery.py", "tests/integration/test_shard_recovery.py",
    "tests/integration/test_results.py", "tests/integration/test_workspace_*.py",
]

LANE_EXIT_VERDICT = {0: "PASS", 1: "VIOLATIONS", 2: "UNAVAILABLE", 3: "UNMEASURED"}
_SAFE_NAME = re.compile(r"[A-Za-z0-9_]+")
_SAFE_CLASS = re.compile(r"[A-Za-z0-9_.]+")


def safe_case_id(case: ET.Element) -> str | None:
    classname = case.get("classname") or ""
    name = (case.get("name") or "").split("[", 1)[0]
    if not _SAFE_CLASS.fullmatch(classname) or not _SAFE_NAME.fullmatch(name):
        return None
    return f"{classname}::{name}"


def parse_junit(raw: bytes) -> dict[str, Any]:
    """Counts plus per-case outcome (worst outcome wins for parametrized cases)."""
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
        status = "pass"
    elif values & {"failed", "error"}:
        status = "fail"
    else:
        status = "not_run"
    return {"status": status, "cases": per_case}


def evaluate_clauses(outcomes: dict[str, str], lane_violations: dict[str, int] | None = None) -> dict[str, Any]:
    result = {}
    for key, spec in AC03_CLAUSES.items():
        clause = {"title": spec["title"], **clause_status(outcomes, spec["cases"])}
        rules = spec.get("lane_rules", [])
        if rules:
            hits = {rule: (lane_violations or {}).get(rule, 0) for rule in rules}
            clause["dbLaneRules"] = hits
            if any(hits.values()) and clause["status"] != "fail":
                clause["status"] = "fail"
        result[key] = clause
    return result


def run_suite(spec: dict[str, Any], junit_dir: Path, *, python: str = sys.executable) -> dict[str, Any]:
    """One pytest process for one suite entry; JUnit is private, only counts/ids leave."""
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
    if spec.get("select"):
        command += ["-k", spec["select"]]
    started = dt.datetime.now(dt.timezone.utc)
    completed = subprocess.run(command, cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    elapsed = (dt.datetime.now(dt.timezone.utc) - started).total_seconds()
    result: dict[str, Any] = {
        "id": spec["id"], "paths": spec["paths"], "select": spec.get("select"),
        "postgres": spec["postgres"], "exitCode": completed.returncode,
        "elapsedSeconds": round(elapsed, 3), "junitSha256": None, "counts": None,
        "outcomes": {}, "status": "unavailable",
    }
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


def run_lanes(out_dir: Path, label: str, *, dsn: str | None, container_image: str | None,
              note: str | None) -> dict[str, Any]:
    """Run tools/collect_container_evidence.py unchanged and summarize its own evidence."""
    from tools import collect_container_evidence as cce

    argv = ["--out-dir", str(out_dir), "--label", label]
    if dsn:
        argv += ["--dsn", dsn]
    elif os.environ.get("INV_TEST_ADMIN_DSN"):
        argv += ["--disposable"]
    else:
        return {"status": "unavailable", "verdict": "UNAVAILABLE", "reason": "no DSN and no INV_TEST_ADMIN_DSN"}
    if container_image:
        argv += ["--container-image", container_image]
    if note:
        argv += ["--note", note]
    out_dir.mkdir(parents=True, exist_ok=True)
    code = cce.main(argv)
    summary: dict[str, Any] = {"status": "complete" if code in (0, 1, 3) else "unavailable",
                               "verdict": LANE_EXIT_VERDICT.get(code, "UNAVAILABLE"), "exitCode": code,
                               "ledgerSource": "product-dsn" if dsn else "empty-disposable-database",
                               "evidenceJson": None}
    json_path = out_dir / f"{label}.json"
    if json_path.is_file():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        db, lane = payload.get("db") or {}, payload.get("container") or {}
        violations = payload.get("violations") or []
        summary.update({
            "evidenceJson": json_path.relative_to(REPO_ROOT).as_posix(),
            "jsonSha256": hashlib.sha256(json_path.read_bytes()).hexdigest(),
            "collectorSha256": (payload.get("provenance") or {}).get("collector_sha256"),
            "db": {"measured": bool(db.get("measured")), "runs": (db.get("counts") or {}).get("runs"),
                   "leases": (db.get("counts") or {}).get("leases")},
            "container": {"measured": bool(lane.get("measured")), "probes": len(lane.get("probes") or []),
                          "reason": lane.get("reason")},
            "violationsByRule": {rule: sum(1 for v in violations if v.get("rule") == rule)
                                 for rule in sorted({v.get("rule") for v in violations})},
        })
    return summary


def overall_verdict(clauses: dict[str, Any], suites: list[dict[str, Any]], lanes: dict[str, Any]) -> str:
    statuses = {c["status"] for c in clauses.values()}
    if any(s["status"] in ("unavailable", "invalid-junit") for s in suites) or lanes["status"] == "unavailable":
        return "UNAVAILABLE"
    if "fail" in statuses or lanes.get("verdict") == "VIOLATIONS":
        return "FAIL"
    if statuses != {"pass"}:
        return "NOT_RUN"
    db_measured = (lanes.get("db") or {}).get("measured")
    container_measured = (lanes.get("container") or {}).get("measured")
    if lanes.get("verdict") == "PASS" and db_measured and container_measured:
        return "PASS"
    return "PASS_MEASURED_PARTIAL"


EXIT_BY_VERDICT = {"PASS": 0, "PASS_MEASURED_PARTIAL": 0, "FAIL": 1, "UNAVAILABLE": 2, "NOT_RUN": 3}


def build_evidence(*, provenance: dict[str, Any], suites: list[dict[str, Any]], lanes: dict[str, Any],
                   note: str | None = None) -> dict[str, Any]:
    outcomes: dict[str, str] = {}
    for suite in suites:
        outcomes.update(suite.get("outcomes") or {})
    clauses = evaluate_clauses(outcomes, lanes.get("violationsByRule"))
    verdict = overall_verdict(clauses, suites, lanes)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "task": "S03-DB",
        "acceptance": "AC-03",
        "acceptanceClaim": False,
        "acceptanceScope": ("measured: AC-03 clause tests at one code SHA plus collect_container_evidence lanes as "
                            "reported; UNMEASURED lanes and Linux-Docker-only files carry no numbers; real restricted "
                            "container execution, ToolGateway Node and product Storage output remain physical waits"),
        "codeSha": provenance.get("commit_sha"),
        "provenance": {
            **{key: provenance.get(key) for key in (
                "commit_sha", "branch", "integration_ref", "integration_sha", "integration_check_mode",
                "working_tree_clean_status", "content_clean_diff", "modified_paths", "interpreter",
                "runtime_python", "timestamp_kst", "executor", "os_platform")},
            "runnerSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "environment": {
            "database": "disposable PostgreSQL database per pytest session / per lane run from "
                        "INV_TEST_ADMIN_DSN (DSN, host, port, password not recorded)",
            "ci": bool(os.environ.get("CI")),
        },
        "suites": [{k: v for k, v in suite.items() if k != "outcomes"} for suite in suites],
        "clauses": clauses,
        "lanes": lanes,
        "linuxDockerOnly": {"status": "not_run_here", "files": LINUX_DOCKER_ONLY,
                            "reason": "Real Linux Docker runtime explicitly enabled only in isolated CI"},
        "physicalWaits": [
            {"item": "실제 Linux 제한 컨테이너 실행·ToolGateway Node", "status": "UNMEASURED", "value": None},
            {"item": "제품 Storage 실출력 bytes(RunRecord 완료 파이프라인)", "status": "UNMEASURED", "value": None},
            {"item": "S03-ST 전송 정본(결정 #5)", "status": "pending-decision", "value": None},
        ],
        "verdict": verdict,
        "note": note,
    }


def render_markdown(evidence: dict[str, Any]) -> str:
    p = evidence["provenance"]
    lines = [
        f"# S03-DB AC-03 acceptance evidence — `{(evidence.get('codeSha') or 'nogit')[:12]}`",
        "",
        f"- verdict (measured part): **{evidence['verdict']}** · acceptanceClaim: `false`",
        f"- captured: {p.get('timestamp_kst')} · executor: {p.get('executor')} · clean tree: {p.get('working_tree_clean_status')}",
        "",
        "| suite | postgres | status | exit | counts | elapsed s |",
        "|---|---|---|---|---|---|",
    ]
    for s in evidence["suites"]:
        lines.append(f"| {s['id']} | {s['postgres']} | {s['status']} | {s['exitCode']} | {s.get('counts')} | {s['elapsedSeconds']} |")
    lines += ["", "| AC-03 clause | status | cases |", "|---|---|---|"]
    for key, clause in evidence["clauses"].items():
        cases = ", ".join(f"{name.split('::')[-1]}={state}" for name, state in clause["cases"].items())
        rules = f" · lane rules {clause['dbLaneRules']}" if clause.get("dbLaneRules") else ""
        lines.append(f"| {clause['title']} (`{key}`) | **{clause['status']}** | {cases}{rules} |")
    lanes = evidence["lanes"]
    lines += ["", f"- collector lanes: **{lanes.get('verdict')}** (exit {lanes.get('exitCode')}), ledger `{lanes.get('ledgerSource')}`,"
                  f" db {lanes.get('db')}, container {lanes.get('container')}, violations {lanes.get('violationsByRule')}"
                  f" → `{lanes.get('evidenceJson')}`",
              f"- Linux-Docker-only files: `{evidence['linuxDockerOnly']['status']}` ({len(evidence['linuxDockerOnly']['files'])} entries, no numbers)",
              "", "| physical wait | status | value |", "|---|---|---|"]
    for item in evidence["physicalWaits"]:
        lines.append(f"| {item['item']} | {item['status']} | — |")
    if evidence.get("note"):
        lines += ["", f"- note: {evidence['note']}"]
    return "\n".join(lines) + "\n"


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
    assert_no_secrets(json_text)
    assert_no_secrets(md_text)
    json_path, md_path = out_dir / f"{label}.json", out_dir / f"{label}.md"
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    return json_path, md_path


def remove_stale_outputs(out_dir: Path, label: str) -> None:
    for name in (f"{label}.json", f"{label}.md", f"{label}-lanes.json", f"{label}-lanes.md"):
        (out_dir / name).unlink(missing_ok=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    result.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    result.add_argument("--label", default=None, help="file stem (default: s03-acceptance-<sha12>-<utc date>)")
    result.add_argument("--executor", default=os.environ.get("INV_S03_EXECUTOR") or "Claude")
    result.add_argument("--note", default=None)
    result.add_argument("--dsn", default=None, help="owner DSN of a database holding a PRODUCT run ledger (never recorded)")
    result.add_argument("--container-image", default=None, help="local image for the container lane (never pulled)")
    result.add_argument("--junit-dir", type=Path, default=REPO_ROOT / ".work" / "s03-acceptance")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    provenance = collect_provenance(executor=args.executor)
    sha12 = (provenance.get("commit_sha") or "nogit")[:12]
    label = args.label or f"s03-acceptance-{sha12}-{dt.datetime.now(dt.timezone.utc):%Y%m%d}"
    remove_stale_outputs(args.out_dir, label)
    if not os.environ.get("INV_TEST_ADMIN_DSN") and not args.dsn:
        print("INV_TEST_ADMIN_DSN (or --dsn) is required; nothing measured", file=sys.stderr)
        return 2
    suites = [run_suite(spec, args.junit_dir / label) for spec in SUITES]
    lanes = run_lanes(args.out_dir, f"{label}-lanes", dsn=args.dsn, container_image=args.container_image,
                      note=args.note)
    evidence = build_evidence(provenance=provenance, suites=suites, lanes=lanes, note=args.note)
    try:
        json_path, md_path = write_evidence(evidence, args.out_dir, label)
    except ValueError as error:
        print(f"refused to write evidence: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"verdict": evidence["verdict"],
                      "clauses": {k: v["status"] for k, v in evidence["clauses"].items()},
                      "lanes": lanes.get("verdict"), "json": str(json_path), "markdown": str(md_path)},
                     ensure_ascii=False))
    return EXIT_BY_VERDICT[evidence["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
