"""Path-to-row binding for run-scoped business routes (G-04 design v1.1 §3).

``runs`` has no ``project_id``; a run belongs to a project through its
workload (``runs.workload_id`` -> ``workloads.project_id``). Every route whose
path is ``/projects/{project_id}/runs/{run_id}/...`` binds the path's project
to the run through that parent, in one place, with one answer for every way
the binding can fail: absent run, another tenant's run, another project's run
and a run whose workload is gone are all the same ``RES-0004``. Distinguishing
them would let a path variable probe for existence, which
``require_project_access`` already refuses for projects.

This is the run counterpart of ``lineage_query._version_in_project``. It reads
only -- no ``FOR UPDATE`` -- because the read routes change nothing; the
sealing write (W1) locks the row itself under its own Codex contract.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from ...db.models.execution import Run, Workload
from ..problem import RES_NOT_FOUND, CanonicalProblem

NO_SUCH_RUN = "No such run."


def run_in_project(
    session: Session, *, tenant_id: uuid.UUID, project_id: str, run_id: str
) -> Run:
    """Resolve ``(project, run)`` to one ``Run`` row through its workload, or 404."""
    run = session.get(Run, run_id, populate_existing=True)
    if run is None or run.tenant_id != tenant_id:
        raise CanonicalProblem(RES_NOT_FOUND, 404, NO_SUCH_RUN)
    workload = session.get(Workload, run.workload_id, populate_existing=True)
    if (
        workload is None
        or workload.tenant_id != tenant_id
        or workload.project_id != project_id
    ):
        raise CanonicalProblem(RES_NOT_FOUND, 404, NO_SUCH_RUN)
    return run
