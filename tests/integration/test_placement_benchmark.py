"""Real-PostgreSQL preliminary placement benchmark for the S05 lab harness."""

from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import secrets
from threading import Lock
from types import SimpleNamespace

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb
import pytest

from inv.approvals import Principal
from inv.contracts import validate_contract
from inv.ids import new_id
from inv.db import Database
from inv.placement import PlacementStore
from inv.scheduler import Request
from test_postgres import planned
from tools.placement_benchmark import percentile_nearest_rank, run_round, summarize

pytestmark = pytest.mark.postgres

CPU_PER_REQUEST = 10
MEMORY_PER_REQUEST = 1_048_576


class BenchmarkEnvironment(SimpleNamespace):
    def __repr__(self):
        return "BenchmarkEnvironment(<credentials-redacted>)"


def _count(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if not 1 <= value <= 200:
        raise ValueError(f"{name} must be between 1 and 200")
    return value


@pytest.fixture
def placement_benchmark_env(env):
    request_count = _count("INV_PLACEMENT_BENCHMARK_REQUESTS", 50)
    memory_resource = new_id("res")
    cpu_total = request_count * CPU_PER_REQUEST
    memory_total = request_count * MEMORY_PER_REQUEST
    snapshot = {
        "nonce": secrets.token_hex(32),
        "tenantId": env.tenant,
        "nodeId": env.node,
        "recoveryEpoch": env.epoch,
        "profileVersion": "benchmark:1",
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "sampleMillis": 100,
        "cpuCapacityMillis": cpu_total,
        "cpuBusyMillis": 0,
        "memoryCapacityBytes": memory_total,
        "memoryAvailableBytes": memory_total,
        "osType": "linux",
        "agentVersion": "0.1.0",
    }
    validate_contract("NodeResourceSnapshot", snapshot)
    with psycopg.connect(env.owner) as conn:
        conn.execute(
            "UPDATE inv.resources SET capacity=%s,offered=%s WHERE tenant_id=%s AND resource_id=%s",
            (cpu_total, cpu_total, env.tenant, env.resource),
        )
        conn.execute(
            "INSERT INTO inv.resources VALUES(%s,%s,%s,'memory',%s,%s)",
            (env.tenant, memory_resource, env.node, memory_total, memory_total),
        )
        conn.execute(
            "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request,can_approve) VALUES(%s,%s,'benchmark',true,false)",
            (env.tenant, env.project),
        )
        conn.execute(
            "INSERT INTO inv.project_nodes(tenant_id,project_id,node_id) VALUES(%s,%s,%s)",
            (env.tenant, env.project, env.node),
        )
        conn.execute(
            "INSERT INTO inv.project_resource_limits(tenant_id,project_id,cpu_millis,memory_bytes) VALUES(%s,%s,%s,%s)",
            (env.tenant, env.project, cpu_total, memory_total),
        )
        conn.execute(
            """INSERT INTO inv.node_channels(
            tenant_id,node_id,recovery_epoch,version,endpoint,certificate_sha256,
            certificate_not_after,enabled) VALUES(%s,%s,%s,1,'https://benchmark.invalid',%s,
            clock_timestamp()+interval '1 hour',true)""",
            (env.tenant, env.node, env.epoch, "a" * 64),
        )
    sql_diagnostics = []
    lock_hold_metrics = []
    diagnostics_lock = Lock()

    def observe_statement(event):
        with diagnostics_lock:
            sql_diagnostics.append(event)

    def observe_lock_hold(event):
        with diagnostics_lock:
            lock_hold_metrics.append(event)

    diagnostic = os.getenv("INV_PLACEMENT_SQL_DIAGNOSTIC") == "1"
    if diagnostic:
        runtime_role = conninfo_to_dict(env.runtime)["user"]
        with psycopg.connect(env.owner) as conn:
            conn.execute(
                sql.SQL("ALTER ROLE {} SET log_min_duration_statement='500ms'").format(
                    sql.Identifier(runtime_role)
                )
            )
    placement_db = Database(
        env.runtime,
        recovery_epoch=env.epoch,
        placement_short_commit=os.getenv("INV_PLACEMENT_SHORT_COMMIT") == "1",
        statement_observer=observe_statement if diagnostic else None,
        placement_metric_sink=observe_lock_hold,
    )
    return BenchmarkEnvironment(
        e=env,
        principal=Principal(env.tenant, "benchmark"),
        placement=PlacementStore(placement_db),
        request=Request(
            CPU_PER_REQUEST,
            MEMORY_PER_REQUEST,
            max_host_load=Decimal(1),
        ),
        request_count=request_count,
        memory_resource=memory_resource,
        snapshot=snapshot,
        sql_diagnostics=sql_diagnostics,
        lock_hold_metrics=lock_hold_metrics,
    )


def _active(a) -> dict[str, int]:
    with a.e.db.transaction(a.e.tenant) as conn:
        rows = conn.execute(
            """SELECT r.kind,coalesce(sum(l.amount),0) AS amount
            FROM inv.resources r LEFT JOIN inv.resource_leases l
            ON (l.tenant_id,l.resource_id)=(r.tenant_id,r.resource_id)
            AND l.released_at IS NULL
            WHERE r.tenant_id=%s AND r.node_id=%s AND r.kind IN ('cpu','memory')
            GROUP BY r.kind""",
            (a.e.tenant, a.e.node),
        ).fetchall()
    return {row["kind"]: int(row["amount"]) for row in rows}


def _release_round(a) -> None:
    # Disposable benchmark database only. Reset both resource dimensions in one
    # owner transaction so round two starts from byte-identical capacity state.
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            """UPDATE inv.resource_leases SET released_at=clock_timestamp(),
            stop_receipt=gen_random_uuid() WHERE tenant_id=%s AND released_at IS NULL""",
            (a.e.tenant,),
        )
        conn.execute(
            "UPDATE inv.nodes SET heartbeat_at=clock_timestamp() WHERE tenant_id=%s AND node_id=%s",
            (a.e.tenant, a.e.node),
        )


