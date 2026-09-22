"""Collect restricted-container output, denial and lease-reclaim evidence (S03-DB).

Two lanes, each honest about what it could observe:

DB lane (real PostgreSQL, owner DSN or ``--disposable``): for every run in the
kernel ledger it records the physical stop receipt hash, the committed output
object (``inv.storage_objects.content_hash`` / ``size_bytes``), the evidence
envelope's ``outputSha256``, result completions, tool claims, execution
delivery error codes, output-ingestion errors, and every resource lease with
its release provenance (``stop_receipt`` or ``reservation_abort``).  Nothing is
written to the measured database.

Container lane (local Docker, ``--container-image``): launches probe
containers with exactly the constraints of the kernel sandbox launch plan
(``inv.sandbox.compile_launch``: network none, read-only rootfs, cap-drop ALL,
no-new-privileges, uid 65532, pids-limit 64) and records captured stdout /
stderr bytes and SHA-256, the rootfs-write denial, the network denial, the
effective uid and capability set.  When Docker or the image is unavailable the
lane is reported as ``measured: false`` with the reason -- never as a pass.

Expectations (violations -> exit 1; only judged on what was measured):
  C1 a terminal run (succeeded/failed/cancelled/stopped) holds no active lease;
  C2 a succeeded run has >=1 evidence, and for EVERY evidence a result completion
     and a result commitment carrying the SAME ``evidence_id`` exist (a completion
     or commitment keyed to another evidence is a violation), and the evidence
     ``outputSha256`` equals the committed storage object's ``content_hash``
     (which equals the commitment's ``content_hash``);
  C3 a failed run has no success evidence and no result completion;
  C4 every released lease carries a stop receipt or a reservation abort;
  P1 probe stdout/stderr are captured byte-exact (sha256 recorded, exit 0);
  P2 writing to the rootfs is denied;
  P3 the network namespace is isolated: the only interface is ``lo``, the route
     table is empty and an external address fails with ENETUNREACH (a loopback
     "connection refused" is NOT accepted as evidence); a control probe on the
     default bridge network must NOT look isolated, or P3 is non-discriminating;
  P4 the process runs as uid 65532 with an empty effective capability set.

Verdict: PASS only when every lane was measured AND had something to judge.  A DB
lane with zero runs, or an unmeasured container lane, yields UNMEASURED (exit 3),
never PASS.

Rerun (values not recorded):
  INV_AUDIT_DSN=<owner dsn> python tools/collect_container_evidence.py --container-image python:3.12-slim --out-dir <dir>
  python tools/collect_container_evidence.py --disposable --container-image python:3.12-slim --out-dir <dir>
Exit 0: PASS; 1: violations; 2: DB observation unavailable; 3: UNMEASURED (no violation,
but at least one lane had nothing to judge).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

TERMINAL_STATES = {"succeeded", "failed", "cancelled", "stopped"}
# Mirror of inv.sandbox.compile_launch's fixed plan fields (kept in sync by a self-test).
SANDBOX_PLAN = {"network": "none", "rootfsReadOnly": True, "capDropAll": True,
                "noNewPrivileges": True, "userId": 65532, "pidsLimit": 64}

PROBES = [
    {"id": "P1", "name": "output-capture", "argv": ["sh", "-c", "printf 'probe-stdout\\n'; printf 'probe-stderr\\n' 1>&2"],
     "expect": "exit 0, stdout 'probe-stdout\\n', stderr 'probe-stderr\\n'"},
    {"id": "P2", "name": "rootfs-write-denied", "argv": ["sh", "-c", "echo x > /etc/inv-probe"],
     "expect": "non-zero exit, stderr mentions read-only"},
    {"id": "P3", "name": "network-namespace-isolated",
     "argv": ["python3", "-c",
              "import os,json,socket,errno\n"
              "ifaces=sorted(os.listdir('/sys/class/net'))\n"
              "routes=[l.split()[0] for l in open('/proc/net/route').read().splitlines()[1:]]\n"
              "try:\n    socket.create_connection(('192.0.2.1', 9), timeout=3); err='connected'\n"
              "except OSError as e:\n    err=errno.errorcode.get(e.errno, type(e).__name__)\n"
              "print(json.dumps({'ifaces': ifaces, 'routes': routes, 'external_connect': err}))"],
     "expect": "ifaces == ['lo'], routes == [], external connect ENETUNREACH (loopback refusal is not evidence)"},
    {"id": "P4", "name": "uid-and-capabilities", "argv": ["sh", "-c", "id -u; grep CapEff /proc/self/status"],
     "expect": "uid 65532, CapEff 0000000000000000"},
]


# --------------------------------------------------------------------------- DB lane

def _q(conn, sql: str, params=()) -> list[dict]:
    from psycopg.rows import dict_row
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(sql, params).fetchall()


def collect_db(dsn: str, tenant: str | None = None) -> dict:
    """Observe the kernel run ledger (read-only; rolled back)."""
    import psycopg

    with psycopg.connect(dsn) as conn:
        conn.execute("SET statement_timeout = '30s'")
        conn.execute("SET TRANSACTION READ ONLY")
        dbname = conn.execute("SELECT current_database()").fetchone()[0]
        version = conn.execute("SHOW server_version").fetchone()[0]
        try:
            head = conn.execute("SELECT version_num FROM alembic_version").fetchone()
            migration = head[0] if head else None
        except psycopg.Error:
            migration = None
        where = "WHERE tenant_id = %s" if tenant else ""
        params = (tenant,) if tenant else ()
        runs = _q(conn, f"SELECT tenant_id::text, project_id, run_id, state, attempt, version FROM inv.runs {where} ORDER BY tenant_id, run_id", params)
        leases = _q(conn, f"SELECT tenant_id::text, run_id, lease_id, resource_id, amount, released_at, stop_receipt::text, reservation_abort::text, expires_at FROM inv.resource_leases {where} ORDER BY lease_id", params)
        claims = _q(conn, f"SELECT tenant_id::text, run_id, command_id::text, claim_id::text, node_id, not_after FROM inv.tool_claims {where} ORDER BY created_at", params)
        deliveries = _q(conn, f"SELECT tenant_id::text, run_id, command_id::text, node_id, phase, operation, attempts, last_error_code FROM inv.execution_deliveries {where} ORDER BY created_at", params)
        receipts = _q(conn, f"SELECT tenant_id::text, command_id::text, content_hash, recorded_at FROM inv.node_stop_receipts {where} ORDER BY recorded_at", params)
        commitments = _q(conn, f"SELECT tenant_id::text, run_id, attempt, command_id::text, object_id::text, evidence_id, content_hash, envelope FROM inv.result_commitments {where} ORDER BY prepared_at", params)
        completions = _q(conn, f"SELECT tenant_id::text, run_id, attempt, command_id::text, evidence_id, completed_at FROM inv.result_completions {where} ORDER BY completed_at", params)
        evidence = _q(conn, f"SELECT tenant_id::text, run_id, evidence_id, envelope, created_at FROM inv.evidence {where} ORDER BY created_at", params)
        objects = _q(conn, f"SELECT tenant_id::text, object_id::text, content_hash, size_bytes, state FROM inv.storage_objects {where} ORDER BY created_at", params)
        ingestions = _q(conn, f"SELECT tenant_id::text, command_id::text, attempts, finished, last_error FROM inv.output_ingestions {where}", params)
        audits = _q(conn, f"SELECT phase, count(*) AS n FROM inv.approval_audit {where} GROUP BY phase ORDER BY phase", params)
        conn.rollback()

    by_run: dict[str, dict] = {}
    for r in runs:
        by_run[r["run_id"]] = {
            "tenant_id": r["tenant_id"], "project_id": r["project_id"], "state": r["state"], "attempt": r["attempt"],
            "leases": [], "claims": [], "deliveries": [], "commitments": [], "completions": [], "evidence": [],
        }
    for group, rows in (("leases", leases), ("claims", claims), ("deliveries", deliveries),
                        ("commitments", commitments), ("completions", completions), ("evidence", evidence)):
        for row in rows:
            target = by_run.setdefault(row["run_id"], {"state": None, "orphan": True, "leases": [], "claims": [],
                                                       "deliveries": [], "commitments": [], "completions": [], "evidence": []})
            target[group].append(_json_safe(row))
    objects_by_id = {o["object_id"]: _json_safe(o) for o in objects}
    receipts_by_cmd = {r["command_id"]: _json_safe(r) for r in receipts}
    for run in by_run.values():
        for c in run["commitments"]:
            c["storage_object"] = objects_by_id.get(c["object_id"])
            c["stop_receipt"] = receipts_by_cmd.get(c["command_id"])
            env = c.get("envelope") or {}
            c["envelope_outputSha256"] = env.get("outputSha256") if isinstance(env, dict) else None
            c.pop("envelope", None)
        for e in run["evidence"]:
            env = e.get("envelope") or {}
            e["outputSha256"] = env.get("outputSha256") if isinstance(env, dict) else None
            e["result"] = env.get("result") if isinstance(env, dict) else None
            e.pop("envelope", None)
        run["active_leases"] = sum(1 for l in run["leases"] if l["released_at"] is None)
    return {
        "database": {"name": dbname, "server_version": version, "migration_head": migration},
        "tenant_filter": tenant,
        "runs": by_run,
        "counts": {"runs": len(runs), "leases": len(leases), "tool_claims": len(claims), "deliveries": len(deliveries),
                   "stop_receipts": len(receipts), "commitments": len(commitments), "completions": len(completions),
                   "evidence": len(evidence), "storage_objects": len(objects)},
        "denials": {
            "delivery_error_codes": sorted({d["last_error_code"] for d in deliveries if d["last_error_code"]}),
            "ingestion_errors": sorted({i["last_error"] for i in ingestions if i["last_error"]}),
            "approval_audit_phases": {a["phase"]: a["n"] for a in audits},
        },
        "measured": True,
    }


def _json_safe(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, (dt.datetime, dt.date)):
            out[k] = v.isoformat()
        elif isinstance(v, uuid.UUID):
            out[k] = str(v)
        else:
            out[k] = v
    return out


def evaluate_db(db: dict) -> list[dict]:
    violations: list[dict] = []
    if not db.get("measured"):
        return violations
    for run_id, run in db["runs"].items():
        state = run.get("state")
        if state in TERMINAL_STATES and run["active_leases"] > 0:
            violations.append({"rule": "C1", "run": run_id, "detail": f"{run['active_leases']} active lease(s) on {state} run"})
        if state == "succeeded":
            if not run["evidence"]:
                violations.append({"rule": "C2", "run": run_id, "detail": "succeeded run without evidence"})
            evidence_ids = {e["evidence_id"] for e in run["evidence"]}
            for comp in run["completions"]:
                if comp["evidence_id"] not in evidence_ids:
                    violations.append({"rule": "C2", "run": run_id, "detail": f"completion keyed to {comp['evidence_id']} which is not this run's evidence"})
            for e in run["evidence"]:
                if not [x for x in run["completions"] if x["evidence_id"] == e["evidence_id"]]:
                    violations.append({"rule": "C2", "run": run_id, "detail": f"evidence {e['evidence_id']} has no completion with the same evidence_id"})
                matching = [c for c in run["commitments"] if c["evidence_id"] == e["evidence_id"]]
                if not matching:
                    violations.append({"rule": "C2", "run": run_id, "detail": f"evidence {e['evidence_id']} has no commitment"})
                    continue
                c = matching[0]
                obj = c.get("storage_object") or {}
                if not e["outputSha256"] or e["outputSha256"] != obj.get("content_hash") or c["content_hash"] != obj.get("content_hash"):
                    violations.append({"rule": "C2", "run": run_id,
                                       "detail": f"evidence outputSha256 {str(e['outputSha256'])[:12]}… != committed object hash {str(obj.get('content_hash'))[:12]}…"})
        if state == "failed" and (run["evidence"] or run["completions"]):
            violations.append({"rule": "C3", "run": run_id, "detail": "failed run carries success evidence/completion"})
        for lease in run["leases"]:
            if lease["released_at"] is not None and not (lease["stop_receipt"] or lease["reservation_abort"]):
                violations.append({"rule": "C4", "run": run_id, "detail": f"lease {lease['lease_id']} released without stop receipt or reservation abort"})
    return violations


# --------------------------------------------------------------------------- container lane

def _docker_run(argv: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    try:
        import docker_diag
        return docker_diag.run(argv, timeout=timeout, capture_output=True)
    except Exception:  # docker_diag unavailable outside the repo: plain subprocess
        return subprocess.run(argv, capture_output=True, timeout=timeout)


def _parse_p3(stdout_head: str) -> dict | None:
    try:
        return json.loads(stdout_head.strip().splitlines()[-1])
    except Exception:
        return None


def _isolated(p3: dict | None) -> bool | None:
    if not p3:
        return None
    return p3.get("ifaces") == ["lo"] and p3.get("routes") == [] and p3.get("external_connect") == "ENETUNREACH"


def probe_container(image: str | None, network: str | None = None, with_control: bool = True) -> dict:
    """Run the probe set under the sandbox plan constraints; honest about unavailability.

    ``network`` overrides the plan's network mode (used for the control probe).  With
    ``with_control`` the P3 probe is repeated on the default bridge network and recorded
    under ``control``: the isolation signals must be absent there, or P3 proves nothing."""
    network = network or SANDBOX_PLAN["network"]
    lane = {"measured": False, "image": image, "plan": SANDBOX_PLAN, "network": network, "probes": []}
    if not image:
        lane["reason"] = "no --container-image given; the restricted-container lane was not measured"
        return lane
    probe_ver = _docker_run(["docker", "version", "--format", "{{.Server.Version}}"], timeout=30)
    if probe_ver.returncode != 0:
        lane["reason"] = "docker daemon unavailable on this host"
        return lane
    lane["docker_server_version"] = probe_ver.stdout.decode(errors="replace").strip()
    inspect = _docker_run(["docker", "image", "inspect", "--format", "{{.Id}}", image], timeout=30)
    if inspect.returncode != 0:
        lane["reason"] = f"image {image} is not present locally (not pulled: the collector never fetches images)"
        return lane
    lane["image_id"] = inspect.stdout.decode(errors="replace").strip()
    base = ["docker", "run", "--rm", "--network", network, "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--user", f"{SANDBOX_PLAN['userId']}:{SANDBOX_PLAN['userId']}",
            "--pids-limit", str(SANDBOX_PLAN["pidsLimit"]), "--memory", "128m", "--cpus", "0.5",
            "--label", "ai.saintvision.evidence=collect_container_evidence", image]
    for probe in PROBES:
        result = _docker_run(base + probe["argv"], timeout=90)
        out, err = result.stdout or b"", result.stderr or b""
        record = {
            "id": probe["id"], "name": probe["name"], "argv": probe["argv"], "expect": probe["expect"],
            "exit_code": result.returncode,
            "stdout_bytes": len(out), "stdout_sha256": hashlib.sha256(out).hexdigest(), "stdout_head": out[:300].decode(errors="replace"),
            "stderr_bytes": len(err), "stderr_sha256": hashlib.sha256(err).hexdigest(), "stderr_head": err[:200].decode(errors="replace"),
        }
        if probe["id"] == "P3":
            record["observed"] = _parse_p3(record["stdout_head"])
            record["isolated"] = _isolated(record["observed"])
        lane["probes"].append(record)
    lane["measured"] = True
    if with_control and network == "none":
        p3 = next(p for p in PROBES if p["id"] == "P3")
        control_base = [a if a != "none" else "bridge" for a in base]
        result = _docker_run(control_base + p3["argv"], timeout=90)
        head = (result.stdout or b"")[:300].decode(errors="replace")
        observed = _parse_p3(head)
        lane["control"] = {"network": "bridge", "exit_code": result.returncode, "observed": observed,
                           "isolated": _isolated(observed), "note": "isolation removed on purpose; must NOT look isolated"}
    return lane


def evaluate_container(lane: dict) -> list[dict]:
    violations: list[dict] = []
    if not lane.get("measured"):
        return violations
    probes = {p["id"]: p for p in lane["probes"]}
    p1 = probes.get("P1")
    if p1 and not (p1["exit_code"] == 0 and p1["stdout_sha256"] == hashlib.sha256(b"probe-stdout\n").hexdigest()
                   and p1["stderr_sha256"] == hashlib.sha256(b"probe-stderr\n").hexdigest()):
        violations.append({"rule": "P1", "detail": f"output not captured byte-exact (exit {p1['exit_code']}, stdout {p1['stdout_bytes']}B, stderr {p1['stderr_bytes']}B)"})
    p2 = probes.get("P2")
    if p2 and not (p2["exit_code"] != 0 and "read-only" in p2["stderr_head"].lower()):
        violations.append({"rule": "P2", "detail": f"rootfs write was not denied (exit {p2['exit_code']}: {p2['stderr_head'][:80]!r})"})
    p3 = probes.get("P3")
    if p3:
        if p3["exit_code"] == 127:
            p3["unmeasured"] = "python3 is absent in the image; network probe not measured"
        elif p3.get("isolated") is not True:
            violations.append({"rule": "P3", "detail": f"network namespace not proven isolated: {p3.get('observed') or p3['stdout_head'][:80]!r}"})
        control = lane.get("control")
        if control is not None and control.get("observed") is not None and control.get("isolated") is True:
            violations.append({"rule": "P3", "detail": "control probe on the bridge network also looks isolated: P3 is non-discriminating"})
    p4 = probes.get("P4")
    if p4:
        lines = p4["stdout_head"].split()
        uid_ok = lines[:1] == [str(SANDBOX_PLAN["userId"])]
        cap_ok = any(tok.strip("CapEff:").strip("0") == "" and tok.startswith("CapEff") or tok == "0000000000000000" for tok in lines)
        if not (p4["exit_code"] == 0 and uid_ok and cap_ok):
            violations.append({"rule": "P4", "detail": f"uid/capabilities not restricted: {p4['stdout_head'][:80]!r}"})
    return violations


# --------------------------------------------------------------------------- output

def _git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def provenance() -> dict:
    me = Path(__file__).resolve()
    dirty: list[str] = []
    try:
        status = subprocess.run(["git", "status", "--porcelain", "--", str(me)], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10).stdout
        dirty = [line[3:].strip() for line in status.splitlines() if line.strip()]
    except Exception:
        pass
    try:
        collector_sha = hashlib.sha256(me.read_bytes()).hexdigest()
    except OSError:
        collector_sha = None
    return {"git_sha": _git_sha(), "collector_sha256": collector_sha, "uncommitted_sources": dirty,
            "note": "git_sha is HEAD at collection time; when uncommitted_sources is non-empty the collector content hash identifies the code that ran."}


def _fmt_lease(l: dict) -> str:
    if l["released_at"] is None:
        return f"{l['lease_id']} ACTIVE"
    via = "stop_receipt" if l["stop_receipt"] else ("reservation_abort" if l["reservation_abort"] else "NONE")
    return f"{l['lease_id']} released via {via}"


def render_markdown(observation: dict, violations: list[dict]) -> str:
    db, lane, prov = observation["db"], observation["container"], observation["provenance"]
    lines = [
        "# Restricted container output / denial / lease-reclaim evidence (S03-DB)", "",
        f"- collected_at: {observation['collected_at']} · git HEAD `{prov['git_sha']}` · collector sha256 `{prov['collector_sha256']}` · uncommitted: {prov['uncommitted_sources'] or 'none'}",
        f"- verdict: **{verdict(observation, violations) if not violations else f'{len(violations)} violation(s)'}** (C1..C4 on the DB lane, P1..P4 on the container lane; a lane with nothing to judge makes the verdict UNMEASURED, never PASS)",
        *([f"- unmeasured: {r}" for r in unmeasured_reasons(observation)]),
        "- rerun: `INV_AUDIT_DSN=<owner dsn> python tools/collect_container_evidence.py --container-image <image> --out-dir <dir>` (DSN never recorded)",
    ]
    if observation.get("note"):
        lines.append(f"- condition: {observation['note']}")
    lines.append("")
    if violations:
        lines += ["## Violations", "", "| rule | object | detail |", "|---|---|---|"]
        lines += [f"| {v['rule']} | {v.get('run', '-')} | {v['detail']} |" for v in violations]
        lines.append("")
    lines += ["## DB lane", ""]
    if not db.get("measured"):
        lines += [f"**unmeasured** — {db.get('reason')}", ""]
    else:
        d = db["database"]
        lines += [f"database `{d['name']}` · PostgreSQL {d['server_version']} · migration head `{d['migration_head']}` · tenant filter {db['tenant_filter'] or 'all'}",
                  "", "counts: " + ", ".join(f"{k} {v}" for k, v in db["counts"].items()), ""]
        if not db["runs"]:
            lines += ["**no runs observed on this database** — output/hash/lease facts are unmeasured here (the Linux private Node provider that produces runs does not execute on this host).", ""]
        else:
            lines += ["| run | state | leases | claims | deliveries(last_error) | stop receipt hash | committed object (hash, bytes, state) | evidence outputSha256 | completions |", "|---|---|---|---|---|---|---|---|---|"]
            for run_id, run in db["runs"].items():
                leases = "; ".join(_fmt_lease(l) for l in run["leases"]) or "-"
                deliveries = "; ".join(f"{x['phase']}/{x['operation']}({x['last_error_code'] or 'ok'})" for x in run["deliveries"]) or "-"
                receipts = "; ".join((c.get("stop_receipt") or {}).get("content_hash", "-")[:12] for c in run["commitments"]) or "-"
                objs = "; ".join(f"{(c.get('storage_object') or {}).get('content_hash', '-')[:12]}…, {(c.get('storage_object') or {}).get('size_bytes', '-')}B, {(c.get('storage_object') or {}).get('state', '-')}" for c in run["commitments"]) or "-"
                ev = "; ".join(f"{e['evidence_id']}:{str(e['outputSha256'])[:12]}…({e['result']})" for e in run["evidence"]) or "-"
                lines.append(f"| `{run_id}` | {run['state']} | {leases} | {len(run['claims'])} | {deliveries} | {receipts} | {objs} | {ev} | {len(run['completions'])} |")
            lines.append("")
        den = db["denials"]
        lines += [f"denials observed: delivery error codes {den['delivery_error_codes'] or 'none'} · ingestion errors {den['ingestion_errors'] or 'none'} · approval audit phases {den['approval_audit_phases'] or 'none'}", ""]
    lines += ["## Container lane", ""]
    if not lane.get("measured"):
        lines += [f"**unmeasured** — {lane.get('reason')}", ""]
    else:
        lines += [f"image `{lane['image']}` (`{lane['image_id'][:19]}`) · docker server {lane['docker_server_version']} · plan {json.dumps(lane['plan'])}",
                  "", "| probe | exit | stdout (bytes, sha256, head) | stderr (bytes, sha256, head) | expectation |", "|---|---|---|---|---|"]
        for p in lane["probes"]:
            lines.append(f"| {p['id']} {p['name']} | {p['exit_code']} | {p['stdout_bytes']}, `{p['stdout_sha256'][:12]}…`, {p['stdout_head'].strip()[:90]!r} | {p['stderr_bytes']}, `{p['stderr_sha256'][:12]}…`, {p['stderr_head'].strip()[:60]!r} | {p['expect']}{' — ' + p['unmeasured'] if p.get('unmeasured') else ''} |")
        if lane.get("control"):
            c = lane["control"]
            lines.append(f"| control (network={c['network']}) | {c['exit_code']} | {json.dumps(c.get('observed'))} | - | isolated={c.get('isolated')} — {c['note']} |")
        lines.append("")
    return "\n".join(lines)


def assert_no_secrets(text: str, dsn: str | None) -> None:
    if not dsn:
        return
    from psycopg.conninfo import conninfo_to_dict
    if dsn in text:
        raise ValueError("evidence would embed the DSN")
    try:
        password = conninfo_to_dict(dsn).get("password")
    except Exception:
        password = None
    if password and password in text:
        raise ValueError("evidence would embed a password")


def write_evidence(observation: dict, violations: list[dict], out_dir: Path, label: str, dsn: str | None) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {**observation, "violations": violations, "verdict": verdict(observation, violations),
               "unmeasured": unmeasured_reasons(observation)}
    json_text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str)
    md_text = render_markdown(observation, violations)
    assert_no_secrets(json_text, dsn)
    assert_no_secrets(md_text, dsn)
    json_path, md_path = out_dir / f"{label}.json", out_dir / f"{label}.md"
    json_path.write_text(json_text + "\n", encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    return json_path, md_path


def disposable_database(admin_dsn: str):
    """CREATE DATABASE + alembic head; DROP on exit (no run ledger is seeded: this is an
    empty, honest baseline -- the self-test seeds a synthetic ledger to exercise C1..C4)."""
    import contextlib
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from sqlalchemy.engine import URL

    @contextlib.contextmanager
    def _cm():
        name = "inv_s03_" + uuid.uuid4().hex
        owner = make_conninfo(admin_dsn, dbname=name)
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            info = conninfo_to_dict(owner)
            url = URL.create("postgresql+psycopg", username=info.get("user"), password=info.get("password"),
                             host=info.get("host"), port=int(info.get("port", 5432)), database=name).render_as_string(hide_password=False)
            result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=REPO_ROOT,
                                    env={**os.environ, "INV_MIGRATION_DSN": url, "INV_DATABASE_URL": url}, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError("alembic upgrade failed (credential-bearing output suppressed)")
            yield owner
        finally:
            assert name.startswith("inv_s03_") and len(name) == 40
            with psycopg.connect(admin_dsn, autocommit=True) as conn:
                conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
    return _cm()


def collect(dsn: str | None, image: str | None, tenant: str | None = None, note: str | None = None) -> dict:
    if dsn:
        db = collect_db(dsn, tenant)
    else:
        db = {"measured": False, "reason": "no DSN given; DB lane not measured"}
    return {
        "collector": "tools/collect_container_evidence.py",
        "collected_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "provenance": provenance(),
        "note": note,
        "db": db,
        "container": probe_container(image),
    }


def evaluate(observation: dict) -> list[dict]:
    return evaluate_db(observation["db"]) + evaluate_container(observation["container"])


def unmeasured_reasons(observation: dict) -> list[str]:
    """Why the observation cannot be a PASS even without violations."""
    reasons = []
    db, lane = observation["db"], observation["container"]
    if not db.get("measured"):
        reasons.append(f"db lane unmeasured: {db.get('reason')}")
    elif db["counts"]["runs"] == 0:
        reasons.append("db lane observed 0 runs: output/hash/lease facts unmeasured")
    if not lane.get("measured"):
        reasons.append(f"container lane unmeasured: {lane.get('reason')}")
    else:
        for p in lane["probes"]:
            if p.get("unmeasured"):
                reasons.append(f"{p['id']} unmeasured: {p['unmeasured']}")
    return reasons


def verdict(observation: dict, violations: list[dict]) -> str:
    if violations:
        return "VIOLATIONS"
    return "UNMEASURED" if unmeasured_reasons(observation) else "PASS"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dsn", default=os.environ.get("INV_AUDIT_DSN"), help="owner DSN (default: $INV_AUDIT_DSN); never recorded")
    parser.add_argument("--disposable", action="store_true", help="create an empty migrated database from $INV_TEST_ADMIN_DSN, measure, drop")
    parser.add_argument("--no-db", action="store_true", help="skip the DB lane (container lane only)")
    parser.add_argument("--tenant", default=None)
    parser.add_argument("--container-image", default=None, help="local image to probe under the sandbox plan (never pulled)")
    parser.add_argument("--out-dir", default=str(REPO_ROOT / "docs/vault/30_Development/Evidence/container-boundary"))
    parser.add_argument("--label", default=None)
    parser.add_argument("--note", default=None, help="free-text run condition recorded in the evidence")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    dsn = None if args.no_db else args.dsn
    try:
        if args.disposable and not args.no_db:
            admin = os.environ.get("INV_TEST_ADMIN_DSN")
            if not admin:
                print("INV_TEST_ADMIN_DSN is required for --disposable", file=sys.stderr)
                return 2
            with disposable_database(admin) as dsn:
                observation = collect(dsn, args.container_image, args.tenant, args.note)
        else:
            if not dsn and not args.no_db:
                print("--dsn / INV_AUDIT_DSN is required (or --no-db)", file=sys.stderr)
                return 2
            observation = collect(dsn, args.container_image, args.tenant, args.note)
    except Exception as error:
        print(f"observation unavailable: {type(error).__name__}", file=sys.stderr)
        return 2
    violations = evaluate(observation)
    result = verdict(observation, violations)
    label = args.label or "container-{}-{}".format(observation["provenance"]["git_sha"] or "nogit", dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d"))
    json_path, md_path = write_evidence(observation, violations, Path(args.out_dir), label, dsn)
    if args.json:
        print(json.dumps({**observation, "violations": violations}, indent=2, ensure_ascii=False, default=str))
    db, lane = observation["db"], observation["container"]
    print(f"{result if not violations else 'VIOLATIONS ' + str(len(violations))}: db={'runs ' + str(db['counts']['runs']) if db.get('measured') else 'unmeasured'}"
          f" container={'measured ' + str(len(lane['probes'])) + ' probes' if lane.get('measured') else 'unmeasured'} -> {md_path}")
    for v in violations:
        print(f"  {v['rule']} {v.get('run', '')}: {v['detail']}")
    for r in unmeasured_reasons(observation):
        print(f"  unmeasured: {r}")
    return {"PASS": 0, "VIOLATIONS": 1, "UNMEASURED": 3}[result]


if __name__ == "__main__":
    sys.exit(main())
