"""Card 266: the three-phase collect surface, against a real PostgreSQL.

Everything here is about the two things the design had to get right and my first
drafts got wrong: the ledger response must commit **with** the observation's
writes, and a stored response must not come back to a subject who has since lost
the authority to see it.

The signed envelope is real -- ``ConfiguredSampler`` signs with the channel's own
key -- so the only stand-in is the transport, which lets a test hand back two
different envelopes for one key and inject a crash between the writes and the
commit. Those are the two schedules a mock cannot fake its way around.
"""

from __future__ import annotations

import threading
import uuid

import pytest

from inv.errors import DomainError
from inv.storage_check_collect import (
    OPERATION,
    REQUEST_NAMESPACE,
    SEPARATOR,
    StorageCheckCollector,
    derive_request_id,
)
from test_storage_commit import sample, storage_subject  # noqa: F401  (fixtures)


class Transport:
    """The node call, stood in for. Counts its calls, because "did not touch the
    node" is half of what the authority tests assert."""

    def __init__(self, sampler, certificate_der):
        self.sampler = sampler
        self.certificate_der = certificate_der
        self.calls = 0
        self.before_call = None

    def storage_sample(self, channel, challenge):
        self.calls += 1
        if self.before_call is not None:
            self.before_call()
        return self.sampler.collect(challenge), self.certificate_der


@pytest.fixture
def collector(sample):  # noqa: F811
    transport = Transport(sample.sampler, sample.certificate.der)
    return StorageCheckCollector(sample.e.db, transport), transport


def _counts(sample):  # noqa: F811
    with sample.e.db.transaction(sample.e.tenant) as c:
        checks = c.execute("SELECT count(*) AS n FROM public.storage_checks").fetchone()["n"]
        consumptions = c.execute(
            "SELECT count(*) AS n FROM inv.storage_sample_consumptions"
        ).fetchone()["n"]
        events = c.execute(
            "SELECT count(*) AS n FROM inv.outbox "
            "WHERE event_type='inv.storage.sample_recorded'"
        ).fetchone()["n"]
        ledger = c.execute(
            "SELECT response FROM inv.idempotency WHERE operation=%s", (OPERATION,)
        ).fetchall()
    return checks, consumptions, events, [row["response"] for row in ledger]


OMITTED = object()


def _collect(collector_pair, sample, *, key, contribution=None, sample_limit=OMITTED):  # noqa: F811
    collector, _ = collector_pair
    kwargs = {} if sample_limit is OMITTED else {"sample": sample_limit}
    return collector.collect(
        sample.principal,
        sample.e.project,
        sample.run,
        contribution=contribution or sample.contribution,
        key=key,
        **kwargs,
    )


# =========================================================== the derived request id
def test_the_request_id_is_derived_and_every_scope_element_changes_it():
    base = {
        "tenant_id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
        "project_id": "prj_1",
        "run_id": "run_1",
        "key": "k1",
    }
    first = derive_request_id(**base)
    # Deterministic: the same scope and key recompute the same id, which is the
    # whole reason it is derived rather than minted and stored.
    assert first == derive_request_id(**base)
    assert uuid.UUID(first).version == 5
    for field, other in (
        ("tenant_id", uuid.UUID("22222222-2222-2222-2222-222222222222")),
        ("project_id", "prj_2"),
        ("run_id", "run_2"),
        ("key", "k2"),
    ):
        assert derive_request_id(**{**base, field: other}) != first, field


def test_the_separator_keeps_adjacent_fields_from_blurring():
    """Bare concatenation would make these two scopes the same input."""
    left = derive_request_id(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        project_id="prj_ab", run_id="c", key="k",
    )
    right = derive_request_id(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        project_id="prj_a", run_id="bc", key="k",
    )
    assert left != right
    assert SEPARATOR not in "prj_ab"


def test_a_missing_key_is_refused_before_anything_is_derived():
    for key in (None, "", "k" * 201, 7):
        with pytest.raises(DomainError) as raised:
            derive_request_id(
                tenant_id=uuid.uuid4(), project_id="prj_1", run_id="run_1", key=key
            )
        assert raised.value.code == "VAL-0003"


def test_the_namespace_is_a_literal_constant():
    """If it were computed from anything that drifts, every retry in flight would
    get a different id -- the one thing the derivation exists to prevent."""
    assert isinstance(REQUEST_NAMESPACE, uuid.UUID)
    assert str(REQUEST_NAMESPACE) == "6f0b6a1e-5a3f-5d4b-9c21-7f1d2e4a8b03"


