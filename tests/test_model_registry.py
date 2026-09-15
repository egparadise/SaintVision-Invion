"""Model version registry and lineage (VF-CL-03, existing S10 substrate).

This exercises the model *version* registry and its lineage graph -- the S10-ST
Model / ModelVersion / ModelLineage substrate and services/lineage.py -- which had
no direct test coverage. It is separate from the VF-CX-02 ModelManifest/Shard
contract (still to land) and does not touch it.

Each assertion guards a way a model could be treated as trustworthy without being
so:

* a version is ``draft`` until verified, and ``released`` demands verification,
  a retention pin and full traceability -- the database enforces the first two,
  the service the third (AC-10);
* two names for identical weights is a mistake the unique checksum catches;
* a traceback reports what is *missing*, so a model nobody recorded anything
  about does not read as fully traceable;
* a non-owner scoped to one tenant cannot see another tenant's versions.

The fully-traceable *success* path additionally needs eval_run and approval
fixtures (FK chains into evaluation/execution); it is left to a follow-up, and
the refusal that a missing eval_run/approval produces is asserted here instead.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.services import lineage as lineage_service
from saintvision.services.lineage import LineageEdge

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 15, 7, 0, 0, tzinfo=UTC)
LATER = dt.datetime(2027, 1, 1, tzinfo=UTC)
SHA = "e" * 64
OTHER_SHA = "f" * 64


@pytest.fixture
def registry(owner_engine, two_tenants):
    """Tenant A: a project, a model, and a dataset to hang versions and lineage off."""
    tenant_a, tenant_b = two_tenants
    ids = {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "project_id": new_id("project"),
        "model_id": new_id("model"),
        "dataset_id": new_id("dataset"),
    }
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO projects (project_id, tenant_id, code, display_name, status, "
                "created_at, version) VALUES (:p, :t, 'a', 'A', 'active', now(), 1)"
            ),
            {"p": ids["project_id"], "t": tenant_a},
        )
        c.execute(
            text(
                "INSERT INTO models (model_id, tenant_id, project_id, name, created_at) "
                "VALUES (:m, :t, :p, 'classifier', now())"
            ),
            {"m": ids["model_id"], "t": tenant_a, "p": ids["project_id"]},
        )
        c.execute(
            text(
                "INSERT INTO datasets (dataset_id, tenant_id, project_id, name, created_at) "
                "VALUES (:d, :t, :p, 'corpus', now())"
            ),
            {"d": ids["dataset_id"], "t": tenant_a, "p": ids["project_id"]},
        )
    return ids


def _draft(session, registry, *, version="1", sha=SHA):
    return lineage_service.register_model_version(
        session,
        tenant_id=registry["tenant_a"],
        model_id=registry["model_id"],
        version=version,
        content_sha256=sha,
        uri=f"inv://models/classifier@{version}/w.safetensors",
        now=NOW,
    )


def test_a_registered_version_starts_as_draft(app_sessionmaker, registry):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, registry["tenant_a"]):
                mv = _draft(session, registry)
                assert mv.stage == "draft"
                assert mv.verified_at is None
                assert mv.retention_pinned_until is None


def test_registering_requires_a_hex_sha256_and_an_existing_model(app_sessionmaker, registry):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, registry["tenant_a"]):
                with pytest.raises(InvError, match="SHA-256"):
                    _draft(session, registry, sha="NOTAHEX")
                with pytest.raises(InvError, match="model not found"):
                    lineage_service.register_model_version(
                        session, tenant_id=registry["tenant_a"], model_id=new_id("model"),
                        version="1", content_sha256=SHA, uri="inv://models/x@1/w", now=NOW,
                    )


def test_identical_weights_under_two_names_is_refused(owner_engine, app_sessionmaker, registry):
    """content_sha256 is unique per tenant: the same bytes are one build."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, registry["tenant_a"]):
                _draft(session, registry, version="1", sha=SHA)
    with pytest.raises(IntegrityError):
        with app_sessionmaker() as session:
            with session.begin():
                with tenant_scope(session, registry["tenant_a"]):
                    _draft(session, registry, version="2", sha=SHA)


def test_verify_sets_the_timestamp_and_rejects_a_mismatch(app_sessionmaker, registry):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, registry["tenant_a"]):
                mv = _draft(session, registry)
                with pytest.raises(InvError, match="does not match"):
                    lineage_service.verify_model_version(
                        session, tenant_id=registry["tenant_a"],
                        model_version_id=mv.model_version_id, content_sha256=OTHER_SHA, now=NOW,
                    )
                verified = lineage_service.verify_model_version(
                    session, tenant_id=registry["tenant_a"],
                    model_version_id=mv.model_version_id, content_sha256=SHA, now=NOW,
                )
                assert verified.verified_at is not None


def test_a_retention_pin_only_extends(app_sessionmaker, registry):
    earlier = dt.datetime(2026, 6, 1, tzinfo=UTC)
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, registry["tenant_a"]):
                mv = _draft(session, registry)
                lineage_service.pin_retention(
                    session, tenant_id=registry["tenant_a"],
                    model_version_id=mv.model_version_id, until=LATER,
                )
                lineage_service.pin_retention(
                    session, tenant_id=registry["tenant_a"],
                    model_version_id=mv.model_version_id, until=earlier,
                )
                assert mv.retention_pinned_until == LATER


