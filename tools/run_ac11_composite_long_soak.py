"""Build the AC-11 composite long-soak producer report without inventing evidence.

``dry-run`` traverses the exact registered case/fault universe with synthetic
LAN-pilot state only.  Its report is permanently reference-only.  ``physical``
performs the same strict inventory/topology preflight, but this repository does
not own the G-24 fault-control adapter; it therefore stops before any action and
reports BLOCKED_EXTERNAL until that operator resource is supplied.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import subprocess
import sys
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
for import_root in (ROOT, ROOT / "tools"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from tools.five_node_lab_preflight import (
    FIVE_NODE_INVENTORY_SCHEMA_VERSION,
    five_node_inventory_revision,
    validate_five_node_inventory,
)
from tools.import_ac11_composite_long_soak import (
    ALLOWED_FAULT_CLASSES_BY_PREFIX,
    CASE_IDENTITIES,
    DRY_RUN_PURPOSE,
    FAULT_CLASSES,
    RepositoryGit,
    _canonical_sha,
    import_report,
)
from tools.lan_pilot import manifest_for_node, normalized_state, validate_node_ips

G19_SCHEMA_VERSION = "s01-readiness-inventory:1"
REPORT_SCHEMA_VERSION = "1.0.0"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_NODE_ID = re.compile(r"^nod_[A-Za-z0-9][A-Za-z0-9_-]{0,126}$")


class InventoryError(ValueError):
    """The supplied G-19 inventory cannot authorize a composite run."""


def _exact(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InventoryError(f"{where} must be an object")
    if set(value) != keys:
        raise InventoryError(f"{where} has missing, null, or unknown fields")
    if any(value[key] is None for key in keys):
        raise InventoryError(f"{where} has missing, null, or unknown fields")
    return value


def _nonempty(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InventoryError(f"{where} must be a non-empty string")
    return value


def _integer(value: Any, where: str, *, allow_zero: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < (0 if allow_zero else 1):
        raise InventoryError(f"{where} must be a valid integer")
    return value


def validate_g19_inventory(payload: Any) -> dict[str, Any]:
    """Validate the strict #224 G-19 inventory and AC-11 topology subset."""

    root = _exact(payload, {"schemaVersion", "topology", "hostnames", "nodes"}, "inventory")
    if root["schemaVersion"] != G19_SCHEMA_VERSION:
        raise InventoryError("inventory schemaVersion is not supported")
    if root["topology"] != "cp-colocated-plus-four-workers":
        raise InventoryError("AC-11 target requires one CP-colocated node and four workers")
    hostnames = _exact(root["hostnames"], {"controlPlane", "portal", "idp"}, "hostnames")
    names: list[str] = []
    for field in ("controlPlane", "portal", "idp"):
        values = hostnames[field]
        if not isinstance(values, list) or not values:
            raise InventoryError(f"hostnames.{field} must be a non-empty list")
        names.extend(_nonempty(value, f"hostnames.{field}") for value in values)
    if len(names) != len(set(names)):
        raise InventoryError("hostnames must be unique")

    nodes = root["nodes"]
    if not isinstance(nodes, list) or len(nodes) != 5:
        raise InventoryError("AC-11 target requires exactly five nodes")
    node_keys = {
        "nodeId", "hostname", "dnsName", "ip", "installationId", "os", "role",
        "certificateSHA256", "profile", "hardware", "capacity", "allowedResources",
        "allowedFolders", "ntp", "storageRole",
    }
    unique: dict[str, set[str]] = {
        field: set()
        for field in ("nodeId", "hostname", "dnsName", "ip", "installationId", "certificateSHA256")
    }
    colocated = 0
    workers = 0
    for index, raw in enumerate(nodes):
        where = f"nodes[{index}]"
        node = _exact(raw, node_keys, where)
        for field in ("nodeId", "hostname", "dnsName", "ip", "installationId", "certificateSHA256"):
            value = _nonempty(node[field], f"{where}.{field}")
            if value in unique[field]:
                raise InventoryError(f"{where}.{field} duplicates another node")
            unique[field].add(value)
        if not _NODE_ID.fullmatch(node["nodeId"]):
            raise InventoryError(f"{where}.nodeId is invalid")
        try:
            address = ipaddress.ip_address(node["ip"])
        except ValueError:
            raise InventoryError(f"{where}.ip must be private IPv4") from None
        if address.version != 4 or not address.is_private or address.is_loopback:
            raise InventoryError(f"{where}.ip must be private IPv4")
        if not _HEX64.fullmatch(node["certificateSHA256"]):
            raise InventoryError(f"{where}.certificateSHA256 must be lowercase SHA-256")
        if node["profile"] != "lan-workspace-v1":
            raise InventoryError(f"{where}.profile must be lan-workspace-v1")
        if node["role"] == "cp-colocated":
            colocated += 1
        elif node["role"] == "worker":
            workers += 1
        else:
            raise InventoryError(f"{where}.role is invalid")
        os_value = _exact(node["os"], {"family", "version", "containerRuntime"}, f"{where}.os")
        for field in os_value:
            _nonempty(os_value[field], f"{where}.os.{field}")
        if node["role"] == "worker" and "ubuntu" not in os_value["family"].lower():
            raise InventoryError(f"{where} timed worker must be Ubuntu")

        hardware = _exact(
            node["hardware"],
            {"cpuModel", "physicalCoreCount", "logicalThreadCount", "gpus", "storageDevice", "networkInterface"},
            f"{where}.hardware",
        )
        for field in ("cpuModel", "storageDevice", "networkInterface"):
            _nonempty(hardware[field], f"{where}.hardware.{field}")
        physical = _integer(hardware["physicalCoreCount"], f"{where}.hardware.physicalCoreCount")
        logical = _integer(hardware["logicalThreadCount"], f"{where}.hardware.logicalThreadCount")
        if logical < physical:
            raise InventoryError(f"{where} logical threads cannot be below physical cores")
        if not isinstance(hardware["gpus"], list):
            raise InventoryError(f"{where}.hardware.gpus must be a list")
        for gpu_index, raw_gpu in enumerate(hardware["gpus"]):
            gpu = _exact(raw_gpu, {"model", "vramBytes", "driver"}, f"{where}.hardware.gpus[{gpu_index}]")
            _nonempty(gpu["model"], f"{where}.hardware.gpus[{gpu_index}].model")
            _nonempty(gpu["driver"], f"{where}.hardware.gpus[{gpu_index}].driver")
            _integer(gpu["vramBytes"], f"{where}.hardware.gpus[{gpu_index}].vramBytes")

        capacity = _exact(
            node["capacity"],
            {"cpuMillis", "memoryBytes", "gpuDevices", "storageBytes", "networkBitsPerSecond"},
            f"{where}.capacity",
        )
        for field in capacity:
            _integer(capacity[field], f"{where}.capacity.{field}", allow_zero=field == "gpuDevices")
        if len(hardware["gpus"]) != capacity["gpuDevices"]:
            raise InventoryError(f"{where} GPU inventory and capacity differ")
        allowed = _exact(
            node["allowedResources"],
            {"cpuMillis", "memoryBytes", "gpuDevices", "storageBytes"},
            f"{where}.allowedResources",
        )
        for field in allowed:
            _integer(allowed[field], f"{where}.allowedResources.{field}", allow_zero=field == "gpuDevices")
            if allowed[field] > capacity[field]:
                raise InventoryError(f"{where}.allowedResources exceeds capacity")
        folders = node["allowedFolders"]
        if not isinstance(folders, list) or not folders:
            raise InventoryError(f"{where}.allowedFolders must authorize at least one path")
        for folder in folders:
            _nonempty(folder, f"{where}.allowedFolders")
            if not (PurePosixPath(folder).is_absolute() or PureWindowsPath(folder).is_absolute()):
                raise InventoryError(f"{where}.allowedFolders must be absolute")
        ntp = _exact(node["ntp"], {"configured", "source", "maxSkewSeconds"}, f"{where}.ntp")
        if ntp["configured"] is not True:
            raise InventoryError(f"{where}.ntp must be configured")
        _nonempty(ntp["source"], f"{where}.ntp.source")
        skew = ntp["maxSkewSeconds"]
        if isinstance(skew, bool) or not isinstance(skew, (int, float)) or not 0 <= skew <= 5:
            raise InventoryError(f"{where}.ntp.maxSkewSeconds must be in [0,5]")
        if node["storageRole"] not in {"provider", "archive", "none"}:
            raise InventoryError(f"{where}.storageRole is invalid")
    if (colocated, workers) != (1, 4):
        raise InventoryError("AC-11 target requires one CP-colocated node and four workers")
    return root


