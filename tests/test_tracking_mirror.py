"""MLflow mirror against a real PostgreSQL (S10-BE, design PR #168 v1.3).

Decision B in one sentence: the lineage tables are the truth, the mirror is a
copy, and nothing about the copy can change the truth. These tests hold the
three places where that could silently stop being so -- the enqueue in the
canonical transaction (one test per canonical path, with its rollback twin),
the append-only outcome rows with their exact status/code pairs and delivery
identity, and delivery that must produce one attempt per outcome however many
times the outbox redelivers.

The fixtures are the lineage ones: a mirror intent is only meaningful for a
canonical row that exists.
"""

from __future__ import annotations

import datetime as dt
import threading
import time

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

from saintvision.adapters.contract import Attestation, AttestationResult
from saintvision.adapters.tracking import MirrorRecord
from saintvision.adapters.tracking_reference import ReferenceSink
from saintvision.db.models import (
    Deployment,
    MlflowMirrorAttempt,
    MlflowMirrorDefect,
    MlflowMirrorIntent,
    ModelVersion,
    OutboxEvent,
)
from saintvision.db.session import tenant_scope
from saintvision.ids import new_id
from saintvision.runs.state import TerminationReason
from saintvision.services import evaluation as eval_service
from saintvision.services import lineage as lineage_service
from saintvision.services import runs as run_service
from saintvision.services import tracking as tracking_service
from saintvision.services.evidence import enqueue_event
from saintvision.tracking import config as tracking_config
from saintvision.tracking.canonical import CanonicalizationError
from saintvision.tracking.codes import MirrorStatus
from test_lineage import NOW, WEIGHTS_SHA, _full_lineage, catalogue  # noqa: F401  (fixture)

pytestmark = pytest.mark.postgres

GOOD_ENV = {
    "INV_MLFLOW_TRACKING_URI": "https://mlflow.lab.example/",
    "INV_MLFLOW_DESTINATION": "lab-mlflow",
    "INV_MLFLOW_EXPERIMENT_PREFIX": "inv",
}


@pytest.fixture
def configured(monkeypatch):
    """A configured sink, with the client "installed"."""
    for key, value in GOOD_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(tracking_config, "mlflow_client_present", lambda: True)
    return tracking_config.resolve()


@pytest.fixture
def absent(monkeypatch):
    for key in GOOD_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("INV_MLFLOW_TIMEOUT_SECONDS", raising=False)


def _register(session, catalogue, **kw):
    return _full_lineage(session, catalogue, **kw)["version"]


def _rows(session, model):
    return session.scalars(select(model)).all()


def _intents_by_kind(session):
    out: dict[str, list] = {}
    for intent in _rows(session, MlflowMirrorIntent):
        out.setdefault(intent.subject_kind, []).append(intent)
    return out


def _mirror_events(session):
    return session.scalars(
        select(OutboxEvent).where(OutboxEvent.event_type == tracking_service.MIRROR_EVENT_TYPE)
    ).all()


def _release(session, tenant, version):
    lineage_service.verify_model_version(
        session, tenant_id=tenant, model_version_id=version.model_version_id,
        content_sha256=WEIGHTS_SHA, now=NOW,
    )
    lineage_service.pin_retention(
        session, tenant_id=tenant, model_version_id=version.model_version_id,
        until=NOW + dt.timedelta(days=365),
    )
    return lineage_service.release_model_version(
        session, tenant_id=tenant, model_version_id=version.model_version_id, now=NOW
    )


# --------------------------------------------------------------------------
# Enqueue in the canonical transaction (§1, §2, F-R3) -- one test per path
# --------------------------------------------------------------------------


def test_register_model_version_enqueues_experiment_and_version_intents_with_events(
    app_sessionmaker, catalogue, configured
):
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                version = _register(session, catalogue)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        by_kind = _intents_by_kind(session)
        assert set(by_kind) == {"experiment", "model_version"}        # first intent brings the experiment (§1)
        experiment = by_kind["experiment"][0]
        assert experiment.project_id == catalogue["project_id"] and experiment.payload["tags"]["inv.project_id"] == catalogue["project_id"]
        intent = by_kind["model_version"][0]
        assert intent.model_version_id == version.model_version_id and intent.project_id == catalogue["project_id"]
        assert intent.payload["tags"]["inv.content_sha256"] == WEIGHTS_SHA
        assert intent.payload["tags"]["inv.stage"] == "draft"
        events = {e.event_id: e for e in _mirror_events(session)}
        assert set(events) == {experiment.outbox_event_id, intent.outbox_event_id}
        assert all(e.status == "pending" and e.aggregate_type == "mirror_intent" for e in events.values())


