"""S10-DB / S10-ST AC-10 acceptance evidence collector (model lineage and immutability).

At one fixed, committed code SHA and in one invocation this collector re-runs the
existing S10 real-PostgreSQL set (one pytest process per file, memory rule) and maps
its cases to five AC-10 clauses:

* lineage traceability (dataset / commit / image / eval / approval trace-back);
* model version append-only (no update/delete, no shared content);
* retention pin and release gate (pin only extends; release needs verify + pin + trace);
* deployment digest and approval (digest comes from the released version; approval
  is for that exact content; one active deployment);
* tenant isolation of lineage and versions.

Rules applied from the start (Codex review of the S02 collector, PR #120):

* fail-closed on every suite: any failed/error case (mapped or not), a non-zero
  pytest exit or a suite status other than ``complete`` makes the bundle FAIL; a
  clause is ``pass`` only if every mapped case passed in THIS run, skipped or
  missing cases make it ``not_run``;
* provenance from ``tools.provenance.collect`` computed with the repository root
  as cwd (commit SHA, branch, integration distance, clean-tree flags) plus this
  collector's own content hash; a dirty working tree is refused by default
  (``--allow-dirty-tree`` is an explicit, recorded opt-out); the output label carries
  the SHA and a UTC timestamp, and an existing output with the same label is refused
  rather than deleted or overwritten;
* redaction contract (checked before every write, violations refuse the write):
  DSN values and passwords from ``INV_TEST_ADMIN_DSN`` / ``INV_AUDIT_DSN`` /
  ``INV_DATABASE_URL`` / ``INV_TEST_DATABASE_URL`` are refused; disposable database
  names (``inv_backend_test_``/``inv_rls_``/``inv_s03_`` + hex), UUIDs, every
  ``<prefix>_<26-char Crockford ULID>`` entity id regardless of prefix (the real S10
  prefixes from ``saintvision.ids.PREFIXES`` are ``dst``/``dsv``/``cmt``/``img``/``mdl``/
  ``mdv``/``dpl`` plus ``apv``/``usr``/``wsp``/``wkl``/``evs``/``evr`` and the kernel
  ``run``/``evd``/``nod``/``prj``/``res``/``lse``) and ``IPv4:port`` are replaced by
  placeholders in every produced file; ``--note`` passes through the same
  replacement; pytest failure messages are never kept (parameter-free case ids and
  counts only).  This bundle is internal evidence, not a public artifact.

External waits carry no numbers: real external Provider execution/cancel/collect/
attest (CX-02 credential boundary, S10-BE) and a real MLflow connection are
``UNMEASURED``.  ``acceptanceClaim`` is always ``false``.

Exit codes: 0 PASS; 1 FAIL; 2 UNAVAILABLE (no DSN or a suite could not run);
3 NOT_RUN (nothing executed / a mapped case skipped).
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

SCHEMA_VERSION = "s10-db-acceptance-evidence:1"
DEFAULT_OUT_DIR = REPO_ROOT / "docs/vault/30_Development/Evidence/s10-db-acceptance"

# One pytest process per entry (memory rule); the PG-free core files share one process.
SUITES: list[dict[str, Any]] = [
    {"id": "lineage", "postgres": True, "paths": ["tests/test_lineage.py"]},
    {"id": "model-registry", "postgres": True, "paths": ["tests/test_model_registry.py"]},
    {"id": "deployment-guard", "postgres": True, "paths": ["tests/test_deployment_guard.py"]},
    {"id": "model-commit", "postgres": True, "paths": ["tests/integration/test_model_commit.py"]},
    {"id": "model-registry-binding", "postgres": True, "paths": ["tests/integration/test_model_registry_binding.py"]},
    {"id": "model-registry-revalidation", "postgres": True,
     "paths": ["tests/integration/test_model_registry_revalidation.py"]},
    {"id": "model-locality", "postgres": True, "paths": ["tests/integration/test_model_locality.py"]},
    {"id": "model-view", "postgres": True, "paths": ["tests/integration/test_model_view.py"]},
    {"id": "model-runtime", "postgres": True, "paths": ["tests/integration/test_model_runtime.py"]},
    {"id": "model-retry", "postgres": True, "paths": ["tests/integration/test_model_retry.py"]},
    {"id": "model-license-readthrough", "postgres": True,
     "paths": ["tests/integration/test_model_license_readthrough.py"]},
    {"id": "pgfree-model-core", "postgres": False,
     "paths": ["tests/core/test_model_manifest.py", "tests/core/test_model_execution_registry.py",
               "tests/core/test_model_remote.py"]},
]

AC10_CLAUSES: dict[str, dict[str, Any]] = {
    "lineage-traceability": {
        "title": "모델 계보 역추적(데이터·코드·평가·승인)",
        "cases": [
            "tests.test_lineage::test_a_fully_linked_model_traces_back_to_everything",
            "tests.test_lineage::test_the_traceback_names_what_is_missing",
            "tests.test_lineage::test_an_edge_whose_subject_vanished_is_reported_as_dangling",
            "tests.test_lineage::test_recording_the_same_edge_twice_is_idempotent",
            "tests.test_lineage::test_an_untraceable_model_cannot_be_released",
            "tests.test_model_registry::test_record_lineage_rejects_unknown_kinds_and_is_idempotent",
            "tests.test_model_registry::test_trace_reports_missing_required_kinds_and_shrinks_as_they_are_recorded",
            "tests.test_model_registry::test_release_succeeds_when_verified_pinned_and_fully_traceable",
        ],
    },
    "model-version-append-only": {
        "title": "모델 버전 append-only·content 유일",
        "cases": [
            "tests.test_lineage::test_two_model_versions_cannot_share_content",
            "tests.test_lineage::test_model_versions_are_append_only_for_the_application",
            "tests.test_lineage::test_the_database_refuses_a_tag_shaped_digest",
            "tests.test_lineage::test_an_image_is_its_digest_not_its_tag",
            "tests.test_model_registry::test_identical_weights_under_two_names_is_refused",
            "tests.test_model_registry::test_registering_requires_a_hex_sha256_and_an_existing_model",
        ],
    },
    "retention-pin-and-release-gate": {
        "title": "보존 pin(연장만)·release gate(verify+pin+trace)",
        "cases": [
            "tests.test_lineage::test_a_retention_pin_only_extends",
            "tests.test_lineage::test_release_requires_verification_pin_and_traceability",
            "tests.test_lineage::test_verification_refuses_a_mismatched_checksum",
            "tests.test_lineage::test_the_database_refuses_a_release_without_verification",
            "tests.test_model_registry::test_a_retention_pin_only_extends",
            "tests.test_model_registry::test_release_is_refused_until_verified_then_pinned_then_traceable",
            "tests.test_model_registry::test_the_database_refuses_released_without_verification_and_pin",
            "tests.test_model_registry::test_verify_sets_the_timestamp_and_rejects_a_mismatch",
        ],
    },
    "deployment-digest-and-approval": {
        "title": "배포 digest는 버전에서·정확 content 승인·활성 배포 1",
        "cases": [
            "tests.test_lineage::test_a_deployment_pins_the_digest_that_shipped",
            "tests.test_lineage::test_an_approval_for_other_content_cannot_deploy",
            "tests.test_lineage::test_an_unreleased_version_cannot_be_deployed",
            "tests.test_lineage::test_redeploying_supersedes_the_previous_active_one",
            "tests.test_lineage::test_the_database_refuses_two_active_deployments",
            "tests.test_lineage::test_a_deployment_without_an_approval_is_refused",
            "tests.test_model_registry::test_deploying_a_released_version_pins_the_shipped_digest_and_supersedes",
            "tests.test_model_registry::test_a_draft_version_cannot_be_deployed",
            "tests.test_deployment_guard::test_approval_time_and_cached_revocation_are_checked",
            "tests.test_deployment_guard::test_concurrent_first_deployments_leave_one_active_record",
            "tests.test_deployment_guard::test_cached_released_stage_cannot_override_current_draft",
            "tests.test_deployment_guard::test_database_rejects_duplicate_active_and_service_supersedes",
        ],
    },
    "tenant-isolation": {
        "title": "계보·버전 tenant 격리",
        "cases": [
            "tests.test_lineage::test_lineage_is_tenant_isolated",
            "tests.test_model_registry::test_a_non_owner_scoped_to_one_tenant_cannot_see_another_tenants_version",
        ],
    },
}

EXTERNAL_WAITS: list[dict[str, str]] = [
    {"id": "CX-02", "item": "실제 두 외부 Provider 실행/취소/collect/attest", "owner": "credential boundary; S10-BE"},
    {"id": "MLflow", "item": "실 MLflow 접속·등록", "owner": "S10-BE"},
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
        status = "pass"
    elif values & {"failed", "error"}:
        status = "fail"
    else:
        status = "not_run"
    return {"status": status, "cases": per_case}


def evaluate_clauses(outcomes: dict[str, str]) -> dict[str, Any]:
    return {key: {"title": spec["title"], **clause_status(outcomes, spec["cases"])}
            for key, spec in AC10_CLAUSES.items()}


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
                              "exitCode": completed.returncode, "elapsedSeconds": round(elapsed, 3),
                              "junitSha256": None, "counts": None, "outcomes": {}, "status": "unavailable"}
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
    statuses = {c["status"] for c in clauses.values()}
    if "fail" in statuses:
        return "FAIL"
    if any(s["status"] in ("unavailable", "invalid-junit") for s in suites):
        return "UNAVAILABLE"
    if statuses == {"pass"} and all(s["status"] == "complete" for s in suites):
        return "PASS"
    return "NOT_RUN"


EXIT_BY_VERDICT = {"PASS": 0, "FAIL": 1, "UNAVAILABLE": 2, "NOT_RUN": 3}


def build_evidence(*, provenance: dict[str, Any], suites: list[dict[str, Any]],
                   note: str | None = None) -> dict[str, Any]:
    outcomes: dict[str, str] = {}
    for suite in suites:
        outcomes.update(suite.get("outcomes") or {})
    clauses = evaluate_clauses(outcomes)
    totals = {k: sum((s.get("counts") or {}).get(k, 0) for s in suites) for k in ("passed", "failed", "error", "skipped")}
    return {
        "schemaVersion": SCHEMA_VERSION,
        "task": ["S10-DB", "S10-ST"],
        "acceptance": "AC-10",
        "acceptanceClaim": False,
        "acceptanceScope": ("measured: the S10 real-PostgreSQL set at one code SHA mapped to five AC-10 clauses; "
                            "UNMEASURED: real external Providers (CX-02) and MLflow"),
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
        },
        "suites": [{k: v for k, v in suite.items() if k != "outcomes"} for suite in suites],
        "totals": totals,
        "clauses": clauses,
        "externalWaits": [{**item, "status": "UNMEASURED", "value": None} for item in EXTERNAL_WAITS],
        "verdict": overall_verdict(clauses, suites),
        "note": note,
    }


def render_markdown(evidence: dict[str, Any]) -> str:
    p = evidence["provenance"]
    lines = [
        f"# S10-DB/ST AC-10 acceptance evidence — `{(evidence.get('codeSha') or 'nogit')[:12]}`",
        "",
        f"- verdict (measured part): **{evidence['verdict']}** · acceptanceClaim: `false` · totals {evidence['totals']}",
        f"- captured: {p.get('timestamp_kst')} · executor: {p.get('executor')} · clean tree: {p.get('working_tree_clean_status')}"
        f" · collector sha256 `{(p.get('collectorSha256') or '')[:16]}`",
        "",
        "| suite | postgres | status | exit | counts | elapsed s |",
        "|---|---|---|---|---|---|",
    ]
    for s in evidence["suites"]:
        lines.append(f"| {s['id']} | {s['postgres']} | {s['status']} | {s['exitCode']} | {s.get('counts')} | {s['elapsedSeconds']} |")
    lines += ["", "| AC-10 clause | status | cases |", "|---|---|---|"]
    for key, clause in evidence["clauses"].items():
        cases = ", ".join(f"{name.split('::')[-1]}={state}" for name, state in clause["cases"].items())
        lines.append(f"| {clause['title']} (`{key}`) | **{clause['status']}** | {cases} |")
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
    result.add_argument("--label", default=None, help="file stem (default: s10-acceptance-<sha12>-<utc date>)")
    result.add_argument("--executor", default=os.environ.get("INV_S10_EXECUTOR") or "Claude")
    result.add_argument("--note", default=None)
    result.add_argument("--junit-dir", type=Path, default=REPO_ROOT / ".work" / "s10-acceptance")
    result.add_argument("--allow-dirty-tree", action="store_true",
                        help="explicit opt-out: run on a dirty working tree (recorded in provenance); "
                             "by default a dirty tree is refused because the evidence would not be reachable")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    provenance = collect_provenance_at_repo_root(args.executor)
    provenance["dirtyTreeAllowed"] = bool(args.allow_dirty_tree)
    sha12 = (provenance.get("commit_sha") or "nogit")[:12]
    label = args.label or f"s10-acceptance-{sha12}-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}"
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
                      "json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False))
    return EXIT_BY_VERDICT[evidence["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
