"""Hosted product S3 adapter with real migrated PostgreSQL and RLS.

This file is intentionally excluded from the ordinary Core collection because
it requires both disposable PostgreSQL and the digest-pinned MinIO service.  The
``s01-storage-roundtrip`` job owns those dependencies and executes it directly.
"""

from __future__ import annotations

import hashlib
import os
from uuid import uuid4

import psycopg
import pytest

from inv.s3_client import S3Client, S3Config
from inv.s3_object_store import S3Objects
from inv.snapshots import SnapshotStore

pytestmark = pytest.mark.postgres


def _provider(prefix: str) -> S3Objects:
    required = (
        "INV_OBJECT_STORE_ENDPOINT",
        "INV_OBJECT_STORE_BUCKET",
        "INV_OBJECT_STORE_ACCESS_KEY_ID",
        "INV_OBJECT_STORE_SECRET_ACCESS_KEY",
        "INV_OBJECT_STORE_REGION",
    )
    missing = [name for name in required if not os.environ.get(name)]
    assert not missing, "Hosted S3/PostgreSQL lane configuration is incomplete"
    client = S3Client(
        S3Config(
            endpoint=os.environ["INV_OBJECT_STORE_ENDPOINT"],
            bucket=os.environ["INV_OBJECT_STORE_BUCKET"],
            access_key=os.environ["INV_OBJECT_STORE_ACCESS_KEY_ID"],
            secret_key=os.environ["INV_OBJECT_STORE_SECRET_ACCESS_KEY"],
            region=os.environ["INV_OBJECT_STORE_REGION"],
        )
    )
    return S3Objects("s3-compatible-v1", prefix, client)


def test_snapshot_store_persists_s3_locator_and_rls_hides_it_from_other_tenant(env):
    data = b"hosted product s3 persistence"
    digest = hashlib.sha256(data).hexdigest()
    object_id = str(uuid4())
    provider = _provider("hosted/" + uuid4().hex)
    store = SnapshotStore(env.db, provider)

    with psycopg.connect(env.owner) as owner:
        owner.execute(
            "INSERT INTO inv.storage_budgets VALUES(%s,%s,%s)",
            (env.tenant, env.project, len(data) * 4),
        )

    store.begin(env.tenant, env.project, object_id, digest, len(data))
    store.put_part(env.tenant, env.project, object_id, 0, data)
    assert store.finalize(env.tenant, env.project, object_id) == digest

    with env.db.transaction(env.tenant) as connection:
        row = connection.execute(
            """SELECT provider_id,locator,content_hash,size_bytes,state
            FROM inv.storage_objects WHERE project_id=%s AND object_id=%s""",
            (env.project, object_id),
        ).fetchone()
    assert row["provider_id"] == "s3-compatible-v1"
    assert row["content_hash"] == digest
    assert row["size_bytes"] == len(data) and row["state"] == "ready"
    assert f"/tenants/{env.tenant}/projects/{env.project}/" in "/" + row["locator"]
    assert provider.get(row["locator"], digest, len(data)) == data

    # The other application tenant cannot discover the locator and therefore
    # cannot use the provider as an authority bypass.
    with env.db.transaction(env.other) as connection:
        assert (
            connection.execute(
                "SELECT locator FROM inv.storage_objects WHERE object_id=%s",
                (object_id,),
            ).fetchone()
            is None
        )

    store.collect(env.tenant, env.project, object_id)
    assert provider.exists(row["locator"]) is False