def test_release_enqueues_a_stage_transition_intent(app_sessionmaker, catalogue, configured):
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                version = _register(session, catalogue)
                _release(session, tenant, version)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        stages = sorted(i.payload["tags"]["inv.stage"] for i in _intents_by_kind(session)["model_version"])
        assert stages == ["draft", "released"]                        # two intents, one per stage
        released = next(i for i in _intents_by_kind(session)["model_version"] if i.payload["tags"]["inv.stage"] == "released")
        assert released.payload["params"]["verified_at_ms"] is not None
        assert len(_mirror_events(session)) == 3                       # experiment + draft + released


def test_deployment_enqueues_its_intent(app_sessionmaker, catalogue, configured):
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                built = _full_lineage(session, catalogue)
                _release(session, tenant, built["version"])
                deployment = lineage_service.record_deployment(
                    session, tenant_id=tenant, model_version_id=built["version"].model_version_id,
                    environment="lab", approval_id=built["approval_id"],
                    deployed_by_user_id=catalogue["user_id"], now=NOW,
                )
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        intent = _intents_by_kind(session)["deployment"][0]
        assert intent.deployment_id == deployment.deployment_id
        assert intent.payload["tags"]["inv.deployed_digest"] == WEIGHTS_SHA
        assert intent.payload["tags"]["inv.approval_id"] == built["approval_id"]
        assert intent.project_id == catalogue["project_id"]


def test_finished_eval_run_enqueues_suite_identity_and_category_scores(app_sessionmaker, catalogue, configured):
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                built = _full_lineage(session, catalogue)
                eval_run = session.get(eval_service.EvalRun, built["eval_run_id"])
                suite = session.get(eval_service.EvalSuite, eval_run.suite_id)
                case = session.scalars(select(eval_service.EvalCase)).first()
                eval_service.record_result(
                    session, tenant_id=tenant, eval_run_id=built["eval_run_id"], case_id=case.case_id,
                    outcome="passed", now=NOW, score=0.9,
                )
                eval_service.finish_eval_run(session, tenant_id=tenant, eval_run_id=built["eval_run_id"], now=NOW)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        intent = _intents_by_kind(session)["eval_run"][0]
        assert intent.eval_run_id == built["eval_run_id"] and intent.project_id is None   # an eval run has no project
        params = intent.payload["params"]
        assert (params["suite_name"], params["suite_version"], params["suite_definition_sha256"]) == (
            suite.name, suite.version, suite.definition_sha256
        )
        metrics = {m["key"]: m["value"] for m in intent.payload["metrics"]}
        assert {"passed_cases", "total_cases", "violations", "gate_passed"} <= set(metrics)
        assert metrics["category.coding_task.pass_rate"] == 1
        assert metrics["category.coding_task.mean_score"] == "0.9"


def test_completed_training_run_enqueues_its_intent(app_sessionmaker, catalogue, configured):
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                run = run_service.create_run(
                    session, tenant_id=tenant, workload_id=catalogue["workload_id"],
                    workspace_id=catalogue["workspace_id"],
                    requested_by_user_id=catalogue["user_id"], now=NOW,
                )
                run_id = run.run_id
                _drive_to_verifying(session, tenant, run_id)
                _complete(session, tenant, run_id)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        intent = _intents_by_kind(session)["training_run"][0]
        assert intent.run_id == run_id and intent.project_id == catalogue["project_id"]
        assert intent.payload["tags"]["inv.workload_spec_sha256"] == catalogue["spec_sha256"]
        assert intent.payload["tags"]["inv.evidence_id"].startswith("evd_")


def _drive_to_verifying(session, tenant, run_id):
    """Take a run through the states that precede ``complete_run`` (as test_execution does)."""
    for target in ("validated", "planned", "scheduled"):
        run_service.advance(session, tenant_id=tenant, run_id=run_id, target=target, now=NOW)
    run_service.start_attempt(session, tenant_id=tenant, run_id=run_id, now=NOW)
    run_service.advance(session, tenant_id=tenant, run_id=run_id, target="verifying", now=NOW)


