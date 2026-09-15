"""Owner-scoped recorded replica counts, never an execution eligibility proof."""

from sqlalchemy import and_, func, select

from ..db.models.locality import DataReplica
from ..db.models.storage import DataLocation, StorageContribution
from ..errors import InvError, RES_ARTIFACT_NOT_FOUND
from ..storage.pathsafe import parse_uri


def observe_replicas(session, *, tenant_id, reader_user_id, uri):
    parse_uri(uri)
    # One statement binds the access gate and every count to the same snapshot.
    # At most five state rows (or one empty outer-join row) cross the DB boundary.
    rows = session.execute(
        select(
            DataLocation.location_id, DataLocation.version,
            func.statement_timestamp(), DataReplica.state,
            func.count(DataReplica.replica_id),
        )
        .join(StorageContribution, and_(
            StorageContribution.tenant_id == DataLocation.tenant_id,
            StorageContribution.contribution_id == DataLocation.contribution_id,
        ))
        .outerjoin(DataReplica, and_(
            DataReplica.tenant_id == DataLocation.tenant_id,
            DataReplica.location_id == DataLocation.location_id,
        ))
        .where(
            DataLocation.tenant_id == tenant_id, DataLocation.uri == uri,
            StorageContribution.registered_by_user_id == reader_user_id,
            StorageContribution.status == "active",
        )
        .group_by(DataLocation.location_id, DataLocation.version, DataReplica.state)
    ).all()
    if not rows:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "data location not found", status=404)
    counts = dict.fromkeys(("ready", "transferring", "stale", "corrupt", "evicted"), 0)
    for _, _, _, state, count in rows:
        if state is not None:
            counts[state] = count
    location_id, version, observed_at, _, _ = rows[0]
    return {
        "locationId": location_id,
        "locationVersion": version,
        "observedAt": observed_at.isoformat(),
        "recordedStates": counts,
        "totalRecords": sum(counts.values()),
        "currentAvailability": "unknown",
        "requiresExecutionRevalidation": True,
    }
