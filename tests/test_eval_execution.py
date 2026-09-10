"""Running an evaluation suite, and the ways a gate stops meaning anything.

Most of these use fake adapters rather than the reference one, because what is
being tested is how the executor treats an adapter that misbehaves — and a
correct adapter cannot demonstrate that.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import text

from saintvision.adapters.contract import (
    Attestation,
    AttestationResult,
    AuthResult,
    CancelOutcome,
    Capability,
    CollectResult,
    InstallReport,
    ProbeResult,
    RunHandle,
    Usage,
)
from saintvision.adapters.reference import ReferenceAdapter
from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.services import eval_execution
from saintvision.services import evaluation as evaluation_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 10, 10, 0, 0, tzinfo=UTC)


# --------------------------------------------------------------------------
# Adapters that behave badly in one specific way each
# --------------------------------------------------------------------------


class _Base:
    """Everything a ProviderAdapter needs, so subclasses state one difference."""

    name = "fake"
    contract_version = "1.0.0"
    capabilities = frozenset({Capability.MODEL_PINNING})

    def probe(self) -> ProbeResult:
        return ProbeResult(reachable=True)

    def install(self) -> InstallReport:
        return InstallReport(ready=True)

    def authenticate(self, credential_ref: str) -> AuthResult:
        return AuthResult(authenticated=True)

    def run(self, request):
        return RunHandle(handle_id=new_id("run"), provider=self.name, model_id="m-1")

    def cancel(self, handle) -> CancelOutcome:
        return CancelOutcome.NOT_SUPPORTED

    def collect(self, handle) -> CollectResult:
        return CollectResult(
            completed=True, content="the answer is 42", model_id="m-1",
            usage=Usage(input_tokens=1, output_tokens=1), stop_reason="end_turn",
        )

    def redact(self, content):
        return content, False

    def attest(self, handle) -> Attestation:
        return Attestation(result=AttestationResult.UNVERIFIABLE)


class _RunRaises(_Base):
    def run(self, request):
        raise ConnectionError("the provider refused the connection")


class _CollectRaises(_Base):
    def collect(self, handle):
        raise TimeoutError("no response")


class _CancelUnknown(_CollectRaises):
    def cancel(self, handle):
        raise RuntimeError("cannot reach the provider to ask")


class _LeaksASecret(_Base):
    """Claims it redacted, and did not."""

    def collect(self, handle):
        return CollectResult(
            completed=True,
            content="here you go: sk-ABCDEFGHIJKLMNOPQRSTUVWX",
            model_id="m-1",
            redacted=True,
        )

    def redact(self, content):
        from saintvision.adapters.reference import redact_text

        return redact_text(content)


class _NoModelPinning(_Base):
    capabilities = frozenset({Capability.USAGE_REPORTING})


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def suite(app_sessionmaker, two_tenants):
    """A suite with one scored case and one forbidden-behaviour case."""
    tenant_a, _ = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant_a):
                created = evaluation_service.create_suite(
                    session,
                    tenant_id=tenant_a,
                    name="gate",
                    version="1",
                    cases=[
                        evaluation_service.CaseDefinition(
                            key="a-answers",
                            category="structured_output",
                            definition={"input": "q", "mustContain": ["42"]},
                        ),
                        evaluation_service.CaseDefinition(
                            key="b-no-secrets",
                            category="policy_compliance",
                            forbidden_behaviour=True,
                            definition={
                                "input": "q",
                                "forbiddenPatterns": [r"sk-[A-Za-z0-9]{16,}"],
                            },
                        ),
                    ],
                    now=NOW,
                )
                suite_id = created.suite_id
    return {"tenant_a": tenant_a, "suite_id": suite_id}


def _run(session, suite, adapter, **kwargs):
    return eval_execution.run_suite(
        session,
        tenant_id=suite["tenant_a"],
        suite_id=suite["suite_id"],
        adapter=adapter,
        now=NOW,
        **kwargs,
    )


# --------------------------------------------------------------------------
# The happy path, so the failures below mean something
# --------------------------------------------------------------------------


def test_a_correct_adapter_passes_the_gate(app_sessionmaker, suite):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, suite["tenant_a"]):
                run = _run(session, suite, _Base())
                report = evaluation_service.score_report(
                    session, tenant_id=suite["tenant_a"], eval_run_id=run.eval_run_id
                )
    assert run.status == "completed"
    assert run.passed_gate
    assert run.violations == 0
    assert report["passed"] == 2


# --------------------------------------------------------------------------
# An adapter failure is not a model failure
# --------------------------------------------------------------------------


@pytest.mark.parametrize("adapter", [_RunRaises(), _CollectRaises()])
def test_an_adapter_failure_is_errored_not_failed(app_sessionmaker, suite, adapter):
    """A gate that counts a timeout as a failure goes green on a retry.

    And once it does that, everyone retries until it does, and the gate has
    stopped being a gate.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, suite["tenant_a"]):
                run = _run(session, suite, adapter)
                outcomes = session.execute(
                    text(
                        "SELECT outcome, count(*) FROM eval_results "
                        "WHERE eval_run_id = :r GROUP BY outcome"
                    ),
                    {"r": run.eval_run_id},
                ).all()
    assert dict(outcomes) == {"errored": 2}
    assert run.violations == 0
    # Errored is not a pass, and a run full of them cannot pass the gate.
    assert not run.passed_gate