def test_release_is_refused_until_verified_then_pinned_then_traceable(app_sessionmaker, registry):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, registry["tenant_a"]):
                mv = _draft(session, registry)
                # 1. unverified
                with pytest.raises(InvError, match="unverified"):
                    lineage_service.release_model_version(
                        session, tenant_id=registry["tenant_a"],
                        model_version_id=mv.model_version_id, now=NOW,
                    )
                lineage_service.verify_model_version(
                    session, tenant_id=registry["tenant_a"],
                    model_version_id=mv.model_version_id, content_sha256=SHA, now=NOW,
                )
                # 2. verified but unpinned
                with pytest.raises(InvError, match="retention pinned"):
                    lineage_service.release_model_version(
                        session, tenant_id=registry["tenant_a"],
                        model_version_id=mv.model_version_id, now=NOW,
                    )
                lineage_service.pin_retention(
                    session, tenant_id=registry["tenant_a"],
                    model_version_id=mv.model_version_id, until=LATER,
                )
                # 3. verified and pinned but no lineage -> not fully traceable
                with pytest.raises(InvError, match="not fully traceable"):
                    lineage_service.release_model_version(
                        session, tenant_id=registry["tenant_a"],
                        model_version_id=mv.model_version_id, now=NOW,
                    )


def test_the_database_refuses_released_without_verification_and_pin(owner_engine, app_sessionmaker, registry):
    """The stage guard is a CHECK constraint, not only service logic."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, registry["tenant_a"]):
                mv = _draft(session, registry)
                version_id = mv.model_version_id
    with pytest.raises(IntegrityError):
        with owner_engine.begin() as c:
            c.execute(
                text("UPDATE model_versions SET stage = 'released' WHERE model_version_id = :v"),
                {"v": version_id},
            )


def test_record_lineage_rejects_unknown_kinds_and_is_idempotent(app_sessionmaker, registry):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, registry["tenant_a"]):
                mv = _draft(session, registry)
                with pytest.raises(InvError, match="unknown lineage kind"):
                    lineage_service.record_lineage(
                        session, tenant_id=registry["tenant_a"],
                        model_version_id=mv.model_version_id,
                        edge=LineageEdge(kind="astrology", subject_id="x"), now=NOW,
                    )
                edge = LineageEdge(kind="approval", subject_id="apr_1")
                first = lineage_service.record_lineage(
                    session, tenant_id=registry["tenant_a"],
                    model_version_id=mv.model_version_id, edge=edge, now=NOW,
                )
                again = lineage_service.record_lineage(
                    session, tenant_id=registry["tenant_a"],
                    model_version_id=mv.model_version_id, edge=edge, now=NOW,
                )
                assert (first.model_version_id, first.subject_id) == (
                    again.model_version_id, again.subject_id
                )


def test_trace_reports_missing_required_kinds_and_shrinks_as_they_are_recorded(
    app_sessionmaker, registry
):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, registry["tenant_a"]):
                mv = _draft(session, registry)
                trace = lineage_service.trace_model(
                    session, tenant_id=registry["tenant_a"], model_version_id=mv.model_version_id
                )
                assert set(trace["missing"]) == {
                    "dataset_version", "code_commit", "eval_run", "approval",
                }
                assert trace["fullyTraceable"] is False

                # Record two subjects that actually exist, via their services.
                dsv = lineage_service.register_dataset_version(
                    session, tenant_id=registry["tenant_a"], dataset_id=registry["dataset_id"],
                    version="1", content_sha256=SHA, uri="inv://datasets/corpus@1", now=NOW,
                )
                commit = lineage_service.register_commit(
                    session, tenant_id=registry["tenant_a"],
                    repository="git@x/repo", commit_sha="a" * 40, now=NOW,
                )
                lineage_service.record_lineage(
                    session, tenant_id=registry["tenant_a"], model_version_id=mv.model_version_id,
                    edge=LineageEdge(kind="dataset_version", subject_id=dsv.dataset_version_id), now=NOW,
                )
                lineage_service.record_lineage(
                    session, tenant_id=registry["tenant_a"], model_version_id=mv.model_version_id,
                    edge=LineageEdge(kind="code_commit", subject_id=commit.commit_id), now=NOW,
                )
                trace = lineage_service.trace_model(
                    session, tenant_id=registry["tenant_a"], model_version_id=mv.model_version_id
                )
                assert set(trace["missing"]) == {"eval_run", "approval"}
                assert len(trace["datasets"]) == 1
                assert len(trace["commits"]) == 1
                assert trace["dangling"] == []


def test_a_non_owner_scoped_to_one_tenant_cannot_see_another_tenants_version(
    owner_engine, app_sessionmaker, registry
):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, registry["tenant_a"]):
                mv = _draft(session, registry)
                version_id = mv.model_version_id
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, registry["tenant_b"]):
                found = session.execute(
                    text("SELECT count(*) FROM model_versions WHERE model_version_id = :v"),
                    {"v": version_id},
                ).scalar_one()
                assert found == 0
