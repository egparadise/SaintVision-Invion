"""Reading what a Run actually produced.

This is the API a screen calls to show a result, and its governing rule comes
from a defect found in the screen that will call it: when the server did not
answer, the studio displayed a fixed hash, a byte count of 1,024, an invented
Evidence id and a stop-receipt confirmation line — all plausible, none real.

The fix is not only in the screen. **An API that returns a shaped-looking empty
result invites exactly that.** So nothing here ever substitutes a placeholder
for a fact it does not have:

* a digest that was never computed is ``null``, never a zero hash and never a
  hash of nothing;
* a size nobody measured is ``null``, never ``0`` and never a round number;
* an Evidence id that does not exist is ``null``, and the field explaining why
  is beside it;
* "verified" is only ever true when something verified it — an artifact with a
  digest and no ``verified_at`` is recorded, not promoted.

Every absent value carries a ``reason``. A screen that cannot tell "no result
yet" from "result with nothing in it" will eventually show one as the other, and
the one time that matters is when somebody is deciding whether a job really ran.

**On agreement with the kernel.** The Run, the Evidence and the binding are read
from the rows the execution side writes — ``public.execution_bindings`` is
Codex's table and this side has SELECT on it and nothing more. So "the screen
and the API return the same Run and Evidence" is true because there is one copy,
not because two are kept in step.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..db.models import (
    Artifact,
    EvidenceEnvelope,
    Run,
    RunAttempt,
    RunRecord,
    RunRecordArtifact,
)
from ..errors import RES_NODE_NOT_FOUND, InvError
from . import projects as project_service


def _absent(reason: str) -> dict[str, Any]:
    """A value that is not there, said so that nothing can render it as a value."""
    return {"value": None, "reason": reason}


def run_result(
    session: Session, *, tenant_id: uuid.UUID, run_id: str, user_id: str
) -> dict[str, Any]:
    """Everything known about one Run's outcome, with the gaps named.

    Reads the Run first and authorises against its project, so a caller cannot
    learn a Run exists in a project they cannot see.
    """
    run = session.get(Run, run_id)
    if run is None or run.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "run not found")

    workspace_project = _project_of(session, tenant_id=tenant_id, run=run)
    project_service.require_project_access(
        session, tenant_id=tenant_id, project_id=workspace_project, user_id=user_id
    )

    record = session.scalars(
        select(RunRecord).where(
            RunRecord.tenant_id == tenant_id, RunRecord.run_id == run_id
        )
    ).one_or_none()
    evidence = session.scalars(
        select(EvidenceEnvelope)
        .where(
            EvidenceEnvelope.tenant_id == tenant_id,
            EvidenceEnvelope.run_id == run_id,
        )
        .order_by(EvidenceEnvelope.recorded_at.desc())
    ).first()

    body: dict[str, Any] = {
        "runId": run.run_id,
        "projectId": workspace_project,
        "state": run.state,
        "attemptCount": run.attempt_count,
        "terminationReason": run.termination_reason,
        "sealed": record is not None,
    }

    if record is None:
        # Not an empty record. A Run with no sealed record has not finished, or
        # finished without being sealed — and a screen must be able to tell that
        # from a record whose fields happen to be empty.
        body["record"] = None
        body["recordAbsent"] = _absent(
            "this Run has no sealed record yet; a record is written when the Run "
            "reaches a terminal state"
        )
    else:
        body["record"] = {
            "recordId": record.record_id,
            "finalState": record.final_state,
            "terminationReason": record.termination_reason,
            "workloadSpecSha256": record.workload_spec_sha256,
            "componentVersions": record.component_versions,
            "attemptCount": record.attempt_count,
            "sealedAt": record.sealed_at.isoformat(),
            # Present or explicitly absent. Never a placeholder digest.
            "bundleHash": record.bundle_hash,
            "bundleHashAbsent": (
                None
                if record.bundle_hash
                else _absent("no context bundle was pinned into this record")
            ),
        }

    if evidence is None:
        body["evidence"] = None
        body["evidenceAbsent"] = _absent(
            "no Evidence has been recorded for this Run"
        )
    else:
        body["evidence"] = {
            "evidenceId": evidence.evidence_id,
            "action": evidence.action,
            "result": evidence.result,
            "inputSha256": evidence.input_sha256,
            # The output is referenced, not inlined. A reference that is absent
            # is absent; it is never rendered as an empty result.
            "outputRef": evidence.output_ref,
            "outputRefAbsent": (
                None
                if evidence.output_ref
                else _absent("this Evidence records no output reference")
            ),
            "componentVersions": evidence.component_versions,
            "recordedAt": evidence.recorded_at.isoformat(),
        }

    body["binding"] = _binding(session, tenant_id=tenant_id, run_id=run_id)
    return body


def _project_of(session: Session, *, tenant_id: uuid.UUID, run: Run) -> str:
    """The project a Run belongs to, through its workspace.

    Resolved rather than taken from a caller-supplied parameter: a Run's project
    is what decides who may read its result, so it must not be something the
    request can choose.
    """
    from ..db.models import Workspace

    workspace = session.get(Workspace, run.workspace_id)
    if workspace is None or workspace.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "run not found")
    return workspace.project_id


def _binding(
    session: Session, *, tenant_id: uuid.UUID, run_id: str
) -> dict[str, Any] | None:
    """The execution handoff record, if the kernel made one.

    Read from ``public.execution_bindings``, which the execution side owns and
    this side may only SELECT. One copy, so the screen and the kernel cannot
    disagree about which approval and which epoch a Run ran under.
    """
    row = session.execute(
        text(
            "SELECT binding_id, approval_id, recovery_epoch, bound_run_version, "
            "created_at FROM public.execution_bindings "
            "WHERE tenant_id = :t AND run_id = :r "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"t": str(tenant_id), "r": run_id},
    ).one_or_none()
    if row is None:
        return None
    return {
        "bindingId": str(row[0]),
        "approvalId": row[1],
        "recoveryEpoch": str(row[2]),
        "boundRunVersion": row[3],
        "createdAt": row[4].isoformat(),
    }


def list_artifacts(
    session: Session, *, tenant_id: uuid.UUID, run_id: str, user_id: str
) -> list[dict[str, Any]]:
    """The files a Run produced, with unverified ones visibly unverified.

    ``verified`` is true only when something verified it. An artifact that
    carries a digest but was never checked is the one a screen is most likely to
    present as confirmed, because it looks complete.
    """
    run = session.get(Run, run_id)
    if run is None or run.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "run not found")
    project_service.require_project_access(
        session,
        tenant_id=tenant_id,
        project_id=_project_of(session, tenant_id=tenant_id, run=run),
        user_id=user_id,
    )

    artifacts = session.scalars(
        select(Artifact)
        .where(
            Artifact.tenant_id == tenant_id,
            Artifact.run_id == run_id,
            Artifact.deleted_at.is_(None),
        )
        .order_by(Artifact.name)
    ).all()

    pinned = {
        artifact_id
        for artifact_id in session.scalars(
            select(RunRecordArtifact.artifact_id).where(
                RunRecordArtifact.tenant_id == tenant_id
            )
        ).all()
    }

    out = []
    for artifact in artifacts:
        body: dict[str, Any] = {
            "artifactId": artifact.artifact_id,
            "name": artifact.name,
            "mediaType": artifact.media_type,
            "status": artifact.status,
            "objectVersion": artifact.object_version,
            "pinnedIntoRecord": artifact.artifact_id in pinned,
            # Only true when something verified it.
            "verified": artifact.verified_at is not None,
            "verifiedAt": (
                artifact.verified_at.isoformat() if artifact.verified_at else None
            ),
            "createdAt": artifact.created_at.isoformat(),
        }
        if artifact.checksum_sha256:
            body["checksumSha256"] = artifact.checksum_sha256
        else:
            body["checksumSha256"] = None
            body["checksumAbsent"] = _absent(
                "no digest has been computed for this artifact"
            )
        # A size of zero is a real size; a size nobody measured is not. They are
        # reported differently because a screen showing a confident number for a
        # file that was never written is the defect this API exists to prevent.
        #
        # The signal is "no bytes and no digest": the schema already refuses an
        # `active` artifact without both a digest and a verification
        # (``active_requires_verification``), so a digest at any status means
        # something read the bytes and the size is real even when it is zero.
        if artifact.byte_size == 0 and artifact.checksum_sha256 is None:
            body["byteSize"] = None
            body["byteSizeAbsent"] = _absent(
                "this artifact is still staging and its size is not final"
            )
        else:
            body["byteSize"] = artifact.byte_size
        out.append(body)
    return out


def attempt_log(
    session: Session, *, tenant_id: uuid.UUID, run_id: str, user_id: str
) -> list[dict[str, Any]]:
    """What happened, attempt by attempt.

    The closest thing to a log this side holds. Actual process output lives with
    the node and is collected through the adapter; what is here is the record of
    each attempt — which is the part that survives a machine being turned off.
    """
    run = session.get(Run, run_id)
    if run is None or run.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "run not found")
    project_service.require_project_access(
        session,
        tenant_id=tenant_id,
        project_id=_project_of(session, tenant_id=tenant_id, run=run),
        user_id=user_id,
    )
    attempts = session.scalars(
        select(RunAttempt)
        .where(RunAttempt.tenant_id == tenant_id, RunAttempt.run_id == run_id)
        .order_by(RunAttempt.attempt_number)
    ).all()
    return [
        {
            "attemptId": attempt.attempt_id,
            "attemptNumber": attempt.attempt_number,
            "outcome": attempt.outcome,
            "nodeId": attempt.node_id,
            "startedAt": attempt.started_at.isoformat() if attempt.started_at else None,
            "endedAt": attempt.ended_at.isoformat() if attempt.ended_at else None,
            "errorCode": attempt.error_code,
            "fenceToken": attempt.fence_token,
            "policyVersion": attempt.policy_version,
        }
        for attempt in attempts
    ]
