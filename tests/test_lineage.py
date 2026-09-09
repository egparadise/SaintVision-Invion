"""S10 lineage against a real PostgreSQL.

AC-10 is "모델의 데이터·코드·평가·승인 역추적" plus a deployment digest. What
makes that answerable is that every link is pinned to something immutable, so
these tests are mostly about identity: a tag is not an image, a version name is
not a model, and an approval is for exact content.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.runs.state import TerminationReason
from saintvision.services import evaluation as eval_service
from saintvision.services import lineage as lineage_service
from saintvision.services import runs as run_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 9, 7, 0, 0, tzinfo=UTC)
LATER = NOW + dt.timedelta(days=365)

WEIGHTS_SHA = "a" * 64
DATA_SHA = "b" * 64
COMMIT_SHA = "c" * 40
IMAGE_DIGEST = "sha256:" + "d" * 64


@pytest.fixture
def catalogue(owner_engine, two_tenants):
    """A project with a dataset, a model, a workspace and a workload."""
    tenant_a, tenant_b = two_tenants
    ids = {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_id": new_id("user"),
        "project_id": new_id("project"),
        "workspace_id": new_id("workspace"),
        "workload_id": new_id("workload"),
        "dataset_id": new_id("dataset"),
        "model_id": new_id("model"),
    }
    digest = run_service.workload_digest({"objective": "train"})
    ids["spec_sha256"] = digest
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO users (user_id, tenant_id, external_subject, display_name, "
                "status, created_at, updated_at, version) "
                "VALUES (:u, :t, 'sub', 'U', 'active', now(), now(), 1)"
            ),
            {"u": ids["user_id"], "t": tenant_a},
        )
        c.execute(
            text(
                "INSERT INTO projects (project_id, tenant_id, code, display_name, status, "
                "created_at, version) VALUES (:p, :t, 'a', 'A', 'active', now(), 1)"
            ),
            {"p": ids["project_id"], "t": tenant_a},
        )
        c.execute(
            text(
                "INSERT INTO workspaces (workspace_id, tenant_id, project_id, name, status, "
                "created_by_user_id, created_at, version) "
                "VALUES (:w, :t, :p, 'ws', 'ready', :u, now(), 1)"
            ),
            {"w": ids["workspace_id"], "t": tenant_a, "p": ids["project_id"], "u": ids["user_id"]},
        )
        c.execute(
            text(
                "INSERT INTO workloads (workload_id, tenant_id, project_id, kind, objective, "
                "spec, spec_sha256, contract_version, created_by_user_id, created_at, version) "
                "VALUES (:wl, :t, :p, 'batch', 'train', '{}', :d, '1.0.0', :u, now(), 1)"
            ),
            {"wl": ids["workload_id"], "t": tenant_a, "p": ids["project_id"],
             "d": digest, "u": ids["user_id"]},
        )
        c.execute(
            text(
                "INSERT INTO datasets (dataset_id, tenant_id, project_id, name, sensitivity, "
                "created_at) VALUES (:d, :t, :p, 'corpus', 'synthetic', now())"
            ),
            {"d": ids["dataset_id"], "t": tenant_a, "p": ids["project_id"]},
        )
        c.execute(
            text(
                "INSERT INTO models (model_id, tenant_id, project_id, name, created_at) "
                "VALUES (:m, :t, :p, 'classifier', now())"
            ),
            {"m": ids["model_id"], "t": tenant_a, "p": ids["project_id"]},
        )
    return ids


def _full_lineage(session, catalogue, *, now=NOW, with_approval=True):
    """Build a model version with every required link, and return the ids."""
    tenant = catalogue["tenant_a"]
    dsv = lineage_service.register_dataset_version(
        session, tenant_id=tenant, dataset_id=catalogue["dataset_id"], version="1.0.0",
        content_sha256=DATA_SHA, uri="inv://datasets/corpus@1.0.0", now=now,
    )
    commit = lineage_service.register_commit(
        session, tenant_id=tenant, repository="git@lab:svi.git",
        commit_sha=COMMIT_SHA, now=now, ref="refs/heads/main",
    )
    image = lineage_service.register_image(
        session, tenant_id=tenant, repository="lab/trainer",
        digest=IMAGE_DIGEST, now=now, tag="v1",
    )
    suite = eval_service.create_suite(
        session, tenant_id=tenant, name="model-golden", version="1.0.0", now=now,
        cases=[eval_service.CaseDefinition("acc-01", "coding_task", {})],
    )
    eval_run = eval_service.start_eval_run(
        session, tenant_id=tenant, suite_id=suite.suite_id, now=now
    )

    edges = [
        lineage_service.LineageEdge("dataset_version", dsv.dataset_version_id, "trained_on"),
        lineage_service.LineageEdge("code_commit", commit.commit_id, "built_with"),
        lineage_service.LineageEdge("container_image", image.image_id, "built_in"),
        lineage_service.LineageEdge("eval_run", eval_run.eval_run_id, "evaluated_by"),
    ]

    approval_id = None
    if with_approval:
        run = run_service.create_run(
            session, tenant_id=tenant, workload_id=catalogue["workload_id"],
            workspace_id=catalogue["workspace_id"],
            requested_by_user_id=catalogue["user_id"], now=now,
        )
        # The approval binds to exact content, so it is recorded against the
        # model weights digest rather than the workload spec here.
        approval_id = new_id("approval")
        session.execute(
            text(
                "INSERT INTO approvals (approval_id, tenant_id, run_id, subject_sha256, "
                "decision, risk_level, scope, decided_by_user_id, decided_at, expires_at) "
                "VALUES (:a, :t, :r, :s, 'approved', 2, '{}', :u, :n, :e)"
            ),
            {"a": approval_id, "t": tenant, "r": run.run_id, "s": WEIGHTS_SHA,
             "u": catalogue["user_id"], "n": now, "e": now + dt.timedelta(days=30)},
        )
        edges.append(lineage_service.LineageEdge("approval", approval_id, "approved_by"))

    version = lineage_service.register_model_version(
        session, tenant_id=tenant, model_id=catalogue["model_id"], version="1.0.0",
        content_sha256=WEIGHTS_SHA, uri="inv://models/classifier@1.0.0",
        now=now, lineage=edges,
    )
    return {
        "version": version,
        "dataset_version_id": dsv.dataset_version_id,
        "commit_id": commit.commit_id,
        "image_id": image.image_id,
        "eval_run_id": eval_run.eval_run_id,
        "approval_id": approval_id,
    }


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------


def test_an_image_is_its_digest_not_its_tag(app_sessionmaker, catalogue):
    """The same digest under two tags is one image; two digests are two."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                first = lineage_service.register_image(
                    session, tenant_id=catalogue["tenant_a"], repository="lab/trainer",
                    digest=IMAGE_DIGEST, now=NOW, tag="v1",
                )
                same = lineage_service.register_image(
                    session, tenant_id=catalogue["tenant_a"], repository="lab/trainer",
                    digest=IMAGE_DIGEST, now=NOW, tag="latest",
                )
                other = lineage_service.register_image(
                    session, tenant_id=catalogue["tenant_a"], repository="lab/trainer",
                    digest="sha256:" + "e" * 64, now=NOW, tag="latest",
                )
    assert first.image_id == same.image_id
    # The tag it was first seen under is kept; re-registering does not rewrite it.
    assert same.tag == "v1"
    assert other.image_id != first.image_id


