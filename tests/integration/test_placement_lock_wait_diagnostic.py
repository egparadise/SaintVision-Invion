"""Approved S05 legacy lock-wait diagnostic against one disposable PostgreSQL DB.

This file is opt-in.  It records one 20-request wave, PostgreSQL server lock-wait
messages, ``pg_stat_activity``/``backend_xid`` samples, and ``pgrowlocks`` modes.
The companion CLI runs this file once with the production FK and once after
dropping only the disposable database's idempotency->projects FK.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from threading import Event, Lock, Thread
from time import perf_counter_ns, time

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
import pytest

from inv.approvals import Principal
from inv.db import Database
from inv.placement import PlacementStore
from test_placement_benchmark import (
    _active,
    _release_round,
    _start_observation_window,
    placement_benchmark_env,
)
from test_postgres import planned
from tools.placement_benchmark import percentile_nearest_rank, run_round

pytestmark = pytest.mark.postgres

_LOG_RE = re.compile(
    r"process (?P<pid>\d+) (?P<event>still waiting for|acquired) "
    r"(?P<lock>.+?) after (?P<ms>[0-9.]+) ms"
)
_XID_RE = re.compile(r"transaction (?P<xid>\d+)")


def _classification(statement: str) -> str:
    compact = " ".join(statement.split())
    if "FROM inv.projects" in compact and "FOR NO KEY UPDATE" in compact:
        return "project-lock"
    if "FROM inv.project_resource_limits" in compact and "FOR UPDATE" in compact:
        return "limit-lock"
    if "INSERT INTO inv.idempotency" in compact:
        return "idempotency-insert"
    return "other"


class DiagnosticObserver:
    """Keep raw PID/XID only in memory; expose stable aliases in the report."""

    def __init__(self, owner_dsn: str, *, project_id: str, prefix: str):
        self.owner_dsn = owner_dsn
        self.project_id = project_id
        self.prefix = prefix
        self.stop_event = Event()
        self.ready = Event()
        self.thread = Thread(target=self._run, name="s05-lock-wait-observer", daemon=True)
        self.origin_ns: int | None = None
        self.error: str | None = None
        self.samples: list[dict] = []
        self.row_samples: list[dict] = []
        self.raw_pid_to_alias: dict[int, str] = {}
        self.raw_xid_to_alias: dict[str, str] = {}
        self.intervals_ms: list[float] = []

    def _alias(self, pid: int) -> str:
        if pid not in self.raw_pid_to_alias:
            self.raw_pid_to_alias[pid] = f"backend-{len(self.raw_pid_to_alias) + 1}"
        return self.raw_pid_to_alias[pid]

    def start(self) -> None:
        self.thread.start()
        if not self.ready.wait(5):
            raise RuntimeError("diagnostic observer did not become ready")
        if self.error:
            raise RuntimeError(f"diagnostic observer failed: {self.error}")

    def mark_wave_start(self) -> None:
        self.origin_ns = perf_counter_ns()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(5)
        if self.thread.is_alive():
            raise RuntimeError("diagnostic observer did not stop")
        if self.error:
            raise RuntimeError(f"diagnostic observer failed: {self.error}")

    def _run(self) -> None:
        try:
            with psycopg.connect(self.owner_dsn, autocommit=True, row_factory=dict_row) as conn:
                target_ctid = conn.execute(
                    "SELECT ctid::text AS ctid FROM inv.projects WHERE project_id=%s",
                    (self.project_id,),
                ).fetchone()["ctid"]
                self.ready.set()
                previous_ns = perf_counter_ns()
                while not self.stop_event.is_set():
                    sampled_ns = perf_counter_ns()
                    self.intervals_ms.append((sampled_ns - previous_ns) / 1_000_000)
                    previous_ns = sampled_ns
                    rows = conn.execute(
                        """SELECT pid,application_name,state,wait_event_type,wait_event,
                        backend_xid::text AS backend_xid,
                        pg_blocking_pids(pid) AS blockers,query,
                        extract(epoch from (clock_timestamp()-query_start))*1000 AS query_age_ms
                        FROM pg_stat_activity
                        WHERE datname=current_database()
                          AND application_name LIKE %s
                          AND pid<>pg_backend_pid() AND state<>'idle'
                        ORDER BY pid""",
                        (self.prefix + "%",),
                    ).fetchall()
                    if self.origin_ns is not None:
                        raw_graph = {
                            int(row["pid"]): [int(value) for value in row["blockers"]]
                            for row in rows
                        }

                        def depth(pid: int, seen: frozenset[int]) -> int:
                            if pid in seen or not raw_graph.get(pid):
                                return 0
                            return 1 + max(
                                depth(blocker, seen | {pid})
                                for blocker in raw_graph[pid]
                            )

                        public_rows = []
                        for row in rows:
                            pid = int(row["pid"])
                            alias = self._alias(pid)
                            if row["backend_xid"]:
                                self.raw_xid_to_alias[str(row["backend_xid"])] = alias
                            public_rows.append(
                                {
                                    "backendId": alias,
                                    "applicationName": row["application_name"],
                                    "state": row["state"],
                                    "waitEventType": row["wait_event_type"],
                                    "waitEvent": row["wait_event"],
                                    "statementClass": _classification(row["query"]),
                                    "queryAgeMs": round(float(row["query_age_ms"]), 3),
                                    "blockingBackendIds": [
                                        self._alias(blocker) for blocker in raw_graph[pid]
                                    ],
                                    "blockingChainDepth": depth(pid, frozenset()),
                                    "hasBackendXid": bool(row["backend_xid"]),
                                }
                            )
                        offset_ms = round((sampled_ns - self.origin_ns) / 1_000_000, 3)
                        self.samples.append({"offsetMs": offset_ms, "backends": public_rows})
                        row_locks = conn.execute(
                            """SELECT modes,pids FROM pgrowlocks('inv.projects')
                            WHERE locked_row::text=%s""",
                            (target_ctid,),
                        ).fetchall()
                        if row_locks:
                            modes = sorted(
                                mode
                                for item in row_locks
                                for mode in (item["modes"] or [])
                            )
                            self.row_samples.append(
                                {
                                    "offsetMs": offset_ms,
                                    "modes": modes,
                                    "holderCount": len(
                                        {
                                            int(pid)
                                            for item in row_locks
                                            for pid in (item["pids"] or [])
                                            if int(pid) > 0
                                        }
                                    ),
                                }
                            )
                    self.stop_event.wait(0.005)
        except Exception as error:  # retain only the exception class
            self.error = type(error).__name__
            self.ready.set()

    def public_report(self) -> dict:
        interval_values = self.intervals_ms[1:]
        depths = [
            backend["blockingChainDepth"]
            for sample in self.samples
            for backend in sample["backends"]
        ]
        lock_waiters = [
            sum(b["waitEventType"] == "Lock" for b in sample["backends"])
            for sample in self.samples
        ]
        return {
            "nominalSamplingIntervalMs": 5,
            "actualSamplingIntervalP50Ms": round(percentile_nearest_rank(interval_values, 0.5), 3)
            if interval_values
            else None,
            "actualSamplingIntervalP95Ms": round(percentile_nearest_rank(interval_values, 0.95), 3)
            if interval_values
            else None,
            "actualSamplingIntervalMaxMs": round(max(interval_values), 3)
            if interval_values
            else None,
            "sampleCount": len(self.samples),
            "maxLockWaiterCount": max(lock_waiters, default=0),
            "maxBlockingChainDepth": max(depths, default=0),
            "backendXidSampleCount": sum(
                backend["hasBackendXid"]
                for sample in self.samples
                for backend in sample["backends"]
            ),
            "pgrowlocksSnapshotCount": len(self.row_samples),
            "pgrowlocksModes": sorted(
                set(mode for sample in self.row_samples for mode in sample["modes"])
            ),
            "pgrowlocksMaxHolderCount": max(
                (sample["holderCount"] for sample in self.row_samples), default=0
            ),
            "timeline": self.samples,
            "pgrowlocksSnapshots": self.row_samples,
            "rawPidRetained": False,
            "rawXidRetained": False,
        }


def _server_segments(container: str, since_epoch: float, observer: DiagnosticObserver) -> dict:
    completed = subprocess.run(
        ["docker", "logs", "--since", str(max(0, int(since_epoch) - 1)), container],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError("PostgreSQL service log read failed")
    lines = (completed.stdout + "\n" + completed.stderr).splitlines()
    events = []
    for line in lines:
        matched = _LOG_RE.search(line)
        if not matched:
            continue
        pid = int(matched.group("pid"))
        waiter = observer.raw_pid_to_alias.get(pid)
        if waiter is None:
            continue
        lock_text = matched.group("lock")
        xid_match = _XID_RE.search(lock_text)
        holder = (
            observer.raw_xid_to_alias.get(xid_match.group("xid"))
            if xid_match
            else None
        )
        events.append(
            {
                "backendId": waiter,
                "event": (
                    "still-waiting"
                    if matched.group("event") == "still waiting for"
                    else "acquired"
                ),
                "lockKind": "tuple" if "tuple" in lock_text.lower() else "transactionid",
                "holderAlias": holder or "unresolved-holder",
                "reportedWaitMs": round(float(matched.group("ms")), 3),
            }
        )
    acquired = [item for item in events if item["event"] == "acquired"]
    by_waiter = defaultdict(list)
    for item in acquired:
        by_waiter[item["backendId"]].append(item)
    summaries = []
    for backend, items in sorted(by_waiter.items()):
        holders = [item["holderAlias"] for item in items]
        summaries.append(
            {
                "backendId": backend,
                "loggedSegmentCount": len(items),
                "sumLoggedWaitMs": round(sum(i["reportedWaitMs"] for i in items), 3),
                "maxSegmentWaitMs": max(i["reportedWaitMs"] for i in items),
                "holderChanges": sum(a != b for a, b in zip(holders, holders[1:])),
                "tupleWaitCount": sum(i["lockKind"] == "tuple" for i in items),
                "unresolvedHolderCount": sum(
                    i["holderAlias"] == "unresolved-holder" for i in items
                ),
            }
        )
    return {
        "logRead": True,
        "thresholdMs": 10,
        "loggedEventCount": len(events),
        "loggedAcquiredSegmentCount": len(acquired),
        "transactionSegmentCount": sum(i["lockKind"] == "transactionid" for i in acquired),
        "tupleSegmentCount": sum(i["lockKind"] == "tuple" for i in acquired),
        "waiters": summaries,
        "events": events,
        "rawLogRetained": False,
    }


def test_approved_legacy_lock_wait_wave(placement_benchmark_env):
    assert os.getenv("INV_S05_LOCK_WAIT_DIAGNOSTIC") == "1", (
        "run only through tools/placement_lock_wait_diagnostic.py"
    )
    phase = os.environ["INV_S05_LOCK_WAIT_PHASE"]
    assert phase in {"legacy", "fk-dropped"}
    assert placement_benchmark_env.request_count == 20
    a = placement_benchmark_env
    assert a.e.lock_wait_diagnostic
    assert a.e.fk_dropped_control == (phase == "fk-dropped")

    with a.e.db.transaction(a.e.tenant) as conn:
        settings = {
            "logLockWaits": conn.execute("SHOW log_lock_waits").fetchone()["log_lock_waits"],
            "deadlockTimeout": conn.execute("SHOW deadlock_timeout").fetchone()["deadlock_timeout"],
            "lockTimeout": conn.execute("SHOW lock_timeout").fetchone()["lock_timeout"],
            "statementTimeout": conn.execute("SHOW statement_timeout").fetchone()["statement_timeout"],
        }
    assert settings == {
        "logLockWaits": "on",
        "deadlockTimeout": "10ms",
        "lockTimeout": "500ms",
        "statementTimeout": "2s",
    }

    runs = [planned(a.e) for _ in range(20)]
    _start_observation_window(a)
    prefix = f"s05lw-{phase}-"
    observer = DiagnosticObserver(a.e.owner, project_id=a.e.project, prefix=prefix)
    observer.start()
    started_epoch = time()

    def reserve(index: int):
        dsn = make_conninfo(a.e.runtime, application_name=f"{prefix}{index:02d}")
        store = PlacementStore(
            Database(
                dsn,
                recovery_epoch=a.e.epoch,
                placement_short_commit=False,
            )
        )
        return store.reserve(
            Principal(a.e.tenant, "benchmark"),
            a.e.project,
            runs[index]["runId"],
            a.request,
            key=f"s05-lock-wait:{phase}:{index}",
            policy_version="roof:s05-lock-wait:1",
            pool_version="project-nodes:s05-lock-wait:1",
        )

    try:
        round_evidence, _ = run_round(
            name=phase,
            request_count=20,
            concurrency=20,
            reserve=reserve,
            on_wave_start=observer.mark_wave_start,
        )
    finally:
        observer.stop()
    server = _server_segments(os.environ["INV_S05_PG_CONTAINER"], started_epoch, observer)
    queue = observer.public_report()
    errors_by_sqlstate = dict(round_evidence.errors_by_sqlstate)
    report = {
        "schemaVersion": "1.0.0",
        "scope": "development-PC; disposable PostgreSQL; diagnostic-only",
        "phase": phase,
        "codeSha": os.environ["INV_S05_CODE_SHA"],
        "requestCount": 20,
        "concurrency": 20,
        "settings": settings,
        "fkPresent": phase == "legacy",
        "successCount": round_evidence.success_count,
        "failureCount": round_evidence.failure_count,
        "p95AllMs": round_evidence.p95_all_ms,
        "p95SuccessMs": round_evidence.p95_success_ms,
        "errorsByCode": round_evidence.errors_by_code,
        "errorsBySqlstate": errors_by_sqlstate,
        "queueObservation": queue,
        "serverLockWaits": server,
        "cleanup": "pytest fixture owns disposable DB and role; verified after subprocess exit",
        "limitations": [
            "one 20-request diagnostic wave; not AC-05 evidence",
            "server log segments shorter than 10ms are intentionally unlogged",
            "backend_xid-to-holder alias may remain unresolved between observer samples",
        ],
    }
    report_path = Path(os.environ["INV_S05_LOCK_WAIT_REPORT"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _release_round(a)
    assert _active(a) == {"cpu": 0, "memory": 0}
    assert queue["sampleCount"] > 0
    assert server["logRead"]
    assert queue["pgrowlocksSnapshotCount"] > 0
