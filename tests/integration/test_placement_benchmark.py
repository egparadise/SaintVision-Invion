"""Real-PostgreSQL preliminary placement benchmark for the S05 lab harness."""

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import secrets
from threading import Event, Lock, Thread
from time import perf_counter_ns
from types import SimpleNamespace

import psycopg
from psycopg.rows import dict_row
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


class PgQueueObserver:
    """Sample runtime backends without retaining SQL parameters or raw PIDs."""

    def __init__(self, runtime_dsn: str, *, interval_ms: int = 5):
        self.runtime_dsn = runtime_dsn
        self.interval_ms = interval_ms
        self._stop = Event()
        self._ready = Event()
        self._thread = Thread(target=self._run, name="placement-queue-observer", daemon=True)
        self._wave_origin_ns: int | None = None
        self._backend_ids: dict[int, str] = {}
        self._timeline: list[dict] = []
        self._settings: dict[str, str] = {}
        self._error: str | None = None

    def start(self) -> None:
        self._thread.start()
        if not self._ready.wait(timeout=5):
            raise RuntimeError("Queue observer did not become ready")
        if self._error is not None:
            raise RuntimeError(f"Queue observer failed: {self._error}")

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            raise RuntimeError("Queue observer did not stop")

    def mark_wave_start(self) -> None:
        self._wave_origin_ns = perf_counter_ns()

    def _backend_id(self, pid: int) -> str:
        if pid not in self._backend_ids:
            self._backend_ids[pid] = f"backend-{len(self._backend_ids) + 1}"
        return self._backend_ids[pid]

    @staticmethod
    def _chain_depth(pid: int, graph: dict[int, list[int]], seen: frozenset[int]) -> int:
        if pid in seen or not graph.get(pid):
            return 0
        return 1 + max(
            PgQueueObserver._chain_depth(blocker, graph, seen | {pid}) for blocker in graph[pid]
        )

    def _run(self) -> None:
        try:
            with psycopg.connect(self.runtime_dsn, autocommit=True, row_factory=dict_row) as conn:
                self._settings = {
                    "logLockWaits": conn.execute("SHOW log_lock_waits").fetchone()[
                        "log_lock_waits"
                    ],
                    "deadlockTimeout": conn.execute("SHOW deadlock_timeout").fetchone()[
                        "deadlock_timeout"
                    ],
                }
                self._ready.set()
                while not self._stop.is_set():
                    rows = conn.execute("""SELECT pid,state,wait_event_type,wait_event,
                        pg_blocking_pids(pid) AS blockers,
                        CASE
                          WHEN position('FROM inv.projects' in query)>0
                           AND position('FOR NO KEY UPDATE' in query)>0 THEN 'project-lock'
                          WHEN position('FROM inv.project_resource_limits' in query)>0
                           AND position('FOR UPDATE' in query)>0 THEN 'limit-lock'
                          WHEN position('FROM inv.tenant_controls' in query)>0 THEN 'tenant-control'
                          WHEN position('FROM inv.runs' in query)>0 THEN 'run-lock'
                          ELSE 'other'
                        END AS statement_class,
                        extract(epoch from (clock_timestamp()-query_start))*1000
                          AS query_age_ms
                        FROM pg_stat_activity
                        WHERE datname=current_database() AND usename=current_user
                          AND pid<>pg_backend_pid() AND state<>'idle'
                        ORDER BY pid""").fetchall()
                    if rows and self._wave_origin_ns is not None:
                        graph = {
                            int(row["pid"]): [int(item) for item in row["blockers"]] for row in rows
                        }
                        backends = []
                        for row in rows:
                            pid = int(row["pid"])
                            blockers = graph[pid]
                            backends.append(
                                {
                                    "backendId": self._backend_id(pid),
                                    "state": row["state"],
                                    "waitEventType": row["wait_event_type"],
                                    "waitEvent": row["wait_event"],
                                    "statementClass": row["statement_class"],
                                    "queryAgeMs": round(float(row["query_age_ms"]), 3),
                                    "blockingBackendIds": [
                                        self._backend_id(blocker) for blocker in blockers
                                    ],
                                    "blockingChainDepth": self._chain_depth(
                                        pid, graph, frozenset()
                                    ),
                                }
                            )
                        lock_waiters = sum(item["waitEventType"] == "Lock" for item in backends)
                        self._timeline.append(
                            {
                                "offsetMs": round(
                                    (perf_counter_ns() - self._wave_origin_ns) / 1_000_000,
                                    3,
                                ),
                                "activeBackendCount": len(backends),
                                "lockWaiterCount": lock_waiters,
                                "maxBlockingChainDepth": max(
                                    item["blockingChainDepth"] for item in backends
                                ),
                                "backends": backends,
                            }
                        )
                    self._stop.wait(self.interval_ms / 1000)
        except Exception as error:  # Evidence reports observer failure by type only.
            self._error = type(error).__name__
            self._ready.set()

    def report(self) -> dict:
        classes = Counter(
            backend["statementClass"] for sample in self._timeline for backend in sample["backends"]
        )
        return {
            "enabled": True,
            "samplingIntervalMs": self.interval_ms,
            "timelineOrigin": "concurrent-wave-barrier-release",
            "serverSettings": self._settings,
            "serverLogRead": False,
            "serverLogBoundary": (
                "log_lock_waits setting is recorded; this collector uses "
                "pg_stat_activity wait_event and does not read PostgreSQL logs"
            ),
            "observerErrorType": self._error,
            "rawPidRetained": False,
            "sqlParametersRetained": False,
            "sampleCount": len(self._timeline),
            "maxActiveBackendCount": max(
                (sample["activeBackendCount"] for sample in self._timeline), default=0
            ),
            "maxLockWaiterCount": max(
                (sample["lockWaiterCount"] for sample in self._timeline), default=0
            ),
            "maxBlockingChainDepth": max(
                (sample["maxBlockingChainDepth"] for sample in self._timeline),
                default=0,
            ),
            "statementClassSampleCounts": dict(sorted(classes.items())),
            "timeline": self._timeline,
        }


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
        if event["outcome"] == "error" or event["elapsedMs"] >= 50:
            with diagnostics_lock:
                sql_diagnostics.append(event)

    def observe_lock_hold(event):
        with diagnostics_lock:
            lock_hold_metrics.append(event)

    diagnostic = os.getenv("INV_PLACEMENT_SQL_DIAGNOSTIC") == "1"
    queue_diagnostic = os.getenv("INV_PLACEMENT_QUEUE_DIAGNOSTIC") == "1"
    placement_db = Database(
        env.runtime,
        recovery_epoch=env.epoch,
        placement_short_commit=os.getenv("INV_PLACEMENT_SHORT_COMMIT") == "1",
        placement_candidate_limit_lock_timeout_ms=int(
            os.getenv("INV_PLACEMENT_CANDIDATE_LIMIT_LOCK_TIMEOUT_MS", "500")
        ),
        placement_project_semaphore_enabled=(os.getenv("INV_PLACEMENT_PROJECT_SEMAPHORE") == "1"),
        placement_project_semaphore_limit=int(
            os.getenv("INV_PLACEMENT_PROJECT_SEMAPHORE_LIMIT", "4")
        ),
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
        queue_observer=(PgQueueObserver(env.runtime) if queue_diagnostic else None),
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
    runs = [[planned(a.e) for _ in range(a.request_count)] for _ in range(round_count)]
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

    if a.queue_observer is not None:
        a.queue_observer.start()
    try:
        first, first_samples = run_round(
            name="round-1",
            request_count=a.request_count,
            concurrency=concurrency,
            reserve=lambda index: reserve(0, index),
            on_wave_start=(
                a.queue_observer.mark_wave_start if a.queue_observer is not None else None
            ),
        )
    finally:
        if a.queue_observer is not None:
            a.queue_observer.stop()
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
    timeout_statement_counts = Counter(
        (item["sqlState"], item["statement"])
        for item in a.sql_diagnostics
        if item["outcome"] == "error" and item["sqlState"] in {"55P03", "57014"}
    )
    report["sqlDiagnostics"] = {
        "enabled": os.getenv("INV_PLACEMENT_SQL_DIAGNOSTIC") == "1",
        "observer": "in-process-connection-wrapper",
        "successThresholdMs": 50,
        "baseLockTimeoutMs": 500,
        "candidateLimitLockTimeoutMs": int(
            os.getenv("INV_PLACEMENT_CANDIDATE_LIMIT_LOCK_TIMEOUT_MS", "500")
        ),
        "statementTimeoutMs": 2000,
        "events": list(a.sql_diagnostics),
        "timeoutStatements": [
            {"sqlState": state, "statement": statement, "count": count}
            for (state, statement), count in sorted(timeout_statement_counts.items())
        ],
    }
    report["requestTimeline"] = [
        {
            "requestIndex": sample.request_index,
            "arrivalOffsetMs": sample.arrival_offset_ms,
            "completionOffsetMs": sample.completion_offset_ms,
            "status": "success" if sample.result is not None else "failure",
            "sqlState": sample.sqlstate,
        }
        for sample in first.samples
    ]
    report["queueObservation"] = (
        a.queue_observer.report()
        if a.queue_observer is not None
        else {
            "enabled": False,
            "reason": "set INV_PLACEMENT_QUEUE_DIAGNOSTIC=1 for pg_stat_activity sampling",
        }
    )
    report["measurementLimitations"] = {
        "boundDatabaseStaleAttemptHold": (
            "not exercised by this benchmark; in a caller-owned outer transaction, "
            "a savepoint-rolled-back stale attempt is overwritten by the next phase "
            "before the outer transaction finalizer emits lockHold"
        ),
        "operationalLegacyMetricSink": (
            "benchmark injects placement_metric_sink; the production app does not, "
            "and the logger fallback is inactive while placementShortCommit=false"
        ),
    }
    hold_metrics = [
        item
        for item in a.lock_hold_metrics
        if item["mode"]
        not in {
            "placement-limit-row-wait",
            "placement-legacy-lock-wait",
            "placement-project-semaphore",
        }
    ]
    candidate_wait_metrics = [
        item for item in a.lock_hold_metrics if item["mode"] == "placement-limit-row-wait"
    ]
    legacy_wait_metrics = [
        item for item in a.lock_hold_metrics if item["mode"] == "placement-legacy-lock-wait"
    ]
    semaphore_metrics = [
        item for item in a.lock_hold_metrics if item["mode"] == "placement-project-semaphore"
    ]
    committed_holds = [item["lockHoldMs"] for item in hold_metrics if item["outcome"] == "commit"]
    report["lockHold"] = {
        "mode": (
            "placement-short-commit"
            if os.getenv("INV_PLACEMENT_SHORT_COMMIT") == "1"
            else "placement-legacy-lock-scope"
        ),
        "samples": hold_metrics,
        "commitCount": len(committed_holds),
        "rollbackCount": sum(item["outcome"] == "rollback" for item in hold_metrics),
        "commitP50Ms": (
            round(percentile_nearest_rank(committed_holds, 0.50), 3) if committed_holds else None
        ),
        "commitP95Ms": (
            round(percentile_nearest_rank(committed_holds, 0.95), 3) if committed_holds else None
        ),
        "commitMaxMs": round(max(committed_holds), 3) if committed_holds else None,
    }

    def summarize_waits(metrics, *, mode, policy):
        values = [item["waitMs"] for item in metrics]
        return {
            "mode": mode,
            "contentionPolicy": policy,
            "measurementMethod": "client-wall-clock-around-lock-statements",
            "samples": metrics,
            "attemptCount": len(metrics),
            "acquisitionAttemptCount": len(metrics),
            "acquiredCount": sum(item["outcome"] == "acquired" for item in metrics),
            "timeoutCount": sum(item["outcome"] == "timeout" for item in metrics),
            "timeoutRetryCount": 0,
            "p50Ms": (round(percentile_nearest_rank(values, 0.50), 3) if values else None),
            "p95Ms": (round(percentile_nearest_rank(values, 0.95), 3) if values else None),
            "maxMs": round(max(values), 3) if values else None,
        }

    report["legacyLockWait"] = summarize_waits(
        legacy_wait_metrics,
        mode="placement-legacy-lock-wait",
        policy="project-then-limit-serial",
    )
    report["limitRowWait"] = summarize_waits(
        candidate_wait_metrics,
        mode="placement-limit-row-wait",
        policy="fail-fast",
    )
    report["lockAcquireWait"] = (
        report["limitRowWait"]
        if os.getenv("INV_PLACEMENT_SHORT_COMMIT") == "1"
        else report["legacyLockWait"]
    )
    permit_holds = [item["holdMs"] for item in semaphore_metrics if item["outcome"] == "released"]
    report["projectSemaphore"] = {
        "enabled": os.getenv("INV_PLACEMENT_PROJECT_SEMAPHORE") == "1",
        "limit": int(os.getenv("INV_PLACEMENT_PROJECT_SEMAPHORE_LIMIT", "4")),
        "permitWaitBudgetMs": 0,
        "scope": "process-local-tenant-project",
        "samples": semaphore_metrics,
        "acquiredCount": sum(
            item["outcome"] == "acquired" and not item["reentrant"] for item in semaphore_metrics
        ),
        "reentrantCount": sum(
            item["outcome"] == "acquired" and item["reentrant"] for item in semaphore_metrics
        ),
        "rejectedCount": sum(item["outcome"] == "rejected" for item in semaphore_metrics),
        "releasedCount": sum(item["outcome"] == "released" for item in semaphore_metrics),
        "maxInUse": max(
            (
                item["inUseBefore"] + 1
                for item in semaphore_metrics
                if item["outcome"] == "acquired" and not item["reentrant"]
            ),
            default=0,
        ),
        "permitHoldP50Ms": (
            round(percentile_nearest_rank(permit_holds, 0.50), 3) if permit_holds else None
        ),
        "permitHoldP95Ms": (
            round(percentile_nearest_rank(permit_holds, 0.95), 3) if permit_holds else None
        ),
        "permitHoldMaxMs": round(max(permit_holds), 3) if permit_holds else None,
        "releaseCauses": dict(
            Counter(
                item["releaseCause"] for item in semaphore_metrics if item["outcome"] == "released"
            )
        ),
        "registryEntryCountAfterWave": len(a.placement.db._placement_project_permit_snapshot()),
        "registryPermitCountAfterWave": sum(
            a.placement.db._placement_project_permit_snapshot().values()
        ),
    }
    all_samples = list(first.samples) + (list(second.samples) if second else [])
    semaphore_reject_count = sum(
        sample.cause_type == "_PlacementSemaphoreLimit" for sample in all_samples
    )
    sql_timeout_count = sum(sample.sqlstate in {"55P03", "57014"} for sample in all_samples)
    report["externalFailure"] = {
        "semaphoreRejectCount": semaphore_reject_count,
        "sqlTimeoutCount": sql_timeout_count,
        "count": semaphore_reject_count + sql_timeout_count,
        "gateDefinition": "semaphore reject + 55P03 + 57014",
    }
    report["schemaVersion"] = "1.8.0"
    report["contentionObservation"]["candidateLimitLockTimeoutMs"] = int(
        os.getenv("INV_PLACEMENT_CANDIDATE_LIMIT_LOCK_TIMEOUT_MS", "500")
    )
    report["contentionObservation"]["serverSideLockHoldMeasured"] = True
    report["contentionObservation"]["serverSideLockWaitSeparatelyMeasured"] = False
    report["contentionObservation"]["clientObservedLockAcquireElapsedSeparatelyMeasured"] = True
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
    record_property("lockAcquireWaitMode", report["lockAcquireWait"]["mode"])
    record_property("lockAcquireWaitP50Ms", report["lockAcquireWait"]["p50Ms"])
    record_property("lockAcquireWaitP95Ms", report["lockAcquireWait"]["p95Ms"])
    record_property("lockAcquireWaitMaxMs", report["lockAcquireWait"]["maxMs"])
    record_property("limitRowWaitP50Ms", report["limitRowWait"]["p50Ms"])
    record_property("limitRowWaitP95Ms", report["limitRowWait"]["p95Ms"])
    record_property("limitRowWaitMaxMs", report["limitRowWait"]["maxMs"])
    record_property(
        "limitRowAcquisitionAttemptCount",
        report["limitRowWait"]["acquisitionAttemptCount"],
    )
    record_property("limitRowTimeoutCount", report["limitRowWait"]["timeoutCount"])
    record_property(
        "projectSemaphoreRejectCount",
        report["projectSemaphore"]["rejectedCount"],
    )
    record_property(
        "projectSemaphoreRegistryPermitCountAfterWave",
        report["projectSemaphore"]["registryPermitCountAfterWave"],
    )
    record_property("externalFailureCount", report["externalFailure"]["count"])
    record_property(
        "candidateLimitLockTimeoutMs",
        report["contentionObservation"]["candidateLimitLockTimeoutMs"],
    )
    record_property("limitRowTimeoutRetryCount", report["limitRowWait"]["timeoutRetryCount"])
    record_property("sqlTimeoutStatementCount", len(report["sqlDiagnostics"]["timeoutStatements"]))
    record_property("queueObservationEnabled", report["queueObservation"]["enabled"])
    if report["queueObservation"]["enabled"]:
        record_property(
            "queueMaxLockWaiterCount",
            report["queueObservation"]["maxLockWaiterCount"],
        )
        record_property(
            "queueMaxBlockingChainDepth",
            report["queueObservation"]["maxBlockingChainDepth"],
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