@pytest.mark.parametrize(
    "digest",
    ["latest", "sha256:short", "md5:" + "a" * 64, "sha256:" + "A" * 64, ""],
)
def test_a_malformed_image_digest_is_refused(app_sessionmaker, catalogue, digest):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                with pytest.raises(InvError):
                    lineage_service.register_image(
                        session, tenant_id=catalogue["tenant_a"],
                        repository="lab/x", digest=digest, now=NOW,
                    )


@pytest.mark.parametrize("sha", ["main", "c" * 39, "z" * 40, ""])
def test_a_malformed_commit_sha_is_refused(app_sessionmaker, catalogue, sha):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                with pytest.raises(InvError):
                    lineage_service.register_commit(
                        session, tenant_id=catalogue["tenant_a"],
                        repository="r", commit_sha=sha, now=NOW,
                    )


def test_a_dirty_tree_is_recorded_rather_than_refused(app_sessionmaker, catalogue):
    """Refusing it would push someone to record a clean SHA that is a lie."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                commit = lineage_service.register_commit(
                    session, tenant_id=catalogue["tenant_a"], repository="r",
                    commit_sha=COMMIT_SHA, now=NOW, dirty=True,
                )
    assert commit.dirty is True


def test_the_database_refuses_a_tag_shaped_digest(app_sessionmaker, catalogue):
    """The constraint, checked by going around the service."""
    with app_sessionmaker() as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, catalogue["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO container_images (image_id, tenant_id, repository, "
                            "digest, byte_size, recorded_at) "
                            "VALUES (:i, :t, 'lab/x', 'latest', 0, now())"
                        ),
                        {"i": new_id("image"), "t": catalogue["tenant_a"]},
                    )


def test_two_model_versions_cannot_share_content(app_sessionmaker, catalogue):
    """Identical bytes under two names is a mistake worth catching."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                lineage_service.register_model_version(
                    session, tenant_id=catalogue["tenant_a"], model_id=catalogue["model_id"],
                    version="1.0.0", content_sha256=WEIGHTS_SHA,
                    uri="inv://models/classifier@1.0.0", now=NOW,
                )
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, catalogue["tenant_a"]):
                    lineage_service.register_model_version(
                        session, tenant_id=catalogue["tenant_a"], model_id=catalogue["model_id"],
                        version="1.0.1", content_sha256=WEIGHTS_SHA,
                        uri="inv://models/classifier@1.0.1", now=NOW,
                    )