def _complete(session, tenant, run_id):
    return run_service.complete_run(
        session, tenant_id=tenant, run_id=run_id, now=NOW, actor_type="system", actor_id="control-plane",
        action="run.complete", input_schema="RunInput@1", input_payload={"objective": "train"},
        output_ref=f"inv://artifacts/{run_id}/art_x",
    )


@pytest.mark.parametrize("path", ["register", "release", "deployment", "eval_run", "training_run"])
def test_a_rolled_back_canonical_change_leaves_neither_intent_nor_event(
    app_sessionmaker, catalogue, configured, path
):
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with pytest.raises(RuntimeError):
            with session.begin():
                with tenant_scope(session, tenant):
                    built = _full_lineage(session, catalogue)
                    if path == "release":
                        _release(session, tenant, built["version"])
                    elif path == "deployment":
                        _release(session, tenant, built["version"])
                        lineage_service.record_deployment(
                            session, tenant_id=tenant, model_version_id=built["version"].model_version_id,
                            environment="lab", approval_id=built["approval_id"],
                            deployed_by_user_id=catalogue["user_id"], now=NOW,
                        )
                    elif path == "eval_run":
                        eval_service.finish_eval_run(session, tenant_id=tenant, eval_run_id=built["eval_run_id"], now=NOW)
                    elif path == "training_run":
                        run = run_service.create_run(
                            session, tenant_id=tenant, workload_id=catalogue["workload_id"],
                            workspace_id=catalogue["workspace_id"],
                            requested_by_user_id=catalogue["user_id"], now=NOW,
                        )
                        _drive_to_verifying(session, tenant, run.run_id)
                        _complete(session, tenant, run.run_id)
                    assert _rows(session, MlflowMirrorIntent)          # visible inside the tx
                    raise RuntimeError("abort after the canonical change")
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        assert _rows(session, MlflowMirrorIntent) == []
        assert _rows(session, MlflowMirrorDefect) == []
        assert _rows(session, ModelVersion) == []
        assert _mirror_events(session) == []


def test_absent_configuration_records_nothing_and_the_canonical_path_is_unchanged(app_sessionmaker, catalogue, absent):
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                version = _register(session, catalogue)
                _release(session, tenant, version)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        assert session.get(ModelVersion, version.model_version_id).stage == "released"
        assert _rows(session, MlflowMirrorIntent) == [] and _rows(session, MlflowMirrorDefect) == []
        assert _mirror_events(session) == []


def test_invalid_configuration_records_nothing_either(app_sessionmaker, catalogue, monkeypatch):
    for key, value in GOOD_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(tracking_config, "mlflow_client_present", lambda: False)    # client-missing
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                version = _register(session, catalogue)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        assert session.get(ModelVersion, version.model_version_id) is not None
        assert _rows(session, MlflowMirrorIntent) == []


def test_canonicalization_failure_commits_the_change_with_a_defect_and_no_intent(
    app_sessionmaker, catalogue, configured, monkeypatch
):
    def refuse(payload):
        raise CanonicalizationError("nan-or-infinity", "injected")

    monkeypatch.setattr(tracking_service, "canonical_payload", refuse)
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                version = _register(session, catalogue)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        assert session.get(ModelVersion, version.model_version_id) is not None
        assert _rows(session, MlflowMirrorIntent) == []
        defects = _rows(session, MlflowMirrorDefect)
        assert len(defects) == 1
        assert (defects[0].error_code, defects[0].reason_class) == ("TRACK-0005", "nan-or-infinity")
        assert defects[0].model_version_id == version.model_version_id
        assert not hasattr(defects[0], "payload")                  # the payload itself is never stored


def test_a_blocked_defect_insert_fails_the_whole_canonical_transaction(
    app_sessionmaker, catalogue, configured, monkeypatch
):
    """Only a database failure rolls the change back -- and then it rolls all of it back."""

    def refuse(payload):
        raise CanonicalizationError("key-collision", "injected")

    real_new_id = tracking_service.new_id

    def oversized(kind):
        if kind == "mirror_defect":
            return real_new_id(kind) + "X"        # 31 chars: CHAR(30) refuses the row
        return real_new_id(kind)

    monkeypatch.setattr(tracking_service, "canonical_payload", refuse)
    monkeypatch.setattr(tracking_service, "new_id", oversized)
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with pytest.raises((DBAPIError, IntegrityError)):
            with session.begin():
                with tenant_scope(session, tenant):
                    _register(session, catalogue)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        assert _rows(session, ModelVersion) == []
        assert _rows(session, MlflowMirrorDefect) == []


