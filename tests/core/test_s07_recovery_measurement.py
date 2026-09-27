import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import measure_s07_recovery
from tools.measure_s07_recovery import percentile, summarize, validated_config


def config(**changes):
    values = dict(
        nodes=5,
        repetitions=3,
        liveness_timeout_seconds=60.0,
        poll_interval_seconds=0.5,
        max_detection_seconds=61.0,
        target_recovery_success_rate=0.95,
        json_out=__import__("pathlib").Path("result.json"),
        junit_out=__import__("pathlib").Path("result.xml"),
    )
    values.update(changes)
    return argparse.Namespace(**values)


def _five_node_inventory() -> dict:
    nodes = []
    for index in range(5):
        colocated = index == 0
        nodes.append(
            {
                "nodeId": f"nod_{index:026d}",
                "ip": f"192.168.45.{140 + index}",
                "certificateSHA256": f"{index + 1:064x}",
                "profile": "lan-workspace-v1",
                "hostId": "host-cp" if colocated else f"host-ubuntu-{index}",
                "failureDomainId": f"physical-host-{index}",
                "coLocatedWithControlPlane": colocated,
                "measurementEligible": {"s05": not colocated, "s07": not colocated},
                "exclusionReason": "cp-host-colocation" if colocated else None,
            }
        )
    return {
        "schemaVersion": "1.0.0",
        "revision": "sha256:" + "a" * 64,
        "controlPlaneHostId": "host-cp",
        "nodes": nodes,
    }


def _registration_observation(inventory: dict) -> dict:
    observed = []
    for node in inventory["nodes"]:
        observed.append(
            {
                **node,
                "coLocationValidation": "matched",
                "readiness": {
                    "registered": True,
                    "statusOnline": True,
                    "heartbeatFresh": True,
                    "heartbeatAgeSeconds": 1.0,
                    "channelReady": True,
                    "snapshotFresh": True,
                    "resourceSnapshotComplete": True,
                    "snapshotAgeSeconds": 1.0,
                    "clockSkewAcceptable": True,
                    "profileReady": True,
                    "ready": True,
                    "reasons": [],
                },
                "selectedForAllFiveSmoke": True,
                "selectedForTimedWave": not node["coLocatedWithControlPlane"],
            }
        )
    return {
        "schemaVersion": "five-node-lab-preflight:1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "adapter": "five-node-lab",
        "dryRun": True,
        "inventoryRevision": inventory["revision"],
        "databaseReadOnly": True,
        "syntheticRowsCreated": False,
        "heartbeatUpdated": False,
        "loadExecuted": False,
        "nodes": observed,
    }


def test_validation_rejects_non_reproducible_or_unsafe_shapes():
    for changes in (
        {"nodes": 2},
        {"repetitions": 101},
        {"poll_interval_seconds": 61.0},
        {"max_detection_seconds": 59.0},
        {"junit_out": __import__("pathlib").Path("result.json")},
    ):
        with pytest.raises(ValueError):
            validated_config(config(**changes))


def test_summary_uses_nearest_rank_and_never_claims_operational_acceptance():
    cfg = validated_config(config())
    cfg["provenance"] = {
        "codeSha": "a" * 40,
        "integrationSha": "a" * 40,
        "integrationInSync": True,
        "workingTreeClean": True,
        "contentClean": True,
        "capturedAtKst": "2026-09-22T23:25:00+09:00",
        "executor": "Codex",
    }
    rounds = [
        {
            "detected": True,
            "detectionDelaySeconds": delay,
            "freshReplacementCandidates": 0,
            "shardsAttempted": 2,
            "shardsRecovered": recovered,
        }
        for delay, recovered in ((60.1, 2), (60.2, 2), (60.9, 1))
    ]
    result = summarize(cfg, rounds)
    assert result["detectionDelaySeconds"] == {
        "min": 60.1,
        "p50": 60.2,
        "p95": 60.9,
        "max": 60.9,
    }
    assert result["syntheticShardRecoverySuccessRate"] == pytest.approx(5 / 6, abs=1e-6)
    assert result["operationalAcceptanceAssessed"] is False
    assert result["acceptanceShapeRequested"] is True
    assert result["codeSha"] == "a" * 40
    assert result["provenance"] == cfg["provenance"]
    assert result["measurementClock"] == "harness-process-wall-clock-utc"
    assert {finding["id"] for finding in result["findings"]} == {
        "F-S07-01",
        "F-S07-02",
        "F-S07-03",
    }
    assert percentile([], 0.95) is None


def test_default_detection_limit_is_timeout_plus_poll_interval():
    result = validated_config(config(max_detection_seconds=None))

    assert result["maxDetectionSeconds"] == 60.5
    assert result["detectionLimitSource"] == "liveness-timeout-plus-poll-default"