def test_model_versions_are_append_only_for_the_application(app_sessionmaker, catalogue):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                lineage_service.register_model_version(
                    session, tenant_id=catalogue["tenant_a"], model_id=catalogue["model_id"],
                    version="1.0.0", content_sha256=WEIGHTS_SHA,
                    uri="inv://models/classifier@1.0.0", now=NOW,
                )
    for statement in (
        "UPDATE model_versions SET content_sha256 = '" + "f" * 64 + "'",
        "DELETE FROM model_versions",
    ):
        with app_sessionmaker() as session:
            with pytest.raises((ProgrammingError, DBAPIError)):
                with session.begin():
                    with tenant_scope(session, catalogue["tenant_a"]):
                        session.execute(text(statement))


# --------------------------------------------------------------------------
# The AC-10 traceback
# --------------------------------------------------------------------------


def test_a_fully_linked_model_traces_back_to_everything(app_sessionmaker, catalogue):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                built = _full_lineage(session, catalogue)
                trace = lineage_service.trace_model(
                    session, tenant_id=catalogue["tenant_a"],
                    model_version_id=built["version"].model_version_id,
                )
    assert trace["fullyTraceable"]
    assert trace["missing"] == []
    assert trace["dangling"] == []
    assert [d["contentSha256"] for d in trace["datasets"]] == [DATA_SHA]
    assert [c["commitSha"] for c in trace["commits"]] == [COMMIT_SHA]
    assert [i["digest"] for i in trace["images"]] == [IMAGE_DIGEST]
    assert len(trace["evaluations"]) == 1
    assert [a["subjectSha256"] for a in trace["approvals"]] == [WEIGHTS_SHA]