def test_enqueue_is_idempotent_for_the_same_subject_and_payload(app_sessionmaker, catalogue, configured):
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                version = _register(session, catalogue)
                payload = {"tags": {"inv.model_version_id": version.model_version_id}, "params": {"n": 1.0}}
                first = tracking_service.enqueue_mirror(
                    session, tenant_id=tenant, subject_kind="model_version",
                    subject_id=version.model_version_id, project_id=catalogue["project_id"],
                    payload=payload, now=NOW,
                )
                again = tracking_service.enqueue_mirror(
                    session, tenant_id=tenant, subject_kind="model_version",
                    subject_id=version.model_version_id, project_id=catalogue["project_id"],
                    payload={"params": {"n": 1}, "tags": {"inv.model_version_id": version.model_version_id}},
                    now=NOW,
                )
    assert first.kind == "intent" and first.experiment_intent_id is None      # the experiment already existed
    assert again.kind == "existing" and again.intent_id == first.intent_id
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        # experiment + register's draft + the explicit one; the duplicate made none.
        assert len(_rows(session, MlflowMirrorIntent)) == 3


# --------------------------------------------------------------------------
# Constraints, append-only, RLS
# --------------------------------------------------------------------------


def _intent_kwargs(catalogue, version, **override):
    base = dict(
        tenant_id=catalogue["tenant_a"], intent_id=new_id("mirror_intent"),
        project_id=catalogue["project_id"], subject_kind="model_version",
        model_version_id=version.model_version_id, payload={}, payload_sha256="0" * 64,
        outbox_event_id=None, created_at=NOW,
    )
    base.update(override)
    return base


def _seed_event(session, tenant):
    return enqueue_event(
        session, tenant_id=tenant, event_type=tracking_service.MIRROR_EVENT_TYPE,
        aggregate_type="mirror_intent", aggregate_id=new_id("mirror_intent"), payload={}, now=NOW,
    )


@pytest.mark.parametrize(
    "override,constraint",
    [
        ({"run_id": "run_00000000000000000000000000"}, "exactly_one_subject"),           # two subjects
        ({"model_version_id": None}, "exactly_one_subject"),                              # none
        ({"subject_kind": "deployment"}, "subject_matches_kind"),                         # kind vs column
        ({"subject_kind": "experiment"}, "exactly_one_subject"),                          # experiment with a subject
        ({"subject_kind": "training_run", "model_version_id": None}, "exactly_one_subject"),
        ({"project_id": None}, "project_bound_unless_eval_run"),
        ({"payload_sha256": "X" * 64}, "payload_sha256_hex"),
        ({"subject_kind": "run"}, "subject_kind_allowed"),
    ],
)
def test_intent_check_constraints_refuse_malformed_rows(app_sessionmaker, catalogue, absent, override, constraint):
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with pytest.raises(IntegrityError) as exc:
            with session.begin():
                with tenant_scope(session, tenant):
                    version = _register(session, catalogue)
                    event_id = _seed_event(session, tenant)
                    session.add(MlflowMirrorIntent(**_intent_kwargs(catalogue, version, outbox_event_id=event_id, **override)))
                    session.flush()
        assert constraint in str(exc.value)


def _attempt_kwargs(intent, **override):
    base = dict(
        tenant_id=intent.tenant_id, attempt_id=new_id("mirror_attempt"), intent_id=intent.intent_id,
        attempt_no=1, outbox_event_id=intent.outbox_event_id, delivery_no=1, status="mirrored",
        error_code=None, tracking_uri_sha256="a" * 64, reference_id="ref-1",
        response_payload_sha256=intent.payload_sha256, worker_id="w", started_at=NOW, finished_at=NOW,
    )
    base.update(override)
    return base


def _one_intent(session, catalogue):
    """One intent row (the model_version one) with its event, for attempt tests."""
    _register(session, catalogue)
    return _intents_by_kind(session)["model_version"][0]