def test_failed_rerun_cannot_reuse_stale_evidence(tmp_path, monkeypatch):
    json_out = tmp_path / "stale.json"
    junit_out = tmp_path / "stale.xml"
    json_out.write_text('{"stale":true}', encoding="utf-8")
    junit_out.write_text("<stale/>", encoding="utf-8")
    monkeypatch.setattr(
        measure_s07_recovery.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(
        measure_s07_recovery,
        "measurement_provenance",
        lambda: {"codeSha": "a" * 40},
    )

    result = measure_s07_recovery.main(
        [
            "--nodes",
            "3",
            "--repetitions",
            "1",
            "--liveness-timeout-seconds",
            "1",
            "--max-detection-seconds",
            "1",
            "--json-out",
            str(json_out),
            "--junit-out",
            str(junit_out),
        ]
    )

    assert result == 2
    assert not json_out.exists()
    assert not junit_out.exists()


def test_five_node_projection_excludes_cp_colocated_node_without_running_a_wave():
    inventory = _five_node_inventory()
    report = measure_s07_recovery.build_five_node_s07_preflight(
        inventory,
        _registration_observation(inventory),
        provenance={"codeSha": "b" * 40, "executor": "Codex"},
    )

    assert report["schemaVersion"] == "s07-five-node-preflight:1"
    assert report["counts"] == {
        "inventory": 5,
        "physicalExecutionHosts": 5,
        "registered": 5,
        "ready": 5,
        "cpColocated": 1,
        "cpIndependent": 4,
        "s07Eligible": 4,
        "s07Selected": 4,
        "s07Excluded": 1,
    }
    assert report["topologyReady"] is True
    assert report["recoveryWaveReady"] is True
    assert report["nodes"][0]["selectedForTopology"] is True
    assert report["nodes"][0]["selectedForDisruption"] is False
    assert report["nodes"][0]["disruptionExclusionReason"] == "cp-host-colocation"
    assert report["disruptionTargetNodeIds"] == sorted(
        node["nodeId"] for node in inventory["nodes"][1:]
    )
    assert report["plannedTargetCounts"] == {
        node["nodeId"]: 5 for node in inventory["nodes"][1:]
    }
    for field in (
        "syntheticRowsCreated",
        "heartbeatUpdated",
        "resourceSnapshotUpdated",
        "nodeDisrupted",
        "repairExecuted",
        "loadExecuted",
        "operationalAcceptanceAssessed",
    ):
        assert report[field] is False
    assert "tenantId" not in json.dumps(report)


def test_five_node_projection_never_promotes_shared_readiness_or_s05_selection():
    inventory = _five_node_inventory()
    registration = _registration_observation(inventory)
    registration["nodes"][1]["readiness"]["ready"] = False
    registration["nodes"][1]["readiness"]["reasons"] = ["heartbeat-stale-or-missing"]
    assert registration["nodes"][1]["selectedForTimedWave"] is True

    report = measure_s07_recovery.build_five_node_s07_preflight(
        inventory,
        registration,
        provenance={"codeSha": "b" * 40, "executor": "Codex"},
    )

    assert report["topologyReady"] is False
    assert report["recoveryWaveReady"] is False
    assert report["counts"]["s07Selected"] == 3
    assert report["plannedTargetCounts"] == {}
    assert report["nodes"][1]["selectedForDisruption"] is False
    assert report["nodes"][1]["disruptionExclusionReason"] == "registration-or-mtls-not-ready"


def test_five_node_cli_uses_shared_writer_and_never_starts_pytest(
    tmp_path: Path,
    monkeypatch,
):
    inventory = _five_node_inventory()
    inventory_path = tmp_path / "inventory.json"
    report_path = tmp_path / "s07-preflight.json"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    calls = []

    def fake_writer(inventory_arg, dsn, report_arg, *, transform, **_kwargs):
        calls.append((inventory_arg, dsn, report_arg))
        report = transform(inventory, _registration_observation(inventory))
        report_arg.write_text(json.dumps(report), encoding="utf-8")
        return report

    monkeypatch.setenv("INV_TEST_ADMIN_DSN", "postgresql://secret")
    monkeypatch.setattr(measure_s07_recovery, "write_registration_mtls_preflight", fake_writer)
    monkeypatch.setattr(
        measure_s07_recovery,
        "measurement_provenance",
        lambda: {"codeSha": "c" * 40, "executor": "Codex"},
    )
    monkeypatch.setattr(
        measure_s07_recovery.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("five-node dry-run must not launch pytest"),
    )

    result = measure_s07_recovery.main(
        [
            "--adapter",
            "five-node-lab",
            "--inventory",
            str(inventory_path),
            "--dry-run",
            "--json-out",
            str(report_path),
        ]
    )

    assert result == 0
    assert calls == [(inventory_path, "postgresql://secret", report_path)]
    assert json.loads(report_path.read_text(encoding="utf-8"))["nodeDisrupted"] is False


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--nodes", "5"],
        ["--junit-out", "result.xml"],
    ],
)
def test_five_node_cli_rejects_execution_or_missing_dry_run(tmp_path: Path, extra):
    arguments = [
        "--adapter",
        "five-node-lab",
        "--inventory",
        str(tmp_path / "inventory.json"),
        "--json-out",
        str(tmp_path / "report.json"),
    ]
    if extra:
        arguments.append("--dry-run")
        arguments.extend(extra)

    with pytest.raises(SystemExit) as caught:
        measure_s07_recovery.main(arguments)

    assert caught.value.code == 2
