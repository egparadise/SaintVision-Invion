"""Project-scoped public certificate observations; never execution authority.

This read model uses the kernel's persisted, current-epoch Node channel metadata.
It exposes no issuer, endpoint, fingerprint, private material, or pilot state.
The two-day renewal window is advisory and does not claim scheduler registration.
"""

from datetime import timedelta, timezone
import math

from .contracts import validate_contract

MAX_NODES = 200
RENEWAL_WINDOW = timedelta(days=2)


def certificate_summary(items, observed_at, *, complete):
    unknown = {
        'state': 'unknown', 'earliestCertificateNotAfter': None,
        'renewalWindowStartsAt': None, 'secondsUntilEarliestExpiry': None,
    }
    if not complete or not items or any(
        item['channelEnabled'] is not True or item['certificateNotAfter'] is None
        for item in items
    ):
        return unknown
    from datetime import datetime

    earliest = min(datetime.fromisoformat(item['certificateNotAfter']) for item in items)
    starts = earliest - RENEWAL_WINDOW
    state = 'expired' if earliest <= observed_at else (
        'renewal-window' if starts <= observed_at else 'ok'
    )
    return {
        'state': state,
        'earliestCertificateNotAfter': earliest.isoformat(),
        'renewalWindowStartsAt': starts.isoformat(),
        'secondsUntilEarliestExpiry': math.floor((earliest - observed_at).total_seconds()),
    }


def serve(control, principal, project):
    with control.db.transaction(principal.tenant_id) as conn:
        # The existing project grant precedes every metadata query.
        control.grant(conn, principal, project)
        observed_at = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        rows = conn.execute(
            '''SELECT n.node_id,c.certificate_not_after,c.enabled AS channel_enabled
            FROM inv.nodes n JOIN inv.project_nodes p USING(tenant_id,node_id)
            LEFT JOIN inv.node_channels c ON c.tenant_id=n.tenant_id AND c.node_id=n.node_id
                AND c.recovery_epoch=n.recovery_epoch AND c.recovery_epoch=%s::uuid
            WHERE p.project_id=%s AND p.enabled ORDER BY n.node_id LIMIT 201''',
            (control.db.recovery_epoch, project),
        ).fetchall()
        complete = len(rows) <= MAX_NODES
        items = [
            {
                'nodeId': row['node_id'],
                'certificateNotAfter': row['certificate_not_after'].astimezone(timezone.utc).isoformat()
                if row['certificate_not_after'] is not None else None,
                'channelEnabled': row['channel_enabled'],
            }
            for row in rows[:MAX_NODES]
        ]
        response = {
            'source': 'execution-kernel', 'scope': 'project-node-certificates',
            'projectId': project,
            'observedAt': observed_at.astimezone(timezone.utc).isoformat(),
            'complete': complete, 'items': items,
            'trust': certificate_summary(items, observed_at, complete=complete),
        }
        validate_contract("ProjectNodeCertificateObservationResponse", response)
        return response
