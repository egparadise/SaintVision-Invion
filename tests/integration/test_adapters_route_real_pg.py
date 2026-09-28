"""Real PostgreSQL for the adapter routes: the audit trail, and nothing else.

These two routes read local CLIs and touch no table, so almost everything about
them is PG-free (``tests/core/test_adapters_route.py``). One thing is not: whether
a refusal reaches ``audit_events``. The shared denial boundary (#195) writes that
row, and only a database can show it arrived.

Three cases, and the third is the one that is easy to get wrong:

* no credential on the list route -- 401, and exactly one anonymous denial;
* no credential on the single-adapter route -- the same, under that route's own
  bounded action;
* an unknown adapter **with** a valid credential -- 404, and **no** denial. A
  not-found is not a refusal of access, and recording it would fill the AC-02
  trail with requests nobody was refused.

No CLI is launched by any of them: the unauthenticated requests never reach the
route, and an unknown name is refused before ``probe()``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from saintvision.api.app import create_app
from saintvision.api.problem import CANONICAL_KEYS
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id

pytestmark = pytest.mark.postgres

TOKEN = "adapters-real-token"


def _client(app_engine, *, tenant_id, user_id, now):
    """The real verifier, so the no-credential path is the product's own."""
    principal = Principal(
        user_id=user_id, tenant_id=tenant_id, external_subject="adapters-real"
    )
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only"),
        verifier=StaticPrincipalVerifier({TOKEN: principal}, allow_outside_dev=True),
        clock=lambda: now,
        check_partitions_on_startup=False,
    )
    return TestClient(app, raise_server_exceptions=False)


def _denials(owner_engine):
    """Denial rows, read as the owner so RLS does not hide the evidence."""
    with owner_engine.begin() as connection:
        return connection.execute(
            text(
                "SELECT tenant_id, actor_type, actor_id, action, outcome, reason_code, "
                "target_type, target_id, detail FROM audit_events "
                "WHERE outcome = 'deny' ORDER BY occurred_at"
            )
        ).mappings().all()


@pytest.mark.parametrize(
    "path,action",
    [
        ("/v1/adapters", "GET /v1/adapters"),
        ("/v1/adapters/claude-code", "GET /v1/adapters/{name}"),
    ],
    ids=["list", "single"],
)
def test_no_credential_is_refused_and_recorded_once(
    owner_engine, app_engine, two_tenants, frozen_now, path, action
):
    """#195's boundary, observed. The action is the template, never the path value."""
    tenant, _ = two_tenants
    client = _client(app_engine, tenant_id=tenant, user_id=new_id("user"), now=frozen_now)

    response = client.get(path)

    assert response.status_code == 401, response.text
    assert response.headers.get("WWW-Authenticate") == "Bearer"

    rows = _denials(owner_engine)
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["actor_type"] == "anonymous"
    assert row["actor_id"] is None
    # No verified credential, so no tenant is claimed for the row.
    assert row["tenant_id"] is None
    assert row["outcome"] == "deny"
    assert row["action"] == action
    # These paths carry no project, so there is no target to record.
    assert (row["target_type"], row["target_id"]) == (None, None)
    assert row["detail"] == {}
    assert "claude-code" not in row["action"]


def test_an_unknown_adapter_is_a_canonical_404_and_records_no_denial(
    owner_engine, app_engine, two_tenants, frozen_now
):
    """A 404 is not a refusal of access, and the body is the canonical one."""
    tenant, _ = two_tenants
    client = _client(app_engine, tenant_id=tenant, user_id=new_id("user"), now=frozen_now)

    response = client.get(
        "/v1/adapters/not-a-tool", headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert response.status_code == 404, response.text
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["code"] == "RES-0004"
    assert body["detail"] == "No such adapter."
    # The name the caller sent is not echoed into a body a screen renders.
    assert "not-a-tool" not in response.text

    assert _denials(owner_engine) == []
    with owner_engine.begin() as connection:
        total = connection.execute(text("SELECT count(*) FROM audit_events")).scalar_one()
    assert total == 0, "a read that found nothing writes nothing"
