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
def catalogue_engine(sample):  # noqa: F811
    """A SQLAlchemy engine on a login role granted ``inv_app``.

    Not the owner and not the kernel role: the boundary read is only meaningful if
    it runs with the grants production gives it. Measured at head --
    ``has_column_privilege('inv_kernel', 'public.data_locations', 'project_id',
    'SELECT')`` is **False** and ``inv_app``'s is **True** -- which is the whole
    reason that one question is asked on this connection.
    """
    import secrets

    import psycopg
    from psycopg import sql
    from sqlalchemy import create_engine

    role = "c266_app_" + secrets.token_hex(8)
    password = secrets.token_urlsafe(24)
    with psycopg.connect(sample.e.owner) as connection:
        connection.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
        connection.execute(sql.SQL("GRANT inv_app TO {}").format(sql.Identifier(role)))
        connection.commit()
    dsn = psycopg.conninfo.make_conninfo(sample.e.owner, user=role, password=password)
    engine = create_engine("postgresql+psycopg://", connect_args=psycopg.conninfo.conninfo_to_dict(dsn))
    try:
        yield engine
    finally:
        engine.dispose()
        with psycopg.connect(sample.e.owner) as connection:
            connection.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
            connection.commit()


def _bind_locations(sample, project_id):  # noqa: F811
    """Put the folder's catalogue in a project, as the owner would.

    The shared fixture predates ``0062`` in spirit -- its locations have no project
    -- and the boundary now refuses exactly that, so each test says which project
    the folder's contents belong to.
    """
    import psycopg

    with psycopg.connect(sample.e.owner) as connection:
        connection.execute(
            "UPDATE public.data_locations SET project_id=%s WHERE contribution_id=%s",
            (project_id, sample.contribution),
        )
        connection.commit()


@pytest.fixture
def collector(sample, catalogue_engine):  # noqa: F811
    from inv.storage_check_collect import CatalogueProjectReader

    _bind_locations(sample, sample.e.project)
    transport = Transport(sample.sampler, sample.certificate.der)
    built = StorageCheckCollector(
        sample.e.db, transport, CatalogueProjectReader(catalogue_engine)
    )
    return built, transport


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


def _another_user(sample):  # noqa: F811
    """A second real user to hand the folder to. Created here rather than assumed,
    because the fixture only needs one owner for everything else it does."""
    import psycopg

    from inv.ids import new_id

    user = new_id("usr")
    with psycopg.connect(sample.e.owner) as connection:
        connection.execute(
            "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) "
            "VALUES(%s,%s,%s,'other')",
            (sample.e.tenant, user, "oidc:c266-other-" + user),
        )
        connection.commit()
    return user


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


def test_a_contribution_that_changed_hands_is_the_same_answer_as_absence(collector, sample):  # noqa: F811
    """Ownership is read **now**, not taken from the ledger row's memory. A folder
    that was handed to someone else since the first success is the same answer as
    one that is not there."""
    first, _ = _collect(collector, sample, key="c266-k")
    before = _counts(sample)
    _, transport = collector
    calls = transport.calls
    _as_owner(
        sample,
        "UPDATE public.storage_contributions SET registered_by_user_id=%s "
        "WHERE contribution_id=%s",
        (_another_user(sample), sample.contribution),
    )
    with pytest.raises(DomainError) as raised:
        _collect(collector, sample, key="c266-k")
    assert (raised.value.code, raised.value.status) == ("RES-0004", 404)
    # Not 2xx, no node call, nothing written -- and the stored response stayed put.
    assert transport.calls == calls
    assert _counts(sample) == before