def test_the_traceback_names_what_is_missing(app_sessionmaker, catalogue):
    """A traceback that returned only its hits would look complete for a model
    nobody recorded anything about."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                bare = lineage_service.register_model_version(
                    session, tenant_id=catalogue["tenant_a"], model_id=catalogue["model_id"],
                    version="0.1.0", content_sha256="9" * 64,
                    uri="inv://models/classifier@0.1.0", now=NOW,
                )
                trace = lineage_service.trace_model(
                    session, tenant_id=catalogue["tenant_a"],
                    model_version_id=bare.model_version_id,
                )
    assert not trace["fullyTraceable"]
    assert set(trace["missing"]) == {
        "dataset_version", "code_commit", "eval_run", "approval"
    }
    # An image is not required — a model trained outside a container is still
    # traceable if the data, code, evaluation and approval are there.
    assert "container_image" not in trace["missing"]


def test_an_edge_whose_subject_vanished_is_reported_as_dangling(
    owner_engine, app_sessionmaker, catalogue
):
    """Claiming a link you cannot substantiate is worse than claiming none."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                built = _full_lineage(session, catalogue)
                version_id = built["version"].model_version_id

    # Remove the commit as the owner; the lineage edge survives by design,
    # because model_lineage does not foreign-key its polymorphic subject.
    with owner_engine.begin() as connection:
        connection.execute(
            text("DELETE FROM code_commits WHERE commit_id = :c"), {"c": built["commit_id"]}
        )

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                trace = lineage_service.trace_model(
                    session, tenant_id=catalogue["tenant_a"], model_version_id=version_id
                )
    assert not trace["fullyTraceable"]
    assert "code_commit" in trace["missing"]
    assert any(d["kind"] == "code_commit" for d in trace["dangling"])


def test_recording_the_same_edge_twice_is_idempotent(app_sessionmaker, catalogue):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                built = _full_lineage(session, catalogue)
                edge = lineage_service.LineageEdge(
                    "dataset_version", built["dataset_version_id"], "trained_on"
                )
                lineage_service.record_lineage(
                    session, tenant_id=catalogue["tenant_a"],
                    model_version_id=built["version"].model_version_id, edge=edge, now=NOW,
                )
                count = session.execute(
                    text(
                        "SELECT count(*) FROM model_lineage WHERE model_version_id = :m "
                        "AND kind = 'dataset_version'"
                    ),
                    {"m": built["version"].model_version_id},
                ).scalar_one()
    assert count == 1


# --------------------------------------------------------------------------
# Release
# --------------------------------------------------------------------------


def test_release_requires_verification_pin_and_traceability(app_sessionmaker, catalogue):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                built = _full_lineage(session, catalogue)
                version_id = built["version"].model_version_id

                # Unverified.
                with pytest.raises(InvError, match="unverified"):
                    lineage_service.release_model_version(
                        session, tenant_id=catalogue["tenant_a"],
                        model_version_id=version_id, now=NOW,
                    )
                lineage_service.verify_model_version(
                    session, tenant_id=catalogue["tenant_a"],
                    model_version_id=version_id, content_sha256=WEIGHTS_SHA, now=NOW,
                )

                # Unpinned.
                with pytest.raises(InvError, match="retention pinned"):
                    lineage_service.release_model_version(
                        session, tenant_id=catalogue["tenant_a"],
                        model_version_id=version_id, now=NOW,
                    )
                lineage_service.pin_retention(
                    session, tenant_id=catalogue["tenant_a"],
                    model_version_id=version_id, until=LATER,
                )

                released = lineage_service.release_model_version(
                    session, tenant_id=catalogue["tenant_a"],
                    model_version_id=version_id, now=NOW,
                )
    assert released.stage == "released"


def test_an_untraceable_model_cannot_be_released(app_sessionmaker, catalogue):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                bare = lineage_service.register_model_version(
                    session, tenant_id=catalogue["tenant_a"], model_id=catalogue["model_id"],
                    version="0.2.0", content_sha256="7" * 64,
                    uri="inv://models/classifier@0.2.0", now=NOW,
                )
                lineage_service.verify_model_version(
                    session, tenant_id=catalogue["tenant_a"],
                    model_version_id=bare.model_version_id,
                    content_sha256="7" * 64, now=NOW,
                )
                lineage_service.pin_retention(
                    session, tenant_id=catalogue["tenant_a"],
                    model_version_id=bare.model_version_id, until=LATER,
                )
                with pytest.raises(InvError) as caught:
                    lineage_service.release_model_version(
                        session, tenant_id=catalogue["tenant_a"],
                        model_version_id=bare.model_version_id, now=NOW,
                    )
    assert "not fully traceable" in caught.value.message


