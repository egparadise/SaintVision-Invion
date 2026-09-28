"""Service credentials and the worker delivery path against a real PostgreSQL (stage 2).

Design #168 §4 decision (b): a tenant-scoped operator credential, separate from
the run-bound 0035 registry. The negatives are the point: every way a lookup
can be wrong (revoked, expired, other epoch, other destination, other worker,
other purpose, unpinned URI) must answer ``None`` -> ``TRACK-0002``, with no
network call and no secret bytes anywhere in the database.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from saintvision.adapters.tracking_reference import ReferenceSink
from saintvision.db.models import (
    MlflowMirrorAttempt,
    MlflowMirrorIntent,
    OutboxEvent,
    ServiceCredentialGrant,
    ServiceCredentialVersion,
)
from saintvision.db.session import tenant_scope
from saintvision.ids import new_id
from saintvision.services import tracking as tracking_service
from saintvision.services.evidence import mark_published
from saintvision.tracking import config as tracking_config
from saintvision.tracking.canonical import tracking_uri_sha256
from saintvision.tracking.service_credentials import (
    PURPOSE_MLFLOW_MIRROR,
    LookupRequest,
    ServiceCredentialRegistry,
    ServiceRegistryAdapter,
    credential_reference,
    worker_context,
)
from test_lineage import NOW, _full_lineage, catalogue  # noqa: F401  (fixture)
from test_tracking_mirror import GOOD_ENV, configured  # noqa: F401  (fixture)

pytestmark = pytest.mark.postgres

URI_SHA = tracking_uri_sha256("https://mlflow.lab.example/")
FILE_NAME = "0123456789abcdef0123456789abcdef.secret"
PRINCIPAL = "mirror-worker.lab"
LATER = NOW + dt.timedelta(days=30)


def _seed_credential(session, tenant, **override):
    version = ServiceCredentialVersion(
        tenant_id=tenant, credential_id=uuid.uuid4(), version_id=uuid.uuid4(),
        purpose=PURPOSE_MLFLOW_MIRROR, destination="lab-mlflow", destination_uri_sha256=URI_SHA,
        file_name=FILE_NAME, device=64769, inode=1234567, content_sha256="c" * 64, created_at=NOW,
    )
    for key in ("purpose", "destination", "destination_uri_sha256", "revoked_at", "file_name", "content_sha256"):
        if key in override:
            setattr(version, key, override[key])
    session.add(version)
    session.flush()
    grant = ServiceCredentialGrant(
        tenant_id=tenant, grant_id=new_id("service_credential_grant"),
        credential_id=version.credential_id, version_id=version.version_id,
        worker_principal=override.get("worker_principal", PRINCIPAL),
        enabled=override.get("enabled", True), recovery_epoch=override.get("recovery_epoch", 0),
        created_at=NOW, expires_at=override.get("expires_at", LATER), revoked_at=override.get("grant_revoked_at"),
    )
    session.add(grant)
    session.flush()
    return version, grant


def _request(tenant, **override):
    base = dict(
        tenant_id=tenant, purpose=PURPOSE_MLFLOW_MIRROR, destination="lab-mlflow",
        destination_uri_sha256=URI_SHA, worker_principal=PRINCIPAL, recovery_epoch=0, now=NOW,
    )
    base.update(override)
    return LookupRequest(**base)


# --------------------------------------------------------------------------
# Lookup
# --------------------------------------------------------------------------


def test_a_valid_grant_resolves_to_the_pinned_file_binding_without_secret_bytes(app_sessionmaker, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                version, _grant = _seed_credential(session, tenant)
                match = ServiceCredentialRegistry(session).lookup(_request(tenant))
    assert match is not None
    assert (match.credential_id, match.version_id) == (version.credential_id, version.version_id)
    assert match.binding.file_name == FILE_NAME and match.binding.content_sha256 == "c" * 64
    assert match.binding.device == 64769 and match.binding.inode == 1234567
    assert match.reference == credential_reference(version.credential_id, version.version_id)
    assert match.reference.startswith("svcred:1:")
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        columns = [c.name for c in ServiceCredentialVersion.__table__.columns]
        assert not any("secret" in c or "token" in c for c in columns)      # a file reference, never bytes


@pytest.mark.parametrize(
    "seed,request_override",
    [
        ({"grant_revoked_at": NOW}, {}),                                          # grant revoked
        ({"enabled": False}, {}),                                                 # grant disabled
        ({"expires_at": NOW + dt.timedelta(seconds=1)}, {"now": NOW + dt.timedelta(seconds=2)}),   # expired
        ({"recovery_epoch": 1}, {}),                                              # other recovery epoch
        ({"revoked_at": NOW}, {}),                                                # version revoked
        ({"worker_principal": "other-worker.lab"}, {}),                           # other principal
        ({"destination": "other-mlflow"}, {}),                                    # other destination alias
        ({"destination_uri_sha256": tracking_uri_sha256("https://other.example/")}, {}),   # alias bound to another URI
        ({}, {"destination_uri_sha256": tracking_uri_sha256("https://other.example/")}),   # configured URI differs
    ],
)
def test_every_wrong_condition_refuses(app_sessionmaker, two_tenants, clean_tables, seed, request_override):
    tenant, _ = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                _seed_credential(session, tenant, **seed)
                assert ServiceCredentialRegistry(session).lookup(_request(tenant, **request_override)) is None


def test_lookup_request_shape_is_validated():
    with pytest.raises(ValueError):
        _request(uuid.uuid4(), purpose="encryption.unwrap")
    with pytest.raises(ValueError):
        _request(uuid.uuid4(), destination_uri_sha256="X" * 64)
    with pytest.raises(ValueError):
        _request(uuid.uuid4(), recovery_epoch=-1)
    with pytest.raises(ValueError):
        _request(uuid.uuid4(), now=dt.datetime(2026, 9, 28))


def test_the_adapter_speaks_the_0035_signature_and_binds_tenant_principal_purpose_destination(
    app_sessionmaker, two_tenants, clean_tables
):
    tenant, other = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                version, _ = _seed_credential(session, tenant)
                request = _request(tenant)
                adapter = ServiceRegistryAdapter(ServiceCredentialRegistry(session), request)
                context = worker_context(request)
                assert context.subject_id == PRINCIPAL and context.run_id == "-" and context.project_id == "-"
                cid, vid = str(version.credential_id), str(version.version_id)
                assert adapter.lookup(cid, vid, context, PURPOSE_MLFLOW_MIRROR, "lab-mlflow").content_sha256 == "c" * 64
                assert adapter.lookup(str(uuid.uuid4()), vid, context, PURPOSE_MLFLOW_MIRROR, "lab-mlflow") is None
                assert adapter.lookup(cid, vid, context, "encryption.unwrap", "lab-mlflow") is None
                assert adapter.lookup(cid, vid, context, PURPOSE_MLFLOW_MIRROR, "other") is None
                assert adapter.lookup("not-a-uuid", vid, context, PURPOSE_MLFLOW_MIRROR, "lab-mlflow") is None
                from saintvision.credentials.contract import CredentialContext

                foreign = CredentialContext(tenant_id=str(other), project_id="-", subject_id=PRINCIPAL, run_id="-")
                assert adapter.lookup(cid, vid, foreign, PURPOSE_MLFLOW_MIRROR, "lab-mlflow") is None
                impostor = CredentialContext(tenant_id=str(tenant), project_id="-", subject_id="other-worker.lab", run_id="-")
                assert adapter.lookup(cid, vid, impostor, PURPOSE_MLFLOW_MIRROR, "lab-mlflow") is None


# --------------------------------------------------------------------------
# Constraints, lifecycle grants, RLS
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "override,constraint",
    [
        ({"purpose": "s3.read"}, "purpose_allowed"),
        ({"destination": "Lab"}, "destination_alias"),
        ({"file_name": "secret.txt"}, "file_name_secret"),
        ({"content_sha256": "Z" * 64}, "content_sha256_hex"),
        ({"destination_uri_sha256": "Z" * 64}, "destination_uri_sha256_hex"),
    ],
)
def test_version_check_constraints(app_sessionmaker, two_tenants, clean_tables, override, constraint):
    tenant, _ = two_tenants
    with app_sessionmaker() as session:
        with pytest.raises(IntegrityError) as exc:
            with session.begin():
                with tenant_scope(session, tenant):
                    _seed_credential(session, tenant, **override)
        assert constraint in str(exc.value)


def test_grant_shape_constraints(app_sessionmaker, two_tenants, clean_tables):
    tenant, _ = two_tenants
    for override, constraint in (
        ({"worker_principal": "W"}, "worker_principal_shape"),
        ({"expires_at": NOW}, "expiry_after_creation"),
        ({"recovery_epoch": -1}, "recovery_epoch_non_negative"),
    ):
        with app_sessionmaker() as session:
            with pytest.raises(IntegrityError) as exc:
                with session.begin():
                    with tenant_scope(session, tenant):
                        _seed_credential(session, tenant, **override)
            assert constraint in str(exc.value)


def test_only_lifecycle_columns_can_move_and_nothing_can_be_deleted(app_sessionmaker, two_tenants, clean_tables):
    tenant, _ = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                _seed_credential(session, tenant)
    # Allowed: revoke and disable.
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                session.execute(text("UPDATE service_credential_grants SET enabled = false, revoked_at = now()"))
                session.execute(text("UPDATE service_credential_versions SET revoked_at = now()"))
    for statement in (
        "UPDATE service_credential_versions SET content_sha256 = repeat('d', 64)",
        "UPDATE service_credential_versions SET file_name = 'ffffffffffffffffffffffffffffffff.secret'",
        "UPDATE service_credential_grants SET worker_principal = 'other-worker.lab'",
        "UPDATE service_credential_grants SET expires_at = now() + interval '1 year'",
        "DELETE FROM service_credential_grants",
        "DELETE FROM service_credential_versions",
    ):
        with app_sessionmaker() as session:
            with pytest.raises(ProgrammingError) as exc:
                with session.begin():
                    with tenant_scope(session, tenant):
                        session.execute(text(statement))
            assert "permission denied" in str(exc.value)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        assert ServiceCredentialRegistry(session).lookup(_request(tenant)) is None      # revoked now


@pytest.mark.parametrize(
    "statement,constraint",
    [
        ("UPDATE service_credential_grants SET revoked_at = NULL", "revocation_is_final"),
        ("UPDATE service_credential_grants SET revoked_at = now() + interval '1 day'", "revocation_is_final"),
        ("UPDATE service_credential_grants SET enabled = true", "disable_is_final"),
        ("UPDATE service_credential_versions SET revoked_at = NULL", "revocation_is_final"),
        ("UPDATE service_credential_versions SET revoked_at = now() + interval '1 day'", "revocation_is_final"),
    ],
)
def test_a_revoked_or_disabled_credential_cannot_be_revived(app_sessionmaker, two_tenants, clean_tables, statement, constraint):
    """Codex #176 finding 2: revoke and disable are one-way, enforced in the database."""
    tenant, _ = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                _seed_credential(session, tenant)
                session.execute(text("UPDATE service_credential_grants SET enabled = false, revoked_at = now()"))
                session.execute(text("UPDATE service_credential_versions SET revoked_at = now()"))
    with app_sessionmaker() as session:
        with pytest.raises(IntegrityError) as exc:
            with session.begin():
                with tenant_scope(session, tenant):
                    session.execute(text(statement))
        # RAISE ... USING CONSTRAINT puts the name in the diagnostics, not the message
        # (hosted run 36378728263); the trigger's ERRCODE is check_violation.
        diag = exc.value.orig.diag
        assert diag.constraint_name == constraint, (diag.constraint_name, str(exc.value)[:200])
        assert diag.sqlstate == "23514"
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        assert ServiceCredentialRegistry(session).lookup(_request(tenant)) is None       # still refused