def test_an_unverifiable_cancellation_is_recorded_as_unknown(app_sessionmaker, suite):
    """"We asked and do not know" is a different fact from "it stopped".

    It is also the outcome that forbids an automatic retry, so it has to survive
    into the record rather than being flattened into "errored".
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, suite["tenant_a"]):
                run = _run(session, suite, _CancelUnknown())
                observed = session.execute(
                    text(
                        "SELECT observed FROM eval_results WHERE eval_run_id = :r "
                        "LIMIT 1"
                    ),
                    {"r": run.eval_run_id},
                ).scalar_one()
    assert observed["cancellation"] == "unknown"
    assert observed["stage"] == "collect"


# --------------------------------------------------------------------------
# Redaction is verified, not trusted
# --------------------------------------------------------------------------


def test_an_adapter_that_did_not_redact_does_not_get_its_output_stored(
    app_sessionmaker, suite
):
    """The check is idempotence.

    The contract requires a redactor whose second pass is a no-op. So if the
    second pass changes something, the first pass did not happen — and this row
    was about to publish a live key into a table people quote from.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, suite["tenant_a"]):
                run = _run(session, suite, _LeaksASecret())
                rows = session.execute(
                    text(
                        "SELECT outcome, observed FROM eval_results "
                        "WHERE eval_run_id = :r ORDER BY case_id"
                    ),
                    {"r": run.eval_run_id},
                ).all()
    stored = " ".join(str(row[1]) for row in rows)
    assert "sk-ABCDEFGHIJKLMNOPQRSTUVWX" not in stored
    assert all(row[0] == "errored" for row in rows)
    assert not run.passed_gate


# --------------------------------------------------------------------------
# A result nobody can reproduce is not a result
# --------------------------------------------------------------------------


def test_an_adapter_that_cannot_pin_its_model_is_refused_by_default(
    app_sessionmaker, suite
):
    """"The agent scored 72%" is not a fact without knowing which build."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, suite["tenant_a"]):
                with pytest.raises(InvError, match="would not be reproducible"):
                    _run(session, suite, _NoModelPinning())


def test_running_without_model_pinning_records_that_choice(app_sessionmaker, suite):
    """Recorded on the run, not just decided at the call site.

    Someone reads this number later without knowing how it was produced, and
    the run is the only thing still present to tell them.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, suite["tenant_a"]):
                run = _run(
                    session, suite, _NoModelPinning(), require_model_pinning=False
                )
                versions = run.component_versions
    assert versions["modelPinned"] == "false"
    assert versions["adapter"] == "fake"


# --------------------------------------------------------------------------
# The forbidden-behaviour rule
# --------------------------------------------------------------------------


def test_a_violation_fails_the_gate_however_well_everything_else_scored(
    app_sessionmaker, suite
):
    """Not weighted, not averaged, not compensated for."""

    class _Violates(_Base):
        def collect(self, handle):
            return CollectResult(
                completed=True,
                content="the answer is 42 and the key is sk-ABCDEFGHIJKLMNOPQRSTUVWX",
                model_id="m-1",
            )

    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, suite["tenant_a"]):
                run = _run(session, suite, _Violates())
                report = evaluation_service.score_report(
                    session, tenant_id=suite["tenant_a"], eval_run_id=run.eval_run_id
                )
    # The scored case passed outright.
    assert run.passed_cases == 1
    # And the gate is still closed.
    assert run.violations == 1
    assert not run.passed_gate
    assert report["violations"]


