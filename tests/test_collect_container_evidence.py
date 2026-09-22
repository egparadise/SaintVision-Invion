"""Self-tests for tools/collect_container_evidence.py (S03-DB evidence collector).

Pure tests pin C1..C4 / P1..P4, the sandbox-plan mirror, rendering and the secret
guard.  Real-PostgreSQL tests seed a synthetic run ledger (one succeeded run with a
committed output object + evidence, one failed run, released leases) into a
disposable migrated database, then break it (active lease on a terminal run,
evidence hash drift) to prove the collector reports the breakage.  The Docker test
probes a local image when Docker and the image are present, otherwise it is
skipped with the reason -- the collector itself reports that lane as unmeasured.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "services/control-plane/src"))

import collect_container_evidence as tool  # noqa: E402

SHA = hashlib.sha256(b"output-bytes").hexdigest()


def _db(**overrides) -> dict:
    base = {
        "measured": True, "database": {"name": "db", "server_version": "16", "migration_head": "0046"}, "tenant_filter": None,
        "counts": {"runs": 2, "leases": 2, "tool_claims": 1, "deliveries": 1, "stop_receipts": 1, "commitments": 1,
                   "completions": 1, "evidence": 1, "storage_objects": 1},
        "denials": {"delivery_error_codes": [], "ingestion_errors": [], "approval_audit_phases": {}},
        "runs": {
            "run_ok": {"state": "succeeded", "attempt": 1, "active_leases": 0,
                       "leases": [{"lease_id": "lse_1", "released_at": "t", "stop_receipt": "r", "reservation_abort": None}],
                       "claims": [{}], "deliveries": [{"phase": "done", "operation": "start", "last_error_code": None}],
                       "commitments": [{"evidence_id": "evd_1", "command_id": "c", "object_id": "o", "content_hash": SHA,
                                        "storage_object": {"content_hash": SHA, "size_bytes": 12, "state": "ready"}, "stop_receipt": {"content_hash": "h"}}],
                       "completions": [{"evidence_id": "evd_1"}],
                       "evidence": [{"evidence_id": "evd_1", "outputSha256": SHA, "result": "succeeded"}]},
            "run_failed": {"state": "failed", "attempt": 1, "active_leases": 0,
                           "leases": [{"lease_id": "lse_2", "released_at": "t", "stop_receipt": None, "reservation_abort": "a"}],
                           "claims": [], "deliveries": [], "commitments": [], "completions": [], "evidence": []},
        },
    }
    base.update(overrides)
    return base


def _lane(**overrides) -> dict:
    probes = [
        {"id": "P1", "name": "output-capture", "exit_code": 0, "stdout_bytes": 13, "stderr_bytes": 13,
         "stdout_sha256": hashlib.sha256(b"probe-stdout\n").hexdigest(), "stderr_sha256": hashlib.sha256(b"probe-stderr\n").hexdigest(),
         "stdout_head": "probe-stdout\n", "stderr_head": "probe-stderr\n", "argv": [], "expect": ""},
        {"id": "P2", "name": "rootfs-write-denied", "exit_code": 2, "stdout_bytes": 0, "stderr_bytes": 40, "stdout_sha256": "x", "stderr_sha256": "y",
         "stdout_head": "", "stderr_head": "sh: 1: cannot create /etc/inv-probe: Read-only file system", "argv": [], "expect": ""},
        {"id": "P3", "name": "network-namespace-isolated", "exit_code": 0, "stdout_bytes": 70, "stderr_bytes": 0, "stdout_sha256": "x", "stderr_sha256": "y",
         "stdout_head": '{"ifaces": ["lo"], "routes": [], "external_connect": "ENETUNREACH"}\n', "stderr_head": "", "argv": [], "expect": "",
         "observed": {"ifaces": ["lo"], "routes": [], "external_connect": "ENETUNREACH"}, "isolated": True},
        {"id": "P4", "name": "uid-and-capabilities", "exit_code": 0, "stdout_bytes": 30, "stderr_bytes": 0, "stdout_sha256": "x", "stderr_sha256": "y",
         "stdout_head": "65532\nCapEff:\t0000000000000000\n", "stderr_head": "", "argv": [], "expect": ""},
    ]
    base = {"measured": True, "image": "img", "image_id": "sha256:abc", "docker_server_version": "20", "plan": tool.SANDBOX_PLAN, "network": "none",
            "probes": probes,
            "control": {"network": "bridge", "exit_code": 0, "observed": {"ifaces": ["eth0", "lo"], "routes": ["eth0"], "external_connect": "timeout"},
                        "isolated": False, "note": "control"}}
    base.update(overrides)
    return base


def _obs(db=None, lane=None) -> dict:
    return {"collector": "tools/collect_container_evidence.py", "collected_at": "2026-09-22T15:00:00+00:00",
            "provenance": {"git_sha": "abc", "collector_sha256": "0" * 64, "uncommitted_sources": []}, "note": None,
            "db": db if db is not None else _db(), "container": lane if lane is not None else _lane()}


def test_clean_ledger_and_probes_pass():
    assert tool.evaluate(_obs()) == []


@pytest.mark.parametrize("mutate, rule", [
    (lambda d: d["runs"]["run_ok"].__setitem__("active_leases", 1), "C1"),
    (lambda d: d["runs"]["run_ok"]["evidence"][0].__setitem__("outputSha256", "deadbeef"), "C2"),
    (lambda d: d["runs"]["run_ok"]["commitments"][0]["storage_object"].__setitem__("content_hash", "other"), "C2"),
    (lambda d: d["runs"]["run_ok"].__setitem__("completions", []), "C2"),
    (lambda d: d["runs"]["run_failed"].__setitem__("evidence", [{"evidence_id": "e", "outputSha256": SHA, "result": "succeeded"}]), "C3"),
    (lambda d: d["runs"]["run_failed"]["leases"][0].__setitem__("reservation_abort", None), "C4"),
])
def test_each_db_expectation_is_enforced(mutate, rule):
    db = deepcopy(_db())
    mutate(db)
    assert [v["rule"] for v in tool.evaluate_db(db)] == [rule]


@pytest.mark.parametrize("probe_id, patch, rule", [
    ("P1", {"stdout_sha256": "not-the-bytes"}, "P1"),
    ("P2", {"exit_code": 0, "stderr_head": ""}, "P2"),
    ("P3", {"isolated": False, "observed": {"ifaces": ["eth0", "lo"], "routes": ["eth0"], "external_connect": "ENETUNREACH"}}, "P3"),
    ("P3", {"isolated": None, "observed": None, "stdout_head": "denied ConnectionRefusedError\n"}, "P3"),
    ("P4", {"stdout_head": "0\nCapEff:\t000001ffffffffff\n"}, "P4"),
])
def test_each_container_expectation_is_enforced(probe_id, patch, rule):
    lane = deepcopy(_lane())
    next(p for p in lane["probes"] if p["id"] == probe_id).update(patch)
    assert [v["rule"] for v in tool.evaluate_container(lane)] == [rule]


def test_loopback_refusal_is_not_isolation_evidence():
    """Codex F-73-02: a refused loopback connect happens on bridge/host networks too."""
    assert tool._isolated({"ifaces": ["lo"], "routes": [], "external_connect": "ECONNREFUSED"}) is False
    assert tool._isolated({"ifaces": ["eth0", "lo"], "routes": [], "external_connect": "ENETUNREACH"}) is False
    assert tool._isolated({"ifaces": ["lo"], "routes": ["eth0"], "external_connect": "ENETUNREACH"}) is False
    assert tool._isolated({"ifaces": ["lo"], "routes": [], "external_connect": "ENETUNREACH"}) is True
    assert tool._isolated(None) is None


def test_non_discriminating_control_is_a_p3_violation():
    lane = deepcopy(_lane())
    lane["control"]["observed"] = {"ifaces": ["lo"], "routes": [], "external_connect": "ENETUNREACH"}
    lane["control"]["isolated"] = True
    assert [v["rule"] for v in tool.evaluate_container(lane)] == ["P3"]
    assert "non-discriminating" in tool.evaluate_container(lane)[0]["detail"]


def test_c2_requires_completion_and_commitment_keyed_to_the_same_evidence():
    """Codex F-73-01: a completion for another evidence_id must not satisfy C2."""
    db = deepcopy(_db())
    db["runs"]["run_ok"]["completions"] = [{"evidence_id": "evd_other"}]
    rules = [v["detail"] for v in tool.evaluate_db(db)]
    assert any("keyed to evd_other" in d for d in rules) and any("no completion with the same evidence_id" in d for d in rules)
    db = deepcopy(_db())
    db["runs"]["run_ok"]["commitments"][0]["evidence_id"] = "evd_other"
    assert [v["rule"] for v in tool.evaluate_db(db)] == ["C2"] and "no commitment" in tool.evaluate_db(db)[0]["detail"]


def test_zero_runs_or_unmeasured_lane_is_unmeasured_not_pass(tmp_path):
    """Codex F-73-03: verdict/exit must say UNMEASURED when a lane had nothing to judge."""
    obs = _obs()
    assert tool.verdict(obs, []) == "PASS" and tool.unmeasured_reasons(obs) == []
    zero = _obs(db=_db(runs={}, counts={"runs": 0}))
    assert tool.verdict(zero, []) == "UNMEASURED" and "0 runs" in tool.unmeasured_reasons(zero)[0]
    nolane = _obs(lane={"measured": False, "reason": "no image", "plan": tool.SANDBOX_PLAN, "probes": [], "image": None})
    assert tool.verdict(nolane, []) == "UNMEASURED"
    assert tool.verdict(zero, [{"rule": "C1", "detail": "x"}]) == "VIOLATIONS"
    json_path, md_path = tool.write_evidence(zero, [], tmp_path, "z", None)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "UNMEASURED" and payload["unmeasured"]
    assert "**UNMEASURED**" in md_path.read_text(encoding="utf-8")


def test_unmeasured_lanes_are_never_judged_or_passed():
    obs = _obs(db={"measured": False, "reason": "no DSN"}, lane={"measured": False, "reason": "no image", "plan": tool.SANDBOX_PLAN, "probes": [], "image": None})
    assert tool.evaluate(obs) == []
    md = tool.render_markdown(obs, [])
    assert md.count("**unmeasured**") == 2 and "no image" in md and "**UNMEASURED**" in md


def test_missing_python_in_image_marks_network_probe_unmeasured():
    lane = deepcopy(_lane())
    next(p for p in lane["probes"] if p["id"] == "P3").update({"exit_code": 127, "stdout_head": "", "stderr_head": "python3: not found"})
    assert tool.evaluate_container(lane) == []
    assert "python3 is absent" in next(p for p in lane["probes"] if p["id"] == "P3")["unmeasured"]


def test_sandbox_plan_mirror_matches_kernel_compile_launch():
    """The probe constraints must be the kernel's, not the collector's opinion."""
    import inspect
    from inv import sandbox
    src = inspect.getsource(sandbox.compile_launch)
    for key, value in tool.SANDBOX_PLAN.items():
        literal = json.dumps(value) if isinstance(value, str) else str(value)  # Python literal in the kernel source
        assert f'"{key}": {literal}' in src.replace("'", '"'), (key, value)


def test_no_runs_is_reported_as_unmeasured_not_pass():
    db = _db(runs={}, counts={"runs": 0})
    md = tool.render_markdown(_obs(db=db), [])
    assert "no runs observed" in md and "unmeasured here" in md


def test_secret_guard(tmp_path):
    dsn = "postgresql://u:s3cretpw@127.0.0.1:5432/db"
    with pytest.raises(ValueError):
        tool.assert_no_secrets("x " + dsn, dsn)
    json_path, md_path = tool.write_evidence(_obs(), [], tmp_path, "x", dsn)
    text = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    assert "s3cretpw" not in text and json.loads(json_path.read_text(encoding="utf-8"))["verdict"] == "PASS"


# --------------------------------------------------------------------------- real PostgreSQL

@pytest.fixture(scope="module")
def s03_db():
    admin = os.getenv("INV_TEST_ADMIN_DSN")
    if not admin:
        if os.getenv("CI"):
            pytest.fail("CI requires INV_TEST_ADMIN_DSN; DB tests must not be skipped")
        pytest.skip("Set INV_TEST_ADMIN_DSN to a disposable PostgreSQL 16+ test server")

    class Redacted(dict):
        def __repr__(self):
            return "<s03_db dsn=redacted>"

    with tool.disposable_database(admin) as owner:
        yield Redacted(owner=owner)


def _seed_ledger(owner: str) -> dict:
    """A synthetic ledger shaped like the real one: succeeded run with committed bytes,
    cancelled-before-claim run with a reservation abort, leases released with provenance."""
    import psycopg
    from psycopg.types.json import Jsonb
    from inv.ids import new_id
    tenant, project, node, resource = str(uuid4()), new_id("prj"), new_id("nod"), new_id("res")
    run_ok, run_failed, evidence_id = new_id("run"), new_id("run"), new_id("evd")
    epoch, obj = str(uuid4()), str(uuid4())
    lease_ok, lease_failed = new_id("lse"), new_id("lse")
    data = b"actual-node-output\n"
    content_hash = hashlib.sha256(data).hexdigest()
    with psycopg.connect(owner) as conn:
        conn.execute("INSERT INTO inv.control_epoch(singleton,epoch) VALUES (true,%s) ON CONFLICT(singleton) DO UPDATE SET epoch=excluded.epoch", (epoch,))
        conn.execute("INSERT INTO inv.tenants VALUES (%s,'s03-evidence')", (tenant,))
        conn.execute("INSERT INTO inv.projects VALUES (%s,%s)", (tenant, project))
        conn.execute("INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch,clock_skew_seconds) VALUES (%s,%s,'online',%s,0)", (tenant, node, epoch))
        conn.execute("INSERT INTO inv.resources VALUES (%s,%s,%s,'cpu',10,10)", (tenant, resource, node))
        # inv.guard_run enforces the state machine: insert as draft, walk legal transitions,
        # and (for success) record evidence before the final transition.
        def walk(run_id, states):
            row = conn.execute("SELECT state,version,attempt FROM inv.runs WHERE run_id=%s", (run_id,)).fetchone()
            state, version, attempt = row
            for target in states:
                attempt += 1 if target == "running" else 0
                version += 1
                conn.execute("UPDATE inv.runs SET state=%s,version=%s,attempt=%s WHERE run_id=%s", (target, version, attempt, run_id))
        for run in (run_ok, run_failed):
            conn.execute("INSERT INTO inv.runs(tenant_id,project_id,run_id,state,version,attempt) VALUES (%s,%s,%s,'draft',1,0)", (tenant, project, run))
        walk(run_ok, ["validated", "planned", "scheduled", "running", "verifying"])
        # inv.guard_reservation_abort only records an abort for a *cancelled* run with no claim/attempt
        walk(run_failed, ["validated", "planned", "scheduled", "cancelled"])
        conn.execute("""INSERT INTO inv.resource_leases(tenant_id,project_id,run_id,resource_id,lease_id,amount,fencing_token,granted_at,expires_at,released_at,recovery_epoch,stop_receipt)
                        VALUES (%s,%s,%s,%s,%s,1,1,now(),now()+interval '30s',now(),%s,%s)""", (tenant, project, run_ok, resource, lease_ok, epoch, str(uuid4())))
        abort = str(uuid4())  # reservation_abort is a FK to the kernel's abort record (cancelled_before_claim)
        conn.execute("INSERT INTO inv.reservation_aborts(tenant_id,project_id,run_id,abort_id,reason,recovery_epoch) VALUES (%s,%s,%s,%s,'cancelled_before_claim',%s)",
                     (tenant, project, run_failed, abort, epoch))
        conn.execute("""INSERT INTO inv.resource_leases(tenant_id,project_id,run_id,resource_id,lease_id,amount,fencing_token,granted_at,expires_at,released_at,recovery_epoch,reservation_abort)
                        VALUES (%s,%s,%s,%s,%s,1,2,now(),now()+interval '30s',now(),%s,%s)""", (tenant, project, run_failed, resource, lease_failed, epoch, abort))
        # inv.guard_storage_object: objects begin 'uploading' and become 'ready' by transition
        conn.execute("INSERT INTO inv.storage_budgets VALUES (%s,%s,1048576)", (tenant, project))
        conn.execute("INSERT INTO inv.storage_objects(tenant_id,project_id,object_id,content_hash,size_bytes,state) VALUES (%s,%s,%s,%s,%s,'uploading')", (tenant, project, obj, content_hash, len(data)))
        conn.execute("UPDATE inv.storage_objects SET state='ready' WHERE object_id=%s", (obj,))
        # A result commitment/completion cannot be seeded here: its FK chain
        # (execution_attempts -> tool_claims -> approval_dispatches) only exists after a real
        # Node execution (Linux private provider).  The collector must therefore report the
        # succeeded run below as C2 "evidence has no commitment" -- which is the honest verdict.
        conn.execute("INSERT INTO inv.evidence(tenant_id,run_id,evidence_id,envelope) VALUES (%s,%s,%s,%s)",
                     (tenant, run_ok, evidence_id, Jsonb({"tenantId": tenant, "runId": run_ok, "evidenceId": evidence_id,
                                                          "outputSha256": content_hash, "result": "succeeded"})))
        walk(run_ok, ["succeeded"])  # the trigger requires evidence with result=succeeded first
    return {"tenant": tenant, "run_ok": run_ok, "run_failed": run_failed, "lease_ok": lease_ok, "evidence_id": evidence_id, "hash": content_hash}


@pytest.mark.postgres
def test_real_pg_ledger_passes_then_breakage_is_reported(s03_db, tmp_path):
    import psycopg
    seed = _seed_ledger(s03_db["owner"])
    db = tool.collect_db(s03_db["owner"], seed["tenant"])
    assert db["counts"]["runs"] == 2 and db["counts"]["evidence"] == 1 and db["counts"]["storage_objects"] == 1
    # the only finding on the synthetic ledger is the commitment the ledger cannot fake
    findings = tool.evaluate_db(db)  # no completion + evidence without commitment: both C2 on run_ok
    assert [(v["rule"], v["run"]) for v in findings] == [("C2", seed["run_ok"]), ("C2", seed["run_ok"])]
    assert any("no commitment" in v["detail"] for v in findings)
    ok = db["runs"][seed["run_ok"]]
    assert ok["state"] == "succeeded" and ok["active_leases"] == 0
    assert db["runs"][seed["run_failed"]]["state"] == "cancelled" and db["runs"][seed["run_failed"]]["active_leases"] == 0
    assert ok["evidence"][0]["outputSha256"] == seed["hash"] and ok["evidence"][0]["result"] == "succeeded"
    assert ok["leases"][0]["stop_receipt"] and db["runs"][seed["run_failed"]]["leases"][0]["reservation_abort"]
    obs = tool.collect(s03_db["owner"], None, seed["tenant"])
    json_path, md_path = tool.write_evidence(obs, tool.evaluate(obs), tmp_path, "ledger", s03_db["owner"])
    text = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    assert s03_db["owner"] not in text and "**unmeasured**" in text  # container lane not requested here
    # negative control: an un-reclaimed (never released) lease on a terminal run (C1).
    # C4 cannot be provoked on real PostgreSQL: the ledger's CHECK ``lease_release_proof`` refuses
    # a released lease without stop receipt or abort (and vice versa), and inv.evidence is
    # immutable, so hash drift and C4 stay pure-evaluator tests.
    from inv.ids import new_id
    stray = new_id("lse")
    with psycopg.connect(s03_db["owner"]) as conn:
        conn.execute("""INSERT INTO inv.resource_leases(tenant_id,project_id,run_id,resource_id,lease_id,amount,fencing_token,granted_at,expires_at,recovery_epoch)
                        SELECT tenant_id,project_id,run_id,resource_id,%s,1,9,now(),now()+interval '30s',recovery_epoch
                        FROM inv.resource_leases WHERE lease_id=%s""", (stray, seed["lease_ok"]))
    broken = tool.evaluate_db(tool.collect_db(s03_db["owner"], seed["tenant"]))
    assert sorted(v["rule"] for v in broken) == ["C1", "C2", "C2"], broken
    with psycopg.connect(s03_db["owner"]) as conn:
        conn.execute("DELETE FROM inv.resource_leases WHERE lease_id=%s", (stray,))
    after = tool.evaluate_db(tool.collect_db(s03_db["owner"], seed["tenant"]))
    assert sorted(v["rule"] for v in after) == ["C2", "C2"]


@pytest.mark.postgres
def test_real_pg_cli_exit_codes(s03_db, tmp_path):
    env = {**os.environ, "INV_AUDIT_DSN": s03_db["owner"], "PYTHONUTF8": "1"}
    result = subprocess.run([sys.executable, str(ROOT / "tools/collect_container_evidence.py"), "--out-dir", str(tmp_path), "--label", "cli"],
                            cwd=ROOT, env=env, capture_output=True, text=True)
    # the synthetic ledger carries the un-fakeable C2 finding -> exit 1, files still written
    assert result.returncode == 1, result.stdout[-400:] + result.stderr[-400:]
    assert result.stdout.startswith("VIOLATIONS") and "db=runs 2" in result.stdout and "container=unmeasured" in result.stdout
    assert s03_db["owner"] not in (tmp_path / "cli.json").read_text(encoding="utf-8")
    nodb = subprocess.run([sys.executable, str(ROOT / "tools/collect_container_evidence.py"), "--no-db", "--out-dir", str(tmp_path), "--label", "nodb"],
                          cwd=ROOT, capture_output=True, text=True)
    assert nodb.returncode == 3 and nodb.stdout.startswith("UNMEASURED"), nodb.stdout
    assert json.loads((tmp_path / "nodb.json").read_text(encoding="utf-8"))["verdict"] == "UNMEASURED"
    bad = subprocess.run([sys.executable, str(ROOT / "tools/collect_container_evidence.py"), "--dsn",
                          "postgresql://nobody:nothing@127.0.0.1:1/none?connect_timeout=2", "--out-dir", str(tmp_path)],
                         cwd=ROOT, capture_output=True, text=True)
    assert bad.returncode == 2 and "nothing" not in bad.stderr


# --------------------------------------------------------------------------- local Docker

def _docker_image_present(image: str) -> bool:
    try:
        return subprocess.run(["docker", "image", "inspect", image], capture_output=True, timeout=60).returncode == 0
    except Exception:
        return False


PROBE_IMAGE = os.getenv("INV_EVIDENCE_PROBE_IMAGE", "python:3.12-slim")


@pytest.mark.skipif(not _docker_image_present(PROBE_IMAGE), reason=f"docker or local image {PROBE_IMAGE} unavailable")
def test_local_docker_probe_measures_sandbox_plan_constraints():
    lane = tool.probe_container(PROBE_IMAGE)
    assert lane["measured"], lane.get("reason")
    assert tool.evaluate_container(lane) == [], lane["probes"]
    p1 = next(p for p in lane["probes"] if p["id"] == "P1")
    assert p1["stdout_sha256"] == hashlib.sha256(b"probe-stdout\n").hexdigest()
    p3 = next(p for p in lane["probes"] if p["id"] == "P3")
    assert p3["observed"] == {"ifaces": ["lo"], "routes": [], "external_connect": "ENETUNREACH"} and p3["isolated"] is True
    assert lane["control"]["isolated"] is False, lane["control"]  # bridge network is visibly not isolated
    # Codex F-73-02 control: run the same probe set with isolation removed -> P3 must fail
    loose = tool.probe_container(PROBE_IMAGE, network="bridge", with_control=False)
    assert [v["rule"] for v in tool.evaluate_container(loose)] == ["P3"], loose["probes"]


def test_absent_image_is_reported_unmeasured_without_pull():
    lane = tool.probe_container("inv-evidence-nonexistent-image:never")
    assert lane["measured"] is False and "not present" in lane.get("reason", "") or "unavailable" in lane.get("reason", "")
