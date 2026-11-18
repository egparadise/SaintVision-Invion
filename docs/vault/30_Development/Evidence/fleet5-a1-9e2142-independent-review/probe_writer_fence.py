"""Adversarial probes for a1_writer_fence at 9e2142a9 (disposable tmp fixtures only)."""
import json, os, sqlite3, subprocess, sys, tempfile, time, hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

WT = Path(sys.argv[1]).resolve()
LAN = WT / "deploy" / "lan"
sys.path.insert(0, str(LAN))
import a1_writer_fence as F  # noqa: E402

PY = sys.executable
results = []


def rec(name, ok, detail=""):
    results.append({"probe": name, "ok": bool(ok), "detail": str(detail)[:400]})


def raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


def fresh(tag):
    d = Path(tempfile.mkdtemp(prefix=f"a1p-{tag}-"))
    p = d / "a1-writer.sqlite3"
    F.initialize(p)
    return d, p


def row(p):
    with sqlite3.connect(p) as db:
        f = db.execute("SELECT plan_digest, token, generation FROM fence").fetchall()
        try:
            r = db.execute("SELECT * FROM transfer_receipt").fetchall()
        except sqlite3.OperationalError:
            r = None
    return f, r


W = F.Writer

# 1 atomic receipt+fence commit: both rows present with matching generation
d, p = fresh("atomic")
a1 = F.transfer(p, None, "p", "a")
f, r = row(p)
rec("atomic.initial", f == [("p", "a", 1)] and r == [(1, None, None, None, 1)], (f, r))
b2 = F.transfer(p, a1, "q", "b")
f, r = row(p)
rec("atomic.second", f == [("q", "b", 2)] and r == [(1, "p", "a", 1, 2)], (f, r))

# 2 crash mid-transaction (fence updated, receipt not yet written, no commit) -> rollback
code = (
    "import os,sys,sqlite3;from pathlib import Path\n"
    "db=sqlite3.connect(sys.argv[1]);db.execute('BEGIN IMMEDIATE')\n"
    "db.execute(\"UPDATE fence SET plan_digest='q2',token='c',generation=3 WHERE generation=2\")\n"
    "os._exit(44)\n"
)
c = subprocess.run([PY, "-I", "-c", code, str(p)])
f, r = row(p)  # this connection rolls back any hot journal
rec("crash.midtxn.rolledback", c.returncode == 44 and f == [("q", "b", 2)] and r == [(1, "p", "a", 1, 2)], (c.returncode, f, r))
rec("crash.midtxn.retry_after", F.transfer(p, b2, "q2", "c") == W("q2", "c", 3))

# 2b crash mid-transaction inside real transfer(): monkeypatch to die after fence UPDATE, before receipt
d, p = fresh("crashreal")
a1 = F.transfer(p, None, "p", "a")
code = (
    "import os,sys,sqlite3\n"
    "sys.path.insert(0,sys.argv[2])\n"
    "import a1_writer_fence as F\n"
    "orig=sqlite3.Connection.execute\n"
    "class C(sqlite3.Connection):\n"
    "  def execute(self,sql,*a):\n"
    "    if sql.startswith('INSERT OR REPLACE INTO transfer_receipt'): os._exit(45)\n"
    "    return super().execute(sql,*a)\n"
    "real=sqlite3.connect\n"
    "F.sqlite3.connect=lambda *a,**k: real(*a,factory=C,**k)\n"
    "F.transfer(__import__('pathlib').Path(sys.argv[1]),F.Writer('p','a',1),'q','b')\n"
)
c = subprocess.run([PY, "-I", "-c", code, str(p), str(LAN)])
hot = p.with_name(p.name + "-journal").exists()
# inspection before any writer touches the hot journal must be HOLD and must not mutate
before = p.read_bytes()
hold = F.interrupted_a1_hold(p, a1)
rec("crash.prereceipt.hot_journal_inspect_hold", c.returncode == 45 and hold.startswith("HOLD_") and p.read_bytes() == before,
    (c.returncode, hot, hold))
f, r = row(p)
rec("crash.prereceipt.rolledback", f == [("p", "a", 1)] and r in ([(1, None, None, None, 1)],), (f, r))
rec("crash.prereceipt.retry_transfers", F.transfer(p, a1, "q", "b") == W("q", "b", 2))
rec("crash.prereceipt.replay", F.transfer(p, a1, "q", "b") == W("q", "b", 2))