def test_a_grant_revoked_during_the_node_call_refuses_the_late_replay(collector, sample):  # noqa: F811
    """The schedule the phase-three authority check exists for.

    One request is held inside its node call. A second completes and stores the
    response. The grant is then revoked, and only now is the first released: its
    final transaction finds a response **and** finds the authority gone, so it must
    refuse rather than hand that response back.
    """
    collector_obj, transport = collector
    released = threading.Event()
    in_flight = threading.Event()

    def pause_first():
        if transport.calls == 1:
            in_flight.set()
            released.wait(timeout=30)

    transport.before_call = pause_first
    outcome: dict[str, object] = {}

    def run_first():
        try:
            outcome["result"] = _collect(collector, sample, key="c266-late")
        except Exception as error:
            outcome["result"] = error

    first = threading.Thread(target=run_first)
    first.start()
    assert in_flight.wait(timeout=30), "the first request never reached the node call"

    # A second request on the same key finishes and stores the response.
    transport.before_call = None
    second, replayed = _collect(collector, sample, key="c266-late")
    assert replayed is False
    stored = _counts(sample)
    assert stored[:3] == (1, 1, 1)

    # Now the authority disappears, and only then is the first request released.
    _revoke_grant(sample)
    released.set()
    first.join(timeout=60)

    assert isinstance(outcome["result"], DomainError), outcome["result"]
    assert outcome["result"].code == "AUTH-0030"
    assert outcome["result"].status == 403
    # The stored answer did not go back to a subject who had lost the right to it,
    # and the late request wrote nothing of its own.
    assert _counts(sample) == stored


# ===========================================================================
# Card 266 r2: the project boundary (Codex r1 F2).
#
# storage_contributions has no project column, so the boundary comes from what
# the folder holds. Ownership and tenancy alone let a same-tenant owner collect
# a folder catalogued in another project, or in none.
# ===========================================================================


def _project(sample, suffix):  # noqa: F811
    """A second project of this tenant, created as the owner."""
    import psycopg

    from inv.ids import new_id

    project = new_id("prj")
    with psycopg.connect(sample.e.owner) as connection:
        connection.execute(
            "INSERT INTO public.projects(tenant_id,project_id,code,display_name) "
            "VALUES(%s,%s,%s,%s)",
            (sample.e.tenant, project, suffix, suffix),
        )
        connection.commit()
    return project


def test_a_folder_catalogued_in_another_project_is_the_same_answer_as_absence(
    collector, sample  # noqa: F811
):
    _bind_locations(sample, _project(sample, "c266-other"))
    with pytest.raises(DomainError) as raised:
        _collect(collector, sample, key="c266-other-project")
    assert (raised.value.code, raised.value.status) == ("RES-0004", 404)
    assert _counts(sample)[:3] == (0, 0, 0)


def test_a_legacy_null_project_folder_is_refused(collector, sample):  # noqa: F811
    """``0062`` made the column nullable, so a folder catalogued before it has NULL.
    NULL is not "every project": it is none, and sampling it for a project would
    record a check that project cannot claim."""
    _bind_locations(sample, None)
    with pytest.raises(DomainError) as raised:
        _collect(collector, sample, key="c266-null-legacy")
    assert (raised.value.code, raised.value.status) == ("RES-0004", 404)
    assert _counts(sample)[:3] == (0, 0, 0)


def test_a_folder_straddling_two_projects_is_refused_rather_than_half_sampled(
    collector, sample  # noqa: F811
):
    """All-or-nothing: a mixed catalogue is somebody else's migration to finish."""
    import hashlib

    import psycopg

    from inv.ids import new_id

    other = _project(sample, "c266-mixed")
    with psycopg.connect(sample.e.owner) as connection:
        connection.execute(
            "INSERT INTO public.data_locations(location_id,tenant_id,project_id,"
            "contribution_id,uri,kind,relative_path,byte_size,checksum_sha256) "
            "VALUES(%s,%s,%s,%s,'file:other.bin','dataset','other.bin',12,%s)",
            (
                new_id("dtl"), sample.e.tenant, other, sample.contribution,
                hashlib.sha256(b"other bytes").hexdigest(),
            ),
        )
        connection.commit()
    with pytest.raises(DomainError) as raised:
        _collect(collector, sample, key="c266-mixed")
    assert (raised.value.code, raised.value.status) == ("RES-0004", 404)
    assert _counts(sample)[:3] == (0, 0, 0)


def test_the_boundary_read_runs_with_the_app_roles_grants(catalogue_engine):
    """The measurement this placement rests on, asserted rather than remembered:
    the kernel role cannot read that column and the app role can."""
    from sqlalchemy import text as sql_text

    with catalogue_engine.connect() as connection:
        kernel, app = connection.execute(
            sql_text(
                "SELECT has_column_privilege('inv_kernel','public.data_locations',"
                "'project_id','SELECT'), "
                "has_column_privilege('inv_app','public.data_locations',"
                "'project_id','SELECT')"
            )
        ).one()
    assert kernel is False
    assert app is True


