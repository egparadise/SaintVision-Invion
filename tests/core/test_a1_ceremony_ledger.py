"""Synthetic signer observations, using the reviewed durable-A1 public fixture."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from deploy.lan import a1_writer_fence as fence
from tools import a1_ceremony_ledger as ledger
from tools.check_fleet5_authority_replacement_r2 import CONTRACT_DIR, plan_digest

FIXTURE = CONTRACT_DIR / "fixtures/positive/p02-a1-durable-resume-anchor-stage.json"


@pytest.fixture
def ceremony(tmp_path):
    plan = json.loads(FIXTURE.read_bytes())
    path = tmp_path / "ledger"
    fence.initialize(path)
    owner = None
    for generation in range(1, plan["writerFence"]["generation"] + 1):
        token = plan["writerFence"]["token"] if generation == plan["writerFence"]["generation"] else str(generation)
        owner = fence.transfer(path, owner, plan_digest(plan), token)
    return path, plan, owner


@pytest.mark.parametrize("conflict", ["second-key", "id-reuse", "wrong-leaf", "unknown"])
def test_complete_snapshot_and_conflicts(ceremony, conflict):
    path, plan, owner = ceremony
    key = plan["newAuthority"]["caPublicKeySHA256"]
    log = plan["checkpoint"]["readback"]["ceremonyLog"]
    with pytest.raises(sqlite3.OperationalError):
        ledger.readback(path, plan)
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda _: ledger.record(path, plan, "key", "", key), range(4)))
    with pytest.raises(ValueError):
        ledger.readback(path, plan)
    for event in log["signed"]:
        ledger.record(path, plan, event["subject"], event["subject"], event["leafSHA256"])
    assert ledger.readback(path, plan) == {**log, "signed": sorted(log["signed"], key=lambda e: e["subject"])}
    leaf = log["signed"][0]
    args = {"second-key": ("again", "", key), "id-reuse": ("key", leaf["subject"], leaf["leafSHA256"]),
            "wrong-leaf": ("wrong", leaf["subject"], key), "unknown": ("unknown", "foreign", key)}[conflict]
    for _ in range(2):
        with pytest.raises(ValueError):
            ledger.record(path, plan, *args)
    script = """
import json, sys
from pathlib import Path
from tools import a1_ceremony_ledger as ledger
try:
    ledger.readback(sys.argv[1], json.loads(Path(sys.argv[2]).read_bytes()))
except ValueError as exc:
    sys.exit(0 if 'conflicting' in str(exc) else 2)
sys.exit(1)
"""
    subprocess.run([sys.executable, "-c", script, str(path), str(FIXTURE)], check=True,
                   cwd=Path(__file__).resolve().parents[2])
    ledger.record(path, plan, "key", "", key)
    with pytest.raises(ValueError, match="conflicting"):
        ledger.readback(path, plan)
    assert fence.interrupted_a1_hold(path, owner) == "HOLD_CUSTODY_UNRESOLVED"
    fence.transfer(path, owner, "next-plan", "next-token")
    with pytest.raises(ValueError):
        ledger.readback(path, plan)
    with pytest.raises(ValueError):
        ledger.record(path, plan, "stale", "", key)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT event_id, subject, fingerprint FROM ceremony_conflict").fetchall() == [args]


@pytest.mark.parametrize("before_commit", [True, False])
def test_process_loss(ceremony, before_commit):
    path, plan, _ = ceremony
    script = """
import json, os, sqlite3, sys
from pathlib import Path
from tools import a1_ceremony_ledger as ledger
plan = json.loads(Path(sys.argv[2]).read_bytes())
connect = sqlite3.connect
def observed(*args, **kwargs):
    db = connect(*args, **kwargs)
    db.set_trace_callback(lambda sql: os._exit(73) if sql == 'COMMIT' else None)
    return db
if sys.argv[3] == 'True':
    sqlite3.connect = observed
ledger.record(sys.argv[1], plan, 'key', '', plan['newAuthority']['caPublicKeySHA256'])
os._exit(74)
"""
    result = subprocess.run([sys.executable, "-c", script, str(path), str(FIXTURE), str(before_commit)],
                            cwd=Path(__file__).resolve().parents[2])
    assert result.returncode == (73 if before_commit else 74)
    with sqlite3.connect(path) as db:
        assert bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='ceremony_event'").fetchone()) != before_commit
    ledger.record(path, plan, "key", "", plan["newAuthority"]["caPublicKeySHA256"])
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM ceremony_event").fetchone() == (1,)

@pytest.mark.parametrize("alter", ["member", "client", "authority", "manifest"])
def test_plan_alteration(ceremony, alter):
    path, plan, _ = ceremony
    key = plan["newAuthority"]["caPublicKeySHA256"]
    ledger.record(path, plan, "key", "", key)
    original = plan_digest(plan)
    if alter == "manifest":
        plan["operationManifest"] = None
    elif alter == "authority":
        plan["newAuthority"]["caPublicKeySHA256"] = "0" * 64
    else:
        target = plan["members"][0] if alter == "member" else plan["controlPlaneClient"]
        target["plannedLeafSHA256"] = "0" * 64
    assert plan_digest(plan) == original
    with pytest.raises(ValueError):
        ledger.record(path, plan, "second", "", key)
    with pytest.raises(ValueError):
        ledger.readback(path, plan)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM ceremony_conflict").fetchone() == (0,)

def test_legacy_observations_require_reconciliation(ceremony):
    path, plan, _ = ceremony
    key = plan["newAuthority"]["caPublicKeySHA256"]
    ledger.record(path, plan, "key", "", key)
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE ceremony_conflict")
    with pytest.raises(ValueError, match="reconciliation"):
        ledger.record(path, plan, "key", "", key)
    with pytest.raises(sqlite3.OperationalError):
        ledger.readback(path, plan)
