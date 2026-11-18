"""Independent probes of tools/a1_ceremony_ledger.py at f4af7bb8, using disposable synthetic fixtures.

Usage: python probe_ceremony_ledger.py <repo_root> <out.json>
Every ledger lives in a fresh temp directory. No network, signer, key or fleet host is touched.
"""
import copy
import hashlib
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from deploy.lan import a1_writer_fence as fence  # noqa: E402
from tools import a1_ceremony_ledger as ledger  # noqa: E402
from tools.check_fleet5_authority_replacement_r2 import CONTRACT_DIR, plan_digest  # noqa: E402
import tools.check_fleet5_authority_replacement_r2 as r2  # noqa: E402

FIXTURE = CONTRACT_DIR / "fixtures/positive/p02-a1-durable-resume-anchor-stage.json"
PLAN = json.loads(FIXTURE.read_bytes())
KEY = PLAN["newAuthority"]["caPublicKeySHA256"]
LOG = PLAN["checkpoint"]["readback"]["ceremonyLog"]
LEAVES = [(e["subject"], e["leafSHA256"]) for e in LOG["signed"]]
OTHER = "ab" * 32
RESULTS = []
REAL_CONNECT = sqlite3.connect


def probe(name, area):
    def wrap(fn):
        def run():
            started = time.perf_counter()
            try:
                detail = fn()
                RESULTS.append({"area": area, "probe": name, "ok": True, "detail": detail})
            except Exception as exc:  # report, never hide
                RESULTS.append({"area": area, "probe": name, "ok": False,
                                "detail": f"{type(exc).__name__}: {exc}",
                                "trace": traceback.format_exc().splitlines()[-6:]})
            RESULTS[-1]["seconds"] = round(time.perf_counter() - started, 3)
        PROBES.append(run)
        return fn
    return wrap


PROBES = []


def fresh(plan=PLAN):
    path = Path(tempfile.mkdtemp(prefix="a1cl-")) / "ledger"
    fence.initialize(path)
    owner = None
    target = plan["writerFence"]["generation"]
    for g in range(1, target + 1):
        token = plan["writerFence"]["token"] if g == target else str(g)
        owner = fence.transfer(path, owner, plan_digest(plan), token)
    return path, owner


def complete(path, plan=PLAN):
    ledger.record(path, plan, "key", "", plan["newAuthority"]["caPublicKeySHA256"])
    for subject, leaf in LEAVES:
        ledger.record(path, plan, "sign:" + subject, subject, leaf)


def rows(path):
    with REAL_CONNECT(path) as db:
        try:
            return db.execute("SELECT plan, event_id, subject, fingerprint FROM ceremony_event "
                              "ORDER BY event_id").fetchall()
        except sqlite3.OperationalError:
            return None


def has_table(path, name="ceremony_event"):
    with REAL_CONNECT(path) as db:
        return bool(db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone())


def raises(exc, fn, *args):
    try:
        fn(*args)
    except exc as e:
        return f"{type(e).__name__}: {e}"
    except Exception as e:
        raise AssertionError(f"expected {exc.__name__}, got {type(e).__name__}: {e}")
    raise AssertionError(f"expected {exc.__name__}, call returned")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_log():
    return {**LOG, "signed": sorted(LOG["signed"], key=lambda e: e["subject"])}


# ------------------------------------------------------------------ atomic event and readback

@probe("complete readback equals planned ceremonyLog", "atomic")
def _():
    path, _ = fresh()
    complete(path)
    got = ledger.readback(path, PLAN)
    assert got == expected_log(), got
    n = len(rows(path))
    assert n == 1 + len(LEAVES)
    return f"{n} events; caKeysCreated=1, {len(got['signed'])} signed, sorted by subject"


@probe("readback is read-only and byte-identical", "atomic")
def _():
    path, _ = fresh()
    complete(path)
    before = sha(path)
    for _ in range(3):
        ledger.readback(path, PLAN)
    assert sha(path) == before
    assert not Path(str(path) + "-journal").exists()
    return "3 readbacks left the file hash unchanged and no journal"


