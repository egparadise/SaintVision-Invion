"""Atomic business projection for a kernel-owned user cancellation.

The execution kernel remains the authority. This helper is called only after
the current request moved ``inv.runs`` to ``cancelled`` and in the same
transaction. The database primitive re-checks that fact, derives the business
user from the authenticated subject, and writes the public state and audit row
without granting either table to the kernel role.
"""

from __future__ import annotations

import re

from .errors import DomainError
from .ids import new_id


TRACE_ID = re.compile(r"^[0-9a-f]{32}$")


def record_user_cancel(conn, principal, project: str, run_id: str, trace_id: str) -> bool:
    """Mirror one actual kernel transition; return whether public state changed.

    An unmapped kernel run is deliberately not a business error. Everything
    after the mapping check is fail-closed and is enforced again inside the
    SECURITY DEFINER function.
    """

    if not isinstance(trace_id, str) or TRACE_ID.fullmatch(trace_id) is None:
        raise DomainError("SYS-0001", "Request correlation is unavailable", 503)
    mapped = conn.execute(
        "SELECT 1 FROM inv.business_runs WHERE project_id=%s AND run_id=%s",
        (project, run_id),
    ).fetchone()
    if not mapped:
        return False
    row = conn.execute(
        """SELECT public.record_kernel_run_cancel(
             p_subject_id => %s,
             p_project_id => %s,
             p_run_id => %s,
             p_event_id => %s,
             p_trace_id => %s
           ) AS recorded""",
        (principal.subject_id, project, run_id, new_id("aud"), trace_id),
    ).fetchone()
    if row is None or type(row.get("recorded")) is not bool:
        raise DomainError("SYS-0001", "Cancellation audit bridge is unavailable", 503)
    return row["recorded"]
