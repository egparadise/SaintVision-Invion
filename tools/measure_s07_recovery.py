#!/usr/bin/env python3
"""Run the S07 node-loss/recovery measurement against disposable PostgreSQL.

The subprocess is a pytest integration test so the repository's normal
random-database/random-login-role fixture creates and removes every measured
row. JSON carries distributions and semantic limitations; JUnit carries the
executable pass/fail result. This is deliberately not physical-five-node
acceptance: replacement bytes are represented by a verified synthetic fixture
only after the product liveness and repair-planning paths have run.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from tools.five_node_lab_preflight import write_registration_mtls_preflight
from tools.provenance import collect

KERNEL_FRESHNESS_SECONDS = 15.0
PHYSICAL_ACCEPTANCE_NODES = 5
PHYSICAL_LIVENESS_SECONDS = 60.0
MEASUREMENT_CLOCK = "harness-process-wall-clock-utc"
FIVE_NODE_PLANNED_REPETITIONS = 20


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def probability(value: str) -> float:
    parsed = float(value)
    if not 0 <= parsed <= 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return parsed


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, int(len(ordered) * fraction + 0.999999999))
    return round(ordered[min(rank, len(ordered)) - 1], 6)


def summarize(config: dict[str, Any], rounds: list[dict[str, Any]]) -> dict[str, Any]:
    delays = [float(item["detectionDelaySeconds"]) for item in rounds if item["detected"]]
    attempted = sum(int(item["shardsAttempted"]) for item in rounds)
    recovered = sum(int(item["shardsRecovered"]) for item in rounds)
    success_rate = recovered / attempted if attempted else 0.0
    acceptance_shape = (
        config["nodes"] == PHYSICAL_ACCEPTANCE_NODES
        and config["livenessTimeoutSeconds"] == PHYSICAL_LIVENESS_SECONDS
    )
    findings: list[dict[str, str]] = [
        {
            "id": "F-S07-02",
            "severity": "acceptance-boundary",
            "summary": (
                "Current replica repair code plans and marks state; the harness fixture "
                "does not prove physical byte transfer or execution-shard replay."
            ),
        },
        {
            "id": "F-S07-03",
            "severity": "slo-boundary",
            "summary": (
                "The strict last_seen < now-timeout predicate is retained. AC-07 defines "
                "the detection limit as the liveness timeout plus one poll interval."
            ),
        },
    ]
    if any(int(item.get("freshReplacementCandidates", 0)) == 0 for item in rounds):
        findings.append(
            {
                "id": "F-S07-01",
                "severity": "kernel-boundary",
                "summary": (
                    "No survivor had a fresh replacement observation. The 15s kernel "
                    "window must be refreshed independently during the 60s departure "
                    "wait; recovery must not reuse the departure-time snapshot."
                ),
            }
        )
    return {
        "schemaVersion": 2,
        "codeSha": config["provenance"]["codeSha"],
        "provenance": config["provenance"],
        "measurementScope": "disposable-postgresql-synthetic-measured-nodes",
        "measurementClock": MEASUREMENT_CLOCK,
        "measurementClockDefinition": (
            "detectionDelaySeconds is detected_at minus departed_at; both are sampled "
            "with datetime.now(UTC) by the harness process, not PostgreSQL clock_timestamp()."
        ),
        "nodesPerRound": config["nodes"],
        "repetitions": config["repetitions"],
        "livenessTimeoutSeconds": config["livenessTimeoutSeconds"],
        "pollIntervalSeconds": config["pollIntervalSeconds"],
        "maxDetectionSeconds": config["maxDetectionSeconds"],
        "detectionLimitSource": config["detectionLimitSource"],
        "targetRecoverySuccessRate": config["targetRecoverySuccessRate"],
        "acceptanceShapeRequested": acceptance_shape,
        "operationalAcceptanceAssessed": False,
        "projectLockContentionMeasured": False,
        "kernelFreshnessSeconds": KERNEL_FRESHNESS_SECONDS,
        "syntheticRecoveryMode": "verified-owner-fixture-after-product-repair-plan",
        "detectionDelaySeconds": {
            "min": round(min(delays), 6) if delays else None,
            "p50": percentile(delays, 0.50),
            "p95": percentile(delays, 0.95),
            "max": round(max(delays), 6) if delays else None,
        },
        "shardsAttempted": attempted,
        "shardsRecovered": recovered,
        "syntheticShardRecoverySuccessRate": round(success_rate, 6),
        "detectionSloMet": bool(delays) and max(delays) <= config["maxDetectionSeconds"],
        "recoveryTargetMet": attempted > 0 and success_rate >= config["targetRecoverySuccessRate"],
        "findings": findings,
        "rounds": rounds,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--adapter",
        choices=("synthetic", "five-node-lab"),
        default="synthetic",
        help="measurement backend (default: synthetic)",
    )
    result.add_argument("--inventory", type=Path)
    result.add_argument("--dry-run", action="store_true")
    result.add_argument("--nodes", type=positive_int)
    result.add_argument("--repetitions", type=positive_int)
    result.add_argument("--liveness-timeout-seconds", type=positive_float)
    result.add_argument("--poll-interval-seconds", type=positive_float)
    result.add_argument("--max-detection-seconds", type=positive_float)
    result.add_argument("--target-recovery-success-rate", type=probability)
    result.add_argument("--json-out", type=Path, required=True)
    result.add_argument("--junit-out", type=Path)
    return result


def validated_config(args: argparse.Namespace) -> dict[str, Any]:
    required = {
        "--nodes": args.nodes,
        "--repetitions": args.repetitions,
        "--liveness-timeout-seconds": args.liveness_timeout_seconds,
        "--junit-out": args.junit_out,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise ValueError(
            f"{', '.join(missing)} required for --adapter synthetic"
        )
    if getattr(args, "inventory", None) is not None or getattr(args, "dry_run", False):
        raise ValueError("--inventory/--dry-run are only valid with --adapter five-node-lab")
    if args.poll_interval_seconds is None:
        args.poll_interval_seconds = 0.1
    if args.target_recovery_success_rate is None:
        args.target_recovery_success_rate = 0.95
    if not 3 <= args.nodes <= 50:
        raise ValueError("nodes must be between 3 and 50")
    if args.repetitions > 100:
        raise ValueError("repetitions must not exceed 100")
    if args.liveness_timeout_seconds > 300:
        raise ValueError("liveness timeout must not exceed 300 seconds")
    if args.poll_interval_seconds > args.liveness_timeout_seconds:
        raise ValueError("poll interval must not exceed liveness timeout")
    detection_limit_source = "explicit"
    max_detection_seconds = args.max_detection_seconds
    if max_detection_seconds is None:
        max_detection_seconds = args.liveness_timeout_seconds + args.poll_interval_seconds
        detection_limit_source = "liveness-timeout-plus-poll-default"
    if max_detection_seconds < args.liveness_timeout_seconds:
        raise ValueError("max detection must not be below the configured timeout")
    if args.json_out.resolve() == args.junit_out.resolve():
        raise ValueError("JSON and JUnit outputs must be different files")
    return {
        "nodes": args.nodes,
        "repetitions": args.repetitions,
        "livenessTimeoutSeconds": args.liveness_timeout_seconds,
        "pollIntervalSeconds": args.poll_interval_seconds,
        "maxDetectionSeconds": max_detection_seconds,
        "detectionLimitSource": detection_limit_source,
        "targetRecoverySuccessRate": args.target_recovery_success_rate,
    }


def measurement_provenance() -> dict[str, Any]:
    captured = collect(executor=os.environ.get("INV_S07_EXECUTOR") or "Codex")
    return {
        "codeSha": captured["commit_sha"],
        "integrationSha": captured["integration_sha"],
        "integrationInSync": captured["in_sync"],
        "workingTreeClean": captured["working_tree_clean_status"],
        "contentClean": captured["content_clean_diff"],
        "capturedAtKst": captured["timestamp_kst"],
        "executor": captured["executor"],
    }


def _planned_target_counts(node_ids: list[str]) -> dict[str, int]:
    """Return the future 20-round allocation only for the four-node topology."""

    ordered = sorted(node_ids)
    if len(ordered) != 4:
        return {}
    counts = {node_id: 0 for node_id in ordered}
    for index in range(FIVE_NODE_PLANNED_REPETITIONS):
        counts[ordered[index % len(ordered)]] += 1
    return counts


def build_five_node_s07_preflight(
    inventory: dict[str, Any],
    registration: dict[str, Any],
    *,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """Project the shared registration observation into the S07 dry-run contract."""

    nodes: list[dict[str, Any]] = []
    for observed in registration["nodes"]:
        ready = bool(observed["readiness"]["ready"])
        colocated = bool(observed["coLocatedWithControlPlane"])
        eligible = bool(observed["measurementEligible"]["s07"])
        selected = ready and eligible and not colocated
        if colocated:
            exclusion = "cp-host-colocation"
        elif not eligible:
            exclusion = "s07-measurement-ineligible"
        elif not ready:
            exclusion = "registration-or-mtls-not-ready"
        else:
            exclusion = None
        nodes.append(
            {
                "nodeId": observed["nodeId"],
                "ip": observed["ip"],
                "certificateSHA256": observed["certificateSHA256"],
                "profile": observed["profile"],
                "hostId": observed["hostId"],
                "failureDomainId": observed["failureDomainId"],
                "coLocatedWithControlPlane": colocated,
                "coLocationValidation": observed["coLocationValidation"],
                "measurementEligible": observed["measurementEligible"],
                "exclusionReason": observed["exclusionReason"],
                "readiness": observed["readiness"],
                "selectedForTopology": ready,
                "selectedForDisruption": selected,
                "disruptionExclusionReason": exclusion,
            }
        )

    ready_nodes = [node for node in nodes if node["readiness"]["ready"]]
    disruption_nodes = [node for node in nodes if node["selectedForDisruption"]]
    colocated_count = sum(node["coLocatedWithControlPlane"] for node in nodes)
    independent_count = len(nodes) - colocated_count
    eligible_count = sum(node["measurementEligible"]["s07"] for node in nodes)
    physical_host_count = len({node["hostId"] for node in nodes})
    topology_ready = (
        len(nodes) == PHYSICAL_ACCEPTANCE_NODES
        and len(ready_nodes) == PHYSICAL_ACCEPTANCE_NODES
        and physical_host_count == PHYSICAL_ACCEPTANCE_NODES
        and colocated_count == 1
        and independent_count == 4
        and eligible_count == 4
    )
    disruption_ids = sorted(node["nodeId"] for node in disruption_nodes)
    return {
        "schemaVersion": "s07-five-node-preflight:1",
        "generatedAt": registration["generatedAt"],
        "adapter": "five-node-lab",
        "provenance": {
            **provenance,
            "inventoryRevision": inventory["revision"],
        },
        "inventoryRevision": inventory["revision"],
        "dryRun": True,
        "databaseReadOnly": bool(registration["databaseReadOnly"]),
        "syntheticRowsCreated": False,
        "heartbeatUpdated": False,
        "resourceSnapshotUpdated": False,
        "nodeDisrupted": False,
        "repairExecuted": False,
        "loadExecuted": False,
        "operationalAcceptanceAssessed": False,
        "livenessTimeoutSeconds": PHYSICAL_LIVENESS_SECONDS,
        "detectionLimit": "60-seconds-plus-observer-poll",
        "nodes": nodes,
        "counts": {
            "inventory": len(nodes),
            "physicalExecutionHosts": physical_host_count,
            "registered": sum(node["readiness"]["registered"] for node in nodes),
            "ready": len(ready_nodes),
            "cpColocated": colocated_count,
            "cpIndependent": independent_count,
            "s07Eligible": eligible_count,
            "s07Selected": len(disruption_nodes),
            "s07Excluded": len(nodes) - len(disruption_nodes),
        },
        "topologyReady": topology_ready,
        "recoveryWaveReady": topology_ready and len(disruption_nodes) == 4,
        "allFiveNodeIds": sorted(node["nodeId"] for node in nodes),
        "disruptionTargetNodeIds": disruption_ids,
        "plannedTargetCounts": _planned_target_counts(disruption_ids),
        "plannedRepetitions": FIVE_NODE_PLANNED_REPETITIONS,
    }


def run_five_node_preflight(
    inventory_path: Path,
    dsn: str | None,
    report_path: Path,
    *,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write one current S07 registration/mTLS observation without mutating PostgreSQL."""

    captured = provenance or measurement_provenance()
    return write_registration_mtls_preflight(
        inventory_path,
        dsn,
        report_path,
        transform=lambda inventory, registration: build_five_node_s07_preflight(
            inventory,
            registration,
            provenance=captured,
        ),
    )