def _start_observation_window(a) -> None:
    """Acquire one fixed snapshot immediately before the concurrent wave."""

    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.nodes SET heartbeat_at=clock_timestamp() WHERE tenant_id=%s AND node_id=%s",
            (a.e.tenant, a.e.node),
        )
        conn.execute(
            """INSERT INTO inv.node_resource_snapshots(
            tenant_id,node_id,recovery_epoch,channel_version,received_at,snapshot)
            VALUES(%s,%s,%s,1,clock_timestamp(),%s)""",
            (a.e.tenant, a.e.node, a.e.epoch, Jsonb(a.snapshot)),
        )


def test_fifty_concurrent_placement_decisions_are_repeatable_and_bounded(
    placement_benchmark_env, record_property
):
    a = placement_benchmark_env
    concurrency = _count("INV_PLACEMENT_BENCHMARK_CONCURRENCY", a.request_count)
    round_count = _count("INV_PLACEMENT_BENCHMARK_ROUNDS", 2)
    if round_count not in (1, 2):
        pytest.fail("Benchmark rounds must be 1 or 2")
    if concurrency != a.request_count:
        pytest.fail("Benchmark concurrency must equal request count")
    runs = [
        [planned(a.e) for _ in range(a.request_count)] for _ in range(round_count)
    ]
    _start_observation_window(a)

    def reserve(round_index, request_index):
        return a.placement.reserve(
            a.principal,
            a.e.project,
            runs[round_index][request_index]["runId"],
            a.request,
            key=f"benchmark:{round_index}:{request_index}",
            policy_version="roof:benchmark:1",
            pool_version="project-nodes:benchmark:1",
        )

    first, first_samples = run_round(
        name="round-1",
        request_count=a.request_count,
        concurrency=concurrency,
        reserve=lambda index: reserve(0, index),
    )
    active_after_rounds = [_active(a)]
    expected_active_rounds = [
        {
            "cpu": first.success_count * CPU_PER_REQUEST,
            "memory": first.success_count * MEMORY_PER_REQUEST,
        }
    ]
    second = None
    snapshot_replay_stable = None
    if first.failure_count == 0 and round_count == 2:
        replayed = [reserve(0, sample.request_index) for sample in first_samples]
        snapshot_replay_stable = all(
            sample.result == replay
            and sample.result["placement"]["snapshotId"] == replay["placement"]["snapshotId"]
            for sample, replay in zip(first_samples, replayed)
        )
        _release_round(a)
        assert _active(a) == {"cpu": 0, "memory": 0}
        second, second_samples = run_round(
            name="round-2",
            request_count=a.request_count,
            concurrency=concurrency,
            reserve=lambda index: reserve(1, index),
        )
        if second.failure_count == 0:
            replayed = [reserve(1, sample.request_index) for sample in second_samples]
            snapshot_replay_stable = snapshot_replay_stable and all(
                sample.result == replay
                and sample.result["placement"]["snapshotId"] == replay["placement"]["snapshotId"]
                for sample, replay in zip(second_samples, replayed)
            )
        else:
            snapshot_replay_stable = None
        active_after_rounds.append(_active(a))
        expected_active_rounds.append(
            {
                "cpu": second.success_count * CPU_PER_REQUEST,
                "memory": second.success_count * MEMORY_PER_REQUEST,
            }
        )
    _release_round(a)
    assert _active(a) == {"cpu": 0, "memory": 0}
    report = summarize(
        first,
        second,
        topology="development-PC; one synthetic measured-node row; pre-five-node-lab",
        code_sha=os.getenv("INV_PLACEMENT_BENCHMARK_CODE_SHA", "working-tree"),
        active_after_first=active_after_rounds[0],
        active_after_rounds=active_after_rounds,
        expected_active_rounds=expected_active_rounds,
        snapshot_replay_stable=snapshot_replay_stable,
        rounds_requested=round_count,
    )
    report["sqlDiagnostics"] = {
        "enabled": os.getenv("INV_PLACEMENT_SQL_DIAGNOSTIC") == "1",
        "logMinDurationStatementMs": (
            500 if os.getenv("INV_PLACEMENT_SQL_DIAGNOSTIC") == "1" else None
        ),
        "errors": list(a.sql_diagnostics),
    }
    hold_metrics = [
        item for item in a.lock_hold_metrics if item["mode"] != "placement-limit-row-wait"
    ]
    wait_metrics = [
        item for item in a.lock_hold_metrics if item["mode"] == "placement-limit-row-wait"
    ]
    committed_holds = [
        item["lockHoldMs"]
        for item in hold_metrics
        if item["outcome"] == "commit"
    ]
    report["lockHold"] = {
        "mode": (
            "placement-short-commit"
            if os.getenv("INV_PLACEMENT_SHORT_COMMIT") == "1"
            else "placement-legacy-lock-scope"
        ),
        "samples": hold_metrics,
        "commitCount": len(committed_holds),
        "rollbackCount": sum(
            item["outcome"] == "rollback" for item in hold_metrics
        ),
        "commitP50Ms": (
            round(percentile_nearest_rank(committed_holds, 0.50), 3)
            if committed_holds
            else None
        ),
        "commitP95Ms": (
            round(percentile_nearest_rank(committed_holds, 0.95), 3)
            if committed_holds
            else None
        ),
        "commitMaxMs": round(max(committed_holds), 3) if committed_holds else None,
    }
    wait_values = [item["waitMs"] for item in wait_metrics]
    wait_timeout_count = sum(item["outcome"] == "timeout" for item in wait_metrics)
    report["limitRowWait"] = {
        "contentionPolicy": (
            "fail-fast"
            if os.getenv("INV_PLACEMENT_SHORT_COMMIT") == "1"
            else "legacy-project-serial"
        ),
        "samples": wait_metrics,
        "attemptCount": len(wait_metrics),
        "acquisitionAttemptCount": len(wait_metrics),
        "acquiredCount": sum(item["outcome"] == "acquired" for item in wait_metrics),
        "timeoutCount": wait_timeout_count,
        # Kept for additive compatibility with v1.3 evidence.  Under the
        # fail-fast policy a timeout is returned, never retried internally.
        "timeoutRetryCount": 0,
        "p50Ms": (
            round(percentile_nearest_rank(wait_values, 0.50), 3)
            if wait_values
            else None
        ),
        "p95Ms": (
            round(percentile_nearest_rank(wait_values, 0.95), 3)
            if wait_values
            else None
        ),
        "maxMs": round(max(wait_values), 3) if wait_values else None,
    }
    report["schemaVersion"] = "1.4.0"
    report["contentionObservation"]["serverSideLockHoldMeasured"] = True
    path = Path(os.getenv("INV_PLACEMENT_BENCHMARK_REPORT", ".work/placement-benchmark.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for key in (
        "scope",
        "requestCount",
        "concurrency",
        "p95SuccessfulMsWorstRound",
        "benchmarkComplete",
        "deterministicExplainAndSnapshot",
        "snapshotIdStableOnIdempotentReplay",
        "uniqueFencingTokens",
        "noOverbooking",
        "fiveNodeAC05",
    ):
        record_property(key, report[key])
    record_property("placementMode", report["lockHold"]["mode"])
    record_property("lockHoldCommitP50Ms", report["lockHold"]["commitP50Ms"])
    record_property("lockHoldCommitP95Ms", report["lockHold"]["commitP95Ms"])
    record_property("lockHoldCommitMaxMs", report["lockHold"]["commitMaxMs"])
    record_property("lockHoldRollbackCount", report["lockHold"]["rollbackCount"])
    record_property("limitRowWaitP50Ms", report["limitRowWait"]["p50Ms"])
    record_property("limitRowWaitP95Ms", report["limitRowWait"]["p95Ms"])
    record_property("limitRowWaitMaxMs", report["limitRowWait"]["maxMs"])
    record_property(
        "limitRowAcquisitionAttemptCount",
        report["limitRowWait"]["acquisitionAttemptCount"],
    )
    record_property("limitRowTimeoutCount", report["limitRowWait"]["timeoutCount"])
    record_property(
        "limitRowTimeoutRetryCount", report["limitRowWait"]["timeoutRetryCount"]
    )
    print("PLACEMENT_BENCHMARK_RESULT=" + json.dumps(report, sort_keys=True))
    if first.failure_count:
        pytest.fail(
            "F-S05-01: concurrent placement produced "
            f"{first.failure_count} failures; inspect the JSON/JUnit distribution"
        )
    assert report["benchmarkComplete"]
    if round_count == 2:
        assert report["deterministicExplainAndSnapshot"]
        assert report["snapshotIdStableOnIdempotentReplay"]
    assert report["uniqueFencingTokens"]
    assert report["noOverbooking"]