@probe("readback snapshot spans fence and events while a transfer waits", "atomic")
def _():
    path, owner = fresh()
    complete(path)
    paused, release, order = threading.Event(), threading.Event(), []

    def hooked(*a, **k):
        db = REAL_CONNECT(*a, **k)
        if threading.current_thread().name == "reader":
            def cb(sql):
                if sql.startswith("SELECT subject, fingerprint FROM ceremony_event"):
                    paused.set()
                    release.wait(10)
            db.set_trace_callback(cb)
        return db

    out = {}

    def reader():
        out["log"] = ledger.readback(path, PLAN)
        order.append("readback-done")

    def mover():
        fence.transfer(path, owner, "next-plan", "next-token")
        order.append("transfer-done")

    sqlite3.connect = hooked
    try:
        t1 = threading.Thread(target=reader, name="reader")
        t1.start()
        assert paused.wait(10)
        t2 = threading.Thread(target=mover, name="mover")
        t2.start()
        time.sleep(1.0)
        blocked = t2.is_alive()
        release.set()
        t1.join(15)
        t2.join(15)
    finally:
        sqlite3.connect = REAL_CONNECT
    assert out["log"] == expected_log()
    assert order == ["readback-done", "transfer-done"], order
    assert blocked
    after = raises(ValueError, ledger.readback, path, PLAN)
    return f"transfer blocked while the reader held its snapshot; order={order}; later readback -> {after}"


@probe("check-and-insert holds the write lock against a concurrent transfer", "atomic")
def _():
    path, owner = fresh()
    paused, release, order = threading.Event(), threading.Event(), []

    def hooked(*a, **k):
        db = REAL_CONNECT(*a, **k)
        if threading.current_thread().name == "writer":
            def cb(sql):
                if sql.startswith("INSERT INTO ceremony_event"):
                    paused.set()
                    release.wait(10)
            db.set_trace_callback(cb)
        return db

    def writer():
        ledger.record(path, PLAN, "key", "", KEY)
        order.append("record-done")

    def mover():
        fence.transfer(path, owner, "next-plan", "next-token")
        order.append("transfer-done")

    sqlite3.connect = hooked
    try:
        t1 = threading.Thread(target=writer, name="writer")
        t1.start()
        assert paused.wait(10)
        t2 = threading.Thread(target=mover, name="mover")
        t2.start()
        time.sleep(1.0)
        blocked = t2.is_alive()
        release.set()
        t1.join(15)
        t2.join(15)
    finally:
        sqlite3.connect = REAL_CONNECT
    assert blocked and order == ["record-done", "transfer-done"], order
    assert len(rows(path)) == 1
    late = raises(ValueError, ledger.record, path, PLAN, "sign:x", LEAVES[0][0], LEAVES[0][1])
    return f"transfer waited for the in-flight record; order={order}; post-transfer record -> {late}"


@probe("concurrent writer observes pre-commit state as incomplete, never partial", "atomic")
def _():
    path, _ = fresh()
    ledger.record(path, PLAN, "key", "", KEY)
    for s, l in LEAVES[:-1]:
        ledger.record(path, PLAN, "sign:" + s, s, l)
    paused, release = threading.Event(), threading.Event()

    def hooked(*a, **k):
        db = REAL_CONNECT(*a, **k)
        if threading.current_thread().name == "writer":
            db.set_trace_callback(lambda sql: (paused.set(), release.wait(10)) if sql == "COMMIT" else None)
        return db

    s, l = LEAVES[-1]
    sqlite3.connect = hooked
    try:
        t = threading.Thread(target=lambda: ledger.record(path, PLAN, "sign:" + s, s, l), name="writer")
        t.start()
        assert paused.wait(10)
        during = raises(ValueError, ledger.readback, path, PLAN)
        release.set()
        t.join(15)
    finally:
        sqlite3.connect = REAL_CONNECT
    assert ledger.readback(path, PLAN) == expected_log()
    return f"during uncommitted final leaf: {during}; after commit: complete"


@probe("8 threads x identical CA event -> one row", "atomic")
def _():
    from concurrent.futures import ThreadPoolExecutor
    path, _ = fresh()
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(lambda _: ledger.record(path, PLAN, "key", "", KEY), range(8)))
    assert len(rows(path)) == 1
    return "8 identical concurrent records produced exactly one event"