# ===========================================================================
# Card 266 r2: the remaining counter-examples (Codex r1 F5).
# ===========================================================================


def test_two_samples_of_one_folder_differ_once_the_observed_second_moves(
    collector, sample  # noqa: F811
):
    """The premise of the race test, corrected by measuring it.

    I had assumed two samples of one folder **always** differ. They do not: the
    signed payload carries ``observedAt`` as whole seconds and the signature is
    deterministic, so two calls inside one second produce **byte-identical**
    envelopes -- measured here, not reasoned about. The hazard the three phases
    exist for is therefore not "always different" but "different as soon as the
    second moves", which this asserts both ways.
    """
    import time

    collector_obj, transport = collector
    challenge = collector_obj.samples.issue(
        sample.principal, sample.e.project, sample.run, sample.contribution,
        request_id=str(uuid.uuid4()),
    )
    first, certificate = transport.storage_sample(challenge.channel, challenge)
    immediately, _ = transport.storage_sample(challenge.channel, challenge)
    _, first_hash = collector_obj.samples.bound_envelope(first, certificate)
    _, immediate_hash = collector_obj.samples.bound_envelope(immediately, certificate)
    # Same second, deterministic signature: identical. This is why a response-hash
    # comparison alone can look fine in a fast test and fail in production.
    assert first_hash == immediate_hash

    time.sleep(1.05)
    later, _ = transport.storage_sample(challenge.channel, challenge)
    _, later_hash = collector_obj.samples.bound_envelope(later, certificate)
    assert later_hash != first_hash


def test_the_same_key_with_another_contribution_is_a_conflict(collector, sample):  # noqa: F811
    _collect(collector, sample, key="c266-other-contribution")
    with pytest.raises(DomainError) as raised:
        _collect(
            collector, sample, key="c266-other-contribution",
            contribution="stc_" + "1" * 26,
        )
    assert raised.value.code == "IDEM-0001"


def test_the_same_key_on_another_path_run_is_a_different_request(collector, sample):  # noqa: F811
    """The key is scoped by the path, so the same text on another Run is not a
    replay of this one: it derives a different request id and is judged on that
    Run's own authority instead of being answered from this Run's ledger."""
    first, _ = _collect(collector, sample, key="c266-run-scope")
    collector_obj, _ = collector
    assert derive_request_id(
        tenant_id=sample.e.tenant, project_id=sample.e.project,
        run_id=sample.run, key="c266-run-scope",
    ) != derive_request_id(
        tenant_id=sample.e.tenant, project_id=sample.e.project,
        run_id="run_" + "0" * 26, key="c266-run-scope",
    )
    with pytest.raises(DomainError):
        collector_obj.collect(
            sample.principal, sample.e.project, "run_" + "0" * 26,
            contribution=sample.contribution, key="c266-run-scope",
        )
    assert _counts(sample)[3] == [first]


def test_a_crash_inside_the_pre_io_phase_leaves_neither_row(collector, sample):  # noqa: F811
    """F3's reason, measured: the ledger row and the pending request are in one
    transaction, so a failure between them strands nothing."""
    collector_obj, transport = collector
    real_issue = collector_obj.samples.locked_issue

    def issue_then_fail(*args, **kwargs):
        real_issue(*args, **kwargs)
        raise RuntimeError("injected inside the pre-I/O transaction")

    collector_obj.samples.locked_issue = issue_then_fail
    try:
        with pytest.raises(RuntimeError, match="injected"):
            _collect(collector, sample, key="c266-preio-crash")
    finally:
        collector_obj.samples.locked_issue = real_issue

    with sample.e.db.transaction(sample.e.tenant) as c:
        pending = c.execute(
            "SELECT count(*) AS n FROM inv.storage_sample_requests"
        ).fetchone()["n"]
    assert pending == 0
    assert _counts(sample)[3] == []
    assert transport.calls == 0