def _inventory_revision(payload: dict[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}"


def _exercise_reused_lan_boundaries(payload: dict[str, Any], source_sha: str) -> dict[str, Any]:
    """Exercise ADR-100 inventory and LAN manifest code without I/O or mutation."""

    colocated = next(node for node in payload["nodes"] if node["role"] == "cp-colocated")
    internal = {
        "schemaVersion": FIVE_NODE_INVENTORY_SCHEMA_VERSION,
        "controlPlaneHostId": colocated["installationId"],
        "nodes": [
            {
                "nodeId": node["nodeId"],
                "ip": node["ip"],
                "certificateSHA256": node["certificateSHA256"],
                "profile": node["profile"],
                "hostId": node["installationId"],
                "failureDomainId": "fd-" + hashlib.sha256(node["installationId"].encode()).hexdigest()[:16],
                "coLocatedWithControlPlane": node["role"] == "cp-colocated",
                "measurementEligible": {
                    "s05": node["role"] != "cp-colocated",
                    "s07": node["role"] != "cp-colocated",
                },
                "exclusionReason": "cp-host-colocation" if node["role"] == "cp-colocated" else None,
            }
            for node in payload["nodes"]
        ],
    }
    internal["revision"] = five_node_inventory_revision(internal)
    validate_five_node_inventory(internal)
    server_ip = colocated["ip"]
    validate_node_ips(
        server_ip,
        [node["ip"] for node in payload["nodes"]],
        allow_server_node_colocation=True,
    )
    state = normalized_state(
        {
            "tenantId": "00000000-0000-4000-8000-000000000001",
            "epoch": "00000000-0000-4000-8000-000000000002",
            "serverIP": server_ip,
            "serverNodeColocationAllowed": True,
            "baseSHA": source_sha,
            "agentImage": "synthetic-reference@sha256:" + "0" * 64,
            "nodes": [
                {
                    "nodeId": node["nodeId"],
                    "nodeIP": node["ip"],
                    "nodePort": 18443,
                    "provisioned": True,
                    "coLocatedWithControlPlane": node["role"] == "cp-colocated",
                }
                for node in payload["nodes"]
            ],
        }
    )
    manifests = [
        manifest_for_node(state, node, {"RootFS": {"Layers": []}, "Config": {}}, "dry-run")
        for node in state["nodes"]
    ]
    if sum(item["coLocatedWithControlPlane"] for item in manifests) != 1:
        raise InventoryError("LAN manifest colocation count differs from target")
    if sum(item["measurementEligible"]["s07"] is None for item in manifests) != 4:
        raise InventoryError("LAN manifest eligible count differs from target")
    return internal


def build_dry_run_report(
    *, inventory: dict[str, Any], source_run_id: str, source_sha: str,
    checkout_tree_sha: str, generated_at: str, storage: dict[str, Any], hosted: dict[str, Any],
) -> dict[str, Any]:
    payload = validate_g19_inventory(inventory)
    _exercise_reused_lan_boundaries(payload, source_sha)
    revision = _inventory_revision(payload)
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "runPurpose": DRY_RUN_PURPOSE,
        "referenceOnly": True,
        "acceptanceClaim": False,
        "verdict": "NOT_OBSERVED",
        "sourceRunId": source_run_id,
        "sourceHeadSha": source_sha,
        "checkoutTreeSha": checkout_tree_sha,
        "cleanCheckout": True,
        "generatedAt": generated_at,
        "inventoryRevision": revision,
        "environment": {
            "topology": "synthetic-five-node",
            "registeredNodeCount": 5,
            "eligibleNodeCount": 4,
            "excludedNodeCount": 1,
            "cpIndependentWorkerHostCount": 4,
            "cpColocatedNodeCount": 1,
            "timedPopulation": "synthetic-cp-independent-four",
            "observer": "synthetic-monotonic-v1",
            "faultInjection": "synthetic-noop-v1",
            "windowClass": "dry-run",
            "comparableGroup": "reference-only",
        },
        "operatorResources": [],
        "caseIdentities": list(CASE_IDENTITIES),
        "faultClasses": list(FAULT_CLASSES),
        "cases": [
            {"caseIdentity": identity, "verdict": "SIMULATED", "faultClass": None}
            for identity in CASE_IDENTITIES
        ],
        "caseReceipts": [
            {
                "caseIdentity": identity,
                "phases": [
                    "preflight", "observe-baseline", "simulate-fault",
                    "observe-recovery", "cleanup",
                ],
                "candidateFaultClasses": sorted(
                    ALLOWED_FAULT_CLASSES_BY_PREFIX[identity.split("/", 1)[0]]
                ),
                "containerLifecycle": {
                    "created": True,
                    "started": True,
                    "stopped": True,
                    "removed": True,
                },
                "physicalActions": False,
            }
            for identity in CASE_IDENTITIES
        ],
        "execution": {
            "driver": "synthetic-lan-pilot-v1",
            "started": True,
            "physicalActions": False,
            "executedCaseCount": len(CASE_IDENTITIES),
        },
        "cleanup": {"residueCount": 0},
        "storageReferenceSha256": _canonical_sha(storage),
        "hostedReferenceSha256": _canonical_sha(hosted),
    }


