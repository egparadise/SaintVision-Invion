"""Independent probes of tools/a1_ceremony_ledger.py at e2f0cac3 against review bdf737d8, synthetic fixtures only.

Usage: python probe_e2f0.py <repo_root> <baseline_root> <out.json>
<baseline_root> is a detached checkout of bdf737d8 (f4af7bb8 ledger code), used only to build a legacy
ledger and to compare R2 evaluate() verdicts. Every ledger lives in a fresh temp directory. No network,
signer, key or fleet host is touched.
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
BASE = Path(sys.argv[2]).resolve()
OUT = Path(sys.argv[3]).resolve()
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
RESULTS, PROBES = [], []
REAL_CONNECT = sqlite3.connect


def probe(name, area):
    def wrap(fn):
        def run():
            started = time.perf_counter()
            try:
                RESULTS.append({"area": area, "probe": name, "ok": True, "detail": fn()})
            except Exception as exc:  # report, never hide
                RESULTS.append({"area": area, "probe": name, "ok": False,
                                "detail": f"{type(exc).__name__}: {exc}",
                                "trace": traceback.format_exc().splitlines()[-6:]})
            RESULTS[-1]["seconds"] = round(time.perf_counter() - started, 3)
        PROBES.append(run)
        return fn
    return wrap


def fresh(plan=PLAN):
    path = Path(tempfile.mkdtemp(prefix="a1e2-")) / "ledger"
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


def table(path, name):
    with REAL_CONNECT(path) as db:
        try:
            cols = "plan, event_id, subject, fingerprint"
            return db.execute(f"SELECT {cols} FROM {name} ORDER BY event_id, subject, fingerprint").fetchall()
        except sqlite3.OperationalError:
            return None


def events(path):
    return table(path, "ceremony_event")


def conflicts(path):
    return table(path, "ceremony_conflict")


def has_table(path, name):
    with REAL_CONNECT(path) as db:
        return bool(db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone())


def raises(exc, fn, *args, match=None):
    try:
        fn(*args)
    except exc as e:
        if match and match not in str(e):
            raise AssertionError(f"{type(e).__name__} without {match!r}: {e}")
        return f"{type(e).__name__}: {e}"
    except Exception as e:
        raise AssertionError(f"expected {exc.__name__}, got {type(e).__name__}: {e}")
    raise AssertionError(f"expected {exc.__name__}, call returned")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_log():
    return {**LOG, "signed": sorted(LOG["signed"], key=lambda e: e["subject"])}


def child(code, *args, env=None):
    return subprocess.run([sys.executable, "-c", code, str(ROOT), *map(str, args)],
                          capture_output=True, text=True, timeout=60, env=env)


PRELUDE = ("import sys,json,os,sqlite3;from pathlib import Path;sys.path.insert(0,sys.argv[1]);"
           "from tools import a1_ceremony_ledger as l;p=json.loads(Path(sys.argv[3]).read_bytes());")

S0, L0 = LEAVES[0]
KINDS = {
    # name: (needs complete ledger first, event_id, subject, fingerprint)
    "second-ca-key": (False, "key-2", "", OTHER),
    "same-ca-key-new-id (lost-ack retry)": (False, "key-retry", "", KEY),
    "event-id-reuse": (False, "key", S0, L0),
    "foreign-subject": (False, "foreign", "unplanned-node", KEY),
    "wrong-leaf": (False, "wrong", S0, OTHER),
    "ca-key-as-leaf": (False, "ca-as-leaf", S0, KEY),
    "same-subject-new-id": (True, "sign2:" + S0, S0, L0),
    "leaf-before-ca": (None, "early", S0, L0),
}


# ------------------------------------------------------------------ conflict persistence

@probe("each conflict kind is journaled once, keeps events unchanged and poisons readback", "conflict")
def _():
    out = {}
    for name, (pre, eid, subj, fp) in KINDS.items():
        path, _ = fresh()
        if pre is True:
            complete(path)
        elif pre is False:
            ledger.record(path, PLAN, "key", "", KEY)
        ev = events(path) or []
        first = raises(ValueError, ledger.record, path, PLAN, eid, subj, fp, match="Conflicting")
        for _ in range(2):  # identical retries
            raises(ValueError, ledger.record, path, PLAN, eid, subj, fp, match="Conflicting")
        assert (events(path) or []) == ev, name
        assert conflicts(path) == [(plan_digest(PLAN), eid, subj, fp)], (name, conflicts(path))
        if pre is not True:
            if pre is None:
                ledger.record(path, PLAN, "key", "", KEY)
                for s, leaf in LEAVES:
                    ledger.record(path, PLAN, "sign:" + s, s, leaf)
            else:
                for s, leaf in LEAVES:
                    ledger.record(path, PLAN, "sign:" + s, s, leaf)
        assert len(events(path)) == 1 + len(LEAVES), name
        ledger.record(path, PLAN, "key", "", KEY)  # identical replay of a valid event stays a no-op
        rb = raises(ValueError, ledger.readback, path, PLAN, match="conflicting")
        out[name] = {"record": first, "conflict_rows": 1, "readback_after_complete": rb}
    return out


@probe("committed conflict survives process exit and is seen by a fresh interpreter", "conflict")
def _():
    path, _ = fresh()
    complete(path)
    code = PRELUDE + (
        "\ntry:\n l.record(sys.argv[2],p,'key-2','',sys.argv[4])\nexcept ValueError as e:\n"
        " print('REJECTED',e,flush=True);os._exit(0)\nos._exit(3)")
    proc = child(code, path, FIXTURE, OTHER)
    assert proc.returncode == 0 and "REJECTED Conflicting" in proc.stdout, (proc.returncode, proc.stdout, proc.stderr)
    assert not Path(str(path) + "-journal").exists()
    code2 = PRELUDE + (
        "\ntry:\n l.readback(sys.argv[2],p)\nexcept ValueError as e:\n print(e);sys.exit(0)\nsys.exit(4)")
    proc2 = child(code2, path, FIXTURE)
    assert proc2.returncode == 0 and "conflicting" in proc2.stdout, (proc2.returncode, proc2.stdout, proc2.stderr)
    return {"child": proc.stdout.strip(), "fresh_readback": proc2.stdout.strip(), "rows": len(conflicts(path))}


@probe("crash before the conflict COMMIT surfaces no rejection and leaves nothing; retry journals it", "conflict")
def _():
    path, _ = fresh()
    complete(path)
    before = (events(path), conflicts(path))
    code = PRELUDE + (
        "\nreal=sqlite3.connect\ndef hooked(*a,**k):\n db=real(*a,**k)\n"
        " def cb(sql):\n  if sql.strip().upper().startswith('COMMIT'):\n   os._exit(75)\n"
        " db.set_trace_callback(cb)\n return db\nsqlite3.connect=hooked\n"
        "try:\n l.record(sys.argv[2],p,'key-2','',sys.argv[4])\nexcept ValueError as e:\n"
        " print('REJECTED',e,flush=True);os._exit(0)\nos._exit(3)")
    proc = child(code, path, FIXTURE, OTHER)
    assert proc.returncode == 75 and "REJECTED" not in proc.stdout, (proc.returncode, proc.stdout, proc.stderr)
    journal = Path(str(path) + "-journal").exists()
    ro = ledger.readback(path, PLAN)  # read-only snapshot of the last committed state
    assert ro == expected_log()
    after = (events(path), conflicts(path))  # rw connection rolls back any hot journal
    assert after == before, after
    msg = raises(ValueError, ledger.record, path, PLAN, "key-2", "", OTHER, match="Conflicting")
    assert len(conflicts(path)) == 1
    rb = raises(ValueError, ledger.readback, path, PLAN, match="conflicting")
    return {"child_exit": proc.returncode, "hot_journal_left": journal, "readback_before_retry": "complete",
            "retry": msg, "readback_after_retry": rb}


@probe("commit blocked past busy timeout raises OperationalError and journals nothing", "conflict")
def _():
    path, _ = fresh()
    complete(path)
    reader = REAL_CONNECT(path, timeout=0, isolation_level=None)
    reader.execute("BEGIN")
    reader.execute("SELECT count(*) FROM ceremony_event").fetchone()  # hold SHARED
    try:
        t = time.perf_counter()
        msg = raises(sqlite3.OperationalError, ledger.record, path, PLAN, "key-2", "", OTHER)
        waited = round(time.perf_counter() - t, 1)
    finally:
        reader.execute("COMMIT")
        reader.close()
    assert conflicts(path) == []
    raises(ValueError, ledger.record, path, PLAN, "key-2", "", OTHER, match="Conflicting")
    assert len(conflicts(path)) == 1
    return {"blocked": msg, "waited_s": waited, "after_release_retry": "journaled 1 conflict"}


@probe("8 processes: 6 identical CA events and 2 conflicting IDs -> 1 event, 2 conflicts", "conflict")
def _():
    path, _ = fresh()
    code = PRELUDE + (
        "\ntry:\n l.record(sys.argv[2],p,sys.argv[4],'',p['newAuthority']['caPublicKeySHA256']);print('OK')\n"
        "except ValueError as e:\n print('REJ',e)")
    ids = ["key"] * 6 + ["other-a", "other-b"]
    procs = [subprocess.Popen([sys.executable, "-c", code, str(ROOT), str(path), str(FIXTURE), i],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in ids]
    outs = [p.communicate(timeout=60)[0].strip() for p in procs]
    ok = sum(o == "OK" for o in outs)
    rej = sum(o.startswith("REJ Conflicting") for o in outs)
    assert ok == 6 and rej == 2, outs
    assert len(events(path)) == 1 and sorted(r[1] for r in conflicts(path)) == ["other-a", "other-b"]
    for s, leaf in LEAVES:
        ledger.record(path, PLAN, "sign:" + s, s, leaf)
    rb = raises(ValueError, ledger.readback, path, PLAN, match="conflicting")
    return {"ok": ok, "rejected": rej, "events": 1, "conflicts": 2, "readback_after_complete": rb}


@probe("8 threads with the same conflict -> one conflict row, all rejected", "conflict")
def _():
    path, _ = fresh()
    ledger.record(path, PLAN, "key", "", KEY)
    res = []

    def go():
        try:
            ledger.record(path, PLAN, "key-2", "", OTHER)
            res.append("ok")
        except ValueError as e:
            res.append(str(e))
    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]
    [t.join(30) for t in ts]
    assert res.count("Conflicting ceremony event") == 8, res
    assert len(conflicts(path)) == 1
    return "8/8 rejected as Conflicting; 1 conflict row"


@probe("readback snapshot holds while a concurrent conflict waits to commit", "conflict")
def _():
    path, _ = fresh()
    complete(path)
    paused, release, order, out = threading.Event(), threading.Event(), [], {}

    def hooked(*a, **k):
        db = REAL_CONNECT(*a, **k)
        if threading.current_thread().name == "reader":
            def cb(sql):
                if sql.startswith("SELECT 1 FROM ceremony_conflict"):
                    paused.set()
                    release.wait(10)
            db.set_trace_callback(cb)
        return db

    def reader():
        out["log"] = ledger.readback(path, PLAN)
        order.append("readback-done")

    def writer():
        try:
            ledger.record(path, PLAN, "key-2", "", OTHER)
        except ValueError as e:
            out["w"] = str(e)
        order.append("conflict-done")

    sqlite3.connect = hooked
    try:
        t1 = threading.Thread(target=reader, name="reader")
        t1.start()
        assert paused.wait(10)
        t2 = threading.Thread(target=writer, name="writer")
        t2.start()
        time.sleep(1.0)
        blocked = t2.is_alive()
        release.set()
        t1.join(15)
        t2.join(15)
    finally:
        sqlite3.connect = REAL_CONNECT
    assert blocked and order == ["readback-done", "conflict-done"], (blocked, order)
    assert out["log"] == expected_log() and out["w"] == "Conflicting ceremony event"
    rb = raises(ValueError, ledger.readback, path, PLAN, match="conflicting")
    return {"order": order, "writer_blocked_during_snapshot": blocked, "later_readback": rb}


# ------------------------------------------------------------------ stale writer exclusion

@probe("in-flight conflict record holds the write lock against a transfer", "stale")
def _():
    path, owner = fresh()
    ledger.record(path, PLAN, "key", "", KEY)
    paused, release, order = threading.Event(), threading.Event(), []

    def hooked(*a, **k):
        db = REAL_CONNECT(*a, **k)
        if threading.current_thread().name == "writer":
            def cb(sql):
                if sql.startswith("INSERT OR IGNORE INTO ceremony_conflict"):
                    paused.set()
                    release.wait(10)
            db.set_trace_callback(cb)
        return db

    def writer():
        try:
            ledger.record(path, PLAN, "key-2", "", OTHER)
        except ValueError:
            order.append("conflict-done")

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
    assert blocked and order == ["conflict-done", "transfer-done"], order
    assert len(conflicts(path)) == 1
    late = raises(ValueError, ledger.record, path, PLAN, "key-3", "", OTHER, match="Writer fence changed")
    assert len(conflicts(path)) == 1
    return {"order": order, "post_transfer": late}


@probe("after transfer away a stale writer can neither record nor journal a conflict", "stale")
def _():
    path, owner = fresh()
    ledger.record(path, PLAN, "key", "", KEY)
    fence.transfer(path, owner, "next-plan", "next-token")
    before = sha(path)
    out = {}
    for eid, subj, fp in [("sign:" + S0, S0, L0), ("key-2", "", OTHER), ("f", "foreign", KEY), ("key", "", KEY)]:
        out[eid] = raises(ValueError, ledger.record, path, PLAN, eid, subj, fp, match="Writer fence changed")
    out["readback"] = raises(ValueError, ledger.readback, path, PLAN, match="Writer fence changed")
    assert sha(path) == before and conflicts(path) == [] and len(events(path)) == 1
    out["inspection_stale"] = fence.interrupted_a1_hold(path, owner)
    assert out["inspection_stale"] == "HOLD_WRITER_FENCE"
    return out


@probe("stale or wrong fence plans are rejected before any write", "stale")
def _():
    out = {}
    for label, mut in [("older-generation", lambda p: p["writerFence"].update(generation=p["writerFence"]["generation"] - 1)),
                       ("wrong-token", lambda p: p["writerFence"].update(token="not-the-token")),
                       ("bool-generation", lambda p: p["writerFence"].update(generation=True))]:
        path, _ = fresh()
        plan = copy.deepcopy(PLAN)
        mut(plan)
        before = sha(path)
        a = raises((ValueError, KeyError, TypeError), ledger.record, path, plan, "key", "", KEY)
        b = raises((ValueError, KeyError, TypeError), ledger.readback, path, plan)
        assert sha(path) == before and not has_table(path, "ceremony_conflict")
        out[label] = {"record": a, "readback": b}
    return out


# ------------------------------------------------------------------ altered plan and fingerprint

def _mutate(value):
    if isinstance(value, str):
        return ("0" if value[:1] != "0" else "1") + value[1:]
    if isinstance(value, list):
        return value + value[:1] if value else ["00" * 32]
    if isinstance(value, dict):
        return {**value, "extra": 1}
    if value is None:
        return "00" * 32
    return value


def _set(plan, dotted, value):
    head, key = dotted.split(".", 1)
    if head in ("newAuthority", "controlPlaneClient", "trustTransition"):
        plan[head][key] = value
    else:
        next(m for m in plan["members"] if m["pc"] == head)[key] = value


@probe("every A1 output mutation is rejected by record and readback with no write", "plan")
def _():
    out, path0 = {}, None
    for dotted, value in r2.ceremony_outputs(PLAN).items():
        plan = copy.deepcopy(PLAN)
        _set(plan, dotted, _mutate(value))
        assert plan_digest(plan) == plan_digest(PLAN), dotted
        path, _ = fresh()
        before = sha(path)
        raises(ValueError, ledger.record, path, plan, "key", "", KEY, match="Unreviewed or invalid")
        raises(ValueError, ledger.readback, path, plan, match="Unreviewed or invalid")
        assert sha(path) == before and not has_table(path, "ceremony_event"), dotted
        binding = r2.digest({"planDigest": plan_digest(plan), "outputs": r2.ceremony_outputs(plan)})
        out[dotted] = {"pin_rejects": binding != "4f04475ca2f6844b46b824657ab087dea484a37a447b6793214711c62441a7de",
                       "validate_plan": r2.validate_plan(plan)}
        path0 = path
    assert all(v["pin_rejects"] for v in out.values())
    return {"mutations": len(out), "all_rejected_no_write": True,
            "also_rejected_by_validate_plan": sum(bool(v["validate_plan"]) for v in out.values()),
            "detail": out}


@probe("mutated CA key document can no longer pin first; the reviewed document still records", "plan")
def _():
    path, _ = fresh()
    bad = copy.deepcopy(PLAN)
    bad["newAuthority"]["caPublicKeySHA256"] = OTHER
    a = raises(ValueError, ledger.record, path, bad, "key", "", OTHER, match="Unreviewed")
    assert not has_table(path, "ceremony_event")
    complete(path)
    assert ledger.readback(path, PLAN) == expected_log()
    return {"mutated_first": a, "reviewed_then": "complete readback"}


@probe("pre-ceremony input, manifest and structure alterations are rejected", "plan")
def _():
    out = {}
    muts = {
        "planID": lambda p: p.update(planID=p["planID"] + "x"),
        "member-address": lambda p: p["members"][0].update(address="10.255.255.1"),
        "manifest-none": lambda p: p.update(operationManifest=None),
        "manifest-digest": lambda p: p["operationManifest"].update(planDigest="0" * 64),
        "duplicate-member": lambda p: p["members"].append(copy.deepcopy(p["members"][0])),
        "secret-marker": lambda p: p["controlPlaneClient"].update(spiffeURI="-----BEGIN PRIVATE KEY-----"),
    }
    for label, mut in muts.items():
        path, _ = fresh()
        plan = copy.deepcopy(PLAN)
        mut(plan)
        before = sha(path)
        out[label] = {"record": raises(ValueError, ledger.record, path, plan, "key", "", KEY),
                      "readback": raises(ValueError, ledger.readback, path, plan)}
        assert sha(path) == before
    return out


@probe("malformed observation inputs are refused before any write and never journaled", "plan")
def _():
    path, _ = fresh()
    ledger.record(path, PLAN, "key", "", KEY)
    before = sha(path)
    out = {}
    for label, args in {"upper-hex": ("x", S0, L0.upper()), "short": ("x", S0, L0[:63]),
                        "none-fp": ("x", S0, None), "int-subject": ("x", 7, L0),
                        "blank-id": (" ", S0, L0), "none-id": (None, S0, L0)}.items():
        out[label] = raises(ValueError, ledger.record, path, PLAN, *args)
    assert sha(path) == before and conflicts(path) == []
    return out


@probe("checkpoint fields outside the pin do not change the expected set", "plan")
def _():
    plan = copy.deepcopy(PLAN)
    plan["checkpoint"]["expectedRecoveryAction"] = "ABANDON_BEFORE_NEW_TRUST"
    v, e = r2.validate_plan(plan), r2.evaluate(plan)
    path, _ = fresh()
    complete(path, plan)
    got = ledger.readback(path, plan)
    assert v == [] and e and got == expected_log()
    return {"validate_plan": v, "evaluate": e, "ledger": "accepted; readback equals the reviewed ceremonyLog"}


@probe("only the reviewed p02 fixture is accepted; every other positive fixture is refused", "plan")
def _():
    acc, rej = [], []
    for f in sorted((CONTRACT_DIR / "fixtures/positive").glob("*.json")):
        doc = json.loads(f.read_bytes())
        try:
            ledger._expected(doc)
            acc.append(f.name)
        except (ValueError, KeyError, TypeError):
            rej.append(f.name)
    assert acc == [FIXTURE.name], acc
    return {"accepted": acc, "refused": len(rej)}


# ------------------------------------------------------------------ compatibility with existing evidence

EVAL = ("import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);"
        "import tools.check_fleet5_authority_replacement_r2 as r;out={}\n"
        "for f in sorted(r.CONTRACT_DIR.rglob('*.json')):\n"
        " try:\n  d=json.loads(f.read_bytes())\n except Exception:\n  continue\n"
        " try:\n  out[str(f.relative_to(r.CONTRACT_DIR))]=r.evaluate(d)\n"
        " except Exception as e:\n  out[str(f.relative_to(r.CONTRACT_DIR))]='EXC '+type(e).__name__\n"
        "print(json.dumps(out,sort_keys=True))")


@probe("R2 evaluate() verdicts are identical at bdf737d8 and e2f0cac3 for every contract JSON", "compat")
def _():
    a = subprocess.run([sys.executable, "-c", EVAL, str(BASE)], capture_output=True, text=True, cwd=BASE, timeout=300)
    b = subprocess.run([sys.executable, "-c", EVAL, str(ROOT)], capture_output=True, text=True, cwd=ROOT, timeout=300)
    assert a.returncode == 0 and b.returncode == 0, (a.stderr[-500:], b.stderr[-500:])
    da, db = json.loads(a.stdout), json.loads(b.stdout)
    assert da == db, [k for k in da if da.get(k) != db.get(k)][:10]
    clean = sum(v == [] for v in db.values())
    return {"documents": len(db), "evaluate_clean": clean, "rejected": len(db) - clean, "differences": 0,
            "sha256_of_verdicts": hashlib.sha256(b.stdout.encode()).hexdigest()}


@probe("legacy f4af7bb8 ledger is refused for record and readback without being modified", "compat")
def _():
    path, owner = fresh()
    code = ("import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);"
            "from tools import a1_ceremony_ledger as l;p=json.loads(Path(sys.argv[3]).read_bytes());"
            "l.record(sys.argv[2],p,'key','',p['newAuthority']['caPublicKeySHA256'])\n"
            "for e in p['checkpoint']['readback']['ceremonyLog']['signed']:\n"
            " l.record(sys.argv[2],p,'sign:'+e['subject'],e['subject'],e['leafSHA256'])\n"
            "print(json.dumps(l.readback(sys.argv[2],p)))")
    proc = subprocess.run([sys.executable, "-c", code, str(BASE), str(path), str(FIXTURE)],
                          capture_output=True, text=True, cwd=BASE, timeout=60)
    assert proc.returncode == 0, proc.stderr[-500:]
    assert json.loads(proc.stdout) == expected_log()
    assert has_table(path, "ceremony_event") and not has_table(path, "ceremony_conflict")
    before = sha(path)
    out = {"legacy_readback_at_f4af7bb8": "complete"}
    out["record_identical"] = raises(ValueError, ledger.record, path, PLAN, "key", "", KEY, match="reconciliation")
    out["record_conflict"] = raises(ValueError, ledger.record, path, PLAN, "key-2", "", OTHER, match="reconciliation")
    out["readback"] = raises(sqlite3.OperationalError, ledger.readback, path, PLAN)
    assert sha(path) == before and not has_table(path, "ceremony_conflict")
    out["inspection"] = fence.interrupted_a1_hold(path, owner)
    assert out["inspection"] == "HOLD_CUSTODY_UNRESOLVED"
    return out


@probe("conflict-only table set is also refused as incomplete", "compat")
def _():
    path, _ = fresh()
    with REAL_CONNECT(path) as db:
        db.execute("CREATE TABLE ceremony_conflict (plan TEXT, event_id TEXT, subject TEXT, fingerprint TEXT)")
    before = sha(path)
    a = raises(ValueError, ledger.record, path, PLAN, "key", "", KEY, match="reconciliation")
    b = raises(sqlite3.OperationalError, ledger.readback, path, PLAN)
    assert sha(path) == before
    return {"record": a, "readback": b}


@probe("fence and pilot code are byte-identical to the reviewed blobs", "compat")
def _():
    out = {}
    for rel in ("deploy/lan/a1_writer_fence.py", "tools/lan_pilot.py"):
        out[rel] = [subprocess.run(["git", "-C", str(r), "rev-parse", f"HEAD:{rel}"], capture_output=True,
                                   text=True).stdout.strip() for r in (BASE, ROOT)]
        assert out[rel][0] == out[rel][1]
    return out


# ------------------------------------------------------------------ HOLD-only

@probe("inspection stays HOLD with complete, conflicting and stale evidence", "hold")
def _():
    path, owner = fresh()
    complete(path)
    a = fence.interrupted_a1_hold(path, owner)
    raises(ValueError, ledger.record, path, PLAN, "key-2", "", OTHER)
    b = fence.interrupted_a1_hold(path, owner)
    c = fence.interrupted_a1_hold(path, fence.Writer(owner.plan_digest, owner.token, owner.generation - 1))
    assert (a, b, c) == ("HOLD_CUSTODY_UNRESOLVED", "HOLD_CUSTODY_UNRESOLVED", "HOLD_WRITER_FENCE")
    return {"complete": a, "with_conflict": b, "stale_owner": c}


@probe("no runtime consumer, network, subprocess or signing surface", "hold")
def _():
    src = (ROOT / "tools/a1_ceremony_ledger.py").read_text(encoding="utf-8")
    imports = sorted(line.strip() for line in src.splitlines() if line.startswith(("import ", "from ")))
    for bad in ("socket", "subprocess", "requests", "http", "ssh", "paramiko", "cryptography", "os.system"):
        assert bad not in src, bad
    users = subprocess.run(["git", "grep", "-l", "a1_ceremony_ledger"], capture_output=True, text=True).stdout.split()
    vp = subprocess.run(["git", "grep", "-l", "validate_plan"], capture_output=True, text=True).stdout.split()
    code_users = [u for u in users if u.endswith(".py") and "/Evidence/" not in u]
    assert code_users == ["tests/core/test_a1_ceremony_ledger.py"], code_users
    assert sorted(v for v in vp if "/Evidence/" not in v) == ["tools/a1_ceremony_ledger.py", "tools/check_fleet5_authority_replacement_r2.py"], vp
    proc = subprocess.run([sys.executable, "tools/lan_pilot.py", "--help"], capture_output=True, text=True)
    return {"imports": imports, "code_references": code_users, "validate_plan_references": vp,
            "lan_pilot_mentions_ceremony": "ceremony" in proc.stdout}


def main():
    for run in PROBES:
        run()
    ok = sum(r["ok"] for r in RESULTS)
    OUT.write_text(json.dumps({
        "candidate": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
        "baseline": subprocess.run(["git", "-C", str(BASE), "rev-parse", "HEAD"], capture_output=True,
                                   text=True).stdout.strip(),
        "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version, "platform": platform.platform(),
        "passed": ok, "total": len(RESULTS), "results": RESULTS}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    for r in RESULTS:
        print(("PASS " if r["ok"] else "FAIL ") + r["area"] + " | " + r["probe"])
        if not r["ok"]:
            print("   ", r["detail"])
    print(f"{ok}/{len(RESULTS)} on Python {sys.version.split()[0]} SQLite {sqlite3.sqlite_version}")


main()