#: Each row violates exactly the named constraint(s) and nothing that fires
#: earlier: codes stay within varchar(16), and a row aimed at one CHECK keeps
#: every other column valid (Codex #172: independent fixtures per constraint).
ATTEMPT_ROWS = [
    ({"status": "unavailable"}, {"status_code_pair"}),                                      # failure without a code
    ({"error_code": "TRACK-0001"}, {"status_code_pair"}),                                   # mirrored with a code
    ({"status": "refused", "error_code": "TRACK-0001"}, {"status_code_pair"}),              # finding 2 counter-example
    ({"status": "unavailable", "error_code": "TRACK-0002"}, {"status_code_pair"}),
    ({"status": "mismatch", "error_code": "TRACK-0004"}, {"status_code_pair"}),
    ({"status": "refused", "error_code": "TRACK-0005"}, {"status_code_pair"}),
    ({"status": "refused", "error_code": "TRACK-MLFLOW-X"}, {"error_code_track", "status_code_pair"}),   # old shape, 14 chars
    ({"status": "refused", "error_code": "track-0002"}, {"error_code_track", "status_code_pair"}),
    ({"status": "refused", "error_code": "TRACK-002"}, {"error_code_track", "status_code_pair"}),
    ({"status": "invalid", "error_code": "TRACK-0005"}, {"status_allowed", "status_code_pair"}),          # no such status
    ({"status": "done"}, {"status_allowed", "status_code_pair"}),
    ({"attempt_no": 0}, {"attempt_no_positive"}),
    ({"delivery_no": 0}, {"delivery_no_positive"}),
    ({"reference_id": None}, {"mirrored_has_reference"}),
    ({"tracking_uri_sha256": "g" * 64}, {"tracking_uri_sha256_hex"}),
]


@pytest.mark.parametrize("override,constraints", ATTEMPT_ROWS)
def test_attempt_check_constraints_refuse_malformed_rows(app_sessionmaker, catalogue, configured, override, constraints):
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with pytest.raises(IntegrityError) as exc:
            with session.begin():
                with tenant_scope(session, tenant):
                    intent = _one_intent(session, catalogue)
                    session.add(MlflowMirrorAttempt(**_attempt_kwargs(intent, **override)))
                    session.flush()
        message = str(exc.value)
        assert any(name in message for name in constraints), (constraints, message)


@pytest.mark.parametrize("pair", [("mirrored", None), ("unavailable", "TRACK-0001"), ("refused", "TRACK-0002"), ("mismatch", "TRACK-0003")])
def test_every_right_pair_is_accepted_by_the_database(app_sessionmaker, catalogue, configured, pair):
    status, code = pair
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                intent = _one_intent(session, catalogue)
                session.add(MlflowMirrorAttempt(**_attempt_kwargs(
                    intent, status=status, error_code=code, reference_id="ref-1" if status == "mirrored" else None,
                )))
                session.flush()


def test_attempt_no_and_delivery_identity_are_unique(app_sessionmaker, catalogue, configured):
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                intent = _one_intent(session, catalogue)
                session.add(MlflowMirrorAttempt(**_attempt_kwargs(intent)))
                session.flush()
    for override in ({"delivery_no": 2}, {"attempt_no": 2}):
        with app_sessionmaker() as session:
            with pytest.raises(IntegrityError) as exc:
                with session.begin():
                    with tenant_scope(session, tenant):
                        intent = _intents_by_kind(session)["model_version"][0]
                        session.add(MlflowMirrorAttempt(**_attempt_kwargs(intent, **override)))
                        session.flush()
            assert "uq_mlflow_mirror_attempts" in str(exc.value)


def test_an_attempt_cannot_cite_an_event_that_is_not_its_intents_own(app_sessionmaker, catalogue, configured):
    """Codex #172 finding 3, at the database: the composite FK refuses a foreign event."""
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with pytest.raises(IntegrityError) as exc:
            with session.begin():
                with tenant_scope(session, tenant):
                    intent = _one_intent(session, catalogue)
                    other_event = _seed_event(session, tenant)                # a real event of this tenant, wrong intent
                    session.add(MlflowMirrorAttempt(**_attempt_kwargs(intent, outbox_event_id=other_event)))
                    session.flush()
        assert "fk_mlflow_mirror_attempts_intent_event" in str(exc.value)
    with app_sessionmaker() as session:
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, tenant):
                    intent = _one_intent(session, catalogue)
                    session.add(MlflowMirrorAttempt(**_attempt_kwargs(intent, outbox_event_id=new_id("outbox"))))   # nonexistent
                    session.flush()