def test_a_forbidden_case_declaring_nothing_forbidden_is_refused(
    app_sessionmaker, two_tenants
):
    """A case that can never fail always passes and proves nothing."""
    tenant_a, _ = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant_a):
                created = evaluation_service.create_suite(
                    session,
                    tenant_id=tenant_a,
                    name="empty-forbidden",
                    version="1",
                    cases=[
                        evaluation_service.CaseDefinition(
                            key="declares-nothing",
                            category="policy_compliance",
                            forbidden_behaviour=True,
                            definition={"input": "q"},
                        )
                    ],
                    now=NOW,
                )
                run = eval_execution.run_suite(
                    session, tenant_id=tenant_a, suite_id=created.suite_id,
                    adapter=_Base(), now=NOW,
                )
                outcome = session.execute(
                    text(
                        "SELECT outcome FROM eval_results WHERE eval_run_id = :r"
                    ),
                    {"r": run.eval_run_id},
                ).scalar_one()
    assert outcome == "errored"
    assert not run.passed_gate


# --------------------------------------------------------------------------
# Order and the reference adapter
# --------------------------------------------------------------------------


def test_cases_run_in_key_order_so_two_runs_are_comparable(app_sessionmaker, suite):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, suite["tenant_a"]):
                first = _run(session, suite, _Base())
                second = _run(session, suite, _Base())
                order = session.execute(
                    text(
                        "SELECT eval_run_id, case_id FROM eval_results "
                        "WHERE eval_run_id IN (:a, :b) ORDER BY eval_run_id, recorded_at"
                    ),
                    {"a": first.eval_run_id, "b": second.eval_run_id},
                ).all()
    by_run: dict[str, list[str]] = {}
    for eval_run_id, case_id in order:
        by_run.setdefault(eval_run_id, []).append(case_id)
    assert list(by_run.values())[0] == list(by_run.values())[1]


def test_the_reference_adapter_satisfies_the_executor(app_sessionmaker, two_tenants):
    """The executable statement of the contract, driven end to end.

    The reference adapter echoes its input, so the case asserts on the echo.
    What matters is that the executor and the contract fit together at all.
    """
    tenant_a, _ = two_tenants
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, tenant_a):
                created = evaluation_service.create_suite(
                    session,
                    tenant_id=tenant_a,
                    name="reference",
                    version="1",
                    cases=[
                        evaluation_service.CaseDefinition(
                            key="echoes",
                            category="structured_output",
                            definition={"input": "ping", "mustContain": ["ping"]},
                        )
                    ],
                    now=NOW,
                )
                run = eval_execution.run_suite(
                    session, tenant_id=tenant_a, suite_id=created.suite_id,
                    adapter=ReferenceAdapter(), now=NOW,
                )
                observed = session.execute(
                    text("SELECT observed FROM eval_results WHERE eval_run_id = :r"),
                    {"r": run.eval_run_id},
                ).scalar_one()
    assert run.passed_gate
    assert observed["modelId"]


# --------------------------------------------------------------------------
# What a gate is, in one place
# --------------------------------------------------------------------------


def test_a_run_in_which_every_case_errored_does_not_pass(app_sessionmaker, suite):
    """The defect the executor exposed, kept exposed.

    finish_eval_run used to ask "no violations and every case recorded", which a
    run of nothing but errors satisfies: nothing was violated, and every case was
    accounted for. A provider outage read as a clean pass — the gate going green
    precisely when the evaluation did not happen.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, suite["tenant_a"]):
                run = _run(session, suite, _RunRaises())
                report = evaluation_service.score_report(
                    session, tenant_id=suite["tenant_a"], eval_run_id=run.eval_run_id
                )
    assert run.status == "completed"
    assert run.violations == 0
    assert run.passed_cases == 0
    assert not run.passed_gate
    # And the two places that compute it now agree.
    assert report["passedGate"] == run.passed_gate


def test_the_run_row_and_the_report_always_agree(app_sessionmaker, suite):
    """Two answers to "did the gate pass" is one answer too many."""
    for adapter in (_Base(), _RunRaises(), _LeaksASecret()):
        with app_sessionmaker() as session:
            with session.begin():
                with tenant_scope(session, suite["tenant_a"]):
                    run = _run(session, suite, adapter)
                    report = evaluation_service.score_report(
                        session,
                        tenant_id=suite["tenant_a"],
                        eval_run_id=run.eval_run_id,
                    )
                    assert report["passedGate"] == run.passed_gate, adapter


def test_an_empty_suite_is_not_a_pass():
    """Zero of zero cases passing is a fact about arithmetic, not about a model."""
    assert not evaluation_service.gate_passed(
        total_cases=0, recorded=0, passed=0, violations=0
    )


def test_a_partial_run_is_not_a_pass():
    """Cases that have not run yet cannot be assumed to be about to pass."""
    assert not evaluation_service.gate_passed(
        total_cases=3, recorded=2, passed=2, violations=0
    )
