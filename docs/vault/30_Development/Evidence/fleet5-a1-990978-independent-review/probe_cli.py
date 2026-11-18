"""Adversarial probes of deploy/lan/inspect_interrupted_a1.py using disposable fixtures.

argv: <worktree> <python exe> [<python exe> ...]
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

WT = Path(sys.argv[1]).resolve()
PYS = sys.argv[2:]
SCRIPT = WT / "deploy" / "lan" / "inspect_interrupted_a1.py"
sys.path.insert(0, str(WT / "deploy" / "lan"))
import a1_writer_fence as fence  # noqa: E402

results = []


def run(py, state, expected, cwd, extra=()):
    args = [py, *extra, str(SCRIPT)]
    if state is not None:
        args += ["--state", str(state)]
    if expected is not None:
        args += ["--expected-writer", str(expected)]
    p = subprocess.run(args, capture_output=True, text=True, cwd=cwd, timeout=60)
    return p.returncode, p.stdout.strip(), p.stderr.strip()[-300:]


def check(name, got, want_rc, want_out):
    rc, out, err = got
    ok = rc == want_rc and out == want_out
    results.append({"probe": name, "ok": ok, "rc": rc, "stdout": out, "stderr_tail": err if not ok else ""})


def snapshot(d: Path):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.iterdir())}


for py in PYS:
    ver = subprocess.run([py, "-c", "import sys;print(sys.version.split()[0])"], capture_output=True, text=True).stdout.strip()
    with tempfile.TemporaryDirectory(dir=str(Path(__file__).parent), ignore_cleanup_errors=True) as tmp:
        tmp = Path(tmp)
        cwd = tmp  # run from an unrelated cwd: standalone, not repo-root dependent
        exp = tmp / "expected.json"
        exp.write_text(json.dumps({"holderPlanDigest": "plan", "token": "first", "generation": 1}))
        tag = f"py{ver}"

        absent = tmp / "absent"
        check(f"{tag} missing state dir", run(py, absent, exp, cwd), 2, "HOLD_WRITER_FENCE")
        results.append({"probe": f"{tag} missing state not created", "ok": not absent.exists()})

        state = tmp / "state"
        state.mkdir()
        ledger = state / "a1-writer.sqlite3"
        fence.initialize(ledger)
        check(f"{tag} initialized but no owner", run(py, state, exp, cwd), 2, "HOLD_WRITER_FENCE")
        w1 = fence.transfer(ledger, None, "plan", "first")
        before = snapshot(state)
        check(f"{tag} matching owner", run(py, state, exp, cwd), 2, "HOLD_CUSTODY_UNRESOLVED")
        for i in range(20):
            run(py, state, exp, cwd)
        results.append({"probe": f"{tag} 21 inspections leave state dir byte-identical, no sidecars",
                        "ok": snapshot(state) == before, "files": list(snapshot(state))})

        for label, body in [
            ("wrong token", {"holderPlanDigest": "plan", "token": "other", "generation": 1}),
            ("wrong plan", {"holderPlanDigest": "x", "token": "first", "generation": 1}),
            ("wrong generation", {"holderPlanDigest": "plan", "token": "first", "generation": 2}),
            ("generation as string", {"holderPlanDigest": "plan", "token": "first", "generation": "1"}),
            ("generation bool", {"holderPlanDigest": "plan", "token": "first", "generation": True}),
            ("generation float", {"holderPlanDigest": "plan", "token": "first", "generation": 1.0}),
            ("generation zero", {"holderPlanDigest": "plan", "token": "first", "generation": 0}),
            ("empty token", {"holderPlanDigest": "plan", "token": "", "generation": 1}),
            ("token null", {"holderPlanDigest": "plan", "token": None, "generation": 1}),
            ("missing key", {"holderPlanDigest": "plan", "generation": 1}),
            ("empty object", {}),
            ("list", ["plan", "first", 1]),
            ("string", "plan"),
            ("number", 1),
        ]:
            bad = tmp / "bad.json"
            bad.write_text(json.dumps(body))
            check(f"{tag} expected {label}", run(py, state, bad, cwd), 2, "HOLD_WRITER_FENCE")
        for label, raw in [("invalid json", b"{not json"), ("non-utf8", b"\xff\xfe\x00{"), ("empty file", b"")]:
            bad = tmp / "bad.json"
            bad.write_bytes(raw)
            check(f"{tag} expected {label}", run(py, state, bad, cwd), 2, "HOLD_WRITER_FENCE")
        check(f"{tag} expected file missing", run(py, state, tmp / "nope.json", cwd), 2, "HOLD_WRITER_FENCE")
        check(f"{tag} expected path is a directory", run(py, state, tmp, cwd), 2, "HOLD_WRITER_FENCE")

        # successor generation: old identity loses, new identity matches
        fence.transfer(ledger, w1, "plan2", "second")
        check(f"{tag} stale gen1 after transfer", run(py, state, exp, cwd), 2, "HOLD_WRITER_FENCE")
        exp2 = tmp / "expected2.json"
        exp2.write_text(json.dumps({"holderPlanDigest": "plan2", "token": "second", "generation": 2}))
        check(f"{tag} current gen2", run(py, state, exp2, cwd), 2, "HOLD_CUSTODY_UNRESOLVED")

        # exclusive write lock held by another connection -> HOLD, not a crash
        lock = sqlite3.connect(ledger, isolation_level=None, timeout=0)
        lock.execute("BEGIN EXCLUSIVE")
        check(f"{tag} exclusive lock held", run(py, state, exp2, cwd), 2, "HOLD_WRITER_FENCE")
        lock.execute("ROLLBACK")
        lock.close()
        check(f"{tag} after lock released", run(py, state, exp2, cwd), 2, "HOLD_CUSTODY_UNRESOLVED")

        # empty ledger (crash between file create and CREATE TABLE)
        s2 = tmp / "s2"; s2.mkdir(); (s2 / "a1-writer.sqlite3").write_bytes(b"")
        check(f"{tag} empty ledger", run(py, s2, exp, cwd), 2, "HOLD_WRITER_FENCE")
        try:
            fence.initialize(s2 / "a1-writer.sqlite3"); reinit = "succeeded"
        except FileExistsError:
            reinit = "FileExistsError"
        results.append({"probe": f"{tag} empty ledger re-initialize", "ok": reinit == "FileExistsError", "observed": reinit})
        # corrupt ledger
        s3 = tmp / "s3"; s3.mkdir(); (s3 / "a1-writer.sqlite3").write_bytes(os.urandom(4096))
        check(f"{tag} corrupt ledger", run(py, s3, exp, cwd), 2, "HOLD_WRITER_FENCE")
        # ledger is a directory
        s4 = tmp / "s4"; s4.mkdir(); (s4 / "a1-writer.sqlite3").mkdir()
        check(f"{tag} ledger path is dir", run(py, s4, exp, cwd), 2, "HOLD_WRITER_FENCE")
        # --state is a regular file
        sf = tmp / "statefile"; sf.write_text("x")
        check(f"{tag} state is a file", run(py, sf, exp, cwd), 2, "HOLD_WRITER_FENCE")
        # foreign schema: a different table named fence with a forged extra row layout
        s5 = tmp / "s5"; s5.mkdir()
        db = sqlite3.connect(s5 / "a1-writer.sqlite3")
        with db:
            db.execute("CREATE TABLE fence (singleton, plan_digest, token, generation)")
            db.execute("INSERT INTO fence VALUES (1, 'plan', 'first', '1')")
        db.close()
        check(f"{tag} forged schema text generation", run(py, s5, exp, cwd), 2, "HOLD_WRITER_FENCE")

        # usage errors: argparse also exits 2 but with empty stdout
        check(f"{tag} missing --state", run(py, None, exp, cwd), 2, "")
        check(f"{tag} missing --expected-writer", run(py, state, None, cwd), 2, "")
        # isolated mode (-I implies -P: script dir not on sys.path)
        rc, out, err = run(py, state, exp2, cwd, extra=("-I",))
        results.append({"probe": f"{tag} python -I", "ok": rc != 0 and out in ("", "HOLD_CUSTODY_UNRESOLVED"),
                        "rc": rc, "stdout": out, "stderr_tail": err[-160:]})

summary = {"passed": sum(r["ok"] for r in results), "total": len(results), "results": results}
out = Path(__file__).with_name("probe-result.json")
out.write_text(json.dumps(summary, indent=1))
print(summary["passed"], "/", summary["total"])
for r in results:
    if not r["ok"] or "python -I" in r["probe"] or "re-initialize" in r["probe"]:
        print(json.dumps(r))
