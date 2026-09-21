"""Evaluate the alarms GOV-ALERT-001 defines that a database can answer.

The alarm table in ``40_Governance/알람 라우팅과 대응 주체.md`` fixed the
conditions, severities and first responder for each alarm and left the channel
and the people as ``unknown`` pending a decision. Nothing evaluates a condition,
so the detection step the security guide's incident response starts from does
not currently happen at all. This is the detection layer, not the routing one:
it decides whether a condition holds. It does not deliver anywhere, because
GOV-ALERT-001 leaves the channel ``unknown`` and routing a P1 to a guess is
worse than printing it.

Recovered 2026-09-21 from the unmerged ``review/claude-account-results`` work
(commit 00b1159), not by cherry-pick: integration moved, so every table and
column below was re-verified against the current tree, the spec was re-read,
and the decision logic was split into pure functions so that *both* sides —
a condition firing when true and staying quiet when false — are testable
without a database. A tool that always fired would pass a one-sided test.

Two node tables exist: the kernel ``inv.nodes`` (status ``online``/``offline``,
``heartbeat_at``, ``clock_skew_seconds``; defined in
``services/control-plane/src/inv/migrations/0001_core.sql``) and the saintvision
``public.nodes`` (status ``active``…, ``last_heartbeat_at``). Node liveness here
reads the kernel table, which is where heartbeats land.

**Says plainly which alarms it cannot evaluate and why.** A tool that printed
"no alarms" while silently omitting every latency and error rate would read as
"the system is healthy" when it means "the four things I can see are fine".

Read-only.

Usage:
    python tools/alarm_check.py --dsn DSN [--tenant UUID] [--json]

Exit: 1 if anything is firing (or --json with firing), else 0.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

#: Alarms from GOV-ALERT-001 this tool cannot decide, with the reason. Listed
#: rather than omitted: an operator reading "nothing is firing" needs to know
#: how much of the table that sentence covers.
NOT_EVALUABLE: tuple[tuple[str, str, str], ...] = (
    ("비밀 원문 노출 탐지", "P1", "needs the redaction detector's output over live traffic"),
    ("정책 우회 또는 승인 없는 L2/L3 실행", "P1", "needs policy decision records over live traffic"),
    ("Evidence 기록 실패", "P1", "needs a write-failure counter; a database cannot report writes it never received"),
    ("OPA 응답 실패·타임아웃", "P1", "needs the policy engine's own metrics"),
    ("중복 부수 효과 탐지", "P1", "needs execution-side idempotency counters"),
    ("Control Plane 오류율", "P1/P2", "needs request metrics over a 5 minute window"),
    ("스케줄 결정 P95", "P2", "needs scheduler latency samples"),
    ("정책 결정 P95", "P2", "needs policy latency samples"),
    ("Run 이벤트 전달 P95", "P2", "needs delivery latency samples"),
    ("아티팩트 검증 대기 적체", "P2", "needs a verification-queue depth metric, not a table a DB keeps"),
    ("캐시 적중률 하락 / 버킷 용량 추세 / lock wait 증가", "P3", "trend alarms need a metrics history"),
)

#: Alarms whose data exists but which GOV-ALERT-001 has NOT activated. The spec
#: excludes nodes with missing/non-finite/abs(skew)>5 measurements from runtime
#: eligibility. That safety filter is distinct from an operator-routed alarm:
#: ±5 seconds is not calibrated against pilot hardware, and the alert channel
#: and responders remain unknown. The guard stays active; this alarm stays gated
#: until those governance inputs are adopted.
GOVERNANCE_GATED: tuple[tuple[str, str, str], ...] = (
    (
        "Node 시각 스큐 한도 초과",
        "P2",
        "Runtime eligibility already excludes missing/non-finite/abs(skew)>5 nodes; "
        "the routed alarm remains gated until the ±5s threshold is calibrated and "
        "channel/responders are decided under ERR-DESIGN-007",
    ),
)


# --- Pure decision functions (no database; this is what the tests exercise) ---

def count_alarm(name: str, severity: str, responder: str, count: int, detail: str) -> dict[str, Any]:
    """Fires iff ``count > 0``. The quiet side (count == 0 → not firing) is the
    half a one-sided test would miss, so it is asserted explicitly."""
    return {
        "alarm": name,
        "severity": severity,
        "firstResponder": responder,
        "firing": count > 0,
        "detail": detail,
    }


def partition_alarm(table: str, latest_bound: dt.datetime | None, now: dt.datetime) -> dict[str, Any]:
    """Runway to a range-partitioned table's last upper bound.

    <30 days → P1 (or already failing when no partition covers now); <60 → P2;
    otherwise not firing. "잔여 <1개월" is meant to be runway, not the outage:
    the P1 must warn *before* inserts start refusing, not announce that they have.
    """
    remaining = (latest_bound - now).days if latest_bound else -1
    if latest_bound is None:
        where = "no partition covers this month; inserts are failing now"
    else:
        where = f"{remaining} day(s) of runway; partitions run to {latest_bound:%Y-%m-%d}"
    if remaining < 30:
        return count_alarm(f"{table} partition 잔여 <1개월", "P1", "DB 운영", 1, where)
    if remaining < 60:
        return count_alarm(f"{table} partition 잔여 <2개월", "P2", "DB 운영", 1, where)
    return count_alarm(f"{table} partition 잔여", "P1/P2", "DB 운영", 0, where)


def coverage_summary(evaluated: int, not_evaluable: int, gated: int) -> str:
    """Describe observation coverage without inventing a spec row count.

    GOV-ALERT-001 contains condition rows that collapse into the same runtime
    data family (for example partition runway thresholds and duplicate
    severity rows).  Counting the collapsed runtime entries as if they were
    the specification's rows produces a false denominator.  Report the three
    observable buckets instead.
    """
    return (
        f"{evaluated} evaluated data families; {not_evaluable} conditions not "
        f"evaluated here; {gated} governance-gated conditions"
    )


# --- Thin database layer: measure, then hand each measurement to the deciders ---

def evaluate(dsn: str, tenant: str | None, now: dt.datetime) -> dict[str, Any]:
    from sqlalchemy import create_engine, text

    from saintvision.db.partitions import partition_status

    url = dsn
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    engine = create_engine(url, future=True)
    alarms: list[dict[str, Any]] = []
    try:
        with engine.connect() as connection:
            for status in partition_status(connection, now=now):
                alarms.append(partition_alarm(status.table, status.latest_bound, now))

            scope = "AND tenant_id = :tenant" if tenant else ""
            params: dict[str, Any] = {"tenant": tenant} if tenant else {}

            mismatches = connection.execute(
                text(
                    "SELECT coalesce(sum(mismatch_count),0) FROM public.storage_checks "
                    f"WHERE checked_at >= :since {scope}"
                ),
                {**params, "since": now - dt.timedelta(days=7)},
            ).scalar_one()
            alarms.append(
                count_alarm(
                    "체크섬 불일치", "P1", "Storage 운영", int(mismatches),
                    f"{mismatches} mismatch(es) in folder checks over the last 7 days",
                )
            )

            unverified = connection.execute(
                text(f"SELECT count(*) FROM public.backup_records WHERE NOT verified {scope}"),
                params,
            ).scalar_one()
            # 0036 constrains a drill to met_targets only when outcome='passed';
            # anything not 'passed' (failed, aborted) is a failed restore smoke.
            failed_drills = connection.execute(
                text(f"SELECT count(*) FROM public.recovery_drills WHERE outcome <> 'passed' {scope}"),
                params,
            ).scalar_one()
            alarms.append(
                count_alarm(
                    "백업 실패 또는 복원 스모크 실패", "P2", "DB 운영",
                    int(unverified) + int(failed_drills),
                    f"{unverified} unverified backup(s), {failed_drills} non-passed drill(s)",
                )
            )

            # Kernel node table: status 'online', heartbeat_at (not last_heartbeat_at).
            stale = connection.execute(
                text(
                    "SELECT count(*) FROM inv.nodes WHERE status = 'online' "
                    "AND heartbeat_at < clock_timestamp() - interval '60 seconds'"
                )
            ).scalar_one()
            alarms.append(
                count_alarm(
                    "Node 이탈 감지 지연", "P2", "인프라", int(stale),
                    f"{stale} node(s) still marked online with no heartbeat for over 60s",
                )
            )
    finally:
        engine.dispose()

    firing = [a for a in alarms if a["firing"]]
    return {
        "evaluatedAt": now,
        "alarms": alarms,
        "firing": firing,
        "notEvaluable": [
            {"alarm": name, "severity": severity, "reason": reason}
            for name, severity, reason in NOT_EVALUABLE
        ],
        "governanceGated": [
            {"alarm": name, "severity": severity, "reason": reason}
            for name, severity, reason in GOVERNANCE_GATED
        ],
        # Never "healthy". This tool saw part of the table.
        "coverage": coverage_summary(
            len(alarms), len(NOT_EVALUABLE), len(GOVERNANCE_GATED)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate GOV-ALERT-001 alarms a database can answer.")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--tenant", help="limit tenant-scoped alarms to one tenant")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = evaluate(args.dsn, args.tenant, dt.datetime.now(dt.timezone.utc))

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 1 if report["firing"] else 0

    for alarm in report["alarms"]:
        mark = f"{alarm['severity']:5} FIRING" if alarm["firing"] else "      ok    "
        print(f"  {mark}  {alarm['alarm']}: {alarm['detail']}")
        if alarm["firing"]:
            print(f"                first responder: {alarm['firstResponder']}")

    print(f"\n{report['coverage']}. Not evaluated here:")
    for entry in report["notEvaluable"]:
        print(f"  {entry['severity']:5} {entry['alarm']} — {entry['reason']}")
    for entry in report["governanceGated"]:
        print(f"  {entry['severity']:5} {entry['alarm']} — gated: {entry['reason']}")
    print(
        "\nNothing firing above does not mean the system is healthy: the alarms "
        "listed as not evaluated have not been checked by anything."
    )
    print(
        "No channel is implemented. GOV-ALERT-001 leaves the channel and the "
        "people as unknown, and routing a P1 to a guess is worse than printing it."
    )
    return 1 if report["firing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
