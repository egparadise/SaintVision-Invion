"""Running an evaluation suite against a provider adapter.

The scoring was already here — pass rates, per-category breakdown, the rule
that a forbidden-behaviour violation fails the gate outright. What was missing
was anything that actually executes a case and produces the outcome to score.

Four judgements are encoded here, and each is a way an evaluation gate becomes
worthless while continuing to report numbers.

**An adapter failure is ``errored``, never ``failed``.** A timeout, a refused
connection or a missing credential says nothing about the model. Counting them
as failures produces a gate that goes green on a retry, which teaches everyone
to retry until it does — and by then the gate has stopped meaning anything.
``errored`` cases keep the run from completing, so the gate cannot pass on a
partial result either.

**An unverifiable cancellation stops the case, and is not retried.**
:class:`~saintvision.adapters.contract.CancelOutcome` is deliberately tri-state:
closing a stream is not the same as stopping generation. ``UNKNOWN`` means the
adapter could not find out what happened, and PLAN-BACKEND-001 forbids
automatically retrying an unverifiable external side effect. Retrying here
would be the same mistake with a bill attached.

**Redaction is verified rather than trusted.** ``collect`` is contracted to
return already-redacted content (ADR-014). This runs the adapter's redactor
over the result once more before storing it: because the redactor is idempotent
by contract, a second pass that *changes* something proves the first pass did
not happen. Eval results are read widely and quoted freely, so a leak in this
table is a leak in the place people paste into chat.

**An eval that cannot name the model build is not a result.** ``eval_runs``
already says so — "the agent scored 72%" is not a fact without knowing which
prompt, context and model produced it. So an adapter that cannot pin its model
is refused by default rather than producing a number nobody can reproduce.
``require_model_pinning=False`` exists for exploratory runs and records that
choice in the run's component versions.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..adapters.contract import (
    CancelOutcome,
    Capability,
    CollectResult,
    ProviderAdapter,
)
from ..db.models import EvalCase, EvalRun
from ..errors import VAL_SCHEMA, InvError
from . import evaluation as evaluation_service

#: How much of the model's output is kept on the result row. The full output
#: belongs in the artefact store; what an eval table needs is enough to see why
#: a case failed, and a row a person will actually read.
OBSERVED_EXCERPT_CHARS: Final[int] = 512


@dataclass(frozen=True, slots=True)
class CaseOutcome:
    """What one case produced, before it is written down."""

    case_id: str
    key: str
    outcome: str
    score: float | None = None
    violated: bool = False
    observed: dict[str, Any] = field(default_factory=dict)
    duration_ms: int | None = None


def _expectation(case: EvalCase) -> dict[str, Any]:
    """The assertions a case declares.

    Read from the definition rather than dispatched on ``category``: a category
    is for reporting, and a coding case and a policy case can both assert that
    the output must contain something. Dispatching on category would mean
    inventing a checker per category and then discovering they are the same.
    """
    definition = case.definition or {}
    return {
        "input": str(definition.get("input", "")),
        "must_contain": tuple(definition.get("mustContain", ())),
        "must_not_contain": tuple(definition.get("mustNotContain", ())),
        "forbidden_patterns": tuple(definition.get("forbiddenPatterns", ())),
    }


def _check(case: EvalCase, content: str) -> tuple[str, float | None, bool]:
    """Return ``(outcome, score, violated)`` for one collected output.

    A forbidden-behaviour case carries no score at all. Giving it one would let
    it be averaged, and the whole point is that it cannot be traded against
    anything.
    """
    expectation = _expectation(case)

    if case.forbidden_behaviour:
        patterns = expectation["forbidden_patterns"] or expectation["must_not_contain"]
        if not patterns:
            # A forbidden-behaviour case that declares nothing forbidden can
            # never fail, which makes it a case that always passes and proves
            # nothing. Refused at execution rather than quietly counted.
            raise InvError(
                VAL_SCHEMA,
                "a forbidden-behaviour case must declare what is forbidden",
                extra={"caseKey": case.key},
            )
        occurred = any(re.search(pattern, content) for pattern in patterns)
        return ("failed" if occurred else "passed", None, occurred)

    required = expectation["must_contain"]
    excluded = expectation["must_not_contain"]
    if not required and not excluded:
        raise InvError(
            VAL_SCHEMA,
            "a scored case must declare what it expects",
            extra={"caseKey": case.key},
        )
    hits = sum(1 for needle in required if needle in content)
    leaks = sum(1 for needle in excluded if needle in content)
    total = len(required) + len(excluded)
    satisfied = hits + (len(excluded) - leaks)
    score = satisfied / total if total else 0.0
    return ("passed" if satisfied == total else "failed", score, False)


def _observed(
    adapter: ProviderAdapter, result: CollectResult, content: str
) -> dict[str, Any]:
    """The row a person reads when a case fails, with the redaction verified.

    The second redaction pass is the check. The contract requires the redactor
    to be idempotent, so if it changes anything here the content it was given
    had not been through it — which means ``collect`` returned raw output and
    this row was about to publish it.
    """
    reredacted, changed = adapter.redact(content)
    if changed:
        raise InvError(
            VAL_SCHEMA,
            "the adapter's collected output was not redacted; refusing to store it",
            public=False,
        )
    return {
        "excerpt": reredacted[:OBSERVED_EXCERPT_CHARS],
        "truncated": len(reredacted) > OBSERVED_EXCERPT_CHARS,
        "stopReason": result.stop_reason,
        "modelId": result.model_id,
        # Recorded, not hidden: a result whose content was redacted is a result
        # whose failure may be explained by the redaction.
        "redacted": result.redacted,
        "usage": {
            "inputTokens": result.usage.input_tokens,
            "outputTokens": result.usage.output_tokens,
        },
    }


def execute_case(
    adapter: ProviderAdapter, case: EvalCase, *, timeout_seconds: int | None = None
) -> CaseOutcome:
    """Run one case and decide what it produced. Writes nothing.

    Separated from recording so the decision can be tested without a database,
    and so a failure to write cannot be mistaken for a failure of the model.
    """
    started = dt.datetime.now(dt.timezone.utc)
    expectation = _expectation(case)

    try:
        handle = adapter.run({"input": expectation["input"], "case": case.key})
    except Exception as error:  # noqa: BLE001 - any adapter failure is infrastructure
        return CaseOutcome(
            case_id=case.case_id,
            key=case.key,
            outcome="errored",
            observed={"error": type(error).__name__, "stage": "run"},
        )

    try:
        result = adapter.collect(handle)
    except Exception as error:  # noqa: BLE001
        # The request was started and may still be running. Ask the adapter to
        # stop it and record what it says, because "we asked and do not know"
        # and "it stopped" are different facts for whoever reads this later.
        outcome = _try_cancel(adapter, handle)
        return CaseOutcome(
            case_id=case.case_id,
            key=case.key,
            outcome="errored",
            observed={
                "error": type(error).__name__,
                "stage": "collect",
                "cancellation": outcome.value,
            },
        )

    duration_ms = int(
        (dt.datetime.now(dt.timezone.utc) - started).total_seconds() * 1000
    )

    if not result.completed:
        return CaseOutcome(
            case_id=case.case_id,
            key=case.key,
            outcome="errored",
            observed={"error": result.error_code, "stage": "collect"},
            duration_ms=duration_ms,
        )

    outcome, score, violated = _check(case, result.content)
    return CaseOutcome(
        case_id=case.case_id,
        key=case.key,
        outcome=outcome,
        score=score,
        violated=violated,
        observed=_observed(adapter, result, result.content),
        duration_ms=duration_ms,
    )


def _try_cancel(adapter: ProviderAdapter, handle) -> CancelOutcome:
    try:
        return adapter.cancel(handle)
    except Exception:  # noqa: BLE001
        # The adapter could not even be asked. That is UNKNOWN, which is the
        # outcome that blocks an automatic retry — and it is the honest one.
        return CancelOutcome.UNKNOWN


def run_suite(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    suite_id: str,
    adapter: ProviderAdapter,
    now: dt.datetime,
    component_versions: dict[str, str] | None = None,
    require_model_pinning: bool = True,
) -> EvalRun:
    """Execute every case in a suite and close the run.

    Cases run in key order so two runs of the same suite are comparable. A case
    that raises is recorded as ``errored`` rather than aborting the loop: the
    results already gathered are worth keeping, and a run missing cases cannot
    pass the gate anyway.
    """
    if require_model_pinning and Capability.MODEL_PINNING not in adapter.capabilities:
        raise InvError(
            VAL_SCHEMA,
            "this adapter cannot report which model build produced a result, so "
            "the score would not be reproducible; pass require_model_pinning=False "
            "to run it anyway and have that recorded",
            extra={"adapter": adapter.name},
        )

    versions = dict(component_versions or {})
    versions.setdefault("adapter", adapter.name)
    versions.setdefault("contractVersion", adapter.contract_version)
    if not require_model_pinning:
        # Recorded on the run, not just decided at the call site. Someone will
        # read this number later without knowing how it was produced.
        versions["modelPinned"] = "false"

    run = evaluation_service.start_eval_run(
        session,
        tenant_id=tenant_id,
        suite_id=suite_id,
        now=now,
        component_versions=versions,
    )

    cases = list(
        session.scalars(
            select(EvalCase)
            .where(EvalCase.tenant_id == tenant_id, EvalCase.suite_id == suite_id)
            .order_by(EvalCase.key)
        ).all()
    )

    for case in cases:
        try:
            outcome = execute_case(adapter, case)
        except InvError as error:
            # A malformed case, or an adapter that returned unredacted content.
            # Both are problems with the evaluation, not with the model, so the
            # case is errored and the run cannot complete.
            outcome = CaseOutcome(
                case_id=case.case_id,
                key=case.key,
                outcome="errored",
                observed={"error": error.code, "stage": "check"},
            )
        evaluation_service.record_result(
            session,
            tenant_id=tenant_id,
            eval_run_id=run.eval_run_id,
            case_id=outcome.case_id,
            outcome=outcome.outcome,
            score=outcome.score,
            violated=outcome.violated,
            observed=outcome.observed,
            duration_ms=outcome.duration_ms,
            now=now,
        )

    return evaluation_service.finish_eval_run(
        session, tenant_id=tenant_id, eval_run_id=run.eval_run_id, now=now
    )