@pytest.mark.parametrize(
    "statements",
    [
        ("UPDATE service_credential_versions SET revoked_at = now()",),                              # versions revoke (no enabled column)
        ("UPDATE service_credential_grants SET revoked_at = now()",),                                 # grants revoke
        ("UPDATE service_credential_grants SET enabled = false",),                                    # grants disable
        ("UPDATE service_credential_grants SET enabled = false", "UPDATE service_credential_grants SET enabled = false"),   # idempotent
        ("UPDATE service_credential_grants SET enabled = false, revoked_at = now()",),                # both at once
    ],
)
def test_each_forward_move_is_allowed_on_its_own_table(app_sessionmaker, two_tenants, clean_tables, statements):
    """hosted job 108787266063: the shared trigger read OLD.enabled on versions; each table has its own now."""
    tenant, _ = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                _seed_credential(session, tenant)
                for statement in statements:
                    session.execute(text(statement))
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        grant = session.scalars(select(ServiceCredentialGrant)).one()
        version = session.scalars(select(ServiceCredentialVersion)).one()
        assert (grant.revoked_at is not None) or (grant.enabled is False) or (version.revoked_at is not None)


def test_credentials_are_invisible_across_tenants(app_sessionmaker, two_tenants, clean_tables):
    tenant_a, tenant_b = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant_a):
                _seed_credential(session, tenant_a)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant_b):
        assert session.scalars(select(ServiceCredentialVersion)).all() == []
        assert ServiceCredentialRegistry(session).lookup(_request(tenant_b)) is None
    with app_sessionmaker() as session, session.begin():
        assert session.execute(text("SELECT count(*) FROM service_credential_grants")).scalar_one() == 0