@pytest.mark.parametrize("table", ["mlflow_mirror_intents", "mlflow_mirror_attempts", "mlflow_mirror_defects"])
@pytest.mark.parametrize("verb", ["UPDATE", "DELETE"])
def test_mirror_tables_are_append_only_for_the_application_role(app_sessionmaker, catalogue, configured, table, verb):
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                _register(session, catalogue)
    statement = f"UPDATE {table} SET created_at = now()" if table != "mlflow_mirror_attempts" else f"UPDATE {table} SET worker_id = 'x'"
    if verb == "DELETE":
        statement = f"DELETE FROM {table}"
    with app_sessionmaker() as session:
        with pytest.raises(ProgrammingError) as exc:
            with session.begin():
                with tenant_scope(session, tenant):
                    session.execute(text(statement))
        assert "permission denied" in str(exc.value)


def test_intents_are_invisible_without_a_tenant_scope_and_to_another_tenant(app_sessionmaker, catalogue, configured):
    tenant_a, tenant_b = catalogue["tenant_a"], catalogue["tenant_b"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant_a):
                _register(session, catalogue)
    with app_sessionmaker() as session, session.begin():
        assert session.execute(text("SELECT count(*) FROM mlflow_mirror_intents")).scalar_one() == 0
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant_b):
        assert _rows(session, MlflowMirrorIntent) == []
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant_a):
        assert len(_rows(session, MlflowMirrorIntent)) == 2            # experiment + model version


# --------------------------------------------------------------------------
# Delivery (§2 idempotency, §6) -- through the application role, SELECT+INSERT only
# --------------------------------------------------------------------------


def _intent_for(app_sessionmaker, catalogue):
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                intent = _one_intent(session, catalogue)
                return intent.intent_id, intent.outbox_event_id


def _deliver(app_sessionmaker, tenant, sink, settings, intent_id, event_id, *, delivery_no, now=NOW):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                attempt = tracking_service.deliver_intent(
                    session, sink, tenant_id=tenant, intent_id=intent_id, outbox_event_id=event_id,
                    delivery_no=delivery_no, settings=settings, worker_id="w1", now=now,
                )
                return attempt.attempt_id, attempt.attempt_no, attempt.status, attempt.error_code, attempt.reference_id


def test_duplicate_delivery_yields_one_attempt_and_no_extra_run(app_sessionmaker, catalogue, configured):
    tenant = catalogue["tenant_a"]
    intent_id, event_id = _intent_for(app_sessionmaker, catalogue)
    sink = ReferenceSink()
    first = _deliver(app_sessionmaker, tenant, sink, configured.settings, intent_id, event_id, delivery_no=1)
    second = _deliver(app_sessionmaker, tenant, sink, configured.settings, intent_id, event_id, delivery_no=2)
    assert first[2] == "mirrored" and first[3] is None
    assert second == first                                      # the terminal row is returned
    assert sink.calls == {"find": 1, "mirror": 1, "attest": 1}   # the sink was not asked again
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        attempts = _rows(session, MlflowMirrorAttempt)
        assert len(attempts) == 1 and attempts[0].tracking_uri_sha256 == configured.settings.tracking_uri_sha256
        intent = session.scalar(select(MlflowMirrorIntent).where(MlflowMirrorIntent.intent_id == intent_id))
        assert attempts[0].response_payload_sha256 == intent.payload_sha256
        assert attempts[0].outbox_event_id == intent.outbox_event_id


def test_a_delivery_with_a_foreign_event_id_is_refused_before_any_sink_call(app_sessionmaker, catalogue, configured):
    """Codex #172 finding 3, at the service: wrong event -> no sink call, no row."""
    tenant = catalogue["tenant_a"]
    intent_id, _event_id = _intent_for(app_sessionmaker, catalogue)
    sink = ReferenceSink()
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant):
                other_event = _seed_event(session, tenant)
    for wrong in (other_event, new_id("outbox")):
        with app_sessionmaker() as session:
            with pytest.raises(tracking_service.DeliveryIdentityError):
                with session.begin():
                    with tenant_scope(session, tenant):
                        tracking_service.deliver_intent(
                            session, sink, tenant_id=tenant, intent_id=intent_id, outbox_event_id=wrong,
                            delivery_no=1, settings=configured.settings, worker_id="w", now=NOW,
                        )
    assert sink.calls == {"find": 0, "mirror": 0, "attest": 0}
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        assert _rows(session, MlflowMirrorAttempt) == []