# 3 lost ack after commit (os._exit after transfer) -> current-owner replay
d, p = fresh("lostack")
a1 = F.transfer(p, None, "p", "a")
code = ("import os,sys;sys.path.insert(0,sys.argv[2]);from pathlib import Path;import a1_writer_fence as F\n"
        "F.transfer(Path(sys.argv[1]),F.Writer('p','a',1),'q','b');os._exit(43)\n")
c = subprocess.run([PY, "-I", "-c", code, str(p), str(LAN)])
b2 = W("q", "b", 2)
rec("lostack.replay", c.returncode == 43 and F.transfer(p, a1, "q", "b") == b2 and row(p)[0] == [("q", "b", 2)])
rec("lostack.replay_twice_no_change", F.transfer(p, a1, "q", "b") == b2 and row(p) == ([("q", "b", 2)], [(1, "p", "a", 1, 2)]))
# conflicting retries against current successor
rec("conflict.same_prev_other_token", raises(lambda: F.transfer(p, a1, "q", "x")))
rec("conflict.same_prev_other_plan", raises(lambda: F.transfer(p, a1, "z", "b")))
rec("conflict.wrong_prev_plan", raises(lambda: F.transfer(p, W("z", "a", 1), "q", "b")))
rec("conflict.wrong_prev_token", raises(lambda: F.transfer(p, W("p", "z", 1), "q", "b")))
rec("conflict.initial_retry_after_second", raises(lambda: F.transfer(p, None, "p", "a")))
rec("conflict.initial_retry_other", raises(lambda: F.transfer(p, None, "q", "b")))
rec("state.unchanged_after_conflicts", row(p) == ([("q", "b", 2)], [(1, "p", "a", 1, 2)]), row(p))

# 4 ownership cycling A->B->A->B, all stale retries rejected
d, p = fresh("cycle")
g1 = F.transfer(p, None, "p", "a")
g2 = F.transfer(p, g1, "q", "b")
g3 = F.transfer(p, g2, "p", "a")
g4 = F.transfer(p, g3, "q", "b")
rec("cycle.generations", [g.generation for g in (g1, g2, g3, g4)] == [1, 2, 3, 4])
stale = [(None, "p", "a"), (g1, "q", "b"), (g2, "p", "a")]
rec("cycle.stale_rejected", all(raises(lambda s=s: F.transfer(p, *s)) for s in stale))
rec("cycle.current_replay_ok", F.transfer(p, g3, "q", "b") == g4)
# stale tuple equal in plan/token to current but older generation
rec("cycle.aba_old_gen_prev", raises(lambda: F.transfer(p, W("p", "a", 1), "q", "b")))
rec("cycle.state", row(p) == ([("q", "b", 4)], [(1, "p", "a", 3, 4)]), row(p))
# self-transfer (same plan/token) then stale self retry
g5 = F.transfer(p, g4, "q", "b")
rec("cycle.self_transfer_gen5", g5 == W("q", "b", 5))
rec("cycle.self_stale_retry_rejected", raises(lambda: F.transfer(p, g3, "q", "b")))
rec("cycle.self_current_replay", F.transfer(p, g4, "q", "b") == g5)

# 5 pre-upgrade ledger (fence only, no receipt table)
d = Path(tempfile.mkdtemp(prefix="a1p-legacy-"))
p = d / "a1-writer.sqlite3"
F.initialize(p)
with sqlite3.connect(p) as db:
    db.execute("INSERT INTO fence VALUES (1,'p','a',1)")
rec("legacy.no_infer_initial_retry", raises(lambda: F.transfer(p, None, "p", "a")))
rec("legacy.current_owner_transfer", F.transfer(p, W("p", "a", 1), "q", "b") == W("q", "b", 2))
rec("legacy.replay_after_upgrade", F.transfer(p, W("p", "a", 1), "q", "b") == W("q", "b", 2))
# legacy ledger at higher generation; a fabricated predecessor that matches nothing fails and creates nothing harmful
d = Path(tempfile.mkdtemp(prefix="a1p-legacy2-"))
p = d / "a1-writer.sqlite3"
F.initialize(p)
with sqlite3.connect(p) as db:
    db.execute("INSERT INTO fence VALUES (1,'q','b',2)")