# --------------------------------------------------------------------------
# Worker path: outbox event -> credential -> sink -> attempt
# --------------------------------------------------------------------------


def _pending_event(session):
    return session.scalar(
        select(OutboxEvent).where(
            OutboxEvent.event_type == tracking_service.MIRROR_EVENT_TYPE,
            OutboxEvent.status == "pending",
        ).order_by(OutboxEvent.created_at)
    )


def _identity(tmp_path):
    return tracking_service.WorkerIdentity(worker_principal=PRINCIPAL, recovery_epoch=0, credentials_root=str(tmp_path))


def test_a_refused_credential_records_a_terminal_refused_attempt_without_any_sink_call(
    app_sessionmaker, catalogue, configured, tmp_path, monkeypatch
):
    """No grant at all -> TRACK-0002 attempt through the same delivery path; nothing contacted."""
    tenant = catalogue["tenant_a"]
    sink = ReferenceSink()
    spied = []
    from inv import credential_registry as run_bound

    monkeypatch.setattr(run_bound.PostgresCredentialRegistry, "lookup", lambda self, *a, **k: spied.append(a) or None)
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                _full_lineage(session, catalogue)
                event = _pending_event(session)
                attempt = tracking_service.deliver_outbox_event(
                    session, event=event, tenant_id=tenant, identity=_identity(tmp_path), worker_id="w",
                    now=NOW, configuration=configured, sink_factory=lambda s: sink,
                )
                assert (attempt.status, attempt.error_code) == ("refused", "TRACK-0002")
                assert attempt.outbox_event_id == event.event_id and attempt.delivery_no == 1
                mark_published(session, event.outbox_id, now=NOW)
    assert sink.calls == {"find": 0, "mirror": 0, "attest": 0}
    assert spied == []                                                # the run-bound 0035 registry is never asked
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        assert len(session.scalars(select(MlflowMirrorAttempt)).all()) == 1