def blocked_physical_report(*, source_run_id: str, blocker: str, detail: str) -> dict[str, Any]:
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "runPurpose": "s11-ac11-composite-long-soak-physical-preflight",
        "sourceRunId": source_run_id,
        "referenceOnly": True,
        "acceptanceClaim": False,
        "verdict": "BLOCKED_EXTERNAL",
        "blocker": blocker,
        "reason": detail,
        "execution": {"started": False, "physicalActions": False},
    }


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} root must be an object")
    return value


def _git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8", capture_output=True, timeout=15
    )
    if result.returncode:
        raise ValueError("Git provenance is unreachable")
    return result.stdout.strip()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_junit(path: Path, report: dict[str, Any], envelope: dict[str, Any]) -> None:
    cases = report.get("cases", [])
    suite = ElementTree.Element(
        "testsuite",
        name="ac11-composite-long-soak-dry-run",
        tests=str(len(cases) + 1),
        failures="0",
        skipped=str(len(cases) + 1),
    )
    for case in cases:
        node = ElementTree.SubElement(suite, "testcase", name=case["caseIdentity"])
        ElementTree.SubElement(node, "skipped", message="reference-only synthetic traversal")
    imported = ElementTree.SubElement(suite, "testcase", name="importer-reference-only-boundary")
    ElementTree.SubElement(imported, "skipped", message=envelope["verdict"])
    path.parent.mkdir(parents=True, exist_ok=True)
    ElementTree.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("dry-run", "physical"), required=True)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--storage-reference", type=Path)
    parser.add_argument("--hosted-reference", type=Path)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-head-sha")
    parser.add_argument("--report-output", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    parser.add_argument("--junit", type=Path)
    args = parser.parse_args(argv)
    source = args.source_head_sha or _git_value("rev-parse", "HEAD")

    protected_inputs = {
        path.resolve()
        for path in (args.inventory, args.storage_reference, args.hosted_reference)
        if path is not None
    }
    outputs = [args.report_output.resolve(), args.evidence_output.resolve()]
    if args.junit is not None:
        outputs.append(args.junit.resolve())
    if len(outputs) != len(set(outputs)) or any(path in protected_inputs for path in outputs):
        parser.error("output paths must be distinct and must not replace an input")

    if args.mode == "physical":
        if args.inventory is None:
            report = blocked_physical_report(
                source_run_id=args.source_run_id,
                blocker="G-19",
                detail="five-node inventory is missing; no physical action was started",
            )
        else:
            try:
                inventory = validate_g19_inventory(_read_json(args.inventory))
                _exercise_reused_lan_boundaries(inventory, source)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                report = blocked_physical_report(
                    source_run_id=args.source_run_id,
                    blocker="G-19",
                    detail=f"inventory preflight failed ({type(exc).__name__}); no physical action was started",
                )
            else:
                report = blocked_physical_report(
                    source_run_id=args.source_run_id,
                    blocker="G-24",
                    detail="operator fault-control adapter is unavailable; no physical action was started",
                )
        _write_json(args.report_output, report)
        _write_json(args.evidence_output, report)
        return 2

    if args.inventory is None or args.storage_reference is None or args.hosted_reference is None:
        parser.error("dry-run requires --inventory, --storage-reference, and --hosted-reference")
    try:
        head = _git_value("rev-parse", "HEAD")
        if source != head or _git_value("status", "--porcelain"):
            raise ValueError("dry-run provenance requires an exact clean HEAD checkout")
        tree = _git_value("rev-parse", f"{source}^{{tree}}")
        inventory = _read_json(args.inventory)
        storage = _read_json(args.storage_reference)
        hosted = _read_json(args.hosted_reference)
        generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        report = build_dry_run_report(
            inventory=inventory,
            source_run_id=args.source_run_id,
            source_sha=source,
            checkout_tree_sha=tree,
            generated_at=generated_at,
            storage=storage,
            hosted=hosted,
        )
        envelope = import_report(report, storage, hosted, RepositoryGit())
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"INVALID_RUN: {type(exc).__name__}")
        return 2
    _write_json(args.report_output, report)
    _write_json(args.evidence_output, envelope)
    if args.junit is not None:
        _write_junit(args.junit, report, envelope)
    return 0 if envelope["verdict"] == "NOT_OBSERVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
