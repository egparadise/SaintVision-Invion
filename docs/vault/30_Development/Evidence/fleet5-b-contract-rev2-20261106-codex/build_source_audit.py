"""Reproducible read-only Git-object inventory; no application imports/operations."""
from pathlib import Path
import ast
import hashlib
import json
import re
import subprocess

BASE = "72028cbac903c4415d9979f980a6e0f9948e914f"
OLD = "100f6f132132199d1204a76190f04712dd82de00"
OUT = Path(__file__).resolve().parent
ROOT = next(p for p in OUT.parents if (p / "AGENTS.md").exists())


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def dump(name, value):
    (OUT / name).write_bytes((json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode())


def blob(base, path):
    return git("show", f"{base}:{path}")


def classification(path):
    name = Path(path).stem
    if path.endswith(".sql") or "/db/models/" in path or path.startswith("migrations/"):
        return "SCHEMA_PERMISSION_REVIEW_REQUIRED"
    if "/tests/" in path:
        return "FIXTURE_ONLY_NO_REAL_B_AUTHORITY"
    if path.startswith("apps/"):
        return "UI_DIAGNOSTIC_DISPLAY_NO_ELIGIBILITY_AUTHORITY"
    if name in ("model_remote", "storage_sampling", "node_certificates"):
        return "CODEC_OR_DIAGNOSTIC_NO_ELIGIBILITY_AUTHORITY"
    if name in ("observer_worker", "lan_console", "storage_view", "operational_readiness"):
        return "DIAGNOSTIC_ONLY_NO_BUSINESS_PROOF"
    if name in ("containment", "node_transport", "build_execution", "observation"):
        return "TYPED_DIAGNOSTIC_STOP_ALLOWED_BUSINESS_AND_STATE_WRITES_CANONICAL_GATE"
    if name in ("node_channels", "lan_pilot", "remote_workspace_entry", "db"):
        return "OPERATOR_OR_TRANSACTION_ENTRY_CANONICAL_GATE_OR_REFUSE_B"
    if path.startswith("src/"):
        return "PUBLIC_ORM_OR_ROUTE_GUARDED_WRITER_OR_REFUSE_B"
    if name.startswith(("test_", "run_s04_", "check_migration_")):
        return "DISPOSABLE_TEST_ONLY_MUST_REFUSE_REAL_B_DATABASE"
    if path.startswith("deploy/"):
        return "ROLE_WRAPPER_CLOSED_ABI_OR_REFUSE_B"
    if path.startswith("services/control-plane/"):
        return "BUSINESS_CANONICAL_GATE_CURRENT_ADMISSION_REQUIRED"
    if path.startswith("tools/"):
        return "TOOL_BUSINESS_READINESS_GATE_OR_REFUSE_B"
    return "CONTRACT_BINDING_REGENERATION_REVIEW_REQUIRED"


def main():
    original_path = "docs/vault/30_Development/Evidence/fleet5-compute-storage-contract-20261105-codex/b-after-p0-proposal/contract-proposal-and-source-surface.json"
    original = json.loads(blob(OLD, original_path))
    inventory = []
    for old in original["sourceSurface"]:
        p = old["path"]
        raw = blob(BASE, p)
        lines = raw.decode("utf-8").splitlines()
        anchors = []
        for a in old["anchors"]:
            matches = [i for i, line in enumerate(lines, 1) if line.strip() == a["text"].strip()]
            anchors.append({"oldLine": a["line"], "currentLines": matches, "text": a["text"], "present": bool(matches)})
        inventory.append({"path": p, "sha256": hashlib.sha256(raw).hexdigest(), "gitBlob": git("rev-parse", f"{BASE}:{p}").decode().strip(), "sameBytesAsOriginal4fInventory": hashlib.sha256(raw).hexdigest() == old["sha256"], "anchors": anchors, "requiredAction": classification(p)})
    dump("source-inventory-72028.json", {"base": BASE, "originalProposal": OLD, "surfaceCount": len(inventory), "files": inventory})
    paths = git("ls-tree", "-r", "--name-only", BASE).decode("utf-8").splitlines()
    roots = ("src/", "apps/", "services/", "packages/", "contracts/", "tools/", "deploy/", "migrations/")
    pattern = re.compile(r"node_channels|NodeChannels|provision_channel|revoke_channel|assert_channel|ChannelProof")
    extra = re.compile(r"inv\.nodes|inv\.control_epoch|public\.nodes|public\.storage_contributions|StorageContribution|register_contribution|activate_contribution|revoke_contribution|enroll_node|record_heartbeat|mark_lost_nodes")
    # git grep selects exact committed objects in one process; no tracked source is executed.
    selected = git("grep", "-l", "-I", "-E", pattern.pattern + "|" + extra.pattern, BASE, "--", *[p for p in roots]).decode("utf-8").splitlines()
    files = []
    for selected_path in selected:
        p = selected_path.split(":", 1)[1]
        if Path(p).suffix not in (".py", ".go", ".sql", ".ps1", ".sh", ".ts", ".tsx", ".js", ".mjs"):
            continue
        raw = blob(BASE, p)
        source = raw.decode("utf-8-sig")
        functions = []
        if p.endswith(".py"):
            tree = ast.parse(source)
            functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        hits = []
        for i, line in enumerate(source.splitlines(), 1):
            direct = bool(pattern.search(line))
            if not direct and not extra.search(line):
                continue
            parents = [n for n in functions if n.lineno <= i <= n.end_lineno]
            parent = min(parents, key=lambda n: n.end_lineno - n.lineno).name if parents else "module/schema"
            hits.append({"line": i, "symbol": parent, "kind": "DIRECT_CHANNEL" if direct else "RELATED_NODE_EPOCH_CONTRIBUTION", "text": line.strip(), "classification": classification(p)})
        files.append({"path": p, "sha256": hashlib.sha256(raw).hexdigest(), "classification": classification(p), "hits": hits})
    locks = ["operation_cohort_routing", "control_epoch", "inv_nodes_sorted", "public_nodes_sorted", "contributions_sorted", "shared_channels_sorted", "role_assignment_current_admission", "runs", "approvals_grants", "resource_claims", "transfer_model_terminal", "nonce_evidence_cas_ledger_audit"]
    dump("caller-lock-graph.json", {
        "schemaVersion": "fleet5-b-source-caller-lock-audit:2", "base": BASE,
        "scope": "All tracked production/tool/schema source in eight roots; exact lexical channel census plus related Node/epoch/contribution paths and wrappers. Static inventory, not execution or whole-program dynamic-call proof.",
        "scanRoots": list(roots), "directRegex": pattern.pattern, "relatedRegex": extra.pattern,
        "sourceFileCount": len(files), "directChannelFileCount": sum(any(h["kind"] == "DIRECT_CHANNEL" for h in f["hits"]) for f in files),
        "unclassified": [], "files": files,
        "defaultUnknownCaller": "DENY_B_UNTIL_CLASSIFIED_AND_REVIEWED",
        "lockRanks": [{"rank": i, "name": n} for i, n in enumerate(locks)],
        "lockEdges": [[a,b] for a,b in zip(locks, locks[1:])],
        "currentSourceInversions": [
            {"path": "tools/lan_pilot.py", "outer": "_channel_row(lock=True)", "inner": "provision_channel", "risk": "channel before Node; B must reroute/refuse"},
            {"path": "services/control-plane/src/inv/storage_commit.py", "outer": "lock_run", "inner": "_scope Node/contribution/channel", "risk": "business before B prefix; discover then ordered new transaction"},
            {"path": "services/control-plane/src/inv/node_execution.py", "outer": "lock_run", "inner": "Node/channel", "risk": "receipt/state writer must gate or typed stop exception with same order"},
            {"path": "services/control-plane/src/inv/db.py", "outer": "transaction control_epoch FOR SHARE", "inner": "business/fence", "risk": "new B transaction entry must acquire fence/routing BEFORE epoch; generic helper refuses B until adapted"}
        ],
        "transitiveEntryClosure": [
            {"entry": "src/saintvision/api/v1/storage.py -> services/storage.py", "rule": "registration/activation/revoke/catalogue gates or REFUSE_B; current read_write mode cannot authorize B"},
            {"entry": "src/saintvision/api/v1/nodes.py -> services/nodes.py", "rule": "enroll/heartbeat/lost/status capability changes canonical B routing/writer gate or REFUSE_B"},
            {"entry": "control/dispatch/leases/placement/tool_gateway/build_adapter/build_product_runtime/build_execution/model_runtime", "rule": "all reservations/dispatch/build/model source and target Nodes use ordered role eligibility; no observation_only exemption"},
            {"entry": "storage_check_collect -> storage_commit.locked_issue -> storage_sampling -> NodeClient", "rule": "gate before state, typed collect authorization, after-reply recheck, ordered commit"},
            {"entry": "terminal -> NodeChannels.snapshot(observation_only=True) -> NodeClient", "rule": "business connect/frame/resume require role grant; stop/release typed safety only"},
            {"entry": "node_transfer -> snapshots -> NodeClient/read_chunk -> authorize callbacks", "rule": "gate before snapshot business mutation; callback uses already ordered transaction; current proof after network"},
            {"entry": "model_runtime/model_source/model_remote -> capture_channels/frozen_sources", "rule": "all source plus execution Nodes sorted; codec cannot grant authority; approval-creation path also gated"},
            {"entry": "tools/lan_pilot provision/revoke/normal/batch -> all deploy/lan wrappers in 46 inventory", "rule": "new role :4 exact planner/intent/fence; old :3 and Windows storage remap helpers REFUSE_B"},
            {"entry": "epoch restore/recovery/db operator direct SQL/migrations", "rule": "all affected B fences first or REFUSE_B; guarded privileges, no GUC-only bypass"}
        ],
        "retry": {"lockTimeoutMs": 2000, "statementTimeoutMs": 5000, "sqlstates": ["40P01", "40001", "55P03"], "action": "rollback transaction, retain committed global intent/fence, NEW ordered transaction reads exact tuple AND CAS ledger; bounded replay only"},
        "evidenceLevel": "SOURCE_STATIC_ONLY_NO_REAL_PG_CONCURRENCY"
    })
    print(json.dumps({"base": BASE, "originalSurfaces": len(inventory), "sameAs4f": sum(x["sameBytesAsOriginal4fInventory"] for x in inventory), "missingAnchors": sum(not a["present"] for x in inventory for a in x["anchors"]), "censusFiles": len(files), "directFiles": sum(any(h["kind"] == "DIRECT_CHANNEL" for h in f["hits"]) for f in files), "unclassified": 0}))


if __name__ == "__main__":
    main()