def test_a_project_the_kernel_knows_but_the_business_surface_does_not_fails_closed(
    collector, sample  # noqa: F811
):
    """``business_permission`` returns **None** for a project with no
    ``inv.business_projects`` row unless it is asked with ``linked=True``.

    Without that flag the next line read ``granted["userId"]`` off None and the
    caller got a 500 where the honest answer is a fail-closed refusal (Codex r1).
    A kernel-only project is exactly that shape, so it is built here rather than
    reasoned about.
    """
    import psycopg

    from inv.ids import new_id

    kernel_only = new_id("prj")
    with psycopg.connect(sample.e.owner) as connection:
        connection.execute(
            "INSERT INTO public.projects(tenant_id,project_id,code,display_name) "
            "VALUES(%s,%s,'c266-kernel-only','c266-kernel-only')",
            (sample.e.tenant, kernel_only),
        )
        # The kernel knows it; the business surface does not. That is the shape --
        # an inv.projects row with no inv.business_projects row.
        connection.execute(
            "INSERT INTO inv.projects VALUES(%s,%s)", (sample.e.tenant, kernel_only)
        )
        # A grant exists, so the first check passes and the second one is reached --
        # which is the only way this path gets exercised at all.
        connection.execute(
            "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request) "
            "VALUES(%s,%s,%s,true)",
            (sample.e.tenant, kernel_only, sample.principal.subject_id),
        )
        connection.commit()

    collector_obj, _ = collector
    with pytest.raises(DomainError) as raised:
        collector_obj.collect(
            sample.principal, kernel_only, sample.run,
            contribution=sample.contribution, key="c266-kernel-only",
        )
    assert raised.value.code == "AUTH-0030"
    assert raised.value.status == 403
    assert _counts(sample)[:3] == (0, 0, 0)


def test_a_partly_migrated_folder_is_refused_even_though_some_rows_are_in_project(
    collector, sample  # noqa: F811
):
    """The case the all-NULL test cannot reach.

    With every row NULL the folder is refused for having nothing *inside* the
    project, which is true but not the reason that matters. A folder with one row
    bound and one still NULL has something inside, so only the "nothing outside"
    half can refuse it -- and a NULL that stopped counting as outside would let it
    through. The sweep found this gap, which is what a sweep is for.
    """
    import hashlib

    import psycopg

    from inv.ids import new_id

    with psycopg.connect(sample.e.owner) as connection:
        connection.execute(
            "INSERT INTO public.data_locations(location_id,tenant_id,project_id,"
            "contribution_id,uri,kind,relative_path,byte_size,checksum_sha256) "
            "VALUES(%s,%s,NULL,%s,'file:unmigrated.bin','dataset','unmigrated.bin',12,%s)",
            (
                new_id("dtl"), sample.e.tenant, sample.contribution,
                hashlib.sha256(b"unmigrated bytes").hexdigest(),
            ),
        )
        connection.commit()
    with pytest.raises(DomainError) as raised:
        _collect(collector, sample, key="c266-partly-migrated")
    assert (raised.value.code, raised.value.status) == ("RES-0004", 404)
    assert _counts(sample)[:3] == (0, 0, 0)


def test_the_pre_io_phase_issues_on_the_transaction_it_already_holds(collector):  # noqa: F811
    """A source-level assertion, and it says so.

    ``issue`` opens its **own connection** (``db.transaction`` connects), so calling
    it from inside phase one would commit the pending request on a second
    connection before this transaction -- and a failure afterwards would strand it
    with no ledger row to consume it (Codex r1 F3).

    This is checked by reading the code rather than by behaviour because the two
    shapes are indistinguishable from outside unless the *commit itself* fails
    after a successful issue, and there is no honest way to inject that here. A
    weaker check that is true beats a stronger one that is staged.
    """
    import inspect

    collector_obj, _ = collector
    source = inspect.getsource(type(collector_obj).collect)
    pre_io, final = source.split("--- 2. node I/O", 1)
    assert "self.samples.locked_issue(" in pre_io
    assert "self.samples.issue(" not in pre_io
    # And the method it must not use is still there for its own callers.
    assert hasattr(collector_obj.samples, "issue")
