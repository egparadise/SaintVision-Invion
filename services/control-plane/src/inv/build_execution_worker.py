"""Trusted internal caller for durable S08-BE product-build intents.

There is deliberately no HTTP route and no CLI which accepts build documents.
The trusted producer validates the three public contracts and stores their exact
JSON values in ``inv.build_execution_intents``.  A worker claims one row with
``FOR UPDATE SKIP LOCKED`` and is the product composition seam which actually
calls :class:`inv.build_execution.BuildExecutionService`.

A failed pre-dispatch claim is returned to pending only when the adapter's
durable one-shot decision claim does not exist.  Once that claim is committed,
the row remains claimed: the decision claim and node-quarantine channel are the
reconciliation authority.  Product dispatch remains disabled unless
``INV_BUILDKIT_PRODUCT_ENABLED`` is exactly ``1``; that check happens before a
queue row is claimed and is repeated by ``BuildExecutionService``.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import logging
import os
from typing import Any, Mapping

from psycopg.types.json import Jsonb

from .approvals import Principal
from .build_execution import (
    PRODUCT_ENABLE_SETTING,
    PRODUCT_ENABLE_VALUE,
    BuildExecutionResult,
)
from .build_governance import canonical_build_action
from .contracts import validate_contract
from .errors import DomainError
from .policy import action_digest

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BuildExecutionIntent:
    tenant_id: str
    project_id: str
    run_id: str
    request: dict[str, Any]
    plan: dict[str, Any]
    decision: dict[str, Any]
    request_sha256: str
    plan_sha256: str
    decision_sha256: str
    policy_version: str
    evidence_id: str
    actor_id: str
    status: str


def _refuse(detail: str) -> DomainError:
    return DomainError("RES-0006", detail, 503, retryable=True)


def _validated_documents(
    principal: Principal,
    request: Mapping[str, Any],
    plan: Mapping[str, Any],
    decision: Mapping[str, Any],
    *,
    policy_version: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Freeze exact contract documents and reject a cross-scope queue row."""

    frozen = (deepcopy(dict(request)), deepcopy(dict(plan)), deepcopy(dict(decision)))
    validate_contract("BuildRequest", frozen[0])
    validate_contract("BuildPlan", frozen[1])
    validate_contract("PolicyDecision", frozen[2])
    expected_action_digest = action_digest(canonical_build_action(frozen[0]))
    if (
        frozen[0]["tenantId"] != principal.tenant_id
        or frozen[1]["tenantId"] != principal.tenant_id
        or frozen[2]["tenantId"] != principal.tenant_id
        or frozen[0]["projectId"] != frozen[1]["projectId"]
        or frozen[0]["projectId"] != frozen[2]["projectId"]
        or frozen[0]["workspaceId"] != frozen[1]["workspaceId"]
        or frozen[1]["requestDigest"] != action_digest(frozen[0])
        or frozen[1]["actionDigest"] != expected_action_digest
        or frozen[2]["actionDigest"] != expected_action_digest
        or frozen[1]["policyVersion"] != policy_version
        or frozen[1]["policyDecisionId"] != frozen[2]["decisionId"]
        or frozen[1]["policyExpiresAt"] != frozen[2]["expiresAt"]
        or frozen[2]["subjectId"] != principal.subject_id
    ):
        raise DomainError("VERIFY-0002", "Build execution intent authority differs", 422)
    return frozen


def _row_to_intent(row: Mapping[str, Any]) -> BuildExecutionIntent:
    return BuildExecutionIntent(
        tenant_id=str(row["tenant_id"]),
        project_id=row["project_id"],
        run_id=row["run_id"],
        request=deepcopy(row["request"]),
        plan=deepcopy(row["plan"]),
        decision=deepcopy(row["decision"]),
        request_sha256=row["request_sha256"],
        plan_sha256=row["plan_sha256"],
        decision_sha256=row["decision_sha256"],
        policy_version=row["policy_version"],
        evidence_id=row["evidence_id"],
        actor_id=row["actor_id"],
        status=row["status"],
    )


