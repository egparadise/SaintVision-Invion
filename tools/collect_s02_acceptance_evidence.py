"""S02-DB AC-02 acceptance evidence collector (API <-> PostgreSQL auth/isolation).

Runs, at one fixed code SHA and in one invocation, the existing evidence that the
S02-DB review package maps to AC-02 and bundles it into a redacted JSON/Markdown
pair:

* ``tests/test_api.py`` (TestClient -> API -> real PostgreSQL) for the four AC-02
  clauses: allowed Node registration/readback, bootstrap token replay blocking,
  cross-tenant/project isolation, and denial recording;
* ``tools/collect_rls_evidence.py --disposable`` for the row-level-security
  boundary of every measured database role.

Nothing here re-implements a check.  The clause table below is the card-5 review
package's "AC-02 clause <-> evidence" table; the tests are reused unchanged, and a
PG-free test asserts every listed case still exists in ``tests/test_api.py``.

Honesty rules baked into the output:

* a clause is ``pass`` only if every mapped case passed in THIS run; a skipped or
  missing case makes the clause ``not_run`` (never ``pass``);
* items that need user inputs U2..U5 (real IdP issuer/JWKS, CA, DNS, physical
  Node mTLS/heartbeat) are always ``UNMEASURED`` and carry no numbers;
* ``acceptanceClaim`` is always ``false``: this bundle feeds the S02-DB review, it
  does not close AC-02;
* the verdict is fail-closed on the WHOLE API suite: any failed/error case in
  ``tests/test_api.py`` (mapped or not), a non-zero pytest exit, or a suite status
  other than ``complete`` makes the bundle FAIL (or UNAVAILABLE when nothing ran);
* redaction contract (checked before every write, violations refuse the write):
  - DSN values and their passwords from ``INV_TEST_ADMIN_DSN`` / ``INV_AUDIT_DSN`` /
    ``INV_DATABASE_URL`` / ``INV_TEST_DATABASE_URL`` are never written;
  - ephemeral identifiers are replaced by placeholders in every produced file,
    including the RLS collector's JSON/Markdown: disposable database names
    (``inv_rls_<hex>``, ``inv_backend_test_<hex>``), UUIDs (tenant ids, GUC probe
    values), and ``IPv4:port`` pairs;
  - ``--note`` is free text: it passes through the same placeholder redaction and
    the same DSN/password refusal, nothing else in it is inspected;
  - pytest failure messages are never kept (only parameter-free case ids and counts).

Exit codes: 0 measured clauses and RLS all pass; 1 a measured clause or any API
case failed, or the RLS collector found violations; 2 observation unavailable (no
DSN, pytest could not run); 3 nothing measured / UNMEASURED only.
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

SCHEMA_VERSION = "s02-db-acceptance-evidence:1"
API_SUITE = "tests/test_api.py"
API_CLASSNAME = "tests.test_api"
DEFAULT_OUT_DIR = REPO_ROOT / "docs/vault/30_Development/Evidence/s02-db-acceptance"

# Card-5 review package, table A-1 (AC-02 clause <-> evidence), reused verbatim.
AC02_CLAUSES: dict[str, dict[str, Any]] = {
    "allowed-node-registration-and-read": {
        "title": "허용 Node 등록·조회 성공",
        "cases": [
            "test_enrolled_node_is_registered_and_readable",
            "test_node_enrollment_db_route_rejects_invalid_response_shape",
            "test_heartbeat_advances_and_replays_are_ignored",
            "test_heartbeat_observations_land_in_the_right_partition",
        ],
    },
    "bootstrap-token-replay-blocked": {
        "title": "토큰 재사용 차단",
        "cases": [
            "test_bootstrap_token_cannot_be_used_twice",
            "test_unknown_bootstrap_token_is_rejected",
            "test_missing_credential_is_refused",
            "test_unknown_credential_is_refused",
        ],
    },
    "cross-tenant-project-isolation": {
        "title": "다른 project/tenant 정보 접근 차단",
        "cases": [
            "test_another_tenants_node_is_not_listed",
            "test_another_tenants_node_is_not_readable_by_id",
            "test_project_scope_is_checked_separately_from_tenancy",
            "test_another_tenant_cannot_see_the_contribution",
            "test_a_tokens_tenant_is_binding",
            "test_a_heartbeat_for_a_node_you_are_not_is_refused",
            "test_liveness_sweep_does_not_cross_tenants",
        ],
    },
    "denial-recorded": {
        "title": "인증 실패 기록",
        "cases": ["test_denials_are_recorded"],
    },
}

# User inputs the S02 checklist still owes; values are never recorded here.
EXTERNAL_WAITS: list[dict[str, str]] = [
    {"id": "U2", "item": "실 IdP(OIDC issuer/JWKS) 경유 로그인", "owner": "user decision; S02-BE"},
    {"id": "U3", "item": "실 CA 발급 Node 인증서", "owner": "user; S01-BE"},
    {"id": "U4", "item": "DNS/endpoint 확정", "owner": "user; S01-BE"},
    {"id": "U5", "item": "물리 Node mTLS/heartbeat 실장비", "owner": "user hardware; S02-BE"},
]

RLS_EXIT_VERDICT = {0: "PASS", 1: "VIOLATIONS", 2: "UNAVAILABLE", 3: "UNMEASURED"}
_SAFE_NAME = re.compile(r"[A-Za-z0-9_]+")
_SAFE_CLASS = re.compile(r"[A-Za-z0-9_.]+")


def safe_case_id(case: ET.Element) -> str | None:
    """classname::name without parameter values; None when it cannot be made safe."""
    classname = case.get("classname") or ""
    name = (case.get("name") or "").split("[", 1)[0]
    if not _SAFE_CLASS.fullmatch(classname) or not _SAFE_NAME.fullmatch(name):
        return None
    return f"{classname}::{name}"


def parse_junit(raw: bytes) -> dict[str, Any]:
    """Counts plus per-case outcome keyed by safe id.  Failure text is never kept."""
    root = ET.fromstring(raw)
    if root.tag not in ("testsuites", "testsuite"):
        raise ValueError("not JUnit")
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
        if case_id is not None:
            outcomes[case_id] = outcome
    return {"counts": counts, "outcomes": outcomes}


def clause_status(outcomes: dict[str, str], cases: list[str]) -> dict[str, Any]:
    """pass only when every mapped case passed in this run."""
    per_case = {}
    for name in cases:
        per_case[name] = outcomes.get(f"{API_CLASSNAME}::{name}", "missing")
    values = set(per_case.values())
    if values == {"passed"}:
        status = "pass"
    elif values & {"failed", "error"}:
        status = "fail"
    else:
        status = "not_run"
    return {"status": status, "cases": per_case}


def evaluate_clauses(outcomes: dict[str, str]) -> dict[str, Any]:
    return {
        key: {"title": spec["title"], **clause_status(outcomes, spec["cases"])}
        for key, spec in AC02_CLAUSES.items()
    }


def run_api_suite(junit_path: Path, *, python: str = sys.executable) -> dict[str, Any]:
    """Run tests/test_api.py once with JUnit output; credentials stay in the env."""
    junit_path.parent.mkdir(parents=True, exist_ok=True)
    junit_path.unlink(missing_ok=True)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    python_paths = [str(REPO_ROOT / "src"), str(REPO_ROOT / "services" / "control-plane" / "src")]
    if env.get("PYTHONPATH"):
        python_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    command = [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rs", API_SUITE,
               f"--junitxml={junit_path}"]
    started = dt.datetime.now(dt.timezone.utc)
    completed = subprocess.run(command, cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    elapsed = (dt.datetime.now(dt.timezone.utc) - started).total_seconds()
    result: dict[str, Any] = {
        "suite": API_SUITE,
        "command": "pytest -q -p no:cacheprovider -rs tests/test_api.py --junitxml=<junit>",
        "exitCode": completed.returncode,
        "elapsedSeconds": round(elapsed, 3),
        "junitSha256": None,
        "counts": None,
        "outcomes": {},
        "status": "unavailable",
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
    result["counts"] = parsed["counts"]
    result["outcomes"] = parsed["outcomes"]
    executed = parsed["counts"]["passed"] + parsed["counts"]["failed"] + parsed["counts"]["error"]
    if executed == 0:
        result["status"] = "not_run"
    elif completed.returncode == 0 and not (parsed["counts"]["failed"] or parsed["counts"]["error"]):
        result["status"] = "complete"
    else:
        result["status"] = "failed"
    return result


def run_rls_collector(out_dir: Path, label: str) -> dict[str, Any]:
    """Run the existing RLS boundary collector against a disposable database."""
    from tools import collect_rls_evidence as rls

    if not os.environ.get("INV_TEST_ADMIN_DSN"):
        return {"status": "unavailable", "verdict": "UNAVAILABLE", "reason": "INV_TEST_ADMIN_DSN is absent"}
    out_dir.mkdir(parents=True, exist_ok=True)
    code = rls.main(["--disposable", "--out-dir", str(out_dir), "--label", label])
    verdict = RLS_EXIT_VERDICT.get(code, "UNAVAILABLE")
    summary: dict[str, Any] = {"status": "complete" if code in (0, 1, 3) else "unavailable",
                               "verdict": verdict, "exitCode": code,
                               "evidenceJson": (out_dir / f"{label}.json").relative_to(REPO_ROOT).as_posix()
                               if (out_dir / f"{label}.json").is_file() else None}
    json_path = out_dir / f"{label}.json"
    if json_path.is_file():
        summary["rawJsonSha256"] = hashlib.sha256(json_path.read_bytes()).hexdigest()
        summary.update(redact_rls_artifacts(out_dir, label))  # placeholders for DB name/UUID/host:port
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        summary["roles"] = sorted(payload.get("roles", {}).keys())
        summary["violations"] = len(payload.get("violations", []))
        summary["accepted"] = len(payload.get("accepted", []))
        summary["unmeasured"] = len(payload.get("unmeasured", []))
        summary["collectorSha256"] = (payload.get("provenance") or {}).get("collector_sha256")
        summary["baselineSha256"] = (payload.get("provenance") or {}).get("baseline_sha256")
    return summary


def overall_verdict(clauses: dict[str, Any], api: dict[str, Any], rls: dict[str, Any]) -> str:
    statuses = {c["status"] for c in clauses.values()}
    if api["status"] in ("unavailable", "invalid-junit") or rls["status"] == "unavailable":
        return "UNAVAILABLE"
    counts = api.get("counts") or {}
    # Fail closed on the whole API suite: an unmapped failure, a non-zero pytest
    # exit or an incomplete suite status must never leave the bundle PASS.
    api_failed = (
        api["status"] != "complete"
        or api.get("exitCode") != 0
        or counts.get("failed", 0) > 0
        or counts.get("error", 0) > 0
    )
    if api_failed and api["status"] == "not_run" and not (counts.get("failed") or counts.get("error")):
        return "NOT_RUN"
    if "fail" in statuses or rls["verdict"] == "VIOLATIONS" or api_failed:
        return "FAIL"
    if statuses == {"pass"} and rls["verdict"] == "PASS":
        return "PASS"
    return "NOT_RUN"


EXIT_BY_VERDICT = {"PASS": 0, "FAIL": 1, "UNAVAILABLE": 2, "NOT_RUN": 3}


def build_evidence(*, provenance: dict[str, Any], api: dict[str, Any], rls: dict[str, Any],
                   note: str | None = None) -> dict[str, Any]:
    clauses = evaluate_clauses(api.get("outcomes") or {})
    verdict = overall_verdict(clauses, api, rls)
    api_public = {k: v for k, v in api.items() if k != "outcomes"}
    return {
        "schemaVersion": SCHEMA_VERSION,
        "task": "S02-DB",
        "acceptance": "AC-02",
        "acceptanceClaim": False,
        "acceptanceScope": ("measured: API<->PostgreSQL clauses and RLS boundary at one code SHA; "
                            "UNMEASURED: real IdP/CA/DNS/physical Node (U2..U5); browser acceptance "
                            "belongs to the browser lane"),
        "codeSha": provenance.get("commit_sha"),
        "provenance": {
            **{
                key: provenance.get(key)
                for key in ("commit_sha", "branch", "integration_ref", "integration_sha",
                            "integration_check_mode", "working_tree_clean_status",
                            "content_clean_diff", "modified_paths", "interpreter",
                            "runtime_python", "timestamp_kst", "executor", "os_platform")
            },
            # The content hash identifies the collector that ran even when it was
            # still uncommitted (working_tree_clean_status false) at run time.
            "collectorSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "environment": {
            "database": "disposable PostgreSQL database per pytest session / per collector run, "
                        "created from INV_TEST_ADMIN_DSN (DSN, host, port and password not recorded)",
            "ci": bool(os.environ.get("CI")),
        },
        "apiSuite": api_public,
        "clauses": clauses,
        "rlsBoundary": rls,
        "externalWaits": [{**item, "status": "UNMEASURED", "value": None} for item in EXTERNAL_WAITS],
        "browserAcceptance": {"status": "not_in_scope", "lane": "browser (Gemini/Codex)"},
        "verdict": verdict,
        "note": note,
    }


def render_markdown(evidence: dict[str, Any]) -> str:
    lines = [
        f"# S02-DB AC-02 acceptance evidence — `{(evidence.get('codeSha') or 'nogit')[:12]}`",
        "",
        f"- verdict (measured part): **{evidence['verdict']}** · acceptanceClaim: `false`",
        f"- captured: {evidence['provenance'].get('timestamp_kst')} · executor: {evidence['provenance'].get('executor')}"
        f" · clean tree: {evidence['provenance'].get('working_tree_clean_status')}",
        f"- API suite `{evidence['apiSuite']['suite']}`: status `{evidence['apiSuite']['status']}`,"
        f" exit {evidence['apiSuite']['exitCode']}, counts {evidence['apiSuite'].get('counts')},"
        f" junit sha256 `{(evidence['apiSuite'].get('junitSha256') or '')[:16]}`",
        "",
        "| AC-02 clause | status | cases |",
        "|---|---|---|",
    ]
    for key, clause in evidence["clauses"].items():
        cases = ", ".join(f"{name}={state}" for name, state in clause["cases"].items())
        lines.append(f"| {clause['title']} (`{key}`) | **{clause['status']}** | {cases} |")
    rls = evidence["rlsBoundary"]
    lines += [
        "",
        f"- RLS boundary: **{rls.get('verdict')}** (exit {rls.get('exitCode')}), roles {rls.get('roles')},"
        f" violations {rls.get('violations')}, accepted {rls.get('accepted')}, unmeasured {rls.get('unmeasured')}"
        f" → `{rls.get('evidenceJson')}`",
        "",
        "| external wait | status | value |",
        "|---|---|---|",
    ]
    for item in evidence["externalWaits"]:
        lines.append(f"| {item['id']} {item['item']} ({item['owner']}) | UNMEASURED | — |")
    lines += ["", f"- browser acceptance: `{evidence['browserAcceptance']['status']}`"
                  f" ({evidence['browserAcceptance']['lane']})"]
    if evidence.get("note"):
        lines += ["", f"- note: {evidence['note']}"]
    return "\n".join(lines) + "\n"


_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\binv_rls_[0-9a-f]{32}\b"), "inv_rls_<redacted>"),
    (re.compile(r"\binv_backend_test_[0-9a-f]{32}\b"), "inv_backend_test_<redacted>"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
     "<uuid:redacted>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b"), "<host:port:redacted>"),
]


def redact_text(text: str) -> str:
    """Replace ephemeral identifiers (disposable DB names, UUIDs, IPv4:port) by placeholders."""
    for pattern, placeholder in _REDACTIONS:
        text = pattern.sub(placeholder, text)
    return text


def assert_redacted(text: str) -> None:
    """Refuse to write evidence that still carries an ephemeral identifier."""
    for pattern, placeholder in _REDACTIONS:
        if pattern.search(text):
            raise ValueError(f"evidence would embed an unredacted identifier ({placeholder})")


def redact_rls_artifacts(out_dir: Path, label: str) -> dict[str, Any]:
    """Rewrite the RLS collector's JSON/Markdown in place with placeholders; JSON stays valid."""
    result: dict[str, Any] = {"redacted": False}
    json_path, md_path = out_dir / f"{label}.json", out_dir / f"{label}.md"
    if json_path.is_file():
        redacted = redact_text(json_path.read_text(encoding="utf-8"))
        json.loads(redacted)  # placeholders never break the document
        assert_redacted(redacted)
        json_path.write_text(redacted, encoding="utf-8")
        result["redacted"] = True
        result["jsonSha256"] = hashlib.sha256(json_path.read_bytes()).hexdigest()
    if md_path.is_file():
        redacted = redact_text(md_path.read_text(encoding="utf-8"))
        assert_redacted(redacted)
        md_path.write_text(redacted, encoding="utf-8")
        result["redacted"] = True
    return result