rec("legacy.lost_ack_unprovable_rejected", raises(lambda: F.transfer(p, W("p", "a", 1), "q", "b")))
f, r = row(p)
rec("legacy.reject_leaves_fence_and_rolls_back_schema", f == [("q", "b", 2)] and r is None, (f, r))

# 6 mixed version: old-code transfer advances fence without receipt -> no replay of either
d, p = fresh("mixed")
a1 = F.transfer(p, None, "p", "a")
b2 = F.transfer(p, a1, "q", "b")
with sqlite3.connect(p) as db:  # simulate pre-9e21 code path
    db.execute("UPDATE fence SET plan_digest='r', token='c', generation=3 WHERE generation=2")
rec("mixed.stale_receipt_no_replay_old", raises(lambda: F.transfer(p, a1, "q", "b")))
rec("mixed.no_replay_new", raises(lambda: F.transfer(p, b2, "r", "c")))
rec("mixed.current_owner_continues", F.transfer(p, W("r", "c", 3), "s", "d") == W("s", "d", 4))

# 7 concurrency: threads, identical request x8 -> all same result, single generation advance
d, p = fresh("thr")
a1 = F.transfer(p, None, "p", "a")
bar = Barrier(8)
def same(_):
    bar.wait(timeout=10)
    return F.transfer(p, a1, "q", "b")
with ThreadPoolExecutor(8) as ex:
    out = list(ex.map(same, range(8)))
rec("thr.identical_all_same", out == [W("q", "b", 2)] * 8 and row(p)[0] == [("q", "b", 2)], out[:2])
# competing distinct successors x8 -> exactly one winner
bar2 = Barrier(8)
def comp(i):
    bar2.wait(timeout=10)
    try:
        return F.transfer(p, W("q", "b", 2), "r", f"t{i}")
    except ValueError:
        return None
with ThreadPoolExecutor(8) as ex:
    out = list(ex.map(comp, range(8)))
win = [o for o in out if o]
rec("thr.competing_one_winner", len(win) == 1 and row(p)[0] == [("r", win[0].token, 3)], out)

# 8 concurrency: separate processes, mixed identical + competing
d, p = fresh("proc")
a1 = F.transfer(p, None, "p", "a")
code = ("import sys,time;sys.path.insert(0,sys.argv[2]);from pathlib import Path;import a1_writer_fence as F\n"
        "t0=float(sys.argv[4])\n"
        "while time.time()<t0: pass\n"
        "try:\n r=F.transfer(Path(sys.argv[1]),F.Writer('p','a',1),'q',sys.argv[3]);print('OK',r.token,r.generation)\n"
        "except ValueError: print('REJECT')\n")