class BuildExecutionIntentQueue:
    """Tenant-scoped trusted enqueue, one-shot claim, and completion boundary."""

    def __init__(self, database):
        self.db = database

    def enqueue(
        self,
        principal: Principal,
        request: Mapping[str, Any],
        plan: Mapping[str, Any],
        decision: Mapping[str, Any],
        *,
        policy_version: str,
        run_id: str,
        evidence_id: str,
    ) -> BuildExecutionIntent:
        request_doc, plan_doc, decision_doc = _validated_documents(
            principal, request, plan, decision, policy_version=policy_version
        )
        project_id = request_doc["projectId"]
        with self.db.transaction(principal.tenant_id) as conn:
            run = conn.execute(
                """SELECT state FROM inv.runs
                WHERE tenant_id=%s AND project_id=%s AND run_id=%s FOR SHARE""",
                (principal.tenant_id, project_id, run_id),
            ).fetchone()
            if not run or run["state"] not in {"scheduled", "running", "verifying"}:
                raise DomainError("RES-0005", "Run cannot queue a product build", 409)
            conn.execute(
                """INSERT INTO inv.build_execution_intents(
                tenant_id,project_id,run_id,request,plan,decision,
                policy_version,evidence_id,actor_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING""",
                (
                    principal.tenant_id,
                    project_id,
                    run_id,
                    Jsonb(request_doc),
                    Jsonb(plan_doc),
                    Jsonb(decision_doc),
                    policy_version,
                    evidence_id,
                    principal.subject_id,
                ),
            )
            row = conn.execute(
                """SELECT * FROM inv.build_execution_intents
                WHERE tenant_id=%s AND project_id=%s AND run_id=%s FOR SHARE""",
                (principal.tenant_id, project_id, run_id),
            ).fetchone()
            if not row:
                raise DomainError("SYS-0001", "Build execution intent was not stored", 503)
            if (
                row["request"] != request_doc
                or row["plan"] != plan_doc
                or row["decision"] != decision_doc
                or row["policy_version"] != policy_version
                or row["evidence_id"] != evidence_id
                or row["actor_id"] != principal.subject_id
            ):
                raise DomainError("IDEM-0001", "Build execution intent replay differs", 409)
            return _row_to_intent(row)

    def claim_next(self, tenant_id: str) -> BuildExecutionIntent | None:
        with self.db.transaction(tenant_id) as conn:
            row = conn.execute(
                """WITH candidate AS (
                  SELECT tenant_id,project_id,run_id
                  FROM inv.build_execution_intents
                  WHERE tenant_id=%s AND status='pending'
                    AND request_sha256 =
                      encode(sha256(convert_to(request::text,'UTF8')),'hex')
                    AND plan_sha256 =
                      encode(sha256(convert_to(plan::text,'UTF8')),'hex')
                    AND decision_sha256 =
                      encode(sha256(convert_to(decision::text,'UTF8')),'hex')
                  ORDER BY created_at,project_id,run_id
                  LIMIT 1 FOR UPDATE SKIP LOCKED
                )
                UPDATE inv.build_execution_intents AS intent SET status='claimed'
                FROM candidate
                WHERE (intent.tenant_id,intent.project_id,intent.run_id) =
                      (candidate.tenant_id,candidate.project_id,candidate.run_id)
                RETURNING intent.*""",
                (tenant_id,),
            ).fetchone()
            if not row:
                return None
            intent = _row_to_intent(row)
            # The database binds scope and policy fields; the worker also validates the
            # complete public contracts before any external side effect.
            _validated_documents(
                Principal(intent.tenant_id, intent.actor_id),
                intent.request,
                intent.plan,
                intent.decision,
                policy_version=intent.policy_version,
            )
            return intent

    def requeue_if_unconsumed(self, intent: BuildExecutionIntent) -> bool:
        """Return a failed pre-dispatch claim to pending, never an admitted dispatch.

        ``BuildExecutionAdapter`` consumes the PolicyDecision in ``inv.idempotency`` before
        its first external side effect and records the decision ID in that claim.  Absence of
        that row is therefore the only safe automatic-retry boundary.  The 0059 trigger asks
        the same question so a direct runtime UPDATE cannot requeue a consumed dispatch.
        """

        claim_key = action_digest({"decisionId": intent.decision["decisionId"]})
        with self.db.transaction(intent.tenant_id) as conn:
            consumed = conn.execute(
                """SELECT 1 FROM inv.idempotency
                WHERE project_id=%s AND operation='build.dispatch' AND key=%s
                  AND response->>'decisionId'=%s""",
                (intent.project_id, claim_key, intent.decision["decisionId"]),
            ).fetchone()
            if consumed:
                return False
            pending = conn.execute(
                """UPDATE inv.build_execution_intents SET status='pending'
                WHERE tenant_id=%s AND project_id=%s AND run_id=%s AND status='claimed'
                RETURNING run_id""",
                (intent.tenant_id, intent.project_id, intent.run_id),
            ).fetchone()
            return pending is not None

    def complete(self, intent: BuildExecutionIntent) -> None:
        with self.db.transaction(intent.tenant_id) as conn:
            completed = conn.execute(
                """UPDATE inv.build_execution_intents SET status='completed'
                WHERE tenant_id=%s AND project_id=%s AND run_id=%s AND status='claimed'
                RETURNING run_id""",
                (intent.tenant_id, intent.project_id, intent.run_id),
            ).fetchone()
            if not completed:
                raise DomainError("IDEM-0001", "Build execution intent is not claimed", 409)


class BuildExecutionWorker:
    """The internal composition seam which calls ``BuildExecutionService``."""

    def __init__(self, queue: BuildExecutionIntentQueue, service, *, environment=None):
        self.queue = queue
        self.service = service
        self.environment = dict(os.environ if environment is None else environment)

    def once(self, tenant_id: str) -> BuildExecutionResult | None:
        # Do not consume a durable row merely to discover that product dispatch is off.
        if self.environment.get(PRODUCT_ENABLE_SETTING) != PRODUCT_ENABLE_VALUE:
            raise _refuse("BuildKit product dispatch is not enabled")
        intent = self.queue.claim_next(tenant_id)
        if intent is None:
            return None
        try:
            result = self.service.execute(
                Principal(intent.tenant_id, intent.actor_id),
                intent.request,
                intent.plan,
                intent.decision,
                policy_version=intent.policy_version,
                run_id=intent.run_id,
                evidence_id=intent.evidence_id,
                actor_id=intent.actor_id,
            )
        except BaseException:
            try:
                self.queue.requeue_if_unconsumed(intent)
            except Exception:
                # Requeue is a recovery aid, never permission to replace the original cause.
                # A consumed dispatch or an unavailable DB therefore remains claimed.
                LOGGER.exception("build intent could not be safely requeued")
            raise
        self.queue.complete(intent)
        return result
