"""A kernel-recorded model measurement, stood in for by the owner (0054).

``inv.model_version_measurements`` is written only by the kernel's accept path
(``node-model-measure-v1``, design #209 v1.1). Tests of the application side --
verification, release, mirroring -- need such a row to exist and have no
kernel to ask, so they insert one as the schema owner, exactly as
``two_tenants`` seeds tenants outside RLS. The application role cannot do
this (``test_model_version_measurements_real_pg`` shows the refusal), which
is the point: a test that could mint its own measurement through the
application would prove nothing about the seam.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid

from sqlalchemy import text

from saintvision.ids import new_id

_INSERT = text(
    "INSERT INTO inv.model_version_measurements ("
    " tenant_id, measurement_id, request_id, project_id, model_version_id, uri,"
    " contribution_id, contribution_version, location_id, location_version, relative_path,"
    " node_id, recovery_epoch, channel_version, certificate_sha256,"
    " sha256, byte_size, observed_at, recorded_at, challenge_sha256, response_sha256, duration_seconds"
    ") VALUES ("
    " :tenant_id, :measurement_id, :request_id, :project_id, :model_version_id, :uri,"
    " :contribution_id, 1, :location_id, 1, :relative_path,"
    " :node_id, :recovery_epoch, 1, :certificate_sha256,"
    " :sha256, :byte_size, :observed_at, :recorded_at, :challenge_sha256, :response_sha256, 0.25"
    ")"
)


def record_measurement(
    owner_engine,
    *,
    tenant_id,
    model_version_id: str,
    sha256: str,
    byte_size: int = 0,
    project_id: str | None = None,
    uri: str | None = None,
    observed_at: dt.datetime | None = None,
    request_id: uuid.UUID | None = None,
) -> str:
    """Insert one measurement of ``model_version_id`` and return its id.

    Committed in its own owner transaction, so a caller mid-transaction on the
    application session sees it through RLS with its tenant scope.
    """
    measurement_id = new_id("model_measurement")
    observed = observed_at or dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
    salt = measurement_id.encode()
    with owner_engine.begin() as connection:
        connection.execute(text("SELECT set_config('inv.tenant_id', :t, true)"), {"t": str(tenant_id)})
        connection.execute(
            _INSERT,
            {
                "tenant_id": tenant_id,
                "measurement_id": measurement_id,
                "request_id": request_id or uuid.uuid4(),
                "project_id": project_id or new_id("project"),
                "model_version_id": model_version_id,
                "uri": uri or f"inv://models/measured@{model_version_id[-8:]}",
                "contribution_id": new_id("storage_contribution"),
                "location_id": new_id("data_location"),
                "relative_path": "weights.safetensors",
                "node_id": new_id("node"),
                "recovery_epoch": uuid.uuid4(),
                "certificate_sha256": hashlib.sha256(b"leaf" + salt).hexdigest(),
                "sha256": sha256,
                "byte_size": byte_size,
                "observed_at": observed,
                "recorded_at": observed + dt.timedelta(milliseconds=250),
                "challenge_sha256": hashlib.sha256(b"challenge" + salt).hexdigest(),
                "response_sha256": hashlib.sha256(b"response" + salt).hexdigest(),
            },
        )
    return measurement_id
