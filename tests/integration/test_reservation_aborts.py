from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from inv.errors import DomainError
from inv.control import Control
from test_approvals import approval, count
from test_tool_admission import gateway, claim
from test_dispatch_queue import cancel

pytestmark = pytest.mark.postgres


def active(a):
    with a.e.db.transaction(a.e.tenant) as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM inv.resource_leases WHERE released_at IS NULL"
        ).fetchone()["n"]


def test_cancel_before_claim_returns_reservations_without_fabricated_node_receipt(gateway):
    a = gateway
    version = a.e.runs.get(a.e.tenant, a.run["runId"])["version"]
    result = cancel(a)
    assert result["state"] == "cancelled" and not result["resourceReleasePending"]
    assert (
        active(a) == 0
        and count(a, "reservation_aborts") == 1
        and count(a, "node_stop_receipts") == 0
    )
    assert (
        Control(a.e.db).cancel(
            a.people["requester"], a.e.project, a.run["runId"], version, "cancel-queued"
        )
        == result
    )
    with pytest.raises(DomainError):
        claim(a)


def test_cancel_racing_admission_never_releases_a_possible_execution(gateway):
    a = gateway
    barrier = Barrier(2)

    def admission():
        barrier.wait(timeout=5)
        try:
            return claim(a).may_start
        except DomainError:
            return False

    def cancellation():
        barrier.wait(timeout=5)
        return cancel(a)

    with ThreadPoolExecutor(max_workers=2) as pool:
        execute = pool.submit(admission)
        cancelled = pool.submit(cancellation)
        started = execute.result(timeout=10)
        result = cancelled.result(timeout=10)
    assert result["state"] == "cancelled"
    assert count(a, "node_stop_receipts") == 0
    assert (active(a), count(a, "reservation_aborts"), count(a, "tool_claims")) == (
        (2, 0, 1) if started else (0, 1, 0)
    )


def test_issued_claim_still_requires_authenticated_node_proof(gateway):
    a = gateway
    assert claim(a).may_start
    assert cancel(a)["resourceReleasePending"]
    assert active(a) == 2 and count(a, "reservation_aborts") == 0
