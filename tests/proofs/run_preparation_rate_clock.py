"""Fixed CI-only real-PG preparation clock proof; no arbitrary command/DSN input.

Raw logs/JUnit stay in the hosted artifact (or ignored scratch), never the vault.
The expected-red probe uses the exact original56651 function and real PG counters;
it establishes a deterministic source counterexample, not the old run's cause.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".work/preparation-rate-clock"
BASE = "56651cba697f2ab6fcd7166ca4e6ea11eac28113"
BRANCH = "refs/heads/agent/codex/fleet5-prepare-rate-clock-test-20261106"
DSN = "postgresql://invowner:ci_local_only@127.0.0.1:5432/invdev"
TEST = "tests/integration/test_build_preparations_real_pg.py"
ORIGINAL = "test_prepare_rate_limit_is_enforced_before_repeated_failed_work"
BOUNDARY = "test_prepare_rate_limit_uses_exact_minute_boundaries"


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2), encoding="utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def command_version(argv):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=20)
        return {"argv": argv, "exit": p.returncode, "version": (p.stdout + p.stderr).strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"argv": argv, "unavailable": type(error).__name__}


def provenance(mode):
    binary = os.environ.get("INV_NODE_BINARY")
    save(mode + ".json", {
        "sourceSHA": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "base": BASE, "event": os.environ.get("GITHUB_EVENT_NAME"),
        "ref": os.environ.get("GITHUB_REF"), "run": os.environ.get("GITHUB_RUN_ID"),
        "runAttempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "atUTC": dt.datetime.now(dt.timezone.utc).isoformat(),
        "python": sys.version, "platform": sys.platform,
        "go": command_version(["go", "version"]),
        "nodeBinarySHA256": sha(Path(binary).read_bytes()) if binary and Path(binary).is_file() else None,
        "syntheticImageID": os.environ.get("INV_NODE_IMAGE"),
        "scope": "fixed hosted test-owned PG and synthetic Node fixtures only",
        "wholeCore": False, "physicalAcceptance": False,
    })


def resource():
    assert sys.platform == "linux" and sys.version_info[:2] == (3, 12)
    assert os.environ.get("GITHUB_ACTIONS") == "true"
    assert os.environ.get("GITHUB_EVENT_NAME") == "push"
    assert os.environ.get("GITHUB_REF") == BRANCH and os.environ.get("CI")
    assert os.environ.get("INV_TEST_ADMIN_DSN") == DSN
    assert os.environ.get("INV_RUN_NODE_TESTS") == "1"
    assert Path(os.environ["INV_NODE_BINARY"]).is_file()
    assert os.environ["INV_NODE_IMAGE"].startswith("sha256:")
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        identity = conn.execute(
            "SELECT current_database() AS database,current_user AS role,"
            "current_setting('server_version_num') AS version"
        ).fetchone()
    assert identity["database"] == "invdev" and identity["role"] == "invowner"
    assert 160000 <= int(identity["version"]) < 170000
    save("real-pg-service-identity.json", {"identity": identity, "host": "127.0.0.1", "port": 5432,
                                         "dedicatedWorkflowService": True, "productionDSN": False})


def run_test(label, target):
    OUT.mkdir(parents=True, exist_ok=True)
    xml = OUT / (label + ".xml")
    log = OUT / (label + ".log")
    argv = [sys.executable, "-B", "-m", "pytest", target, "-q", "-s", "--junitxml=" + str(xml)]
    try:
        p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=600)
        output, code = p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired as error:
        parts = [x.decode("utf-8", errors="replace") if isinstance(x, bytes) else (x or "")
                 for x in (error.stdout, error.stderr)]
        output, code = "\n".join(parts) + "\nFIXED PROOF TIMEOUT\n", -1
    log.write_text(output, encoding="utf-8")
    cases = list(ET.fromstring(xml.read_bytes()).iter("testcase")) if xml.exists() else []
    traces = []
    for line in output.splitlines():
        if "FLEET5_RATE_WINDOW " in line:
            traces.append(json.loads(line.split("FLEET5_RATE_WINDOW ", 1)[1]))
    result = {
        "label": label, "argv": argv, "exit": code, "testcases": len(cases),
        "names": [case.get("name") for case in cases],
        "failures": sum(case.find("failure") is not None for case in cases),
        "errors": sum(case.find("error") is not None for case in cases),
        "skips": sum(case.find("skipped") is not None for case in cases),
        "deselected": "deselected" in output,
        "realWindowTraces": traces, "rawLogSHA256": sha(log.read_bytes()),
        "rawJUnitSHA256": sha(xml.read_bytes()) if xml.exists() else None,
        "rawLogJUnitForOpaqueArtifactOnly": True,
    }
    save(label + ".json", result)
    return result, output


def controls():
    resource()
    raw = subprocess.check_output(["git", "show", BASE + ":" + TEST], cwd=ROOT)
    source = raw.decode("utf-8")
    function = next(node for node in ast.parse(source).body
                    if isinstance(node, ast.FunctionDef) and node.name == ORIGINAL)
    original = ast.get_source_segment(source, function)
    results, okay = [], True
    for label, offsets, buckets, expected_exit in (
        ("original-same-window", (1, 5, 10, 15, 20, 50), {0: 5}, 0),
        ("original-forced-rollover", (1, 5, 10, 15, 20, 60), {0: 5, 60: 1}, 1),
    ):
        probe = ROOT / "tests/integration/test_fleet5_preparation_rate_original_probe.py"
        assert not probe.exists()
        body = '''import pytest
from test_build_preparations_real_pg import (
    DomainError, approval, remote, node_runtime, storage, workspace_http,
    _setup_prepared_build as base_setup, _assert_rate_rows,
)
pytestmark=pytest.mark.postgres
contexts=[]
def _setup_prepared_build(*args,**kwargs):
    kwargs['rate_offsets']=OFFSETS
    context=base_setup(*args,**kwargs)
    contexts.append(context)
    return context
@pytest.fixture(autouse=True)
def real_counter_check(workspace_http):
    yield
    assert len(contexts)==1
    context=contexts[0]
    context['service'].rate_clock.assert_observations()
    _assert_rate_rows(context,BUCKETS)
'''.replace("OFFSETS", repr(offsets)).replace("BUCKETS", repr(buckets)) + "\n" + original + "\n"
        proof_raw = body.encode("utf-8")
        probe.write_bytes(proof_raw)
        (OUT / (label + ".py.txt")).write_bytes(proof_raw)
        try:
            row, output = run_test(label, str(probe))
        finally:
            assert sha(probe.read_bytes()) == sha(proof_raw)
            probe.unlink()  # Only this exact newly created file; source retained in artifact.
        row.update({"expectedExit": expected_exit, "originalFunctionSHA256": sha(original.encode()),
                    "baseSourceRawSHA256": sha(raw), "probeRawSHA256": sha(proof_raw),
                    "historicalCICauseProven": False})
        valid = (row["exit"] == expected_exit and row["testcases"] == 1
                 and row["failures"] == expected_exit and row["errors"] == 0
                 and row["skips"] == 0 and not row["deselected"] and bool(row["realWindowTraces"]))
        if expected_exit:
            valid = valid and "('GRAPH-0003', 409, False)" in output and "('RES-0007', 429, True)" in output
        row["intendedControlOutcome"] = valid
        results.append(row)
        save("original-controls.json", results)
        okay = okay and valid
        print(json.dumps({"control": label, "valid": valid, "exit": row["exit"],
                          "failures": row["failures"], "errors": row["errors"], "skips": row["skips"]}))
    assert okay, "original real-PG controls did not reach both exact intended outcomes"


def positive():
    resource()
    row, _ = run_test("full-affected-file", TEST)
    required = {ORIGINAL, BOUNDARY}
    assert required.issubset(set(row["names"])), "required positive cases not collected/executed"
    assert (row["exit"] == 0 and row["testcases"] > 1 and row["failures"] == 0
            and row["errors"] == 0 and row["skips"] == 0 and not row["deselected"])
    assert row["realWindowTraces"], "no real window/counter evidence"
    print(json.dumps({"fullAffectedFile": True, "passed": row["testcases"],
                      "failures": 0, "errors": 0, "skips": 0, "actualPG": True}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("provenance-start", "provenance-end", "controls", "positive"))
    mode = parser.parse_args().mode
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        if mode.startswith("provenance-"):
            provenance(mode)
        elif mode == "controls":
            controls()
        else:
            positive()
    except Exception as error:
        (OUT / (mode + "-failure.log")).write_text(traceback.format_exc(), encoding="utf-8")
        save(mode + "-failure.json", {"mode": mode, "errorType": type(error).__name__,
                                     "actualProofPassed": False, "noRetry": True})
        print(json.dumps({"mode": mode, "failed": True, "type": type(error).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
