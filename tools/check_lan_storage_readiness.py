"""Read-only pilot inventory; never authorizes deployment or grants privileges."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import psycopg
from psycopg.rows import dict_row

from lan_console import node_view
from lan_pilot import load


RELATIONS = (
    "public.storage_contributions", "public.storage_checks",
    "public.data_locations", "inv.storage_sample_requests",
    "inv.storage_sample_consumptions",
)
REQUIRED_FILES = (
    "Replace-Storage.ps1", "worker_storage_bridge.py", "worker_replace.py",
    "worker_replacement.py", "worker_storage.py",
)


def bundle_view(public):
    results = []
    for name in ("worker", "workspace-worker"):
        path = public / (name + ".zip")
        if not path.is_file():
            results.append({"bundle": name, "present": False})
            continue
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        checksum = public / (name + ".sha256")
        expected = checksum.read_text("ascii").strip().lower() if checksum.is_file() else None
        with ZipFile(path) as archive:
            # Exact root names, matching the launcher bundle layout. No extraction.
            names = archive.namelist()
            files = {f: names.count(f) == 1 for f in REQUIRED_FILES}
        results.append(dict(bundle=name, present=True, sha256=digest,
                            checksumMatches=expected == digest, requiredFiles=files))
    return results


def evaluate(report):
    blockers = []
    if not report["epochMatches"]:
        blockers.append("pilot-epoch-mismatch")
    if report["killSwitch"] is not False:
        blockers.append("tenant-kill-switch-active-or-unknown")
    if not report["nodes"] or any(not n["fresh"] for n in report["nodes"]):
        blockers.append("node-observation-unavailable-or-stale")
    if not report["nodes"] or any(n["profileVersion"] != "lan-workspace-v1" for n in report["nodes"]):
        blockers.append("workspace-profile-not-observed")
    if any(not r["present"] for r in report["relations"]):
        blockers.append("storage-relations-missing")
    if any(r["present"] and not r["selectAllowed"] for r in report["relations"]):
        blockers.append("observer-role-cannot-inspect-storage-registration")
    if not any(b.get("checksumMatches") and all(b.get("requiredFiles", {}).get(f) for f in REQUIRED_FILES)
               for b in report["bundles"]):
        blockers.append("public-storage-replacement-bundle-missing")
    return blockers


def inspect(state_path):
    state = load(state_path)
    with psycopg.connect(state["runtimeDSN"], row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '2s'")
        conn.execute("SELECT set_config('inv.tenant_id', %s, true)", (state["tenantId"],))
        role = conn.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
        if not role or role["rolsuper"] or role["rolbypassrls"]:
            raise ValueError("Read-only inventory requires a role without RLS bypass")
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        epoch = conn.execute("SELECT epoch FROM inv.control_epoch WHERE singleton").fetchone()
        gate = conn.execute("SELECT kill_switch FROM inv.tenant_controls WHERE tenant_id=%s", (state["tenantId"],)).fetchone()
        rows = conn.execute("""SELECT n.node_id,n.status,n.heartbeat_at,s.received_at,s.snapshot,
            c.endpoint,c.enabled AS channel_enabled,c.certificate_not_after
            FROM inv.nodes n LEFT JOIN inv.node_channels c
            ON (c.tenant_id,c.node_id,c.recovery_epoch)=(n.tenant_id,n.node_id,n.recovery_epoch)
            LEFT JOIN inv.node_resource_snapshots s
            ON (s.tenant_id,s.node_id,s.recovery_epoch,s.channel_version)=
               (n.tenant_id,n.node_id,n.recovery_epoch,c.version)
            WHERE n.tenant_id=%s AND n.node_id=%s""", (state["tenantId"], state["nodeId"])).fetchall()
        relations = []
        for name in RELATIONS:
            present = conn.execute("SELECT to_regclass(%s) IS NOT NULL AS present", (name,)).fetchone()["present"]
            allowed = conn.execute("SELECT has_table_privilege(current_user,%s,'SELECT') AS allowed", (name,)).fetchone()["allowed"] if present else None
            relations.append(dict(relation=name, present=present, selectAllowed=allowed))
        nodes = [{k: node_view(r, now)[k] for k in
                  ("nodeId", "address", "status", "fresh", "lastSnapshotAt", "profileVersion", "agentVersion")}
                 for r in rows]
    report = dict(observedAt=now.isoformat(), scope="read-only-pilot-storage-inventory",
                  epochMatches=bool(epoch and str(epoch["epoch"]) == state["epoch"]),
                  killSwitch=gate["kill_switch"] if gate else None, nodes=nodes,
                  relations=relations, bundles=bundle_view(state_path / "public"),
                  operationalAcceptanceAssessed=False,
                  unverified=["full-migration-integrity", "storage-owner-project-binding",
                              "remote-windows-wsl-bind-path", "signed-storage-evidence",
                              "remote-seven-workload-tests", "independent-review", "ci"])
    report["blockers"] = evaluate(report)
    report["deploymentAuthorized"] = False
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = inspect(args.state)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except Exception:
        # Database errors may contain connection details; never echo exceptions.
        print("Read-only inventory failed; no deployment authorized.", file=sys.stderr)
        return 2
    print(json.dumps(dict(blockers=report["blockers"], operationalAcceptanceAssessed=False)))
    return 1 if report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
