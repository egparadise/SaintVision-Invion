"""Evaluate the alarms GOV-ALERT-001 defines that a database can answer.

The alarm table in ``40_Governance/알람 라우팅과 대응 주체.md`` fixed the
conditions, severities and first responder for each alarm and left the channel
and the people as ``unknown`` pending a decision. Nothing has ever evaluated a
condition, so the detection step the security guide's incident response starts
from does not currently happen at all.

This evaluates the subset a database can answer on its own, and — this is the
part that matters — **says plainly which alarms it cannot evaluate and why.** A
tool that printed "no alarms" while silently omitting every latency and error
rate would be worse than no tool: it would read as "the system is healthy" when
it means "the four things I can see are fine".

Three of the conditions below only became answerable once something started
producing the records they read: backup verification, recovery drills and
contributed-folder checks all had recorders with no collector until recently.

Read-only. No channel is implemented, because the channel is a decision that has
not been made and inventing one would route a P1 somewhere nobody watches.

Usage:
    python tools/alarm_check.py --dsn DSN [--tenant UUID] [--json]
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
    ("캐시 적중률 하락 / 버킷 용량 추세 / lock wait 증가", "P3", "trend alarms need a metrics history"),
)


def _fire(
    name: str, severity: str, responder: str, firing: bool, detail: str
) -> dict[str, Any]:
    return {
        "alarm": name,
        "severity": severity,
        "firstResponder": responder,
        "firing": firing,
        "detail": detail,
    }


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
            # Partition headroom. The condition is "상시 검사" precisely because
            # a range-partitioned table does not degrade when it runs out — it
            # refuses the insert, and the Evidence write fails outright.
            for status in partition_status(connection, now=now):
                bound = status.latest_bound
                # Measured as time remaining to the last partition's upper
                # bound, not as a count of whole months from the month floor.
                # The month count reaches zero only once the *current* month is
                # unpartitioned — by which point inserts are already failing, so
                # a P1 raised on it would announce an outage rather than warn of
                # one. "잔여 <1개월" is meant to be runway.
                remaining = (bound - now).days if bound else -1
                where = (
                    f"{remaining} day(s) of runway; partitions run to {bound:%Y-%m-%d}"
                    if bound
                    else "no partition covers this month; inserts are failing now"
                )
                if remaining < 30:
                    alarms.append(
                        _fire(
                            f"{status.table} partition 잔여 <1개월",
                            "P1",
                            "DB 운영",
                            True,
                            where,
                        )
                    )
                elif remaining < 60:
                    alarms.append(
                        _fire(
                            f"{status.table} partition 잔여 <2개월",
                            "P2",
                            "DB 운영",
                            True,
                            where,
                        )
                    )
                else:
                    alarms.append(
                        _fire(
                            f"{status.table} partition 잔여",
                            "P1/P2",
                            "DB 운영",
                            False,
                            where,
                        )
                    )

            scope = "AND tenant_id = :tenant" if tenant else ""
            params = {"tenant": tenant} if tenant else {}

            mismatches = connection.execute(
                text(
                    "SELECT coalesce(sum(mismatch_count),0) FROM public.storage_checks "
                    f"WHERE checked_at >= :since {scope}"
                ),
                {**params, "since": now - dt.timedelta(days=7)},
            ).scalar_one()
            alarms.append(
                _fire(
                    "체크섬 불일치",
                    "P1",
                    "Storage 운영",
                    mismatches > 0,
                    f"{mismatches} mismatch(es) in folder checks over the last 7 days",
                )
            )

            unverified = connection.execute(
                text(
                    "SELECT count(*) FROM public.backup_records "
                    f"WHERE NOT verified {scope}"
                ),
                params,
            ).scalar_one()
            failed_drills = connection.execute(
                text(
                    "SELECT count(*) FROM public.recovery_drills "
                    f"WHERE outcome = 'failed' {scope}"
                ),
                params,
            ).scalar_one()
            alarms.append(
                _fire(
                    "백업 실패 또는 복원 스모크 실패",
                    "P2",
                    "DB 운영",
                    (unverified + failed_drills) > 0,
                    f"{unverified} unverified backup(s), {failed_drills} failed drill(s)",
                )
            )

            stale = connection.execute(
                text(
                    "SELECT count(*) FROM inv.nodes WHERE status = 'online' "
                    "AND heartbeat_at < clock_timestamp() - interval '60 seconds'"
                )
            ).scalar_one()
            alarms.append(
                _fire(
                    "Node 이탈 감지 지연",
                    "P2",
                    "인프라",
                    stale > 0,
                    f"{stale} node(s) marked online with no heartbeat for over 60s",
                )
            )

            skewed = connection.execute(
                text(
                    "SELECT count(*) FROM inv.nodes "
                    "WHERE clock_skew_seconds IS NOT NULL AND abs(clock_skew_seconds) > 5"
                )
            ).scalar_one()
            alarms.append(
                _fire(
                    "Node 시각 스큐 한도 초과",
                    "P2",
                    "인프라",
                    skewed > 0,
                    f"{skewed} node(s) beyond the 5 second limit",
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
        # Never "healthy". This tool saw part of the table.
        "coverage": (
            f"{len(alarms)} of {len(alarms) + len(NOT_EVALUABLE)} alarm conditions "
            f"in GOV-ALERT-001 were evaluated here"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