def test_verification_refuses_a_mismatched_checksum(app_sessionmaker, catalogue):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                built = _full_lineage(session, catalogue)
                with pytest.raises(InvError):
                    lineage_service.verify_model_version(
                        session, tenant_id=catalogue["tenant_a"],
                        model_version_id=built["version"].model_version_id,
                        content_sha256="0" * 64, now=NOW,
                    )


def test_a_retention_pin_only_extends(app_sessionmaker, catalogue):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                built = _full_lineage(session, catalogue)
                version_id = built["version"].model_version_id
                lineage_service.pin_retention(
                    session, tenant_id=catalogue["tenant_a"],
                    model_version_id=version_id, until=LATER,
                )
                shortened = lineage_service.pin_retention(
                    session, tenant_id=catalogue["tenant_a"],
                    model_version_id=version_id, until=NOW + dt.timedelta(days=1),
                )
    assert shortened.retention_pinned_until == LATER


def test_the_database_refuses_a_release_without_verification(app_sessionmaker, catalogue):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                built = _full_lineage(session, catalogue)
                version_id = built["version"].model_version_id
        with pytest.raises((IntegrityError, DBAPIError, ProgrammingError)):
            with session.begin():
                with tenant_scope(session, catalogue["tenant_a"]):
                    session.execute(
                        text(
                            "UPDATE model_versions SET stage = 'released' "
                            "WHERE model_version_id = :m"
                        ),
                        {"m": version_id},
                    )


# --------------------------------------------------------------------------
# Deployment digest
# --------------------------------------------------------------------------


def _released(session, catalogue):
    built = _full_lineage(session, catalogue)
    version_id = built["version"].model_version_id
    lineage_service.verify_model_version(
        session, tenant_id=catalogue["tenant_a"], model_version_id=version_id,
        content_sha256=WEIGHTS_SHA, now=NOW,
    )
    lineage_service.pin_retention(
        session, tenant_id=catalogue["tenant_a"], model_version_id=version_id, until=LATER
    )
    lineage_service.release_model_version(
        session, tenant_id=catalogue["tenant_a"], model_version_id=version_id, now=NOW
    )
    return built


def test_a_deployment_pins_the_digest_that_shipped(app_sessionmaker, catalogue):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                built = _released(session, catalogue)
                deployment = lineage_service.record_deployment(
                    session, tenant_id=catalogue["tenant_a"],
                    model_version_id=built["version"].model_version_id,
                    environment="pilot", approval_id=built["approval_id"],
                    deployed_by_user_id=catalogue["user_id"], now=NOW,
                    image_id=built["image_id"],
                )
    # The digest comes from the model version, not from the caller.
    assert deployment.deployed_digest == WEIGHTS_SHA
    assert deployment.status == "active"


