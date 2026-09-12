"""Every alarm condition this tool evaluates, shown firing.

GOV-ALERT-001 fixed the conditions and severities and nothing ever evaluated
one, so the detection step incident response begins from did not happen. A
checker that only ever printed "ok" would reproduce that state while looking
like it had fixed it, so each condition here is driven into firing.

The coverage statement is tested too. "Nothing is firing" over seven of
seventeen conditions is a very different sentence from "the system is healthy",
and the tool has to be the one that says so.
"""

from __future__ import annotations

import datetime as dt
import random
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

pytestmark = pytest.mark.postgres

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _id(prefix: str) -> str:
    return prefix + "_" + "".join(random.choice(CROCKFORD) for _ in range(26))


@pytest.fixture
def deployment(migrated, database_url):
    """A tenant with a node the kernel knows, and nothing wrong with it."""
    import psycopg

    dsn = database_url.replace("postgresql+psycopg://", "postgresql://")
    ids = {
        "dsn": dsn,
        "tenant": str(uuid.uuid4()),
        "user": _id("usr"),
        "node": _id("nod"),
        "contribution": _id("stc"),
        "epoch": str(uuid.uuid4()),
    }
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO inv.control_epoch(singleton,epoch) VALUES(true,%s) "
            "ON CONFLICT (singleton) DO UPDATE SET epoch=EXCLUDED.epoch",
            (ids["epoch"],),
        )
        conn.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'al')",
            (ids["tenant"], uuid.uuid4().hex[:12]),
        )
        conn.execute(
            "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name,status) "
            "VALUES(%s,%s,%s,'u','active')",
            (ids["tenant"], ids["user"], "oidc:" + uuid.uuid4().hex),
        )
        conn.execute(
            "INSERT INTO public.nodes"
            "(tenant_id,node_id,hostname,os_type,os_version,agent_version,status) "
            "VALUES(%s,%s,'h','linux','1','1','active')",
            (ids["tenant"], ids["node"]),
        )
        conn.execute(
            "INSERT INTO public.storage_contributions"
            "(tenant_id,contribution_id,node_id,declared_path,normalized_path,"
            "mode,status,registered_by_user_id) "
            "VALUES(%s,%s,%s,'/srv/share','/srv/share','read_only','active',%s)",
            (ids["tenant"], ids["contribution"], ids["node"], ids["user"]),
        )
        conn.execute("INSERT INTO inv.tenants(tenant_id,name) VALUES(%s,'al')", (ids["tenant"],))
        conn.execute(
            "INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch,heartbeat_at) "
            "VALUES(%s,%s,'online',%s,clock_timestamp())",
            (ids["tenant"], ids["node"], ids["epoch"]),
        )
    return ids


def _evaluate(ids, now: dt.datetime | None = None):
    from alarm_check import evaluate

    return evaluate(ids["dsn"], ids["tenant"], now or dt.datetime.now(dt.timezone.utc))


def _sql(ids, statement: str, params: tuple = ()) -> None:
    import psycopg

    with psycopg.connect(ids["dsn"], autocommit=True) as conn:
        conn.execute(statement, params)


def _named(report, fragment: str):
    return [a for a in report["alarms"] if fragment in a["alarm"]]


def test_a_sound_deployment_fires_nothing_this_tool_can_see(deployment) -> None:
    report = _evaluate(deployment)
    assert report["firing"] == []


def test_a_checksum_mismatch_fires_p1(deployment) -> None:
    """Storage rot is P1: a corrupted byte is not outvoted by intact ones."""
    _sql(
        deployment,
        "INSERT INTO public.storage_checks"
        "(tenant_id,check_id,contribution_id,reachable,sampled_count,mismatch_count,healthy) "
        "VALUES(%s,%s,%s,true,10,1,false)",
        (deployment["tenant"], _id("stk"), deployment["contribution"]),
    )
    (alarm,) = _named(_evaluate(deployment), "체크섬 불일치")
    assert alarm["firing"] and alarm["severity"] == "P1"
    assert alarm["firstResponder"] == "Storage 운영"


