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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from alarm_check import (  # noqa: E402
    GOVERNANCE_GATED,
    NOT_EVALUABLE,
    count_alarm,
    coverage_summary,
    partition_alarm,
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


def test_clock_skew_is_governance_gated_not_silently_dropped():
    # Runtime eligibility filtering is active, but the routed alarm is gated
    # until the threshold and response path are accepted.
    gated = {row[0]: row[2] for row in GOVERNANCE_GATED}
    assert "Node 시각 스큐 한도 초과" in gated
    assert "Runtime eligibility already excludes" in gated["Node 시각 스큐 한도 초과"]
    assert "channel/responders are decided" in gated["Node 시각 스큐 한도 초과"]


def test_coverage_does_not_claim_a_spec_row_denominator_for_collapsed_families():
    summary = coverage_summary(4, len(NOT_EVALUABLE), len(GOVERNANCE_GATED))
    assert summary == "4 evaluated data families; 11 conditions not evaluated here; 1 governance-gated conditions"
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
