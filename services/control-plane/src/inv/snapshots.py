"""Resumable publication and fenced checkpoint attachment over a local provider.

Internal trusted adapter API: tenant/project authorization belongs to its caller.
Lock order: provider -> budget (quota operations) OR Run -> fences -> object.
Published files precede metadata; failed DB commits leave recoverable files.
Deletion tombstones precede unlink; quota is released only after durable unlink.
"""

import hashlib
import json
import re
from uuid import UUID, uuid5, NAMESPACE_URL
from psycopg.types.json import Jsonb
from .errors import DomainError
from .leases import lock_run, assert_fences
from .object_store import (
    LOCAL_PROVIDER_ID,
    MAX_BYTES,
    PART_BYTES,
    ObjectStoreRegistry,
    object_store_session,
    provider_id,
    registered_provider,
    require_object_provider,
)
from .runs import event


def identity(value):
    return str(UUID(str(value)))


def object_key(value):
    return "obj-" + UUID(str(value)).hex


def part_key(value, index):
    return "part-" + UUID(str(value)).hex + "-" + str(index)


def checkpoint_content(row):
    """Public immutable checkpoint identity; provider locator stays private."""

    return {
        "objectId": identity(row["object_id"]),
        "sha256": row["content_hash"],
        "sizeBytes": row["size_bytes"],
        "provider": row["provider_id"],
    }


def checkpoint_digest(content):
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def attach_checkpoint(
    conn,
    *,
    tenant,
    project,
    run_id,
    attempt,
    step_id,
    object_id,
    content,
    event_name,
    event_payload,
):
    """Attach immutable content once; identical replay is quiet, drift is rejected."""

    content_hash = checkpoint_digest(content)
    prior = conn.execute(
        "SELECT content_hash FROM inv.checkpoints " "WHERE run_id=%s AND attempt=%s AND step_id=%s",
        (run_id, attempt, step_id),
    ).fetchone()
    if prior and prior["content_hash"] != content_hash:
        raise DomainError("GRAPH-0004", "Checkpoint identity already has different content")
    if not prior:
        conn.execute(
            "INSERT INTO inv.checkpoints"
            "(tenant_id,run_id,attempt,step_id,content_hash,checkpoint) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (tenant, run_id, attempt, step_id, content_hash, Jsonb(content)),
        )
        event(conn, tenant, run_id, event_name, event_payload(content_hash))
    conn.execute(
        "INSERT INTO inv.checkpoint_objects VALUES(%s,%s,%s,%s,%s,%s) " "ON CONFLICT DO NOTHING",
        (tenant, project, run_id, attempt, step_id, identity(object_id)),
    )
    return content