class _HandleConsumingSink(ReferenceSink):
    """Like the real sink: authentication reads the handle, so an unreadable file refuses."""

    def authenticate(self, secret_handle):
        use = getattr(secret_handle, "use", None)
        if not callable(use):
            return super().authenticate(None)
        try:
            ok = use(lambda content: bool(content))
        except Exception:  # noqa: BLE001 - CredentialDenied and anything else: refused
            ok = False
        return super().authenticate("ok" if ok else None)


def test_a_valid_grant_but_unreadable_file_is_refused_not_unavailable(app_sessionmaker, catalogue, configured, tmp_path):
    """The grant resolves; the descriptor-bound reader cannot admit the file (absent / wrong identity)."""
    tenant = catalogue["tenant_a"]
    sink = _HandleConsumingSink()
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                _seed_credential(session, tenant)
                _full_lineage(session, catalogue)
                event = _pending_event(session)
                attempt = tracking_service.deliver_outbox_event(
                    session, event=event, tenant_id=tenant, identity=_identity(tmp_path), worker_id="w",
                    now=NOW, configuration=configured, sink_factory=lambda s: sink,
                )
                assert (attempt.status, attempt.error_code) == ("refused", "TRACK-0002")
    assert sink.calls["mirror"] == 0


def test_absent_or_invalid_configuration_delivers_nothing_and_leaves_the_event_pending(
    app_sessionmaker, catalogue, configured, tmp_path, monkeypatch
):
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                _full_lineage(session, catalogue)
    for key in GOOD_ENV:
        monkeypatch.delenv(key, raising=False)
    absent = tracking_config.resolve()
    assert absent.readiness.value == "absent"
    sink = ReferenceSink()
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                event = _pending_event(session)
                assert tracking_service.deliver_outbox_event(
                    session, event=event, tenant_id=tenant, identity=_identity(tmp_path), worker_id="w",
                    now=NOW, configuration=absent, sink_factory=lambda s: sink,
                ) is None
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        assert session.scalars(select(MlflowMirrorAttempt)).all() == []
        assert _pending_event(session) is not None                   # still pending: NOT_OBSERVED, not lost
    assert sink.calls == {"find": 0, "mirror": 0, "attest": 0}