def test_an_unverified_backup_fires(deployment) -> None:
    _sql(
        deployment,
        "INSERT INTO public.backup_records"
        "(tenant_id,backup_id,kind,location_ref,off_site,byte_size,verified,started_at,retention_until) "
        "VALUES(%s,%s,'logical','/b.dump',false,10,false,now(),now()+interval '35 days')",
        (deployment["tenant"], _id("bkp")),
    )
    (alarm,) = _named(_evaluate(deployment), "백업 실패")
    assert alarm["firing"] and alarm["severity"] == "P2"


def test_a_node_that_stopped_beating_fires(deployment) -> None:
    _sql(
        deployment,
        "UPDATE inv.nodes SET heartbeat_at = clock_timestamp() - interval '5 minutes' "
        "WHERE tenant_id=%s",
        (deployment["tenant"],),
    )
    (alarm,) = _named(_evaluate(deployment), "Node 이탈")
    assert alarm["firing"]


def test_clock_skew_beyond_the_limit_fires(deployment) -> None:
    """Skew matters because leases and receipts are ordered in time."""
    _sql(
        deployment,
        "UPDATE inv.nodes SET clock_skew_seconds = 42 WHERE tenant_id=%s",
        (deployment["tenant"],),
    )
    (alarm,) = _named(_evaluate(deployment), "시각 스큐")
    assert alarm["firing"]


def test_partition_headroom_crosses_p2_then_p1(deployment) -> None:
    """A range-partitioned table does not degrade when it runs out.

    It refuses the insert, so the Evidence write fails outright. Evaluating this
    from a future date is how the alarm earns its "상시 검사" condition: the
    migration created partitions three months ahead and nothing creates more.
    """
    report = _evaluate(deployment)
    (baseline,) = _named(report, "evidence_envelopes partition 잔여")
    assert not baseline["firing"], "the fixture starts with runway"

    from sqlalchemy import create_engine

    from saintvision.db.partitions import partition_status

    url = "postgresql+psycopg://" + deployment["dsn"][len("postgresql://") :]
    engine = create_engine(url, future=True)
    try:
        with engine.connect() as connection:
            status = {
                s.table: s
                for s in partition_status(
                    connection, now=dt.datetime.now(dt.timezone.utc)
                )
            }["evidence_envelopes"]
    finally:
        engine.dispose()
    bound = status.latest_bound
    assert bound is not None

    # 45 days of runway: warn, do not alarm.
    report = _evaluate(deployment, bound - dt.timedelta(days=45))
    (alarm,) = _named(report, "evidence_envelopes partition 잔여 <2개월")
    assert alarm["firing"] and alarm["severity"] == "P2"

    # 10 days of runway: still before anything breaks, and already P1, which is
    # the point of measuring runway instead of counting whole months.
    report = _evaluate(deployment, bound - dt.timedelta(days=10))
    (alarm,) = _named(report, "evidence_envelopes partition 잔여 <1개월")
    assert alarm["firing"] and alarm["severity"] == "P1"
    assert "10 day(s) of runway" in alarm["detail"]

    # Past the last bound: the insert has nowhere to land.
    report = _evaluate(deployment, bound + dt.timedelta(days=5))
    (alarm,) = _named(report, "evidence_envelopes partition 잔여 <1개월")
    assert alarm["firing"]
    assert "inserts are failing now" in alarm["detail"]


def test_the_tool_states_how_much_of_the_table_it_did_not_check(deployment) -> None:
    """The sentence that stops "nothing firing" being read as "healthy"."""
    report = _evaluate(deployment)
    assert report["notEvaluable"], "omitting them silently would be the failure"
    # Every alarm it cannot decide carries a reason, not just a name.
    assert all(entry["reason"] for entry in report["notEvaluable"])
    # And the P1s it cannot see are named, because those are the ones that
    # matter most to somebody reading a clean report.
    unseen = " ".join(e["alarm"] for e in report["notEvaluable"] if e["severity"].startswith("P1"))
    assert "비밀 원문 노출" in unseen
    assert "Evidence 기록 실패" in unseen
    assert "of" in report["coverage"]