def assert_no_secrets(text: str) -> None:
    """Refuse to write evidence that embeds a DSN or a password from the environment."""
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
            try:
                password = re.search(r"://[^:/]+:([^@]+)@", dsn).group(1)  # type: ignore[union-attr]
            except Exception:
                password = None
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


def remove_stale_outputs(out_dir: Path, label: str) -> None:
    """A failed rerun must never leave an earlier green bundle looking current."""
    for suffix in (".json", ".md"):
        (out_dir / f"{label}{suffix}").unlink(missing_ok=True)
    (out_dir / f"{label}-rls.json").unlink(missing_ok=True)
    (out_dir / f"{label}-rls.md").unlink(missing_ok=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    result.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    result.add_argument("--label", default=None, help="file stem (default: s02-acceptance-<sha12>-<utc date>)")
    result.add_argument("--executor", default=os.environ.get("INV_S02_EXECUTOR") or "Claude")
    result.add_argument("--note", default=None, help="free-text run condition recorded in the evidence")
    result.add_argument("--junit-dir", type=Path, default=REPO_ROOT / ".work" / "s02-acceptance",
                        help="private directory for the raw JUnit (never committed)")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    provenance = collect_provenance(executor=args.executor)
    sha12 = (provenance.get("commit_sha") or "nogit")[:12]
    label = args.label or f"s02-acceptance-{sha12}-{dt.datetime.now(dt.timezone.utc):%Y%m%d}"
    out_dir = args.out_dir
    remove_stale_outputs(out_dir, label)
    if not os.environ.get("INV_TEST_ADMIN_DSN"):
        print("INV_TEST_ADMIN_DSN is required (disposable PostgreSQL); nothing measured", file=sys.stderr)
        return 2
    api = run_api_suite(args.junit_dir / f"{label}-api.xml")
    rls = run_rls_collector(out_dir, f"{label}-rls")
    note = redact_text(args.note) if args.note else None  # free text: placeholders only, see docstring
    evidence = build_evidence(provenance=provenance, api=api, rls=rls, note=note)
    try:
        json_path, md_path = write_evidence(evidence, out_dir, label)
    except ValueError as error:
        print(f"refused to write evidence: {error}", file=sys.stderr)
        return 2
    print(json.dumps({
        "verdict": evidence["verdict"],
        "clauses": {k: v["status"] for k, v in evidence["clauses"].items()},
        "rls": rls.get("verdict"),
        "json": str(json_path),
        "markdown": str(md_path),
    }, ensure_ascii=False))
    return EXIT_BY_VERDICT[evidence["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