# ====================================================================== the happy path
def test_one_collect_records_one_check_and_stores_the_ledger_response(collector, sample):  # noqa: F811
    response, replayed = _collect(collector, sample, key="c266-a")
    assert replayed is False
    assert set(response) == {"checkId", "evidenceId", "requestId", "contributionId"}
    assert response["contributionId"] == sample.contribution
    assert response["requestId"] == derive_request_id(
        tenant_id=sample.e.tenant, project_id=sample.e.project, run_id=sample.run, key="c266-a"
    )
    checks, consumptions, events, ledger = _counts(sample)
    assert (checks, consumptions, events) == (1, 1, 1)
    # The response is in the ledger, in the same transaction as those rows.
    assert ledger == [response]
    _, transport = collector
    assert transport.calls == 1


def test_the_same_key_and_body_replays_without_touching_the_node(collector, sample):  # noqa: F811
    first, _ = _collect(collector, sample, key="c266-b")
    before = _counts(sample)
    second, replayed = _collect(collector, sample, key="c266-b")
    assert replayed is True
    assert second == first
    assert _counts(sample) == before
    _, transport = collector
    # Phase one replayed: the node was called once, for the first request only.
    assert transport.calls == 1


def test_the_same_key_with_a_different_body_is_an_idempotency_conflict(collector, sample):  # noqa: F811
    _collect(collector, sample, key="c266-c")
    with pytest.raises(DomainError) as raised:
        _collect(collector, sample, key="c266-c", sample_limit=2)
    assert raised.value.code == "IDEM-0001"


def test_an_omitted_sample_limit_and_the_explicit_default_are_the_same_request(
    collector, sample  # noqa: F811
):
    """The case that would bite first: a retry that spells out the default must
    replay, not be refused for a different body."""
    first, _ = _collect(collector, sample, key="c266-d")
    collector_obj, _ = collector
    second, replayed = _collect(
        collector, sample, key="c266-d", sample_limit=collector_obj.MAX_SAMPLE
    )
    assert replayed is True
    assert second == first


def test_a_sample_limit_outside_the_protocol_ceiling_is_refused(collector, sample):  # noqa: F811
    for limit in (0, 33, "32", None):
        with pytest.raises(DomainError) as raised:
            _collect(collector, sample, key=f"c266-e-{limit}", sample_limit=limit)
        assert raised.value.code == "VAL-0003"
    assert _counts(sample)[0] == 0


# ============================================= authority is checked before any replay
def _as_owner(sample, statement, parameters):  # noqa: F811
    """Change authority from outside the request, as the owner role.

    The kernel role deliberately cannot write grants, folders or projects, which
    is why a revocation in these tests has to come from here -- the same place an
    operator's change would come from.
    """
    import psycopg

    with psycopg.connect(sample.e.owner) as connection:
        connection.execute(statement, parameters)
        connection.commit()


def _revoke_grant(sample):  # noqa: F811
    _as_owner(
        sample,
        "UPDATE inv.project_grants SET can_request=false WHERE project_id=%s",
        (sample.e.project,),
    )


def test_a_revoked_grant_refuses_the_replay_of_a_stored_success(collector, sample):  # noqa: F811
    """The hole this card's design had until r7: the stored response was returned
    before authority was re-read, so a revoked subject kept receiving it."""
    _collect(collector, sample, key="c266-f")
    before = _counts(sample)
    _, transport = collector
    calls = transport.calls
    _revoke_grant(sample)
    with pytest.raises(DomainError) as raised:
        _collect(collector, sample, key="c266-f")
    assert raised.value.code == "AUTH-0030"
    assert raised.value.status == 403
    # No node call and no new rows: the refusal happened before either.
    assert transport.calls == calls
    assert _counts(sample) == before


def test_a_deactivated_contribution_is_the_same_answer_as_absence(collector, sample):  # noqa: F811
    _collect(collector, sample, key="c266-g")
    _as_owner(
        sample,
        # The table pairs the status with its timestamp, so a revocation sets both.
        "UPDATE public.storage_contributions SET status='revoked', revoked_at=now() "
        "WHERE contribution_id=%s",
        (sample.contribution,),
    )
    with pytest.raises(DomainError) as raised:
        _collect(collector, sample, key="c266-g")
    assert raised.value.code == "RES-0004"
    assert raised.value.status == 404


