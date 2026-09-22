"""GOV-ALERT-001 alarm evaluation: fires when the condition is true, stays
quiet when it is false.

The half that matters is the quiet side. A tool that always fired would pass
any test that only checked "does it fire when something is wrong"; it would
route a P1 every run and be turned off within a day. So every case below that
asserts firing has a sibling that asserts silence on the same alarm.

Runs without a database: the decision logic in ``alarm_check`` is pure, and the
sqlalchemy import lives inside ``evaluate`` so importing the module needs no PG.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from decimal import Decimal
from uuid import uuid4

import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from alarm_check import (  # noqa: E402
    CLOCK_SKEW_LIMIT_SECONDS,
    GOVERNANCE_GATED,
    NOT_EVALUABLE,
    clock_skew_alarm,
    count_alarm,
    coverage_summary,
    evaluate,
    partition_alarm,
    skew_outside_limit,
)

NOW = dt.datetime(2026, 9, 21, 12, 0, 0, tzinfo=dt.timezone.utc)


# --- count-based alarms: both sides ---

def test_count_alarm_fires_when_positive():
    a = count_alarm("체크섬 불일치", "P1", "Storage 운영", 3, "3 mismatch(es)")
    assert a["firing"] is True
    assert a["severity"] == "P1" and a["firstResponder"] == "Storage 운영"


def test_count_alarm_is_quiet_when_zero():
    # The quiet side: a healthy count must NOT fire. An always-firing tool fails here.
    a = count_alarm("체크섬 불일치", "P1", "Storage 운영", 0, "0 mismatch(es)")
    assert a["firing"] is False


def test_count_alarm_boundary_one_fires():
    assert count_alarm("백업 실패 또는 복원 스모크 실패", "P2", "DB 운영", 1, "")["firing"] is True


# --- partition runway: three regions, only the short ones fire ---

def test_partition_far_future_is_quiet():
    bound = NOW + dt.timedelta(days=120)
    a = partition_alarm("evidence_envelopes", bound, NOW)
    assert a["firing"] is False
    assert "잔여" in a["alarm"]


def test_partition_under_one_month_fires_p1():
    bound = NOW + dt.timedelta(days=20)
    a = partition_alarm("evidence_envelopes", bound, NOW)
    assert a["firing"] is True and a["severity"] == "P1"
    assert "<1개월" in a["alarm"]


def test_partition_under_two_months_fires_p2():
    bound = NOW + dt.timedelta(days=45)
    a = partition_alarm("evidence_envelopes", bound, NOW)
    assert a["firing"] is True and a["severity"] == "P2"
    assert "<2개월" in a["alarm"]


def test_partition_exactly_sixty_days_is_quiet():
    # 60 days remaining is not < 60 → quiet. Guards the boundary between P2 and ok.
    bound = NOW + dt.timedelta(days=60)
    assert partition_alarm("run_records", bound, NOW)["firing"] is False


def test_partition_missing_bound_fires_p1_already_failing():
    a = partition_alarm("evidence_envelopes", None, NOW)
    assert a["firing"] is True and a["severity"] == "P1"
    assert "failing now" in a["detail"]


# --- honesty: the tool must keep declaring what it cannot see ---

def test_not_evaluable_still_lists_the_traffic_and_metric_alarms():
    names = {row[0] for row in NOT_EVALUABLE}
    assert "비밀 원문 노출 탐지" in names
    assert "OPA 응답 실패·타임아웃" in names


def test_clock_skew_is_no_longer_governance_gated():
    # Decision #7 option A (2026-09-22): the routed alarm is active. The gated
    # bucket must be empty AND still declared (a dropped category would read as
    # "never existed"); the alarm itself is asserted below on both sides.
    assert GOVERNANCE_GATED == ()
    assert "Node 시각 스큐 한도 초과" not in {row[0] for row in NOT_EVALUABLE}


# --- clock skew: the alarm predicate must equal the kernel guard (abs <= 5 is eligible) ---

def test_skew_limit_is_the_kernel_five_seconds():
    assert CLOCK_SKEW_LIMIT_SECONDS == Decimal(5)


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("4.9"), Decimal("5"), Decimal("-5"), 0, 4.9])
def test_skew_inside_limit_is_quiet(value):
    # Exactly 5 is INSIDE: kernel eligibility is abs(skew) <= 5, so the alarm is > 5.
    assert skew_outside_limit(value) is False


@pytest.mark.parametrize("value", [Decimal("5.0001"), Decimal("6.2"), Decimal("-5.5"), None, Decimal("NaN"), Decimal("Infinity")])
def test_skew_outside_or_unmeasured_fires(value):
    assert skew_outside_limit(value) is True


def test_clock_skew_alarm_quiet_when_all_online_nodes_inside():
    a = clock_skew_alarm([("nod_a", Decimal("0")), ("nod_b", Decimal("4.9")), ("nod_c", Decimal("-5"))])
    assert a["firing"] is False
    assert a["severity"] == "P2" and a["firstResponder"] == "인프라"
    assert "0 online node(s)" in a["detail"]


def test_clock_skew_alarm_fires_and_names_the_offenders():
    a = clock_skew_alarm([("nod_ok", Decimal("1")), ("nod_null", None), ("nod_far", Decimal("6.2"))])
    assert a["firing"] is True
    assert "nod_null=unmeasured" in a["detail"] and "nod_far=6.2s" in a["detail"]
    assert "nod_ok" not in a["detail"]


def test_clock_skew_alarm_quiet_with_no_online_nodes():
    # No online nodes -> nothing outside; the 이탈 alarm owns "nobody is online".
    assert clock_skew_alarm([])["firing"] is False


def test_coverage_does_not_claim_a_spec_row_denominator_for_collapsed_families():
    summary = coverage_summary(5, len(NOT_EVALUABLE), len(GOVERNANCE_GATED))
    assert summary == "5 evaluated data families; 11 conditions not evaluated here; 0 governance-gated conditions"
    assert " of " not in summary


def test_partition_alarm_fires_as_the_clock_advances_same_bound():
    """Time axis, PG-free: with a FIXED partition bound, advancing 'now' must flip quiet->firing.

    This is the clock-advance shape revival cannot do at a single instant. The bound does not
    change; only the clock does. A tool that ignored elapsed time would stay quiet and fail here.
    """
    bound = dt.datetime(2026, 11, 1, tzinfo=dt.timezone.utc)  # fixed partition upper bound
    t_early = dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc)  # ~92 days of runway -> quiet
    t_late = dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc)  # ~12 days -> P1 fires
    assert partition_alarm("evidence_envelopes", bound, t_early)["firing"] is False
    fired = partition_alarm("evidence_envelopes", bound, t_late)
    assert fired["firing"] is True and fired["severity"] == "P1"


# --- Real PostgreSQL: the seven cases of the ERR-DESIGN-007 revision (section 6.1) ---
#
# Disposable database provisioned through the real Alembic entry point (same
# recipe as tests/integration/conftest.py). Each case inserts kernel node rows,
# runs the real ``evaluate`` (its own connection, so rows are committed), and
# reads the one alarm under test. Deliberately NOT mocked: the point is that the
# SQL selects the right rows and the decision runs on what PostgreSQL returns.

ROOT = Path(__file__).resolve().parents[1]
SKEW_ALARM = "Node 시각 스큐 한도 초과"


def _skew_alarm(dsn: str) -> dict:
    report = evaluate(dsn, None, dt.datetime.now(dt.timezone.utc))
    (alarm,) = [a for a in report["alarms"] if a["alarm"] == SKEW_ALARM]
    return alarm


@pytest.fixture(scope="module")
def skew_db():
    admin = os.getenv("INV_TEST_ADMIN_DSN")
    if not admin:
        if os.getenv("CI"):
            pytest.fail("CI requires INV_TEST_ADMIN_DSN; DB tests must not be skipped")
        pytest.skip("Set INV_TEST_ADMIN_DSN to a disposable PostgreSQL 16+ test server")
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    from sqlalchemy.engine import URL

    name = "inv_test_" + uuid4().hex
    owner = make_conninfo(admin, dbname=name)
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        info = psycopg.conninfo.conninfo_to_dict(owner)
        url = URL.create(
            "postgresql+psycopg", username=info.get("user"), password=info.get("password"),
            host=info.get("host"), port=int(info.get("port", 5432)), database=name,
        ).render_as_string(hide_password=False)
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT, env={**os.environ, "INV_MIGRATION_DSN": url, "INV_DATABASE_URL": url},
            capture_output=True, text=True,
        )
        assert result.returncode == 0, "Alembic migration failed (credential-bearing diagnostics suppressed)"
        tenant = str(uuid4())
        with psycopg.connect(owner) as conn:
            conn.execute("INSERT INTO inv.tenants VALUES (%s,'skew-synthetic')", (tenant,))
        # ``owner`` is a psycopg conninfo (keyword form); ``url`` is what the tool's
        # create_engine needs. evaluate() takes the URL, fixtures take the conninfo.
        yield {"owner": owner, "url": url, "tenant": tenant}
    finally:
        assert name.startswith("inv_test_") and len(name) == 41
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def skew_nodes(skew_db):
    """Insert ``[(status, skew), ...]`` rows; delete them afterwards so cases are independent."""
    import psycopg
    from inv.ids import new_id

    created: list[str] = []

    def insert(rows):
        with psycopg.connect(skew_db["owner"]) as conn:
            for status, skew in rows:
                node = new_id("nod")
                conn.execute(
                    "INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch,clock_skew_seconds) VALUES (%s,%s,%s,%s,%s)",
                    (skew_db["tenant"], node, status, str(uuid4()), skew),
                )
                created.append(node)
        return list(created)

    yield insert
    # Inserting a kernel node fans out rows (inv.node_controls FK), so rows are
    # neutralised rather than deleted: an offline node is outside this alarm's
    # scope by 제4조 4항, which TC-SKEW-06 proves, so leftovers cannot leak.
    with psycopg.connect(skew_db["owner"]) as conn:
        conn.execute("UPDATE inv.nodes SET status = 'offline' WHERE node_id = ANY(%s)", (created,))


@pytest.mark.parametrize(
    "case,status,skew,expect_firing",
    [
        ("TC-SKEW-01", "online", Decimal("0.0"), False),
        ("TC-SKEW-02", "online", Decimal("4.9"), False),
        ("TC-SKEW-03", "online", Decimal("6.2"), True),
        ("TC-SKEW-04", "online", Decimal("-5.5"), True),
        ("TC-SKEW-05", "online", None, True),
        ("TC-SKEW-06", "offline", Decimal("10.0"), False),
    ],
)
def test_real_pg_clock_skew_cases(skew_db, skew_nodes, case, status, skew, expect_firing):
    skew_nodes([(status, skew)])
    alarm = _skew_alarm(skew_db["url"])
    assert alarm["firing"] is expect_firing, (case, alarm["detail"])
    assert alarm["severity"] == "P2" and alarm["firstResponder"] == "인프라"
    if expect_firing:
        assert "1 online node(s)" in alarm["detail"]
    else:
        assert "0 online node(s)" in alarm["detail"]


def test_real_pg_tc07_recovery_clears_the_alarm_without_latching(skew_db, skew_nodes):
    import psycopg

    (node,) = skew_nodes([("online", Decimal("6.2"))])
    assert _skew_alarm(skew_db["url"])["firing"] is True
    with psycopg.connect(skew_db["owner"]) as conn:
        conn.execute("UPDATE inv.nodes SET clock_skew_seconds = 0.2 WHERE node_id = %s", (node,))
    cleared = _skew_alarm(skew_db["url"])
    assert cleared["firing"] is False, cleared["detail"]


# --- The alarm is an INDEPENDENT mirror of the kernel guard: pin both boundaries ---
#
# The kernel decides eligibility in inv/scheduler.py (Python) and in four SQL
# predicates (leases, dispatch, containment, tooling). None of them import this
# tool, so the two sides can drift. These tests fail the moment either side
# changes its number or its direction. (Codex review of PR #41.)

KERNEL = ROOT / "services" / "control-plane" / "src" / "inv"
KERNEL_SQL_SITES = {
    "leases.py": r"abs\(clock_skew_seconds\)\s*<=\s*(\d+(?:\.\d+)?)",
    "dispatch.py": r"abs\(clock_skew_seconds\)\s*<=\s*(\d+(?:\.\d+)?)",
    "containment.py": r"abs\(n\.clock_skew_seconds\)\s*<=\s*(\d+(?:\.\d+)?)",
    "tooling.py": r"abs\(clock_skew_seconds\)\s*<=\s*(\d+(?:\.\d+)?)",
}


def test_alarm_limit_matches_every_kernel_predicate():
    import re

    # Python guard in the scheduler: None / non-finite / abs(...) > N  → rejected.
    scheduler = (KERNEL / "scheduler.py").read_text(encoding="utf-8")
    py = re.search(
        r"c\.clock_skew_seconds is None\s*or not c\.clock_skew_seconds\.is_finite\(\)\s*or abs\(c\.clock_skew_seconds\)\s*>\s*(\d+(?:\.\d+)?)",
        scheduler,
    )
    assert py, "scheduler clock-skew guard shape changed; re-pin the alarm mirror"
    assert Decimal(py.group(1)) == CLOCK_SKEW_LIMIT_SECONDS
    # Four SQL predicates: eligible iff abs(...) <= N (NULL makes the predicate NULL → not eligible).
    for name, pattern in KERNEL_SQL_SITES.items():
        found = re.findall(pattern, (KERNEL / name).read_text(encoding="utf-8"))
        assert found, f"{name}: clock-skew SQL predicate not found; re-pin the alarm mirror"
        assert {Decimal(v) for v in found} == {CLOCK_SKEW_LIMIT_SECONDS}, (name, found)


def test_alarm_predicate_agrees_with_scheduler_eligibility():
    """Behavioural pin at the boundary: what the real scheduler rejects for clock
    reasons is exactly what the alarm calls 'outside'."""
    from inv.scheduler import Candidate, Request, place

    now = dt.datetime(2026, 9, 22, 12, 0, tzinfo=dt.timezone.utc)

    def kernel_rejects_for_clock(skew):
        cand = Candidate(
            node_id="nod_a", status="online", observed_at=now, cpu_millis=1000,
            memory_bytes=1 << 30, gpu_devices=(), local_bytes=0, bandwidth_bps=None,
            host_load=Decimal("0.1"), clock_skew_seconds=skew,
        )
        # A second, always-eligible node keeps place() from raising RES-0003
        # ("No eligible node") so the rejection map for nod_a can be read.
        control = Candidate(
            node_id="nod_b", status="online", observed_at=now, cpu_millis=1000,
            memory_bytes=1 << 30, gpu_devices=(), local_bytes=0, bandwidth_bps=None,
            host_load=Decimal("0.1"), clock_skew_seconds=Decimal("0"),
        )
        result = place(Request(cpu_millis=100, memory_bytes=1 << 20), [cand, control],
                       now=now, snapshot_id="snap", policy_version="v")
        assert "nod_b" not in result["rejected"]
        return "clock_unmeasured_or_skewed" in result["rejected"].get("nod_a", [])

    for skew in (Decimal("0"), Decimal("5"), Decimal("-5"), Decimal("5.0001"), Decimal("-5.5"), None, Decimal("NaN")):
        assert kernel_rejects_for_clock(skew) is skew_outside_limit(skew), skew
