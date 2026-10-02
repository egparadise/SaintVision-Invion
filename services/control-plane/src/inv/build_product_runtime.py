"""Internal producer and composition root for product BuildKit work.

No route or CLI accepts build documents.  A trusted service first commits an
immutable admission after checking project, Run, policy, and live lease
authority.  The product loop promotes only that row to migration 0059's intent
queue, then delegates dispatch to ``BuildExecutionWorker``.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from psycopg.types.json import Jsonb

from .approvals import Principal
from .build_adapter import BuildExecutionAdapter, _database_now, _lock_live_build_authority
from .build_execution import (
    PRODUCT_ENABLE_SETTING,
    PRODUCT_ENABLE_VALUE,
    BuildExecutionService,
)
from .build_execution_worker import (
    BuildExecutionIntentQueue,
    BuildExecutionWorker,
    _validated_documents,
)
from .build_governance import canonical_build_action
from .buildkit_transport import (
    BuildkitTransportConfiguration,
    NodeAgentReceipts,
    RootlessBuildkitTransport,
)
from .control import Control
from .errors import DomainError
from .node_channels import NodeChannels
from .node_transport import NodeTLSClient
from .policy import action_digest, enforce_decision
from .tooling import NodePrincipal

PROMOTED_EVENT = "inv.build.intent_enqueued"


@dataclass(frozen=True)
class BuildExecutionAdmission:
    tenant_id: str
    project_id: str
    run_id: str
    request: dict[str, Any]
    plan: dict[str, Any]
    decision: dict[str, Any]
    policy_version: str
    evidence_id: str
    actor_id: str
    status: str


def _row(row: Mapping[str, Any]) -> BuildExecutionAdmission:
    return BuildExecutionAdmission(
        tenant_id=str(row["tenant_id"]),
        project_id=row["project_id"],
        run_id=row["run_id"],
        request=deepcopy(row["request"]),
        plan=deepcopy(row["plan"]),
        decision=deepcopy(row["decision"]),
        policy_version=row["policy_version"],
        evidence_id=row["evidence_id"],
        actor_id=row["actor_id"],
        status=row["status"],
    )


class BuildExecutionAdmissionStore:
    """Persist and promote only database-verified internal build authority."""

    def __init__(self, database):
        self.db = database

    def record(
        self,
        principal: Principal,
        request: Mapping[str, Any],
        plan: Mapping[str, Any],
        decision: Mapping[str, Any],
        *,
        policy_version: str,
        run_id: str,
        evidence_id: str,
    ) -> BuildExecutionAdmission:
        request_doc, plan_doc, decision_doc = _validated_documents(
            principal, request, plan, decision, policy_version=policy_version
        )
        project_id = request_doc["projectId"]
        with self.db.transaction(principal.tenant_id) as conn:
            Control(self.db).grant(conn, principal, project_id, "can_request")
            now = _database_now(conn)
            enforce_decision(
                decision_doc,
                action=canonical_build_action(request_doc),
                tenant_id=principal.tenant_id,
                project_id=project_id,
                subject_id=principal.subject_id,
                now=now,
            )
            _lock_live_build_authority(
                conn,
                request_doc,
                plan_doc,
                run_id,
                database_recovery_epoch=self.db.recovery_epoch,
                now=now,
            )
            conn.execute(
                """INSERT INTO inv.build_execution_admissions(
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
            stored = conn.execute(
                """SELECT * FROM inv.build_execution_admissions
                WHERE project_id=%s AND run_id=%s FOR SHARE""",
                (project_id, run_id),
            ).fetchone()
            if not stored:
                raise DomainError("SYS-0001", "Build admission was not stored", 503)
            candidate = _row(stored)
            if (
                candidate.request != request_doc
                or candidate.plan != plan_doc
                or candidate.decision != decision_doc
                or candidate.policy_version != policy_version
                or candidate.evidence_id != evidence_id
                or candidate.actor_id != principal.subject_id
            ):
                raise DomainError("IDEM-0001", "Build admission replay differs", 409)
            return candidate

    def promote_next(self, tenant_id: str) -> BuildExecutionAdmission | None:
        """Atomically revalidate one admission and create its 0059 intent."""

        while True:
            with self.db.transaction(tenant_id) as conn:
                stored = conn.execute("""SELECT *,
                    request_sha256 = encode(sha256(convert_to(request::text,'UTF8')),'hex')
                      AND plan_sha256 = encode(sha256(convert_to(plan::text,'UTF8')),'hex')
                      AND decision_sha256 = encode(sha256(convert_to(decision::text,'UTF8')),'hex')
                      AS digests_match
                    FROM inv.build_execution_admissions
                    WHERE status='ready'
                    ORDER BY created_at,project_id,run_id
                    LIMIT 1 FOR UPDATE SKIP LOCKED""").fetchone()
                if not stored:
                    return None
                admission = _row(stored)
                if stored.get("digests_match") is not True:
                    conn.execute(
                        """UPDATE inv.build_execution_admissions
                        SET status='quarantined',last_error_code='VERIFY-0002'
                        WHERE project_id=%s AND run_id=%s AND status='ready'""",
                        (admission.project_id, admission.run_id),
                    )
                    continue
                try:
                    principal = Principal(admission.tenant_id, admission.actor_id)
                    _validated_documents(
                        principal,
                        admission.request,
                        admission.plan,
                        admission.decision,
                        policy_version=admission.policy_version,
                    )
                    Control(self.db).grant(conn, principal, admission.project_id, "can_request")
                    now = _database_now(conn)
                    enforce_decision(
                        admission.decision,
                        action=canonical_build_action(admission.request),
                        tenant_id=admission.tenant_id,
                        project_id=admission.project_id,
                        subject_id=admission.actor_id,
                        now=now,
                    )
                    _lock_live_build_authority(
                        conn,
                        admission.request,
                        admission.plan,
                        admission.run_id,
                        database_recovery_epoch=self.db.recovery_epoch,
                        now=now,
                    )
                except (DomainError, KeyError, TypeError, ValueError) as error:
                    code = error.code if isinstance(error, DomainError) else "VERIFY-0002"
                    conn.execute(
                        """UPDATE inv.build_execution_admissions
                        SET status='quarantined',last_error_code=%s
                        WHERE project_id=%s AND run_id=%s AND status='ready'""",
                        (code, admission.project_id, admission.run_id),
                    )
                    continue

                conn.execute(
                    """INSERT INTO inv.build_execution_intents(
                    tenant_id,project_id,run_id,request,plan,decision,
                    dispatch_claim_key,policy_version,evidence_id,actor_id
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING""",
                    (
                        admission.tenant_id,
                        admission.project_id,
                        admission.run_id,
                        Jsonb(admission.request),
                        Jsonb(admission.plan),
                        Jsonb(admission.decision),
                        action_digest({"decisionId": admission.decision["decisionId"]}),
                        admission.policy_version,
                        admission.evidence_id,
                        admission.actor_id,
                    ),
                )
                intent = conn.execute(
                    """SELECT request,plan,decision,policy_version,evidence_id,actor_id
                    FROM inv.build_execution_intents
                    WHERE project_id=%s AND run_id=%s FOR SHARE""",
                    (admission.project_id, admission.run_id),
                ).fetchone()
                if not intent or any(
                    (
                        intent["request"] != admission.request,
                        intent["plan"] != admission.plan,
                        intent["decision"] != admission.decision,
                        intent["policy_version"] != admission.policy_version,
                        intent["evidence_id"] != admission.evidence_id,
                        intent["actor_id"] != admission.actor_id,
                    )
                ):
                    raise DomainError("IDEM-0001", "Promoted build intent differs", 409)
                conn.execute(
                    """UPDATE inv.build_execution_admissions SET status='promoted'
                    WHERE project_id=%s AND run_id=%s AND status='ready'""",
                    (admission.project_id, admission.run_id),
                )
                conn.execute(
                    """INSERT INTO inv.outbox(tenant_id,run_id,event_id,event_type,payload)
                    VALUES (%s,%s,%s,%s,%s)""",
                    (
                        admission.tenant_id,
                        admission.run_id,
                        uuid4(),
                        PROMOTED_EVENT,
                        Jsonb(
                            {
                                "projectId": admission.project_id,
                                "runId": admission.run_id,
                                "decisionId": admission.decision["decisionId"],
                                "evidenceId": admission.evidence_id,
                            }
                        ),
                    ),
                )
                return admission


class BuildProductRuntime:
    """One product-loop tick: promote authority, then execute one intent."""

    def __init__(self, admission_store, worker, *, environment: Mapping[str, str]):
        self.admissions = admission_store
        self.worker = worker
        self.environment = dict(environment)

    def once(self, tenant_id: str):
        if self.environment.get(PRODUCT_ENABLE_SETTING) != PRODUCT_ENABLE_VALUE:
            raise DomainError(
                "RES-0006", "BuildKit product dispatch is not enabled", 503, retryable=True
            )
        self.admissions.promote_next(tenant_id)
        return self.worker.once(tenant_id)


def configured_tenant_product_runtime(database, tenant_id: str, config, *, tls, environment):
    """Tenant-bound constructor used by the process composition root."""

    values = dict(config)
    expected = {
        "buildctlPath",
        "address",
        "sourceRoot",
        "referenceHealthReceipt",
        "productReceiptDirectory",
        "builderInstanceId",
        "builderProfileId",
        "providerRecoveryEpoch",
        "nodeId",
    }
    if set(values) != expected or not isinstance(tls, Mapping):
        raise ValueError("Exact build execution configuration required")
    transport = RootlessBuildkitTransport(
        BuildkitTransportConfiguration(
            buildctl_path=Path(values["buildctlPath"]),
            address=values["address"],
            source_root=Path(values["sourceRoot"]),
            health_receipt_path=Path(values["referenceHealthReceipt"]),
            builder_instance_id=values["builderInstanceId"],
            builder_profile_id=values["builderProfileId"],
            recovery_epoch=values["providerRecoveryEpoch"],
        ),
        environment=environment,
    )
    channel = NodeChannels(database).snapshot(
        NodePrincipal(tenant_id, values["nodeId"]), observation_only=False
    )
    receipts = NodeAgentReceipts(
        Path(values["productReceiptDirectory"]),
        quarantine_client=NodeTLSClient(**dict(tls)),
        quarantine_channel=channel,
    )
    adapter = BuildExecutionAdapter(database, transport)
    service = BuildExecutionService(database, adapter, receipts, environment=environment)
    queue = BuildExecutionIntentQueue(database)
    worker = BuildExecutionWorker(queue, service, environment=environment)
    return BuildProductRuntime(
        BuildExecutionAdmissionStore(database), worker, environment=environment
    )