def test_an_approval_for_other_content_cannot_deploy(app_sessionmaker, catalogue):
    """The rule an approval exists for, applied to deployment."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                built = _released(session, catalogue)
                run = run_service.create_run(
                    session, tenant_id=catalogue["tenant_a"],
                    workload_id=catalogue["workload_id"],
                    workspace_id=catalogue["workspace_id"],
                    requested_by_user_id=catalogue["user_id"], now=NOW,
                )
                wrong_approval = new_id("approval")
                session.execute(
                    text(
                        "INSERT INTO approvals (approval_id, tenant_id, run_id, subject_sha256, "
                        "decision, risk_level, scope, decided_by_user_id, decided_at, expires_at) "
                        "VALUES (:a, :t, :r, :s, 'approved', 2, '{}', :u, :n, :e)"
                    ),
                    {"a": wrong_approval, "t": catalogue["tenant_a"], "r": run.run_id,
                     "s": "1" * 64, "u": catalogue["user_id"], "n": NOW,
                     "e": NOW + dt.timedelta(days=1)},
                )
                with pytest.raises(InvError) as caught:
                    lineage_service.record_deployment(
                        session, tenant_id=catalogue["tenant_a"],
                        model_version_id=built["version"].model_version_id,
                        environment="pilot", approval_id=wrong_approval,
                        deployed_by_user_id=catalogue["user_id"], now=NOW,
                    )
    assert caught.value.code == "AUTH-APPROVAL-DIGEST-MISMATCH"


def test_an_unreleased_version_cannot_be_deployed(app_sessionmaker, catalogue):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                built = _full_lineage(session, catalogue)
                with pytest.raises(InvError, match="released"):
                    lineage_service.record_deployment(
                        session, tenant_id=catalogue["tenant_a"],
                        model_version_id=built["version"].model_version_id,
                        environment="pilot", approval_id=built["approval_id"],
                        deployed_by_user_id=catalogue["user_id"], now=NOW,
                    )


def test_redeploying_supersedes_the_previous_active_one(app_sessionmaker, catalogue):
    """"What is live" must never be ambiguous."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                built = _released(session, catalogue)
                version_id = built["version"].model_version_id
                first = lineage_service.record_deployment(
                    session, tenant_id=catalogue["tenant_a"], model_version_id=version_id,
                    environment="pilot", approval_id=built["approval_id"],
                    deployed_by_user_id=catalogue["user_id"], now=NOW,
                )
                second = lineage_service.record_deployment(
                    session, tenant_id=catalogue["tenant_a"], model_version_id=version_id,
                    environment="pilot", approval_id=built["approval_id"],
                    deployed_by_user_id=catalogue["user_id"],
                    now=NOW + dt.timedelta(hours=1),
                )
                active = session.execute(
                    text(
                        "SELECT count(*) FROM deployments WHERE model_version_id = :m "
                        "AND environment = 'pilot' AND status = 'active'"
                    ),
                    {"m": version_id},
                ).scalar_one()
    assert active == 1
    assert first.status == "superseded"
    assert second.status == "active"


def test_the_database_refuses_two_active_deployments(app_sessionmaker, catalogue):
    """The partial unique index, checked by going around the service."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                built = _released(session, catalogue)
                version_id = built["version"].model_version_id
                lineage_service.record_deployment(
                    session, tenant_id=catalogue["tenant_a"], model_version_id=version_id,
                    environment="pilot", approval_id=built["approval_id"],
                    deployed_by_user_id=catalogue["user_id"], now=NOW,
                )
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, catalogue["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO deployments (deployment_id, tenant_id, model_version_id, "
                            "environment, status, deployed_digest, approval_id, "
                            "deployed_by_user_id, deployed_at, notes) "
                            "VALUES (:d, :t, :m, 'pilot', 'active', :g, :a, :u, now(), '{}')"
                        ),
                        {"d": new_id("deployment"), "t": catalogue["tenant_a"],
                         "m": version_id, "g": WEIGHTS_SHA, "a": built["approval_id"],
                         "u": catalogue["user_id"]},
                    )


def test_a_deployment_without_an_approval_is_refused(app_sessionmaker, catalogue):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                built = _released(session, catalogue)
                version_id = built["version"].model_version_id
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, catalogue["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO deployments (deployment_id, tenant_id, model_version_id, "
                            "environment, status, deployed_digest, deployed_by_user_id, "
                            "deployed_at, notes) "
                            "VALUES (:d, :t, :m, 'staging', 'active', :g, :u, now(), '{}')"
                        ),
                        {"d": new_id("deployment"), "t": catalogue["tenant_a"],
                         "m": version_id, "g": WEIGHTS_SHA, "u": catalogue["user_id"]},
                    )


# --------------------------------------------------------------------------
# Isolation
# --------------------------------------------------------------------------


def test_lineage_is_tenant_isolated(app_sessionmaker, catalogue):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_a"]):
                _full_lineage(session, catalogue)
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, catalogue["tenant_b"]):
                for table in ("model_versions", "model_lineage", "dataset_versions",
                              "container_images", "code_commits"):
                    assert (
                        session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
                    ), table
