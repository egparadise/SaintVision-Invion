"""Real-PostgreSQL counterexamples for the opt-in placement short commit."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import psycopg
import pytest

from inv.approvals import Principal
from inv.db import BoundDatabase, Database
from inv.errors import DomainError
from inv.leases import Allocation, lock_resources
from inv.placement import PlacementStore, _StalePlacement
from test_placement_benchmark import placement_benchmark_env, _start_observation_window
from test_postgres import planned

pytestmark = pytest.mark.postgres


def _candidate(a, *, metric_sink=None, limit_lock_timeout_ms=500):
    database = Database(
        a.e.runtime,
        recovery_epoch=a.e.epoch,
        placement_short_commit=True,
        placement_candidate_limit_lock_timeout_ms=limit_lock_timeout_ms,
        placement_metric_sink=metric_sink,
    )
    a.placement = PlacementStore(database)
    return a


def _reserve(a, run, *, key="candidate", request=None):
    return a.placement.reserve(
        a.principal,
        a.e.project,
        run["runId"],
        request or a.request,
        key=key,
        policy_version="roof:candidate:1",
        pool_version="project-nodes:candidate:1",
    )


def _assert_no_residue(a, key):
    with psycopg.connect(a.e.owner) as conn:
        assert not conn.execute(
            "SELECT 1 FROM inv.resource_leases WHERE tenant_id=%s",
            (a.e.tenant,),
        ).fetchall()
        assert not conn.execute(
            "SELECT 1 FROM inv.idempotency WHERE project_id=%s AND key=%s",
            (a.e.project, key),
        ).fetchall()


def test_flag_defaults_off_and_candidate_keeps_response_and_idempotency_contract(
    placement_benchmark_env,
):
    a = placement_benchmark_env
    assert a.placement.db.placement_short_commit is False
    metrics = []
    _candidate(a, metric_sink=metrics.append)
    _start_observation_window(a)
    run = planned(a.e)

    first = _reserve(a, run)
    assert first == _reserve(a, run)
    assert set(first) == {"runId", "placement", "leases"}
    assert first["runId"] == run["runId"]
    assert len(first["leases"]) == 2
    assert all(
        lease["fencingToken"].startswith(a.e.epoch + ":")
        for lease in first["leases"]
    )
    with pytest.raises(DomainError, match="IDEM-0001"):
        _reserve(a, run, request=replace(a.request, cpu_millis=a.request.cpu_millis + 1))
    waits = [item for item in metrics if item["mode"] == "placement-limit-row-wait"]
    holds = [item for item in metrics if item["mode"] == "placement-short-commit"]
    assert waits and any(item["outcome"] == "acquired" for item in waits)
    assert holds and any(item["outcome"] == "commit" for item in holds)
    assert all(
        set(item)
        <= {
            "mode",
            "attempt",
            "waitMs",
            "outcome",
            "sqlState",
            "lockTimeoutBudgetMs",
        }
        for item in waits
    )
    assert all(item["lockTimeoutBudgetMs"] == 500 for item in waits)


def test_candidate_does_not_wait_on_legacy_project_mutex(placement_benchmark_env):
    a = _candidate(placement_benchmark_env)
    _start_observation_window(a)
    run = planned(a.e)
    holder = psycopg.connect(a.e.owner)
    try:
        holder.execute(
            "SELECT project_id FROM inv.projects WHERE project_id=%s FOR NO KEY UPDATE",
            (a.e.project,),
        ).fetchone()
        with ThreadPoolExecutor(max_workers=1) as pool:
            sleeping = pool.submit(
                lambda: holder.execute("SELECT pg_sleep(1.2)").fetchone()
            )
            result = _reserve(a, run, key="project-mutex-bypass")
            sleeping.result(timeout=3)
    finally:
        holder.rollback()
        holder.close()
    assert result["runId"] == run["runId"]


def test_legacy_lock_wait_is_separate_from_post_acquisition_hold(
    placement_benchmark_env,
):
    """F-C1: the legacy hold clock starts only after both serial locks exist."""

    a = placement_benchmark_env
    metrics = []
    statements = []
    a.placement = PlacementStore(
        Database(
            a.e.runtime,
            recovery_epoch=a.e.epoch,
            statement_observer=statements.append,
            placement_metric_sink=metrics.append,
        )
    )
    _start_observation_window(a)
    run = planned(a.e)
    result = _reserve(a, run, key="legacy-symmetric-metric")

    waits = [item for item in metrics if item["mode"] == "placement-legacy-lock-wait"]
    holds = [item for item in metrics if item["mode"] == "placement-legacy-lock-scope"]
    project_lock = next(
        item
        for item in statements
        if item["statement"].startswith(
            "SELECT project_id FROM inv.projects WHERE project_id=%s FOR NO KEY UPDATE"
        )
    )
    limit_lock = next(
        item
        for item in statements
        if item["statement"].startswith(
            "SELECT * FROM inv.project_resource_limits WHERE project_id=%s FOR UPDATE"
        )
    )

    assert result["runId"] == run["runId"]
    assert len(waits) == 1 and waits[0]["outcome"] == "acquired"
    assert waits[0]["waitMs"] >= 0
    assert len(holds) == 1 and holds[0]["outcome"] == "commit"
    assert project_lock["phase"] == "placement-legacy-lock-wait"
    assert project_lock["elapsedMs"] >= 0
    assert limit_lock["phase"] == "placement-legacy-lock-wait"
    assert all(item["outcome"] == "success" for item in (project_lock, limit_lock))


def test_selected_guard_change_discards_winner_and_replans(placement_benchmark_env, monkeypatch):
    a = _candidate(placement_benchmark_env)
    _start_observation_window(a)
    run = planned(a.e)
    original = a.placement._speculate
    calls = 0

    def mutate_after_first(*args, **kwargs):
        nonlocal calls
        result = original(*args, **kwargs)
        calls += 1
        if calls == 1:
            with psycopg.connect(a.e.owner) as conn:
                conn.execute(
                    "UPDATE inv.resources SET offered=offered-1 WHERE tenant_id=%s AND kind='cpu'",
                    (a.e.tenant,),
                )
        return result

    monkeypatch.setattr(a.placement, "_speculate", mutate_after_first)
    result = _reserve(a, run, key="guard-replan")
    assert result["runId"] == run["runId"]
    assert calls >= 2


def test_active_total_change_recomputes_fit_without_discarding_valid_winner(
    placement_benchmark_env, monkeypatch
):
    a = _candidate(placement_benchmark_env)
    _start_observation_window(a)
    run = planned(a.e)
    competing = planned(a.e)
    original = a.placement._speculate
    calls = 0

    def reserve_small_competitor(*args, **kwargs):
        nonlocal calls
        result = original(*args, **kwargs)
        calls += 1
        if calls == 1:
            a.e.leases.reserve(
                a.e.tenant,
                a.e.project,
                competing["runId"],
                [Allocation(a.e.resource, 1)],
                key="active-total-competitor",
            )
        return result

    monkeypatch.setattr(a.placement, "_speculate", reserve_small_competitor)
    result = _reserve(a, run, key="active-total-recheck")
    assert result["runId"] == run["runId"]
    assert calls == 1


def test_locked_fit_rejects_tight_fit_after_competing_active_total(
    placement_benchmark_env,
):
    """F-R1: removing active_total from _locked_fit must make this test fail."""

    a = _candidate(placement_benchmark_env)
    competing = planned(a.e)
    with a.e.db.transaction(a.e.tenant) as conn:
        rows = conn.execute(
            "SELECT resource_id,kind,offered FROM inv.resources "
            "WHERE node_id=%s AND kind IN ('cpu','memory') ORDER BY resource_id",
            (a.e.node,),
        ).fetchall()
    by_kind = {row["kind"]: row for row in rows}
    a.e.leases.reserve(
        a.e.tenant,
        a.e.project,
        competing["runId"],
        [
            Allocation(
                by_kind["cpu"]["resource_id"],
                int(by_kind["cpu"]["offered"]) - a.request.cpu_millis + 1,
            ),
            Allocation(
                by_kind["memory"]["resource_id"],
                int(by_kind["memory"]["offered"]) - a.request.memory_bytes + 1,
            ),
        ],
        key="tight-fit-competitor",
    )

    with a.e.db.transaction(a.e.tenant) as conn:
        resources = lock_resources(
            conn,
            [by_kind["cpu"]["resource_id"], by_kind["memory"]["resource_id"]],
        )
        with pytest.raises(_StalePlacement):
            a.placement._locked_fit(conn, resources, a.e.node, a.request)


def test_bound_candidate_rolls_back_stale_attempt_to_savepoint(
    placement_benchmark_env, monkeypatch
):
    a = placement_benchmark_env
    _start_observation_window(a)
    run = planned(a.e)

    with a.e.db.transaction(a.e.tenant) as conn:
        bound = PlacementStore(BoundDatabase(a.e.db, a.e.tenant, conn))
        bound.db.placement_short_commit = True
        original = bound._speculate
        calls = 0

        def mutate_after_first(*args, **kwargs):
            nonlocal calls
            result = original(*args, **kwargs)
            calls += 1
            if calls == 1:
                with psycopg.connect(a.e.owner) as owner:
                    owner.execute(
                        "UPDATE inv.resources SET offered=offered-1 "
                        "WHERE tenant_id=%s AND kind='cpu'",
                        (a.e.tenant,),
                    )
            return result

        monkeypatch.setattr(bound, "_speculate", mutate_after_first)
        result = bound.reserve(
            a.principal,
            a.e.project,
            run["runId"],
            a.request,
            key="bound-guard-replan",
            policy_version="roof:candidate:1",
            pool_version="project-nodes:candidate:1",
        )

    assert result["runId"] == run["runId"]
    assert calls >= 2


def test_bound_candidate_savepoint_recovers_after_fail_fast_limit_row_timeout(
    placement_benchmark_env,
):
    """F-R2: a caller may retry in one outer transaction after a 55P03 savepoint."""

    a = placement_benchmark_env
    _start_observation_window(a)
    run = planned(a.e)
    holder = psycopg.connect(a.e.owner)
    database = Database(
        a.e.runtime,
        recovery_epoch=a.e.epoch,
        placement_short_commit=True,
        placement_candidate_limit_lock_timeout_ms=200,
    )
    try:
        holder.execute(
            "SELECT project_id FROM inv.project_resource_limits " "WHERE project_id=%s FOR UPDATE",
            (a.e.project,),
        ).fetchone()
        with database.transaction(a.e.tenant) as conn:
            conn.execute("SELECT set_config('lock_timeout', '700ms', true)")
            bound = PlacementStore(BoundDatabase(database, a.e.tenant, conn))
            with pytest.raises(psycopg.errors.LockNotAvailable) as caught:
                bound.reserve(
                    a.principal,
                    a.e.project,
                    run["runId"],
                    a.request,
                    key="bound-limit-fail-fast",
                    policy_version="roof:candidate:1",
                    pool_version="project-nodes:candidate:1",
                )
            assert caught.value.sqlstate == "55P03"
            assert (
                conn.execute("SELECT current_setting('lock_timeout') AS value").fetchone()["value"]
                == "700ms"
            )
            holder.rollback()
            result = bound.reserve(
                a.principal,
                a.e.project,
                run["runId"],
                a.request,
                key="bound-limit-fail-fast",
                policy_version="roof:candidate:1",
                pool_version="project-nodes:candidate:1",
            )
            assert (
                conn.execute("SELECT current_setting('lock_timeout') AS value").fetchone()["value"]
                == "700ms"
            )
    finally:
        holder.rollback()
        holder.close()

    assert result["runId"] == run["runId"]


def test_candidate_budget_applies_only_to_limits_statement_and_restores_caller_value(
    placement_benchmark_env, monkeypatch
):
    import inv.placement as module

    a = placement_benchmark_env
    metrics = []
    database = Database(
        a.e.runtime,
        recovery_epoch=a.e.epoch,
        placement_short_commit=True,
        placement_candidate_limit_lock_timeout_ms=1500,
        placement_metric_sink=metrics.append,
    )
    _start_observation_window(a)
    run = planned(a.e)
    observed_after_limit = []
    original = module.lock_resources

    def observe_restored_value(conn, resource_ids):
        observed_after_limit.append(
            conn.execute("SELECT current_setting('lock_timeout') AS value").fetchone()["value"]
        )
        return original(conn, resource_ids)

    monkeypatch.setattr(module, "lock_resources", observe_restored_value)
    with database.transaction(a.e.tenant) as conn:
        conn.execute("SELECT set_config('lock_timeout', '700ms', true)")
        bound = PlacementStore(BoundDatabase(database, a.e.tenant, conn))
        result = bound.reserve(
            a.principal,
            a.e.project,
            run["runId"],
            a.request,
            key="candidate-budget-restore",
            policy_version="roof:candidate:1",
            pool_version="project-nodes:candidate:1",
        )
        assert (
            conn.execute("SELECT current_setting('lock_timeout') AS value").fetchone()["value"]
            == "700ms"
        )

    assert result["runId"] == run["runId"]
    assert observed_after_limit == ["700ms"]
    waits = [item for item in metrics if item["mode"] == "placement-limit-row-wait"]
    assert len(waits) == 1
    assert waits[0]["lockTimeoutBudgetMs"] == 1500


def test_candidate_budget_exhaustion_keeps_res_0007_contract(
    placement_benchmark_env,
):
    a = placement_benchmark_env
    metrics = []
    _candidate(a, metric_sink=metrics.append, limit_lock_timeout_ms=1500)
    _start_observation_window(a)
    run = planned(a.e)
    holder = psycopg.connect(a.e.owner)
    try:
        holder.execute(
            "SELECT project_id FROM inv.project_resource_limits " "WHERE project_id=%s FOR UPDATE",
            (a.e.project,),
        ).fetchone()
        with pytest.raises(DomainError) as caught:
            _reserve(a, run, key="candidate-budget-exhaustion")
    finally:
        holder.rollback()
        holder.close()

    error = caught.value
    assert (error.code, error.status, error.retryable) == ("RES-0007", 503, True)
    assert isinstance(error.__cause__, psycopg.errors.LockNotAvailable)
    assert error.__cause__.sqlstate == "55P03"
    waits = [item for item in metrics if item["mode"] == "placement-limit-row-wait"]
    assert len(waits) == 1
    assert waits[0]["lockTimeoutBudgetMs"] == 1500
    assert waits[0]["outcome"] == "timeout"
    _assert_no_residue(a, "candidate-budget-exhaustion")


def test_candidate_budget_can_wait_beyond_default_without_changing_contract(
    placement_benchmark_env,
):
    a = placement_benchmark_env
    metrics = []
    _candidate(a, metric_sink=metrics.append, limit_lock_timeout_ms=1500)
    _start_observation_window(a)
    run = planned(a.e)
    holder = psycopg.connect(a.e.owner)
    try:
        holder.execute(
            "SELECT project_id FROM inv.project_resource_limits " "WHERE project_id=%s FOR UPDATE",
            (a.e.project,),
        ).fetchone()

        def release_after_default_budget():
            holder.execute("SELECT pg_sleep(0.8)").fetchone()
            holder.rollback()

        with ThreadPoolExecutor(max_workers=1) as pool:
            release = pool.submit(release_after_default_budget)
            result = _reserve(a, run, key="candidate-budget-success")
            release.result(timeout=3)
    finally:
        holder.rollback()
        holder.close()

    assert result["runId"] == run["runId"]
    assert set(result) == {"runId", "placement", "leases"}
    waits = [item for item in metrics if item["mode"] == "placement-limit-row-wait"]
    assert len(waits) == 1
    assert waits[0]["outcome"] == "acquired"
    assert waits[0]["lockTimeoutBudgetMs"] == 1500
    assert waits[0]["waitMs"] > 500


def test_limit_row_contention_fails_fast_with_existing_public_contract(
    placement_benchmark_env,
):
    a = placement_benchmark_env
    metrics = []
    _candidate(a, metric_sink=metrics.append)
    _start_observation_window(a)
    run = planned(a.e)
    holder = psycopg.connect(a.e.owner)
    try:
        holder.execute(
            "SELECT project_id FROM inv.project_resource_limits " "WHERE project_id=%s FOR UPDATE",
            (a.e.project,),
        ).fetchone()
        with pytest.raises(DomainError) as caught:
            _reserve(a, run, key="limit-row-fail-fast")
    finally:
        holder.rollback()
        holder.close()

    error = caught.value
    assert (error.code, error.status, error.retryable) == ("RES-0007", 503, True)
    assert isinstance(error.__cause__, psycopg.errors.LockNotAvailable)
    assert error.__cause__.sqlstate == "55P03"
    waits = [item for item in metrics if item["mode"] == "placement-limit-row-wait"]
    assert len(waits) == 1
    assert waits[0]["attempt"] == 1
    assert waits[0]["outcome"] == "timeout"
    assert waits[0]["sqlState"] == "55P03"
    assert waits[0]["lockTimeoutBudgetMs"] == 500
    _assert_no_residue(a, "limit-row-fail-fast")


def test_grant_revocation_between_speculation_and_commit_fails_closed(
    placement_benchmark_env, monkeypatch
):
    a = _candidate(placement_benchmark_env)
    _start_observation_window(a)
    run = planned(a.e)
    original = a.placement._speculate

    def revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        with psycopg.connect(a.e.owner) as conn:
            conn.execute(
                "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s AND project_id=%s",
                (a.e.tenant, a.e.project),
            )
        return result

    monkeypatch.setattr(a.placement, "_speculate", revoke)
    with pytest.raises(DomainError, match="AUTH-0030"):
        _reserve(a, run, key="revoked-grant")
    _assert_no_residue(a, "revoked-grant")


def test_epoch_flip_between_speculation_and_commit_fails_closed(
    placement_benchmark_env, monkeypatch
):
    a = _candidate(placement_benchmark_env)
    _start_observation_window(a)
    run = planned(a.e)
    original = a.placement._speculate

    def flip(*args, **kwargs):
        result = original(*args, **kwargs)
        with psycopg.connect(a.e.owner) as conn:
            conn.execute(
                "UPDATE inv.control_epoch SET epoch=%s WHERE singleton",
                (str(uuid4()),),
            )
        return result

    monkeypatch.setattr(a.placement, "_speculate", flip)
    with pytest.raises(DomainError, match="LEASE-0004"):
        _reserve(a, run, key="epoch-flip")
    _assert_no_residue(a, "epoch-flip")


def test_event_failure_rolls_back_candidate_leases_and_ledger(
    placement_benchmark_env, monkeypatch
):
    import inv.placement as module

    a = _candidate(placement_benchmark_env)
    _start_observation_window(a)
    run = planned(a.e)
    monkeypatch.setattr(
        module,
        "event",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("event failed")),
    )
    with pytest.raises(RuntimeError, match="event failed"):
        _reserve(a, run, key="event-rollback")
    _assert_no_residue(a, "event-rollback")


def test_candidate_and_direct_lease_share_project_ceiling(placement_benchmark_env):
    a = _candidate(placement_benchmark_env)
    _start_observation_window(a)
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.project_resource_limits SET cpu_millis=%s,version=version+1 WHERE tenant_id=%s",
            (a.request.cpu_millis, a.e.tenant),
        )
    placement_run, direct_run = planned(a.e), planned(a.e)

    def place_one():
        return _reserve(a, placement_run, key="mixed-placement")

    def lease_one():
        return a.e.leases.reserve(
            a.e.tenant,
            a.e.project,
            direct_run["runId"],
            [Allocation(a.e.resource, a.request.cpu_millis)],
            key="mixed-direct",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(place_one), pool.submit(lease_one)]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(("success", future.result()))
            except DomainError as error:
                outcomes.append((error.code, None))

    assert sum(status == "success" for status, _result in outcomes) == 1
    assert any(status in {"RES-0001", "RES-0007"} for status, _result in outcomes)
    with a.e.db.transaction(a.e.tenant) as conn:
        used = conn.execute(
            "SELECT coalesce(sum(amount),0) AS used FROM inv.resource_leases "
            "WHERE project_id=%s AND resource_id=%s AND released_at IS NULL",
            (a.e.project, a.e.resource),
        ).fetchone()["used"]
    assert used == a.request.cpu_millis


def test_candidate_rls_boundary_rejects_other_tenant(placement_benchmark_env):
    a = _candidate(placement_benchmark_env)
    _start_observation_window(a)
    run = planned(a.e)
    outsider = Principal(a.e.other, "benchmark")
    with pytest.raises(DomainError, match="AUTH-0030"):
        a.placement.reserve(
            outsider,
            a.e.project,
            run["runId"],
            a.request,
            key="other-tenant",
            policy_version="roof:candidate:1",
        )
    _assert_no_residue(a, "other-tenant")