start = time.time() + 2.0
toks = ["b"] * 6 + ["x", "y"]
procs = [subprocess.Popen([PY, "-I", "-c", code, str(p), str(LAN), t, str(start)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for t in toks]
outs = [(t, *pr.communicate(timeout=60), pr.returncode) for t, pr in zip(toks, procs)]
f, r = row(p)
win_tok = f[0][1]
ok = all(rc == 0 for *_, rc in outs)
for t, so, se, rc in outs:
    so = so.strip()
    if t == win_tok:
        ok &= so == f"OK {t} 2"
    else:
        ok &= so == "REJECT"
rec("proc.mixed_one_token_wins_identicals_replay", ok and f[0][2] == 2 and r == [(1, "p", "a", 1, 2)], (win_tok, [(t, o.strip(), e[-200:]) for t, o, e, _ in outs]))

# 9 kill a process holding the RESERVED lock mid-transfer (hard kill), then recover
d, p = fresh("kill")
a1 = F.transfer(p, None, "p", "a")
code = ("import sys,sqlite3,time\n"
        "db=sqlite3.connect(sys.argv[1]);db.execute('BEGIN IMMEDIATE')\n"
        "db.execute(\"UPDATE fence SET token='zz', generation=2\")\n"
        "print('LOCKED',flush=True);time.sleep(60)\n")
pr = subprocess.Popen([PY, "-I", "-c", code, str(p)], stdout=subprocess.PIPE, text=True)
assert pr.stdout.readline().strip() == "LOCKED"
# while locked: inspection is HOLD and nonmutating; a writer times out without corrupting
hold_locked = F.interrupted_a1_hold(p, a1)
pr.kill(); pr.wait()
rec("kill.inspect_while_locked_hold", hold_locked.startswith("HOLD_"), hold_locked)
f, r = row(p)
rec("kill.rolled_back", f == [("p", "a", 1)], (f, r))
rec("kill.retry_after", F.transfer(p, a1, "q", "b") == W("q", "b", 2))

# 10 HOLD-only inspection: never returns non-HOLD, never mutates, CLI exit 2 always, does not create receipt table
d, p = fresh("hold")
inspected = []
before = p.read_bytes()
inspected.append(F.interrupted_a1_hold(p, W("p", "a", 1)))
rec("hold.empty_ledger", inspected[-1] == "HOLD_WRITER_FENCE" and p.read_bytes() == before)
a1 = F.transfer(p, None, "p", "a")
b2 = F.transfer(p, a1, "q", "b")
before = p.read_bytes()
for w in (a1, b2, W("q", "b", 3), W("q", "x", 2)):
    inspected.append(F.interrupted_a1_hold(p, w))
rec("hold.values", inspected[1:] == ["HOLD_WRITER_FENCE", "HOLD_CUSTODY_UNRESOLVED", "HOLD_WRITER_FENCE", "HOLD_WRITER_FENCE"] and p.read_bytes() == before, inspected)
# inspection on legacy ledger must not create transfer_receipt
d2 = Path(tempfile.mkdtemp(prefix="a1p-holdlegacy-"))
lp = d2 / "a1-writer.sqlite3"
F.initialize(lp)
with sqlite3.connect(lp) as db:
    db.execute("INSERT INTO fence VALUES (1,'p','a',1)")
lb = lp.read_bytes()
rec("hold.legacy_no_schema_write", F.interrupted_a1_hold(lp, W("p", "a", 1)) == "HOLD_CUSTODY_UNRESOLVED" and lp.read_bytes() == lb and row(lp)[1] is None)
# CLI over state dir with receipts
exp = d / "expected.json"
cli = []
for payload in ({"holderPlanDigest": "q", "token": "b", "generation": 2},
                {"holderPlanDigest": "p", "token": "a", "generation": 1},
                {"holderPlanDigest": "q", "token": "b", "generation": True},
                {"holderPlanDigest": "q", "token": "b", "generation": "2"},
                {}):
    exp.write_text(json.dumps(payload), encoding="utf-8")
    cp = subprocess.run([PY, str(LAN / "inspect_interrupted_a1.py"), "--state", str(d), "--expected-writer", str(exp)],
                        capture_output=True, text=True, cwd=str(d))
    cli.append((cp.returncode, cp.stdout.strip(), cp.stderr[-200:]))
rec("hold.cli", [c[:2] for c in cli] == [(2, "HOLD_CUSTODY_UNRESOLVED"), (2, "HOLD_WRITER_FENCE"), (2, "HOLD_WRITER_FENCE"), (2, "HOLD_WRITER_FENCE"), (2, "HOLD_WRITER_FENCE")] and p.read_bytes() == before, cli)

# 11 module surface: no signing/recovery entry points
import inspect as _i
pub = sorted(n for n, o in vars(F).items() if not n.startswith("_") and callable(o) and getattr(o, "__module__", "") == F.__name__)
rec("surface.public_callables", pub == ["Writer", "initialize", "interrupted_a1_hold", "transfer"], pub)
src = (LAN / "a1_writer_fence.py").read_text(encoding="utf-8") + (LAN / "inspect_interrupted_a1.py").read_text(encoding="utf-8")
rec("surface.no_network_or_exec", not any(k in src for k in ("socket", "subprocess", "requests", "urllib", "ssh", "os.system", "sign(")), "")

out = {"sha": subprocess.run(["git", "-C", str(WT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
       "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
       "passed": sum(r["ok"] for r in results), "total": len(results), "results": results}
print(json.dumps(out, indent=1))
sys.exit(0 if out["passed"] == out["total"] else 1)
