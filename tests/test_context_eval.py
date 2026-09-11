"""S09 context, run record and evaluation against a real PostgreSQL.

The claims tested here are the ones ADR-009, ADR-010 and AC-09 rest on:
a bundle reproduces what the model saw, a sealed record cannot be rewritten, a
pinned digest detects a later overwrite, and a forbidden-behaviour violation
cannot be averaged away.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.runs.state import TerminationReason
from saintvision.services import context as context_service
from saintvision.services import evaluation as eval_service
from saintvision.services import records as record_service
from saintvision.services import runs as run_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 9, 7, 0, 0, tzinfo=UTC)


@pytest.fixture
def project(owner_engine, two_tenants):
    tenant_a, tenant_b = two_tenants
    user_id = new_id("user")
    project_id = new_id("project")
    workspace_id = new_id("workspace")
    workload_id = new_id("workload")
    digest = run_service.workload_digest({"objective": "x"})
    with owner_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (user_id, tenant_id, external_subject, display_name, "
                "status, created_at, updated_at, version) "
                "VALUES (:u, :t, 'sub', 'U', 'active', now(), now(), 1)"
            ),
            {"u": user_id, "t": tenant_a},
        )
        connection.execute(
            text(
                "INSERT INTO projects (project_id, tenant_id, code, display_name, status, "
                "created_at, version) VALUES (:p, :t, 'a', 'A', 'active', now(), 1)"
            ),
            {"p": project_id, "t": tenant_a},
        )
        connection.execute(
            text(
                "INSERT INTO workspaces (workspace_id, tenant_id, project_id, name, status, "
                "created_by_user_id, created_at, version) "
                "VALUES (:w, :t, :p, 'ws', 'ready', :u, now(), 1)"
            ),
            {"w": workspace_id, "t": tenant_a, "p": project_id, "u": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO workloads (workload_id, tenant_id, project_id, kind, objective, "
                "spec, spec_sha256, contract_version, created_by_user_id, created_at, version) "
                "VALUES (:wl, :t, :p, 'batch', 'x', '{}', :d, '1.0.0', :u, now(), 1)"
            ),
            {"wl": workload_id, "t": tenant_a, "p": project_id, "d": digest, "u": user_id},
        )
    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "workload_id": workload_id,
    }


def _make_run(session, project):
    return run_service.create_run(
        session,
        tenant_id=project["tenant_a"],
        workload_id=project["workload_id"],
        workspace_id=project["workspace_id"],
        requested_by_user_id=project["user_id"],
        now=NOW,
    )


def _items(*texts):
    return [
        context_service.ContextItem(
            item_id=f"doc-{i}", item_version=1, kind="document", content=t, redacted=True
        )
        for i, t in enumerate(texts)
    ]


# --------------------------------------------------------------------------
# Context deduplication and reproducibility
# --------------------------------------------------------------------------


def test_the_same_content_is_stored_once_per_tenant(app_sessionmaker, project):
    """P7's whole point: repeated references must not multiply storage."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run_a = _make_run(session, project)
                run_b = _make_run(session, project)
                context_service.build_bundle(
                    session, tenant_id=project["tenant_a"], run_id=run_a.run_id,
                    items=_items("shared handbook", "unique to a"), now=NOW,
                )
                context_service.build_bundle(
                    session, tenant_id=project["tenant_a"], run_id=run_b.run_id,
                    items=_items("shared handbook", "unique to b"), now=NOW,
                )
                snapshots = session.execute(
                    text("SELECT count(*) FROM context_snapshots")
                ).scalar_one()
                references = session.execute(
                    text("SELECT count(*) FROM context_bundle_items")
                ).scalar_one()
    assert references == 4
    assert snapshots == 3  # the handbook is stored once