def test_another_tenants_intent_is_not_deliverable(app_sessionmaker, catalogue, configured):
    tenant_a, tenant_b = catalogue["tenant_a"], catalogue["tenant_b"]
    intent_id, event_id = _intent_for(app_sessionmaker, catalogue)
    sink = ReferenceSink()
    with app_sessionmaker() as session:
        with pytest.raises(LookupError):
            with session.begin():
                with tenant_scope(session, tenant_b):
                    tracking_service.deliver_intent(
                        session, sink, tenant_id=tenant_b, intent_id=intent_id, outbox_event_id=event_id,
                        delivery_no=1, settings=configured.settings, worker_id="w", now=NOW,
                    )
    assert sink.calls["find"] == 0
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant_a):
        assert _rows(session, MlflowMirrorAttempt) == []


def test_unavailable_then_redelivery_appends_attempt_two(app_sessionmaker, catalogue, configured):
    tenant = catalogue["tenant_a"]
    intent_id, event_id = _intent_for(app_sessionmaker, catalogue)
    sink = ReferenceSink()
    sink.fail_with(MirrorStatus.UNAVAILABLE)
    first = _deliver(app_sessionmaker, tenant, sink, configured.settings, intent_id, event_id, delivery_no=1)
    assert (first[1], first[2], first[3], first[4]) == (1, "unavailable", "TRACK-0001", None)
    second = _deliver(app_sessionmaker, tenant, sink, configured.settings, intent_id, event_id, delivery_no=2)
    assert (second[1], second[2], second[3]) == (2, "mirrored", None)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        assert [a.attempt_no for a in sorted(_rows(session, MlflowMirrorAttempt), key=lambda a: a.attempt_no)] == [1, 2]


def test_a_refusal_is_terminal_and_never_retried(app_sessionmaker, catalogue, configured):
    tenant = catalogue["tenant_a"]
    intent_id, event_id = _intent_for(app_sessionmaker, catalogue)
    sink = ReferenceSink()
    sink.fail_with(MirrorStatus.REFUSED)
    first = _deliver(app_sessionmaker, tenant, sink, configured.settings, intent_id, event_id, delivery_no=1)
    assert (first[2], first[3]) == ("refused", "TRACK-0002")
    second = _deliver(app_sessionmaker, tenant, sink, configured.settings, intent_id, event_id, delivery_no=2)
    assert second == first and sink.calls["mirror"] == 1


def test_a_remote_run_without_a_local_attempt_is_attested_not_recreated(app_sessionmaker, catalogue, configured):
    """send-success-before-local-record: the run exists remotely, the worker died before the row."""
    tenant = catalogue["tenant_a"]
    intent_id, event_id = _intent_for(app_sessionmaker, catalogue)
    sink = ReferenceSink()
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        intent = session.scalar(select(MlflowMirrorIntent).where(MlflowMirrorIntent.intent_id == intent_id))
        remote = sink.mirror(MirrorRecord(intent.intent_id, intent.subject_kind, "inv/x/p", dict(intent.payload), intent.payload_sha256))
    sink.calls = {"find": 0, "mirror": 0, "attest": 0}
    attempt = _deliver(app_sessionmaker, tenant, sink, configured.settings, intent_id, event_id, delivery_no=1)
    assert (attempt[2], attempt[4]) == ("mirrored", remote.reference_id)
    assert sink.calls == {"find": 1, "mirror": 0, "attest": 1}


def test_a_tampered_remote_record_is_a_mismatch_not_a_silent_overwrite(app_sessionmaker, catalogue, configured):
    tenant = catalogue["tenant_a"]
    intent_id, event_id = _intent_for(app_sessionmaker, catalogue)

    class Tampering(ReferenceSink):
        def mirror(self, record):
            result = super().mirror(record)
            self.tamper(result.reference_id)
            return result

    sink = Tampering()
    attempt = _deliver(app_sessionmaker, tenant, sink, configured.settings, intent_id, event_id, delivery_no=1)
    assert (attempt[2], attempt[3]) == ("mismatch", "TRACK-0003")
    again = _deliver(app_sessionmaker, tenant, sink, configured.settings, intent_id, event_id, delivery_no=2)
    assert again == attempt                                     # terminal: no retry, no second run


