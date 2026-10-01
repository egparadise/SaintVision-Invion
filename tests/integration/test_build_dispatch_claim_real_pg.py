"""Two real transactions can consume one build decision only once."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from inv.build_adapter import _claim_build_dispatch
from inv.errors import DomainError

pytestmark = pytest.mark.postgres


def test_two_transactions_yield_one_dispatch_claim_and_one_idem_conflict(env):
    run = env.runs.create(env.tenant, env.project)
    request = {
        "tenantId": env.tenant,
        "projectId": env.project,
    }
    plan = {
        "lease": {
            "resourceId": env.resource,
            "leaseId": "lse_" + "0" * 26,
            "fencingToken": env.epoch + ":1",
        }
    }
    decision = {"decisionId": str(uuid4())}
    barrier = Barrier(2, timeout=10)

    def claim_once(_):
        try:
            with env.db.transaction(env.tenant) as conn:
                barrier.wait()
                _claim_build_dispatch(
                    conn,
                    request,
                    plan,
                    decision,
                    run["runId"],
                    "a" * 64,
                )
            return "claimed"
        except DomainError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(claim_once, range(2)))
    assert outcomes == ["IDEM-0001", "claimed"]

    with env.db.transaction(env.tenant) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM inv.idempotency WHERE operation='build.dispatch'"
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM inv.outbox WHERE event_type='inv.build.dispatch_claimed'"
            ).fetchone()["n"]
            == 1
        )