def test_an_event_whose_payload_names_another_intent_is_refused_before_any_credential_or_sink(
    app_sessionmaker, catalogue, configured, tmp_path
):
    tenant = catalogue["tenant_a"]
    sink = ReferenceSink()
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                _full_lineage(session, catalogue)
                event = _pending_event(session)
                event.payload = {**event.payload, "intentId": new_id("mirror_intent")}   # in memory only
                with pytest.raises(tracking_service.DeliveryIdentityError):
                    tracking_service.deliver_outbox_event(
                        session, event=event, tenant_id=tenant, identity=_identity(tmp_path), worker_id="w",
                        now=NOW, configuration=configured, sink_factory=lambda s: sink,
                    )
                session.expire(event)
    assert sink.calls == {"find": 0, "mirror": 0, "attest": 0}


def test_release_and_deploy_succeed_whatever_the_mirror_does(app_sessionmaker, catalogue, configured, tmp_path):
    """Decision B end to end: a refused mirror never blocks release or deploy."""
    from saintvision.services import lineage as lineage_service

    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                built = _full_lineage(session, catalogue)
                version = built["version"]
                lineage_service.verify_model_version(
                    session, tenant_id=tenant, model_version_id=version.model_version_id, content_sha256="a" * 64, now=NOW
                )
                lineage_service.pin_retention(session, tenant_id=tenant, model_version_id=version.model_version_id, until=LATER)
                lineage_service.release_model_version(session, tenant_id=tenant, model_version_id=version.model_version_id, now=NOW)
                deployment = lineage_service.record_deployment(
                    session, tenant_id=tenant, model_version_id=version.model_version_id, environment="lab",
                    approval_id=built["approval_id"], deployed_by_user_id=catalogue["user_id"], now=NOW,
                )
                # Deliver every pending mirror event with no credential: all refused.
                while (event := _pending_event(session)) is not None:
                    attempt = tracking_service.deliver_outbox_event(
                        session, event=event, tenant_id=tenant, identity=_identity(tmp_path), worker_id="w",
                        now=NOW, configuration=configured, sink_factory=lambda s: ReferenceSink(),
                    )
                    assert attempt.status == "refused"
                    mark_published(session, event.outbox_id, now=NOW)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        assert session.get(type(deployment), deployment.deployment_id).status == "active"
        intents = session.scalars(select(MlflowMirrorIntent)).all()
        attempts = session.scalars(select(MlflowMirrorAttempt)).all()
        assert len(attempts) == len(intents) >= 4 and all(a.error_code == "TRACK-0002" for a in attempts)
