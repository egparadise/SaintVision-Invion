"""Golden evaluation (S09-DB).

AC-09 asks for three things and this schema keeps them apart on purpose:

* a **golden** suite — fixed cases with fixed expectations, versioned, so a
  score from last week and one from today mean the same thing;
* **per-category** scores, because an aggregate that hides a weak category is
  the number people quote and the one that misleads;
* **forbidden behaviour** tests, which are pass/fail and not part of any
  average — a run that leaked a secret does not become acceptable by scoring
  well elsewhere.

Nothing here decides what a good score is. The gate lives in the plan; this
records what happened.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, InvId, Sha256, TenantId, Utc

EVAL_CATEGORIES = (
    "structured_output",
    "tool_selection",
    "coding_task",
    "policy_compliance",
    "context_grounding",
)
EVAL_OUTCOMES = ("passed", "failed", "errored", "skipped")


class EvalSuite(Base):
    """A named, versioned set of cases.

    ``(name, version)`` is unique and a suite is never edited in place: a
    changed case set is a new version, or two results that claim to be
    comparable are not.
    """

    __tablename__ = "eval_suites"
    __table_args__ = (
        UniqueConstraint("tenant_id", "suite_id", name="uq_eval_suites_tenant_id_suite_id"),
        UniqueConstraint("tenant_id", "name", "version", name="uq_eval_suites_name_version"),
        CheckConstraint("case_count >= 0", name="case_count_non_negative"),
    )

    suite_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    name: Mapped[str] = mapped_column(String(128))
    #: SemVer of the case set, not a row version.
    version: Mapped[str] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    #: Hash over the ordered case definitions, so a silently edited suite is
    #: detectable rather than merely discouraged.
    definition_sha256: Mapped[Sha256] = mapped_column()
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class EvalCase(Base):
    """One case. Either scored, or a forbidden-behaviour check, never both."""

    __tablename__ = "eval_cases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "suite_id"], ["eval_suites.tenant_id", "eval_suites.suite_id"]
        ),
        UniqueConstraint("tenant_id", "case_id", name="uq_eval_cases_tenant_id_case_id"),
        UniqueConstraint("suite_id", "key", name="uq_eval_cases_suite_id_key"),
        CheckConstraint(
            "category IN ('structured_output','tool_selection','coding_task',"
            "'policy_compliance','context_grounding')",
            name="category_allowed",
        ),
        CheckConstraint("weight > 0", name="weight_positive"),
        # A forbidden-behaviour case is pass/fail and must not carry a score
        # weight, or a violation could be averaged away.
        CheckConstraint(
            "NOT forbidden_behaviour OR weight = 1", name="forbidden_case_has_unit_weight"
        ),
        Index("ix_eval_cases_tenant_id_category", "tenant_id", "category"),
    )

    case_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    suite_id: Mapped[InvId] = mapped_column()
    #: Stable human key within the suite, e.g. "json-schema-nested-01".
    key: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(32))
    #: True when the case checks that something must NOT happen.
    forbidden_behaviour: Mapped[bool] = mapped_column(default=False)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    #: The case definition. Never the raw prompt text of a customer document —
    #: golden cases are synthetic for the pilot (PLAN-STORAGE-001).
    definition: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class EvalRun(Base):
    """One execution of one suite version against one set of component versions.

    The versions are part of the identity of a result. "The agent scored 72%"
    means nothing without which prompt, context and model produced it.
    """

    __tablename__ = "eval_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "suite_id"], ["eval_suites.tenant_id", "eval_suites.suite_id"]
        ),
        UniqueConstraint("tenant_id", "eval_run_id", name="uq_eval_runs_tenant_id_eval_run_id"),
        CheckConstraint("total_cases >= 0", name="total_cases_non_negative"),
        CheckConstraint("passed_cases >= 0", name="passed_cases_non_negative"),
        CheckConstraint("passed_cases <= total_cases", name="passed_within_total"),
        CheckConstraint("violations >= 0", name="violations_non_negative"),
        CheckConstraint(
            "status IN ('running','completed','aborted')", name="status_allowed"
        ),
        # An eval run with any forbidden-behaviour violation is not a pass,
        # whatever the score says.
        CheckConstraint(
            "NOT passed_gate OR violations = 0", name="gate_requires_no_violations"
        ),
        Index("ix_eval_runs_tenant_id_started_at", "tenant_id", "started_at"),
    )

    eval_run_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    suite_id: Mapped[InvId] = mapped_column()
    status: Mapped[str] = mapped_column(String(16), default="running")
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0)
    violations: Mapped[int] = mapped_column(Integer, default=0)
    #: Set only when the suite completed and nothing was violated.
    passed_gate: Mapped[bool] = mapped_column(default=False)
    component_versions: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    started_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    ended_at: Mapped[Utc | None] = mapped_column(nullable=True)


class EvalResult(Base):
    """The outcome of one case in one eval run.

    ``observed`` holds a redacted summary, never the model's raw output: an
    eval table is read often and by many people, and a leaked secret in it is
    still a leak (ADR-014).
    """

    __tablename__ = "eval_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "eval_run_id"],
            ["eval_runs.tenant_id", "eval_runs.eval_run_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"], ["eval_cases.tenant_id", "eval_cases.case_id"]
        ),
        UniqueConstraint(
            "eval_run_id", "case_id", name="uq_eval_results_eval_run_id_case_id"
        ),
        CheckConstraint(
            "outcome IN ('passed','failed','errored','skipped')", name="outcome_allowed"
        ),
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 1)", name="score_in_range"
        ),
        # A violation is recorded only on a case that was checking for one.
        CheckConstraint(
            "NOT violated OR outcome = 'failed'", name="violation_implies_failure"
        ),
        Index("ix_eval_results_tenant_id_eval_run_id", "tenant_id", "eval_run_id"),
        Index("ix_eval_results_violated", "violated"),
    )

    tenant_id: Mapped[TenantId] = mapped_column(primary_key=True)
    eval_run_id: Mapped[InvId] = mapped_column(primary_key=True)
    case_id: Mapped[InvId] = mapped_column(primary_key=True)
    outcome: Mapped[str] = mapped_column(String(16))
    #: NULL for a forbidden-behaviour case, which has no score.
    score: Mapped[float | None] = mapped_column(nullable=True)
    #: True when a forbidden behaviour actually occurred.
    violated: Mapped[bool] = mapped_column(default=False)
    #: Redacted. Not the raw output.
    observed: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    #: The Run that produced this, when the case was executed as a real Run.
    run_id: Mapped[InvId | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