class SnapshotStore:
    def __init__(self, database, provider, object_stores=None):
        self.db, self.provider = database, provider
        self.provider_id = provider_id(provider)
        self.object_stores = object_stores or ObjectStoreRegistry([registered_provider(provider)])

    def _writer(self, row):
        return require_object_provider(self.provider, row)

    def _reader(self, row):
        return self.object_stores.resolve(row["provider_id"])

    def _new_locator(self, tenant, project, object_id, namespace="objects"):
        if self.provider_id == LOCAL_PROVIDER_ID:
            return object_key(object_id)
        locator = getattr(self.provider, "locator", None)
        if locator is None:
            raise DomainError("STORE-0001", "Object provider has no locator factory", 503)
        return locator(tenant, project, namespace, identity(object_id))

    def _part_locator(self, tenant, project, object_id, index):
        if self.provider_id == LOCAL_PROVIDER_ID:
            return part_key(object_id, index)
        part_id = uuid5(
            NAMESPACE_URL,
            f"inv.storage-part:{tenant}:{project}:{identity(object_id)}:{index}",
        )
        return self._new_locator(tenant, project, part_id, "objects")

    @staticmethod
    def _row(conn, project, object_id):
        row = conn.execute(
            "SELECT * FROM inv.storage_objects WHERE project_id=%s AND object_id=%s FOR UPDATE",
            (project, identity(object_id)),
        ).fetchone()
        if not row:
            raise DomainError("RES-0004", "Object not found", 404)
        return row

    def begin(self, tenant, project, object_id, digest, size):
        object_id = identity(object_id)
        locator = self._new_locator(tenant, project, object_id)
        if (
            not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or type(size) is not int
            or not 0 <= size <= MAX_BYTES
        ):
            raise DomainError("VAL-0013", "Invalid bounded upload", 422)
        with object_store_session(self.provider), self.db.transaction(tenant) as conn:
            budget = conn.execute(
                "SELECT quota_bytes FROM inv.storage_budgets WHERE project_id=%s FOR UPDATE",
                (project,),
            ).fetchone()
            if not budget:
                raise DomainError("STORE-0004", "Explicit project storage budget required", 403)
            row = conn.execute(
                "SELECT * FROM inv.storage_objects WHERE project_id=%s AND object_id=%s",
                (project, object_id),
            ).fetchone()
            if row:
                if (
                    (row["content_hash"], row["size_bytes"]) != (digest, size)
                    or (row["provider_id"], row["locator"]) != (self.provider_id, locator)
                    or row["state"] in {"deleting", "deleted"}
                ):
                    raise DomainError("IDEM-0001", "Upload identity conflicts")
                return object_id
            used = conn.execute(
                "SELECT coalesce(sum(size_bytes),0) AS used FROM inv.storage_objects WHERE project_id=%s AND state<>'deleted'",
                (project,),
            ).fetchone()["used"]
            if used + size > budget["quota_bytes"]:
                raise DomainError("RES-0001", "Storage quota exhausted")
            conn.execute(
                """INSERT INTO inv.storage_objects
                (tenant_id,project_id,object_id,provider_id,locator,content_hash,size_bytes)
                VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (tenant, project, object_id, self.provider_id, locator, digest, size),
            )
        return object_id

    def put_part(self, tenant, project, object_id, index, data, *, authorize=None):
        if (
            type(index) is not int
            or not 0 <= index < 4
            or not isinstance(data, bytes)
            or not 0 < len(data) <= PART_BYTES
        ):
            raise DomainError("VAL-0013", "Invalid upload part", 422)
        digest = hashlib.sha256(data).hexdigest()
        with object_store_session(self.provider) as files, self.db.transaction(tenant) as conn:
            if authorize is not None:
                authorize(conn)
            row = self._row(conn, project, object_id)
            self._writer(row)
            if row["state"] != "uploading" or len(data) != min(
                PART_BYTES, row["size_bytes"] - index * PART_BYTES
            ):
                raise DomainError("STORE-0005", "Upload part does not fit current manifest")
            prior = conn.execute(
                "SELECT content_hash FROM inv.storage_parts WHERE project_id=%s AND object_id=%s AND part_index=%s",
                (project, identity(object_id), index),
            ).fetchone()
            if prior and prior["content_hash"] != digest:
                raise DomainError("IDEM-0001", "Upload part already has different bytes")
            files.put(self._part_locator(tenant, project, object_id, index), data, digest)
            conn.execute(
                "INSERT INTO inv.storage_parts VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (tenant, project, identity(object_id), index, digest, len(data)),
            )
        return digest

    def status(self, tenant, project, object_id):
        with self.db.transaction(tenant) as conn:
            row = self._row(conn, project, object_id)
            parts = conn.execute(
                "SELECT part_index,content_hash,size_bytes FROM inv.storage_parts WHERE project_id=%s AND object_id=%s ORDER BY part_index",
                (project, identity(object_id)),
            ).fetchall()
            return {
                "objectId": identity(object_id),
                "state": row["state"],
                "sha256": row["content_hash"],
                "sizeBytes": row["size_bytes"],
                "parts": parts,
            }

    def finalize(self, tenant, project, object_id, *, authorize=None):
        with object_store_session(self.provider) as files, self.db.transaction(tenant) as conn:
            if authorize is not None:
                authorize(conn)
            row = self._row(conn, project, object_id)
            self._writer(row)
            if row["state"] not in {"uploading", "ready"}:
                raise DomainError("STORE-0005", "Object is unavailable")
            if row["state"] == "ready":
                files.get(row["locator"], row["content_hash"], row["size_bytes"])
                return row["content_hash"]
            parts = conn.execute(
                "SELECT * FROM inv.storage_parts WHERE project_id=%s AND object_id=%s ORDER BY part_index",
                (project, identity(object_id)),
            ).fetchall()
            count = (row["size_bytes"] + PART_BYTES - 1) // PART_BYTES
            if [part["part_index"] for part in parts] != list(range(count)):
                raise DomainError("STORE-0006", "Upload has missing parts")
            data = b"".join(
                files.get(
                    self._part_locator(tenant, project, object_id, p["part_index"]),
                    p["content_hash"],
                    p["size_bytes"],
                )
                for p in parts
            )
            if len(data) != row["size_bytes"]:
                raise DomainError("VERIFY-0010", "Assembled size differs", 422)
            files.put(row["locator"], data, row["content_hash"])
            conn.execute(
                "UPDATE inv.storage_objects SET state='ready' WHERE project_id=%s AND object_id=%s",
                (project, identity(object_id)),
            )
            # Parts remain available for crash reconciliation until explicit GC.
            return row["content_hash"]

    def checkpoint(self, tenant, run_id, step_id, object_id, *, proofs):
        if not isinstance(step_id, str) or not 1 <= len(step_id) <= 200:
            raise DomainError("VAL-0003", "Invalid step ID", 422)
        with object_store_session(self.provider) as files, self.db.transaction(tenant) as conn:
            run = lock_run(conn, run_id)
            if run["state"] != "running":
                raise DomainError("GRAPH-0002", "Checkpoint requires running attempt")
            assert_fences(conn, run_id, proofs)
            row = self._row(conn, run["project_id"], object_id)
            self._writer(row)
            if row["state"] != "ready":
                raise DomainError("STORE-0005", "Checkpoint requires published content")
            files.get(row["locator"], row["content_hash"], row["size_bytes"])
            content = checkpoint_content(row)
            return attach_checkpoint(
                conn,
                tenant=tenant,
                project=run["project_id"],
                run_id=run_id,
                attempt=run["attempt"],
                step_id=step_id,
                object_id=object_id,
                content=content,
                event_name="inv.run.checkpoint_published",
                event_payload=lambda content_hash: {
                    "attempt": run["attempt"],
                    "stepId": step_id,
                    "contentHash": content_hash,
                },
            )

    def restore(self, tenant, project, run_id, attempt, step_id):
        # Returns verified bytes to a trusted workspace adapter. It never extracts
        # an archive, accepts a browser filesystem path or starts a process.
        # Read provider identity without holding a provider lock, then acquire
        # provider -> DB and revalidate the immutable row before byte access.
        with self.db.transaction(tenant) as conn:
            pin = conn.execute(
                "SELECT object_id FROM inv.checkpoint_objects WHERE project_id=%s AND run_id=%s AND attempt=%s AND step_id=%s",
                (project, run_id, attempt, step_id),
            ).fetchone()
            if not pin:
                raise DomainError("RES-0004", "Checkpoint object not found", 404)
            row = self._row(conn, project, pin["object_id"])
            provider = self._reader(row)
        with object_store_session(provider) as files, self.db.transaction(tenant) as conn:
            row = self._row(conn, project, pin["object_id"])
            require_object_provider(files, row)
            if row["state"] != "ready":
                raise DomainError("STORE-0005", "Checkpoint object unavailable")
            return files.get(row["locator"], row["content_hash"], row["size_bytes"])

    def collect(self, tenant, project, object_id):
        with object_store_session(self.provider) as files:
            with self.db.transaction(tenant) as conn:
                conn.execute(
                    "SELECT quota_bytes FROM inv.storage_budgets WHERE project_id=%s FOR UPDATE",
                    (project,),
                ).fetchone()
                row = self._row(conn, project, object_id)
                self._writer(row)
                if conn.execute(
                    "SELECT 1 FROM inv.checkpoint_objects WHERE project_id=%s AND object_id=%s",
                    (project, identity(object_id)),
                ).fetchone():
                    raise DomainError("STORE-0007", "Checkpoint retains this object")
                if conn.execute(
                    "SELECT 1 FROM inv.result_commitments WHERE project_id=%s AND object_id=%s",
                    (project, identity(object_id)),
                ).fetchone():
                    raise DomainError("STORE-0007", "Execution result retains this object")
                if row["state"] == "deleted":
                    return
                # Operators decide retention before requesting collection. There
                # is deliberately no filesystem scan or automatic user-file GC.
                conn.execute(
                    "UPDATE inv.storage_objects SET state='deleting' WHERE project_id=%s AND object_id=%s",
                    (project, identity(object_id)),
                )
            files.delete(row["locator"])
            for index in range(4):
                files.delete(self._part_locator(tenant, project, object_id, index))
            with self.db.transaction(tenant) as conn:
                self._row(conn, project, object_id)
                conn.execute(
                    "UPDATE inv.storage_objects SET state='deleted' WHERE project_id=%s AND object_id=%s",
                    (project, identity(object_id)),
                )