@probe("8 processes: 6 identical + 2 conflicting CA events", "atomic")
def _():
    path, _ = fresh()
    script = ("import json,sys;sys.path.insert(0,sys.argv[1]);from pathlib import Path;"
              "from tools import a1_ceremony_ledger as l;p=json.loads(Path(sys.argv[3]).read_bytes());"
              "\ntry:\n l.record(sys.argv[2],p,sys.argv[4],'',sys.argv[5]);print('ok')"
              "\nexcept ValueError as e:\n print('reject',e)")
    procs = []
    for i in range(8):
        eid, fp = ("key", KEY) if i < 6 else (f"key-{i}", KEY)
        procs.append(subprocess.Popen([sys.executable, "-c", script, str(ROOT), str(path), str(FIXTURE), eid, fp],
                                      stdout=subprocess.PIPE, text=True))
    outs = [p.communicate(60)[0].strip() for p in procs]
    assert rows(path) and len(rows(path)) == 1
    winner = rows(path)[0][1]
    if winner == "key":
        assert all(o == "ok" for o in outs[:6]) and all(o.startswith("reject") for o in outs[6:]), outs
    else:
        assert outs.count("ok") == 1, outs
    return f"one committed event ({winner}); outputs={outs}"


# ------------------------------------------------------------------ restart behaviour

def child(path, mode, event_id="key", subject="", fp=KEY):
    script = """
import json, os, sqlite3, sys, time
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from tools import a1_ceremony_ledger as ledger
plan = json.loads(Path(sys.argv[3]).read_bytes())
mode = sys.argv[4]
connect = sqlite3.connect
def hooked(*a, **k):
    db = connect(*a, **k)
    def cb(sql):
        if sql == 'COMMIT' and mode == 'exit-before-commit':
            os._exit(73)
        if sql == 'COMMIT' and mode == 'hang-before-commit':
            print('ready', flush=True); time.sleep(60)
    db.set_trace_callback(cb)
    return db
sqlite3.connect = hooked
ledger.record(sys.argv[2], plan, sys.argv[5], sys.argv[6], sys.argv[7])
os._exit(74)
"""
    args = [sys.executable, "-c", script, str(ROOT), str(path), str(FIXTURE), mode, event_id, subject, fp]
    if mode == "hang-before-commit":
        p = subprocess.Popen(args, stdout=subprocess.PIPE, text=True)
        assert p.stdout.readline().strip() == "ready"
        p.kill()
        p.wait(20)
        return p.returncode
    return subprocess.run(args).returncode


@probe("lost ack after commit: identical retry is a no-op", "restart")
def _():
    path, _ = fresh()
    assert child(path, "exit-after-commit") == 74
    ledger.record(path, PLAN, "key", "", KEY)
    assert len(rows(path)) == 1
    return "child exited 74 after COMMIT; retry left 1 event"


@probe("lost ack retried under a NEW event ID is rejected", "restart")
def _():
    path, _ = fresh()
    assert child(path, "exit-after-commit") == 74
    msg = raises(ValueError, ledger.record, path, PLAN, "key-retry-2", "", KEY)
    assert len(rows(path)) == 1
    return f"{msg}; event IDs must be stable across restarts"


@probe("exit before first COMMIT rolls back the table creation", "restart")
def _():
    path, _ = fresh()
    assert child(path, "exit-before-commit") == 73
    assert not has_table(path)
    ledger.record(path, PLAN, "key", "", KEY)
    return "no ceremony_event after crash; retry committed 1 event"


@probe("hard kill holding RESERVED on a leaf insert: hot journal, readback, retry", "restart")
def _():
    path, owner = fresh()
    ledger.record(path, PLAN, "key", "", KEY)
    for s, l in LEAVES[:-1]:
        ledger.record(path, PLAN, "sign:" + s, s, l)
    s, l = LEAVES[-1]
    rc = child(path, "hang-before-commit", "sign:" + s, s, l)
    journal = Path(str(path) + "-journal")
    hot = journal.exists() and journal.stat().st_size > 0
    try:
        ledger.readback(path, PLAN)
        during = "returned (unexpected: complete)"
    except ValueError as e:
        during = f"ValueError: {e}"
    except sqlite3.Error as e:
        during = f"{type(e).__name__}: {e}"
    assert "complete)" not in during
    hold = fence.interrupted_a1_hold(path, owner)
    ledger.record(path, PLAN, "sign:" + s, s, l)
    assert ledger.readback(path, PLAN) == expected_log()
    return f"killed rc={rc}, hot journal={hot}; readback under hot journal -> {during}; inspection {hold}; retry completed"