def test_an_unverifiable_attestation_is_unavailable_not_mirrored(app_sessionmaker, catalogue, configured):
    tenant = catalogue["tenant_a"]
    intent_id, event_id = _intent_for(app_sessionmaker, catalogue)

    class Blind(ReferenceSink):
        def attest(self, reference_id):
            return Attestation(result=AttestationResult.UNVERIFIABLE, detail="no tags API")

    attempt = _deliver(app_sessionmaker, tenant, Blind(), configured.settings, intent_id, event_id, delivery_no=1)
    assert (attempt[2], attempt[3]) == ("unavailable", "TRACK-0001")


def test_competing_consumers_serialise_on_the_intent(app_sessionmaker, catalogue, configured):
    """Two workers deliver the same event at once: one attempt row, one remote run.

    Serialisation is the transaction-scoped advisory lock keyed by the intent
    (the intents table is append-only, so ``FOR UPDATE`` is not available to
    the application role and would not be wanted).
    """
    tenant = catalogue["tenant_a"]
    intent_id, event_id = _intent_for(app_sessionmaker, catalogue)
    sink = ReferenceSink()
    holder_locked = threading.Event()
    release = threading.Event()
    results: dict[str, tuple] = {}
    errors: dict[str, BaseException] = {}

    def holder():
        try:
            with app_sessionmaker() as session:
                with session.begin():
                    with tenant_scope(session, tenant):
                        attempt = tracking_service.deliver_intent(
                            session, sink, tenant_id=tenant, intent_id=intent_id, outbox_event_id=event_id,
                            delivery_no=1, settings=configured.settings, worker_id="w1", now=NOW,
                        )
                        results["holder"] = (attempt.attempt_id, attempt.attempt_no, attempt.status)
                        holder_locked.set()
                        release.wait(timeout=10)      # keep the lock while the contender queues
        except BaseException as exc:  # noqa: BLE001
            errors["holder"] = exc
            holder_locked.set()

    def contender():
        holder_locked.wait(timeout=10)
        try:
            with app_sessionmaker() as session:
                with session.begin():
                    with tenant_scope(session, tenant):
                        attempt = tracking_service.deliver_intent(
                            session, sink, tenant_id=tenant, intent_id=intent_id, outbox_event_id=event_id,
                            delivery_no=2, settings=configured.settings, worker_id="w2", now=NOW,
                        )
                        results["contender"] = (attempt.attempt_id, attempt.attempt_no, attempt.status)
        except BaseException as exc:  # noqa: BLE001
            errors["contender"] = exc

    threads = [threading.Thread(target=holder), threading.Thread(target=contender)]
    for thread in threads:
        thread.start()
    holder_locked.wait(timeout=10)
    time.sleep(0.5)                 # the contender is now blocked on the advisory lock
    assert "contender" not in results and "contender" not in errors
    release.set()
    for thread in threads:
        thread.join(timeout=20)
    assert not errors, errors
    assert results["contender"] == results["holder"]
    assert sink.calls["mirror"] == 1
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        assert len(_rows(session, MlflowMirrorAttempt)) == 1


def test_delivery_never_touches_the_canonical_rows(app_sessionmaker, catalogue, configured):
    tenant = catalogue["tenant_a"]
    intent_id, event_id = _intent_for(app_sessionmaker, catalogue)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        before = [(v.model_version_id, v.stage, v.content_sha256) for v in _rows(session, ModelVersion)]
        assert _rows(session, Deployment) == []
    sink = ReferenceSink()
    sink.fail_with(MirrorStatus.REFUSED)
    _deliver(app_sessionmaker, tenant, sink, configured.settings, intent_id, event_id, delivery_no=1)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        assert [(v.model_version_id, v.stage, v.content_sha256) for v in _rows(session, ModelVersion)] == before


def test_delivering_an_unknown_intent_fails_closed(app_sessionmaker, catalogue, configured):
    tenant = catalogue["tenant_a"]
    with app_sessionmaker() as session:
        with pytest.raises(LookupError):
            with session.begin():
                with tenant_scope(session, tenant):
                    tracking_service.deliver_intent(
                        session, ReferenceSink(), tenant_id=tenant, intent_id=new_id("mirror_intent"),
                        outbox_event_id=new_id("outbox"), delivery_no=1, settings=configured.settings,
                        worker_id="w", now=NOW,
                    )