def test_an_unknown_contribution_gives_the_same_refusal_as_a_deactivated_one(
    collector, sample  # noqa: F811
):
    """Absent and not-yours must be one answer, or a contribution id becomes an
    existence oracle."""
    with pytest.raises(DomainError) as absent:
        _collect(collector, sample, key="c266-h", contribution="stc_" + "0" * 26)
    assert (absent.value.code, absent.value.status) == ("RES-0004", 404)
    _as_owner(
        sample,
        # The table pairs the status with its timestamp, so a revocation sets both.
        "UPDATE public.storage_contributions SET status='revoked', revoked_at=now() "
        "WHERE contribution_id=%s",
        (sample.contribution,),
    )
    with pytest.raises(DomainError) as revoked:
        _collect(collector, sample, key="c266-i")
    assert (revoked.value.code, revoked.value.detail) == (absent.value.code, absent.value.detail)


def test_an_archived_project_refuses_with_the_project_code(collector, sample):  # noqa: F811
    _collect(collector, sample, key="c266-j")
    _as_owner(
        sample,
        "UPDATE public.projects SET status='archived' WHERE project_id=%s",
        (sample.e.project,),
    )
    with pytest.raises(DomainError) as raised:
        _collect(collector, sample, key="c266-j")
    assert raised.value.code == "AUTH-0030"
    assert raised.value.status == 403


# ================================================================= the two schedules
def test_two_concurrent_requests_on_one_key_converge_on_one_answer(collector, sample):  # noqa: F811
    """Each request gets its **own** signed envelope -- different ``observedAt``,
    different signature -- which is exactly why the ledger response has to be in
    the same transaction as the writes. The loser must replay, not be refused.
    """
    collector_obj, transport = collector
    released = threading.Event()
    first_in_flight = threading.Event()

    def pause_once():
        if transport.calls == 1:
            first_in_flight.set()
            released.wait(timeout=30)

    transport.before_call = pause_once
    results: dict[str, object] = {}

    def run(label):
        try:
            results[label] = _collect(collector, sample, key="c266-race")
        except Exception as error:  # recorded, then asserted on below
            results[label] = error

    first = threading.Thread(target=run, args=("first",))
    first.start()
    assert first_in_flight.wait(timeout=30), "the first request never reached the node call"
    second = threading.Thread(target=run, args=("second",))
    second.start()
    # The second request is now either waiting on the ledger row or doing its own
    # node call; releasing the first lets both finish.
    released.set()
    first.join(timeout=60)
    second.join(timeout=60)

    for label in ("first", "second"):
        assert not isinstance(results[label], Exception), (label, results[label])
    (left, left_replayed), (right, right_replayed) = results["first"], results["second"]
    # One answer, whichever of them produced it.
    assert left == right
    assert sorted([left_replayed, right_replayed]) == [False, True]
    checks, consumptions, events, ledger = _counts(sample)
    assert (checks, consumptions, events) == (1, 1, 1)
    assert ledger == [left]


def test_a_crash_after_the_writes_and_before_the_commit_leaves_nothing(collector, sample):  # noqa: F811
    """The row the design's crash table was missing until r6: the five writes and
    the ledger response are one transaction, so a failure between them is nothing.
    """
    collector_obj, transport = collector
    real_apply = collector_obj.samples.apply_sample

    def apply_then_fail(conn, principal, run_id, context):
        real_apply(conn, principal, run_id, context)
        raise RuntimeError("injected after the writes, before the commit")

    collector_obj.samples.apply_sample = apply_then_fail
    try:
        with pytest.raises(RuntimeError, match="injected"):
            _collect(collector, sample, key="c266-crash")
    finally:
        collector_obj.samples.apply_sample = real_apply

    checks, consumptions, events, ledger = _counts(sample)
    assert (checks, consumptions, events) == (0, 0, 0)
    # The pre-I/O phase committed its own ledger row, with no response in it.
    assert ledger == [None]

    # And the retry converges: same key, same body, and now it succeeds.
    response, replayed = _collect(collector, sample, key="c266-crash")
    assert replayed is False
    assert _counts(sample)[:3] == (1, 1, 1)
    assert _counts(sample)[3] == [response]