def validate_five_node_args(args: argparse.Namespace) -> None:
    if args.inventory is None:
        raise ValueError("--inventory is required for --adapter five-node-lab")
    if not args.dry_run:
        raise ValueError("--adapter five-node-lab requires --dry-run")
    measurement_options = {
        "--nodes": args.nodes,
        "--repetitions": args.repetitions,
        "--liveness-timeout-seconds": args.liveness_timeout_seconds,
        "--poll-interval-seconds": args.poll_interval_seconds,
        "--max-detection-seconds": args.max_detection_seconds,
        "--target-recovery-success-rate": args.target_recovery_success_rate,
        "--junit-out": args.junit_out,
    }
    supplied = [name for name, value in measurement_options.items() if value is not None]
    if supplied:
        raise ValueError(
            "physical recovery execution is not enabled; remove " + ", ".join(supplied)
        )


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.adapter == "five-node-lab":
        try:
            validate_five_node_args(args)
            report = run_five_node_preflight(
                args.inventory,
                os.environ.get("INV_TEST_ADMIN_DSN"),
                args.json_out,
            )
        except (ValueError, RuntimeError) as exc:
            parser().error(str(exc))
        print(
            json.dumps(
                {
                    "json": str(args.json_out.resolve()),
                    "dryRun": report["dryRun"],
                    "topologyReady": report["topologyReady"],
                    "recoveryWaveReady": report["recoveryWaveReady"],
                },
                separators=(",", ":"),
            )
        )
        return 0
    try:
        config = validated_config(args)
    except ValueError as exc:
        parser().error(str(exc))
    config["provenance"] = measurement_provenance()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.junit_out.parent.mkdir(parents=True, exist_ok=True)
    # A failed rerun must never leave an earlier green artifact looking current.
    args.json_out.unlink(missing_ok=True)
    args.junit_out.unlink(missing_ok=True)
    environment = os.environ.copy()
    environment["INV_S07_MEASUREMENT_CONFIG"] = json.dumps(config, separators=(",", ":"))
    environment["INV_S07_MEASUREMENT_JSON"] = str(args.json_out.resolve())
    environment["PYTHONUTF8"] = "1"
    root = Path(__file__).resolve().parents[1]
    python_paths = [str(root / "src"), str(root / "services" / "control-plane" / "src")]
    if environment.get("PYTHONPATH"):
        python_paths.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(python_paths)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/integration/s07_recovery_measurement_case.py",
            f"--junitxml={args.junit_out.resolve()}",
        ],
        cwd=root,
        env=environment,
        check=False,
    )
    if not args.json_out.is_file():
        print("S07 measurement did not produce JSON", file=sys.stderr)
        return completed.returncode or 2
    print(
        json.dumps(
            {
                "json": str(args.json_out.resolve()),
                "junit": str(args.junit_out.resolve()),
                "pytestExitCode": completed.returncode,
            },
            separators=(",", ":"),
        )
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