def test_deduplication_does_not_cross_tenants(app_sessionmaker, project, owner_engine):
    """A shared row would leak the existence of another tenant's document and
    tie the two tenants' retention together."""
    shared = "the very same text"
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                context_service.store_snapshot(
                    session, tenant_id=project["tenant_a"], content=shared, now=NOW
                )
        with session.begin():
            with tenant_scope(session, project["tenant_b"]):
                _, was_new = context_service.store_snapshot(
                    session, tenant_id=project["tenant_b"], content=shared, now=NOW
                )
    # Tenant B stored its own copy; it did not observe A's.
    assert was_new is True
    with owner_engine.connect() as connection:
        rows = connection.execute(
            text("SELECT count(*) FROM context_snapshots WHERE content = :c"),
            {"c": shared},
        ).scalar_one()
    assert rows == 2


def test_storing_the_same_content_twice_is_idempotent(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                first_hash, first_new = context_service.store_snapshot(
                    session, tenant_id=project["tenant_a"], content="abc", now=NOW
                )
                second_hash, second_new = context_service.store_snapshot(
                    session, tenant_id=project["tenant_a"], content="abc", now=NOW
                )
    assert first_hash == second_hash
    assert first_new is True and second_new is False


def test_a_bundle_reproduces_its_items_in_order(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _make_run(session, project)
                bundle = context_service.build_bundle(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id,
                    items=_items("first", "second", "third"), now=NOW,
                )
                read = context_service.read_bundle(
                    session, tenant_id=project["tenant_a"], bundle_id=bundle.bundle_id
                )
                assert [content for _, content in read] == ["first", "second", "third"]
                assert [item.ordinal for item, _ in read] == [0, 1, 2]
                assert context_service.verify_bundle(
                    session, tenant_id=project["tenant_a"], bundle_id=bundle.bundle_id
                )


def test_build_bundle_refuses_a_secret_and_stores_nothing(app_sessionmaker, project):
    """The refusal has to be wired into build_bundle, not merely available.

    Checked through the public function and against the database: a rejected
    bundle must leave no snapshot behind, because a snapshot is keyed by content
    hash and would outlive the bundle that was refused.
    """
    from saintvision.db.models import ContextSnapshot

    token = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz012345"
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _make_run(session, project)
                before = session.scalar(
                    select(func.count()).select_from(ContextSnapshot)
                )
                with pytest.raises(InvError, match="does not make it so"):
                    context_service.build_bundle(
                        session,
                        tenant_id=project["tenant_a"],
                        run_id=run.run_id,
                        items=[
                            context_service.ContextItem(
                                item_id="itm_leak",
                                item_version=1,
                                kind="document",
                                content=token,
                                redacted=True,
                            )
                        ],
                        now=NOW,
                    )
                after = session.scalar(
                    select(func.count()).select_from(ContextSnapshot)
                )
                assert after == before


def test_bundle_hash_depends_on_order(app_sessionmaker, project):
    """Two bundles with the same items in a different order are different."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run_a = _make_run(session, project)
                run_b = _make_run(session, project)
                forwards = context_service.build_bundle(
                    session, tenant_id=project["tenant_a"], run_id=run_a.run_id,
                    items=_items("alpha", "beta"), now=NOW,
                )
                backwards = context_service.build_bundle(
                    session, tenant_id=project["tenant_a"], run_id=run_b.run_id,
                    items=_items("beta", "alpha"), now=NOW,
                )
    assert forwards.bundle_hash != backwards.bundle_hash


def test_the_item_version_survives_the_source_changing(app_sessionmaker, project):
    """The reason a bundle stores version and hash, not just the item id."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _make_run(session, project)
                bundle = context_service.build_bundle(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id,
                    items=[
                        context_service.ContextItem(
                            item_id="handbook", item_version=3, kind="document",
                            content="as it was at v3", redacted=True,
                        )
                    ],
                    now=NOW,
                )
                # The source moves on. The bundle must not.
                items = context_service.read_bundle(
                    session, tenant_id=project["tenant_a"], bundle_id=bundle.bundle_id
                )
    item, content = items[0]
    assert item.item_version == 3
    assert content == "as it was at v3"


def test_an_oversized_item_is_refused_not_truncated(app_sessionmaker, project):
    from saintvision.db.models import SNAPSHOT_SOFT_LIMIT_BYTES

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                with pytest.raises(InvError) as caught:
                    context_service.store_snapshot(
                        session,
                        tenant_id=project["tenant_a"],
                        content="x" * (SNAPSHOT_SOFT_LIMIT_BYTES + 1),
                        now=NOW,
                    )
                assert caught.value.code == "CTX-ITEM-TOO-LARGE"


def test_orphan_snapshots_are_collected_and_referenced_ones_are_not(
    owner_engine, app_sessionmaker, project
):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _make_run(session, project)
                context_service.build_bundle(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id,
                    items=_items("kept"), now=NOW,
                )
                context_service.store_snapshot(
                    session, tenant_id=project["tenant_a"], content="orphaned", now=NOW
                )

    # The collector runs as the owner: the application role has no DELETE here.
    from sqlalchemy.orm import sessionmaker as owner_sessionmaker

    factory = owner_sessionmaker(bind=owner_engine)
    with factory() as session:
        with session.begin():
            removed = context_service.collect_orphan_snapshots(
                session, tenant_id=project["tenant_a"]
            )
    assert removed == 1

    with owner_engine.connect() as connection:
        remaining = connection.execute(
            text("SELECT content FROM context_snapshots")
        ).scalars().all()
    assert remaining == ["kept"]


def test_the_application_role_cannot_delete_snapshots(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                context_service.store_snapshot(
                    session, tenant_id=project["tenant_a"], content="permanent", now=NOW
                )
    with app_sessionmaker() as session:
        with pytest.raises((ProgrammingError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, project["tenant_a"]):
                    session.execute(text("DELETE FROM context_snapshots"))


def test_deduplication_ratio_is_reported(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run_a = _make_run(session, project)
                run_b = _make_run(session, project)
                for run in (run_a, run_b):
                    context_service.build_bundle(
                        session, tenant_id=project["tenant_a"], run_id=run.run_id,
                        items=_items("same", "same-too"), now=NOW,
                    )
                report = context_service.deduplication_ratio(
                    session, tenant_id=project["tenant_a"]
                )
    assert report["references"] == 4
    assert report["distinctSnapshots"] == 2
    assert report["reuseFactor"] == 2.0


# --------------------------------------------------------------------------
# RunRecord
# --------------------------------------------------------------------------


def _finished_run(session, project):
    run = _make_run(session, project)
    run_service.fail_run(
        session,
        tenant_id=project["tenant_a"],
        run_id=run.run_id,
        reason=TerminationReason.UNRECOVERABLE_ERROR,
        now=NOW,
    )
    return run


def test_a_record_cannot_be_sealed_for_an_unfinished_run(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _make_run(session, project)
                with pytest.raises(InvError):
                    record_service.seal_run_record(
                        session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW
                    )


def test_sealing_twice_returns_the_same_record(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _finished_run(session, project)
                first = record_service.seal_run_record(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW
                )
                second = record_service.seal_run_record(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW
                )
    assert first.record_id == second.record_id


def test_a_sealed_record_cannot_be_rewritten(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _finished_run(session, project)
                record_service.seal_run_record(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW
                )
    for statement in (
        "UPDATE run_records SET final_state = 'succeeded'",
        "DELETE FROM run_records",
    ):
        with app_sessionmaker() as session:
            with pytest.raises((ProgrammingError, DBAPIError)):
                with session.begin():
                    with tenant_scope(session, project["tenant_a"]):
                        session.execute(text(statement))


def test_only_one_record_per_run(owner_engine, app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _finished_run(session, project)
                record_service.seal_run_record(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW
                )
                run_id = run.run_id
    with app_sessionmaker() as session:
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, project["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO run_records (record_id, tenant_id, run_id, final_state, "
                            "termination_reason, workload_spec_sha256, attempt_count, sealed_at) "
                            "VALUES (:i, :t, :r, 'failed', 'timeout', :d, 0, now())"
                        ),
                        {
                            "i": new_id("run_record"),
                            "t": project["tenant_a"],
                            "r": run_id,
                            "d": "a" * 64,
                        },
                    )


# --------------------------------------------------------------------------
# Artifact pinning (S09-ST)
# --------------------------------------------------------------------------


def _verified_artifact(session, project, run_id, name):
    artifact_id = new_id("artifact")
    session.execute(
        text(
            "INSERT INTO artifacts (artifact_id, tenant_id, run_id, name, media_type, "
            "status, byte_size, checksum_sha256, verified_at, object_version, created_at, version) "
            "VALUES (:a, :t, :r, :n, 'text/plain', 'active', 12, :c, now(), 'v1', now(), 1)"
        ),
        {
            "a": artifact_id,
            "t": project["tenant_a"],
            "r": run_id,
            "n": name,
            "c": "b" * 64,
        },
    )
    return artifact_id


def test_diff_test_and_trace_artifacts_are_pinned_by_role(app_sessionmaker, project):
    """"diff·테스트·trace Artifact 연결" as a query, not a naming convention."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _finished_run(session, project)
                pins = []
                for name, role in (
                    ("changes.patch", "diff"),
                    ("junit.xml", "test_report"),
                    ("otel.json", "trace"),
                ):
                    artifact_id = _verified_artifact(session, project, run.run_id, name)
                    pins.append(record_service.ArtifactPin(artifact_id, role))
                record = record_service.seal_run_record(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id,
                    now=NOW, artifacts=pins,
                )
                traces = record_service.list_pinned_artifacts(
                    session, tenant_id=project["tenant_a"],
                    record_id=record.record_id, role="trace",
                )
                everything = record_service.list_pinned_artifacts(
                    session, tenant_id=project["tenant_a"], record_id=record.record_id
                )
    assert len(everything) == 3
    assert len(traces) == 1
    assert traces[0].role == "trace"
    assert traces[0].uri.startswith("inv://artifacts/")


def test_an_unverified_artifact_cannot_be_pinned(app_sessionmaker, project):
    """An unverified digest in a permanent record is worse than no record."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _finished_run(session, project)
                artifact_id = new_id("artifact")
                session.execute(
                    text(
                        "INSERT INTO artifacts (artifact_id, tenant_id, run_id, name, "
                        "media_type, status, byte_size, created_at, version) "
                        "VALUES (:a, :t, :r, 'staged', 'text/plain', 'staging', 0, now(), 1)"
                    ),
                    {"a": artifact_id, "t": project["tenant_a"], "r": run.run_id},
                )
                with pytest.raises(InvError):
                    record_service.seal_run_record(
                        session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW,
                        artifacts=[record_service.ArtifactPin(artifact_id, "diff")],
                    )


def test_a_later_overwrite_is_detected_by_the_pin(app_sessionmaker, project):
    """ADR-010: the record says what was true then, and says so verifiably."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                run = _finished_run(session, project)
                artifact_id = _verified_artifact(session, project, run.run_id, "out.bin")
                record = record_service.seal_run_record(
                    session, tenant_id=project["tenant_a"], run_id=run.run_id, now=NOW,
                    artifacts=[record_service.ArtifactPin(artifact_id, "other")],
                )
                assert record_service.verify_pin(
                    session, tenant_id=project["tenant_a"],
                    record_id=record.record_id, artifact_id=artifact_id,
                )
                session.execute(
                    text(
                        "UPDATE artifacts SET checksum_sha256 = :c WHERE artifact_id = :a"
                    ),
                    {"c": "c" * 64, "a": artifact_id},
                )
                assert not record_service.verify_pin(
                    session, tenant_id=project["tenant_a"],
                    record_id=record.record_id, artifact_id=artifact_id,
                )


# --------------------------------------------------------------------------
# Evaluation (AC-09)
# --------------------------------------------------------------------------


def _suite(session, project, now=NOW):
    return eval_service.create_suite(
        session,
        tenant_id=project["tenant_a"],
        name="golden",
        version="1.0.0",
        now=now,
        cases=[
            eval_service.CaseDefinition("json-01", "structured_output", {"n": 1}),
            eval_service.CaseDefinition("json-02", "structured_output", {"n": 2}),
            eval_service.CaseDefinition("code-01", "coding_task", {"n": 3}, weight=2),
            eval_service.CaseDefinition(
                "leak-01", "policy_compliance", {"n": 4}, forbidden_behaviour=True
            ),
        ],
    )


def _cases(session, project, suite_id):
    rows = session.execute(
        text("SELECT key, case_id FROM eval_cases WHERE suite_id = :s"),
        {"s": suite_id},
    ).all()
    return {key: case_id for key, case_id in rows}


def test_a_suite_version_is_unique_and_hashed(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                suite = _suite(session, project)
                assert len(suite.definition_sha256) == 64
                assert suite.case_count == 4
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, project["tenant_a"]):
                    _suite(session, project)


def test_a_forbidden_case_cannot_carry_a_weight(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                with pytest.raises(InvError):
                    eval_service.create_suite(
                        session, tenant_id=project["tenant_a"], name="bad",
                        version="1.0.0", now=NOW,
                        cases=[
                            eval_service.CaseDefinition(
                                "x", "policy_compliance", {},
                                forbidden_behaviour=True, weight=5,
                            )
                        ],
                    )


def test_a_violation_fails_the_gate_however_good_the_score(app_sessionmaker, project):
    """The rule AC-09 turns on: a leak is not compensated by scoring well."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                suite = _suite(session, project)
                cases = _cases(session, project, suite.suite_id)
                run = eval_service.start_eval_run(
                    session, tenant_id=project["tenant_a"],
                    suite_id=suite.suite_id, now=NOW,
                    component_versions={"model": "test-model", "prompt": "1.2.0"},
                )
                for key in ("json-01", "json-02", "code-01"):
                    eval_service.record_result(
                        session, tenant_id=project["tenant_a"],
                        eval_run_id=run.eval_run_id, case_id=cases[key],
                        outcome="passed", score=1.0, now=NOW,
                    )
                eval_service.record_result(
                    session, tenant_id=project["tenant_a"],
                    eval_run_id=run.eval_run_id, case_id=cases["leak-01"],
                    outcome="passed",  # the caller says passed...
                    violated=True,      # ...but a violation was observed
                    now=NOW,
                    observed={"note": "secret appeared in output"},
                )
                finished = eval_service.finish_eval_run(
                    session, tenant_id=project["tenant_a"],
                    eval_run_id=run.eval_run_id, now=NOW,
                )
                report = eval_service.score_report(
                    session, tenant_id=project["tenant_a"], eval_run_id=run.eval_run_id
                )

    assert finished.violations == 1
    assert finished.passed_gate is False
    assert finished.passed_cases == 3
    assert report["passedGate"] is False
    assert report["passRate"] == 0.75
    assert [v["caseKey"] for v in report["violations"]] == ["leak-01"]


def test_the_database_refuses_a_gate_pass_with_violations(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                suite = _suite(session, project)
                run = eval_service.start_eval_run(
                    session, tenant_id=project["tenant_a"],
                    suite_id=suite.suite_id, now=NOW,
                )
                eval_run_id = run.eval_run_id
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, project["tenant_a"]):
                    session.execute(
                        text(
                            "UPDATE eval_runs SET violations = 1, passed_gate = true "
                            "WHERE eval_run_id = :e"
                        ),
                        {"e": eval_run_id},
                    )


def test_per_category_scores_are_reported_separately(app_sessionmaker, project):
    """An aggregate that hides a weak category is the number people quote."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                suite = _suite(session, project)
                cases = _cases(session, project, suite.suite_id)
                run = eval_service.start_eval_run(
                    session, tenant_id=project["tenant_a"],
                    suite_id=suite.suite_id, now=NOW,
                )
                eval_service.record_result(
                    session, tenant_id=project["tenant_a"], eval_run_id=run.eval_run_id,
                    case_id=cases["json-01"], outcome="passed", score=1.0, now=NOW,
                )
                eval_service.record_result(
                    session, tenant_id=project["tenant_a"], eval_run_id=run.eval_run_id,
                    case_id=cases["json-02"], outcome="passed", score=1.0, now=NOW,
                )
                eval_service.record_result(
                    session, tenant_id=project["tenant_a"], eval_run_id=run.eval_run_id,
                    case_id=cases["code-01"], outcome="failed", score=0.0, now=NOW,
                )
                eval_service.record_result(
                    session, tenant_id=project["tenant_a"], eval_run_id=run.eval_run_id,
                    case_id=cases["leak-01"], outcome="passed", now=NOW,
                )
                report = eval_service.score_report(
                    session, tenant_id=project["tenant_a"], eval_run_id=run.eval_run_id
                )

    assert report["categories"]["structured_output"]["passRate"] == 1.0
    assert report["categories"]["coding_task"]["passRate"] == 0.0
    # The aggregate alone would read as 75% and hide that coding is at zero.
    assert report["passRate"] == 0.75


def test_a_scored_forbidden_case_is_refused(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                suite = _suite(session, project)
                cases = _cases(session, project, suite.suite_id)
                run = eval_service.start_eval_run(
                    session, tenant_id=project["tenant_a"],
                    suite_id=suite.suite_id, now=NOW,
                )
                with pytest.raises(InvError):
                    eval_service.record_result(
                        session, tenant_id=project["tenant_a"],
                        eval_run_id=run.eval_run_id, case_id=cases["leak-01"],
                        outcome="passed", score=0.9, now=NOW,
                    )


def test_a_violation_on_a_scored_case_is_refused(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                suite = _suite(session, project)
                cases = _cases(session, project, suite.suite_id)
                run = eval_service.start_eval_run(
                    session, tenant_id=project["tenant_a"],
                    suite_id=suite.suite_id, now=NOW,
                )
                with pytest.raises(InvError):
                    eval_service.record_result(
                        session, tenant_id=project["tenant_a"],
                        eval_run_id=run.eval_run_id, case_id=cases["json-01"],
                        outcome="failed", violated=True, now=NOW,
                    )


def test_an_incomplete_suite_does_not_pass_the_gate(app_sessionmaker, project):
    """A partial run with no failures yet is not a pass."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                suite = _suite(session, project)
                cases = _cases(session, project, suite.suite_id)
                run = eval_service.start_eval_run(
                    session, tenant_id=project["tenant_a"],
                    suite_id=suite.suite_id, now=NOW,
                )
                eval_service.record_result(
                    session, tenant_id=project["tenant_a"], eval_run_id=run.eval_run_id,
                    case_id=cases["json-01"], outcome="passed", score=1.0, now=NOW,
                )
                finished = eval_service.finish_eval_run(
                    session, tenant_id=project["tenant_a"],
                    eval_run_id=run.eval_run_id, now=NOW,
                )
    assert finished.status == "aborted"
    assert finished.passed_gate is False


def test_evaluation_is_tenant_isolated(app_sessionmaker, project):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_a"]):
                _suite(session, project)
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, project["tenant_b"]):
                assert (
                    session.execute(text("SELECT count(*) FROM eval_suites")).scalar_one()
                    == 0
                )
                assert (
                    session.execute(text("SELECT count(*) FROM eval_cases")).scalar_one()
                    == 0
                )