@probe("fresh-process readback after restart matches", "restart")
def _():
    path, _ = fresh()
    complete(path)
    script = ("import json,sys;sys.path.insert(0,sys.argv[1]);from pathlib import Path;"
              "from tools import a1_ceremony_ledger as l;"
              "print(json.dumps(l.readback(sys.argv[2],json.loads(Path(sys.argv[3]).read_bytes())),sort_keys=True))")
    out = subprocess.run([sys.executable, "-c", script, str(ROOT), str(path), str(FIXTURE)],
                         capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == expected_log()
    return "separate interpreter read back the same complete log"


# ------------------------------------------------------------------ missing evidence

@probe("missing evidence: each case rejects readback", "missing")
def _():
    out = {}
    path, _ = fresh()
    out["no-table"] = raises(sqlite3.OperationalError, ledger.readback, path, PLAN)
    ledger.record(path, PLAN, "key", "", KEY)
    out["ca-only"] = raises(ValueError, ledger.readback, path, PLAN)
    for s, l in LEAVES[:-1]:
        ledger.record(path, PLAN, "sign:" + s, s, l)
    out["one-leaf-missing"] = raises(ValueError, ledger.readback, path, PLAN)
    missing = Path(tempfile.mkdtemp(prefix="a1cl-")) / "absent"
    out["no-file"] = raises(sqlite3.OperationalError, ledger.readback, missing, PLAN)
    assert not missing.exists()
    empty = Path(tempfile.mkdtemp(prefix="a1cl-")) / "empty"
    fence.initialize(empty)
    out["no-fence-row"] = raises(ValueError, ledger.readback, empty, PLAN)
    return out


@probe("leaf before CA key is rejected and leaves nothing", "missing")
def _():
    path, _ = fresh()
    s, l = LEAVES[0]
    msg = raises(ValueError, ledger.record, path, PLAN, "early", s, l)
    assert not has_table(path)
    return f"{msg}; CREATE TABLE rolled back"


@probe("plan with unrecorded planned leaf cannot complete", "missing")
def _():
    plan = copy.deepcopy(PLAN)
    plan["members"][0]["plannedLeafSHA256"] = None
    assert plan_digest(plan) == plan_digest(PLAN)
    path, _ = fresh(plan)
    ledger.record(path, plan, "key", "", KEY)
    s, l = LEAVES[0]
    out = {"record": raises(ValueError, ledger.record, path, plan, "sign:" + s, s, l)}
    for s2, l2 in LEAVES[1:]:
        ledger.record(path, plan, "sign:" + s2, s2, l2)
    out["readback"] = raises(ValueError, ledger.readback, path, plan)
    return out


@probe("malformed inputs are rejected before any write", "missing")
def _():
    path, _ = fresh()
    out = {}
    for label, args in {"blank-id": (" ", "", KEY), "none-id": (None, "", KEY),
                        "upper-hex": ("key", "", KEY.upper()), "short": ("key", "", KEY[:63]),
                        "int-fp": ("key", "", 5), "none-subject": ("key", None, KEY)}.items():
        out[label] = raises(ValueError, ledger.record, path, PLAN, *args)
    out["list-subject"] = raises(TypeError, ledger.record, path, PLAN, "key", [], KEY)
    assert not has_table(path)
    bad = copy.deepcopy(PLAN)
    bad["operationManifest"]["planDigest"] = "0" * 64
    out["manifest-digest"] = raises(ValueError, ledger.record, path, bad, "key", "", KEY)
    dup = copy.deepcopy(PLAN)
    dup["members"][1]["nodeID"] = dup["members"][0]["nodeID"]
    out["duplicate-node"] = raises(ValueError, ledger.record, path, dup, "key", "", KEY)
    return out


# ------------------------------------------------------------------ conflicting evidence

@probe("conflicting records are rejected and leave the ledger unchanged", "conflict")
def _():
    path, _ = fresh()
    ledger.record(path, PLAN, "key", "", KEY)
    before = rows(path)
    s, l = LEAVES[0]
    out = {}
    for label, args in {"second-ca-key": ("key-2", "", OTHER), "same-ca-new-id": ("key-2", "", KEY),
                        "reuse-id-other-subject": ("key", s, l), "foreign-subject": ("x", "unknown", l),
                        "wrong-leaf": ("x", s, OTHER), "leaf-is-ca-key": ("x", s, KEY)}.items():
        out[label] = raises(ValueError, ledger.record, path, PLAN, *args)
    ledger.record(path, PLAN, "sign:" + s, s, l)
    out["same-subject-new-id"] = raises(ValueError, ledger.record, path, PLAN, "sign:again", s, l)
    assert rows(path)[:1] == before and len(rows(path)) == 2
    return out


@probe("a rejected conflicting observation does not poison later readback", "conflict")
def _():
    path, _ = fresh()
    ledger.record(path, PLAN, "key", "", KEY)
    attempted = raises(ValueError, ledger.record, path, PLAN, "observed-second-key", "", OTHER)
    foreign = raises(ValueError, ledger.record, path, PLAN, "observed-foreign", "nod_FOREIGN", OTHER)
    for s, l in LEAVES:
        ledger.record(path, PLAN, "sign:" + s, s, l)
    got = ledger.readback(path, PLAN)
    assert got == expected_log() and got["caKeysCreated"] == 1
    doc = copy.deepcopy(PLAN)
    doc["checkpoint"]["readback"]["ceremonyLog"] = got
    hold = r2._ceremony_log_hold(doc, True)
    return (f"second key -> {attempted}; foreign leaf -> {foreign}; later readback returned a clean complete "
            f"log (caKeysCreated=1), and R2 _ceremony_log_hold on it -> {hold}. The observations that R2 maps to "
            f"HOLD_CUSTODY_UNRESOLVED / HOLD_FOREIGN_WRITER are not durably recorded")


@probe("expected fingerprints are not bound by plan_digest (first writer pins)", "conflict")
def _():
    alt = copy.deepcopy(PLAN)
    alt["newAuthority"]["caPublicKeySHA256"] = OTHER
    alt["members"][0]["plannedLeafSHA256"] = "cd" * 32
    same = plan_digest(alt) == plan_digest(PLAN)
    path, _ = fresh()
    ledger.record(path, alt, "key", "", OTHER)
    pinned = raises(ValueError, ledger.record, path, PLAN, "key-true", "", KEY)
    real = raises(ValueError, ledger.readback, path, PLAN)
    leaf_only = copy.deepcopy(PLAN)
    leaf_only["members"][0]["plannedLeafSHA256"] = "cd" * 32
    verdicts = {"real": r2.evaluate(PLAN), "ca-mutated": r2.evaluate(alt),
                "leaf-mutated": r2.evaluate(leaf_only)}
    return (f"same digest={same}; the first record accepted the mutated document's CA key; the real document's "
            f"key then -> {pinned}; real readback -> {real}; R2 evaluate (not called by the ledger) -> {verdicts}")


@probe("two processes with different CA keys under one digest: exactly one wins", "conflict")
def _():
    alt = copy.deepcopy(PLAN)
    alt["newAuthority"]["caPublicKeySHA256"] = OTHER
    tmp = Path(tempfile.mkdtemp(prefix="a1cl-"))
    alt_path = tmp / "alt.json"
    alt_path.write_text(json.dumps(alt))
    path, _ = fresh()
    script = ("import json,sys;sys.path.insert(0,sys.argv[1]);from pathlib import Path;"
              "from tools import a1_ceremony_ledger as l;p=json.loads(Path(sys.argv[3]).read_bytes());"
              "\ntry:\n l.record(sys.argv[2],p,'key','',p['newAuthority']['caPublicKeySHA256']);print('ok')"
              "\nexcept ValueError as e:\n print('reject',e)")
    procs = [subprocess.Popen([sys.executable, "-c", script, str(ROOT), str(path), str(f)],
                              stdout=subprocess.PIPE, text=True) for f in [FIXTURE, alt_path] * 3]
    outs = [p.communicate(60)[0].strip() for p in procs]
    keys = {r[3] for r in rows(path)}
    assert len(rows(path)) == 1 and len(keys) == 1
    return f"one key committed ({'planned' if KEY in keys else 'mutated'}); outputs={outs}"


# ------------------------------------------------------------------ writer ownership

@probe("stale or wrong writer plan is rejected for record and readback", "ownership")
def _():
    path, _ = fresh()
    out = {}
    for label, mutate in {"older-generation": lambda p: p["writerFence"].__setitem__("generation", 6),
                          "wrong-token": lambda p: p["writerFence"].__setitem__("token", "fence:other"),
                          "bool-generation": lambda p: p["writerFence"].__setitem__("generation", True)}.items():
        plan = copy.deepcopy(PLAN)
        mutate(plan)
        if plan["operationManifest"]:
            plan["operationManifest"]["planDigest"] = plan_digest(plan)
        out[label + ":record"] = raises(ValueError, ledger.record, path, plan, "key", "", KEY)
        out[label + ":readback"] = raises((ValueError, sqlite3.OperationalError), ledger.readback, path, plan)
    assert not has_table(path)
    return out


@probe("transfer away then fresh epoch: old events never satisfy the new plan", "ownership")
def _():
    path, owner = fresh()
    complete(path)
    moved = fence.transfer(path, owner, "interim", "interim-token")
    after = {"record": raises(ValueError, ledger.record, path, PLAN, "key", "", KEY),
             "readback": raises(ValueError, ledger.readback, path, PLAN),
             "inspection": fence.interrupted_a1_hold(path, owner)}
    nxt = copy.deepcopy(PLAN)
    nxt["writerFence"]["generation"] = moved.generation + 1
    nxt["operationManifest"]["planDigest"] = plan_digest(nxt)
    fence.transfer(path, moved, plan_digest(nxt), nxt["writerFence"]["token"])
    after["new-epoch-readback"] = raises(ValueError, ledger.readback, path, nxt)
    complete(path, nxt)
    assert ledger.readback(path, nxt) == expected_log()
    after["old-plan-rows-kept"] = sum(1 for r in rows(path) if r[0] == plan_digest(PLAN))
    return after


@probe("record never takes or moves the fence", "ownership")
def _():
    path, owner = fresh()
    with REAL_CONNECT(path) as db:
        before = db.execute("SELECT * FROM fence").fetchall() + db.execute("SELECT * FROM transfer_receipt").fetchall()
    complete(path)
    ledger.readback(path, PLAN)
    with REAL_CONNECT(path) as db:
        after = db.execute("SELECT * FROM fence").fetchall() + db.execute("SELECT * FROM transfer_receipt").fetchall()
    assert before == after
    return "fence and transfer_receipt rows identical before and after a full ceremony"


# ------------------------------------------------------------------ HOLD-only boundary

@probe("complete evidence still inspects as HOLD", "hold")
def _():
    path, owner = fresh()
    complete(path)
    a = fence.interrupted_a1_hold(path, owner)
    stale = fence.Writer(owner.plan_digest, owner.token, owner.generation - 1)
    b = fence.interrupted_a1_hold(path, stale)
    proc = subprocess.run([sys.executable, "tools/lan_pilot.py", "--help"], capture_output=True, text=True)
    return {"current-owner": a, "stale-owner": b, "lan_pilot_mentions_ceremony": "ceremony" in proc.stdout}


@probe("ledger surface has no network, subprocess, signing or activation entry point", "hold")
def _():
    src = (ROOT / "tools/a1_ceremony_ledger.py").read_text(encoding="utf-8")
    imports = sorted(line.strip() for line in src.splitlines() if line.startswith(("import ", "from ")))
    public = sorted(n for n in vars(ledger) if not n.startswith("_") and callable(getattr(ledger, n))
                    and getattr(getattr(ledger, n), "__module__", "") == ledger.__name__)
    for bad in ("socket", "subprocess", "requests", "http", "ssh", "paramiko", "cryptography", "os.system"):
        assert bad not in src, bad
    users = subprocess.run(["git", "grep", "-l", "a1_ceremony_ledger"], capture_output=True, text=True).stdout.split()
    return {"imports": imports, "public": public, "repo_references": users}


def main():
    for run in PROBES:
        run()
    ok = sum(r["ok"] for r in RESULTS)
    OUT.write_text(json.dumps({
        "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version, "platform": platform.platform(),
        "passed": ok, "total": len(RESULTS), "results": RESULTS}, indent=2, ensure_ascii=False), encoding="utf-8")
    for r in RESULTS:
        print(("PASS " if r["ok"] else "FAIL ") + r["area"] + " | " + r["probe"])
        if not r["ok"]:
            print("   ", r["detail"])
    print(f"{ok}/{len(RESULTS)} on Python {sys.version.split()[0]} SQLite {sqlite3.sqlite_version}")


main()
