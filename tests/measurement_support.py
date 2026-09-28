"""A kernel-recorded model measurement, stood in for by the owner (0054).

``inv.model_version_measurements`` is written only by the kernel's accept path
(``node-model-measure-v1``, design #209 v1.1). Tests of the application side --
verification, release, mirroring -- need such a row to exist and have no
kernel to ask, so they insert one as the schema owner, exactly as
``two_tenants`` seeds tenants outside RLS. The application role cannot do
this, nor even name the table (``test_model_version_measurements_real_pg``
shows both refusals), which is the point: a test that could mint its own
measurement through the application would prove nothing about the seam.

Three entry points, one row shape: ``record_measurement`` (an engine, its own
transaction), ``insert_measurement`` (an open SQLAlchemy connection) and
``insert_measurement_psycopg`` (an open psycopg connection). Every one sets
the tenant GUC first, because the table forces row security on the owner too.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid

from sqlalchemy import text

from saintvision.ids import new_id

COLUMNS = (
    "tenant_id", "measurement_id", "request_id", "project_id", "model_version_id", "uri",
    "contribution_id", "contribution_version", "location_id", "location_version", "relative_path",
    "node_id", "recovery_epoch", "channel_version", "certificate_sha256",
    "sha256", "byte_size", "observed_at", "recorded_at", "challenge_sha256", "response_sha256", "duration_seconds",
)


def measurement_values(
    *,
    tenant_id,
    model_version_id: str,
    sha256: str,
    byte_size: int = 0,
    project_id: str | None = None,
    uri: str | None = None,
    observed_at: dt.datetime | None = None,
    request_id: uuid.UUID | None = None,
    location_id: str | None = None,
    contribution_id: str | None = None,
    node_id: str | None = None,
    relative_path: str = "weights.safetensors",
) -> dict:
    """One measurement row's values, with a fresh measurement id."""
    measurement_id = new_id("model_measurement")
    observed = observed_at or dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
    salt = measurement_id.encode()
    return {
        "tenant_id": tenant_id,
        "measurement_id": measurement_id,
        "request_id": request_id or uuid.uuid4(),
        "project_id": project_id or new_id("project"),
        "model_version_id": model_version_id,
        "uri": uri or f"inv://models/measured@{model_version_id[-8:]}",
        "contribution_id": contribution_id or new_id("storage_contribution"),
        "contribution_version": 1,
        "location_id": location_id or new_id("data_location"),
        "location_version": 1,
        "relative_path": relative_path,
        "node_id": node_id or new_id("node"),
        "recovery_epoch": uuid.uuid4(),
        "channel_version": 1,
        "certificate_sha256": hashlib.sha256(b"leaf" + salt).hexdigest(),
        "sha256": sha256,
        "byte_size": byte_size,
        "observed_at": observed,
        "recorded_at": observed + dt.timedelta(milliseconds=250),
        "challenge_sha256": hashlib.sha256(b"challenge" + salt).hexdigest(),
        "response_sha256": hashlib.sha256(b"response" + salt).hexdigest(),
        "duration_seconds": 0.25,
    }


_INSERT = text(
    "INSERT INTO inv.model_version_measurements (" + ", ".join(COLUMNS) + ") VALUES ("
    + ", ".join(f":{column}" for column in COLUMNS) + ")"
)


def insert_measurement(connection, **kwargs) -> str:
    """Insert on an open SQLAlchemy connection (the owner's) and return the id."""
    values = measurement_values(**kwargs)
    connection.execute(text("SELECT set_config('inv.tenant_id', :t, true)"), {"t": str(values["tenant_id"])})
    connection.execute(_INSERT, values)
    return values["measurement_id"]


def insert_measurement_psycopg(conn, **kwargs) -> str:
    """The same, on an open psycopg connection (the kernel-side harness)."""
    values = measurement_values(**kwargs)
    conn.execute("SELECT set_config('inv.tenant_id', %s, true)", (str(values["tenant_id"]),))
    conn.execute(
        "INSERT INTO inv.model_version_measurements (" + ", ".join(COLUMNS) + ") VALUES ("
        + ", ".join(["%s"] * len(COLUMNS)) + ")",
        tuple(values[column] for column in COLUMNS),
    )
    return values["measurement_id"]


def record_measurement(owner_engine, **kwargs) -> str:
    """Insert in the owner's own transaction and return the measurement id.

    Committed on return, so a caller mid-transaction on the application session
    reads it through the tenant-bound reader.
    """
    with owner_engine.begin() as connection:
        return insert_measurement(connection, **kwargs)
