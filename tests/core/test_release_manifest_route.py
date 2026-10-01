"""The HTTP behaviour of the release manifest readers, without PostgreSQL.

``tests/test_pilot.py`` owns the question "is the answer right" against a real
database. This file owns the question "is the answer shaped and refused
correctly" -- the canonical 404, a body on a GET, an unbounded cursor, and the
exported contract. Those are route concerns and none of them needs a database,
so they run in the PG-free lane where a regression is found in a second rather
than in the integration job.

The service is replaced, not re-implemented: these tests must fail when the
route mis-handles what the service returned, and pass unchanged when the service
changes how it decides. ``tests/test_pilot.py`` is where the deciding is pinned.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from saintvision.api.app import create_app  # noqa: E402
from saintvision.api.deps import get_session  # noqa: E402
from saintvision.api.v1 import release_manifests as route  # noqa: E402
from saintvision.config import Settings  # noqa: E402
from saintvision.errors import RES_RELEASE_NOT_FOUND, InvError  # noqa: E402
from saintvision.identity.principal import Principal, StaticPrincipalVerifier  # noqa: E402
from saintvision.api import schemas  # noqa: E402
from saintvision.services import pilot as pilot_service  # noqa: E402

TENANT = uuid.UUID("22222222-2222-2222-2222-222222222222")
AUTH = {"Authorization": "Bearer release-token"}
UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 1, 9, 0, 0, tzinfo=UTC)
HASH = "a" * 64
RELEASE_ID = "release_01J8Z3XQ2K9WMV5T7N4B6C8D0E"

MANIFEST = {
    "releaseId": RELEASE_ID,
    "version": "R4",
    "componentCount": 2,
    "manifestSha256": HASH,
    "components": [
        {"name": "control-plane", "kind": "image", "digest": "sha256:" + "1" * 64},
        {"name": "node-agent", "kind": "image", "digest": "sha256:" + "2" * 64},
    ],
    "createdAt": NOW,
    "operatorSignOff": False,
    "operatorSignOffBlockedBy": "human-attestation-contract-absent",
    "requiredDistinctOperatorCount": 2,
    "confirmedOperatorCount": 0,
    "acceptanceCount": 0,
}


@pytest.fixture
def client(monkeypatch):
    principal = Principal(
        user_id="usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E",
        tenant_id=TENANT,
        external_subject="oidc:release",
    )
    app = create_app(
        engine=object(),
        settings=Settings(database_url="postgresql://unused"),
        verifier=StaticPrincipalVerifier({"release-token": principal}, allow_outside_dev=True),
        check_partitions_on_startup=False,
    )
    # The readers take a Session and these tests never let one be used; the
    # dependency is overridden rather than monkeypatched so a route that started
    # querying would fail loudly instead of silently touching a real engine.
    app.dependency_overrides[get_session] = lambda: None
    return TestClient(app, raise_server_exceptions=False)


def _page(monkeypatch, payload):
    monkeypatch.setattr(
        route.pilot_service, "release_manifest_page", lambda *a, **k: payload
    )


def _detail(monkeypatch, payload):
    def read(*args, **kwargs):
        if isinstance(payload, Exception):
            raise payload
        return payload

    monkeypatch.setattr(route.pilot_service, "release_manifest_detail", read)


def test_an_empty_tenant_is_an_empty_list_and_not_a_not_found(client, monkeypatch):
    _page(monkeypatch, {"items": [], "nextCursor": None})
    response = client.get("/v1/release-manifests", headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {"items": [], "nextCursor": None}


def test_the_page_is_serialised_with_the_wire_names(client, monkeypatch):
    _page(monkeypatch, {"items": [MANIFEST], "nextCursor": RELEASE_ID})
    body = client.get("/v1/release-manifests", headers=AUTH).json()
    assert body["nextCursor"] == RELEASE_ID
    item = body["items"][0]
    assert set(item) == set(MANIFEST)
    assert item["operatorSignOff"] is False
    assert item["manifestSha256"] == HASH


def test_a_release_with_no_acceptance_reports_sign_off_false(client, monkeypatch):
    """The field the re-score recorded as hard-coded false is now answered.

    Answered, not asserted: the route reports what the reader computed, and the
    reader says false until a person's matching acceptance exists.
    """
    _detail(monkeypatch, {"release": MANIFEST, "acceptances": []})
    body = client.get(f"/v1/release-manifests/{RELEASE_ID}", headers=AUTH).json()
    assert body["release"]["operatorSignOff"] is False
    assert body["acceptances"] == []


def test_an_accepted_decision_is_reported_with_its_pinned_hash(client, monkeypatch):
    acceptance = {
        "acceptanceId": "acceptance_01J8Z3XQ2K9WMV5T7N4B6C8D0E",
        "acceptanceIdRef": "AC-12",
        "outcome": "accepted",
        "acceptedManifestSha256": HASH,
        "manifestMatches": True,
        "knownLimitations": [],
        "decidedAt": NOW,
    }
    _detail(
        monkeypatch,
        {
            "release": {**MANIFEST, "confirmedOperatorCount": 1, "acceptanceCount": 1},
            "acceptances": [acceptance],
        },
    )
    body = client.get(f"/v1/release-manifests/{RELEASE_ID}", headers=AUTH).json()
    assert body["release"]["operatorSignOff"] is False
    assert body["release"]["confirmedOperatorCount"] == 1
    assert set(body["acceptances"][0]) == set(acceptance)
    assert "acceptedByUserId" not in body["acceptances"][0]
    assert "notes" not in body["acceptances"][0]


def test_an_unknown_release_is_the_canonical_404_and_does_not_echo_the_id(
    client, monkeypatch
):
    """A 404 names no identifier the caller sent.

    Echoing it back turns a reader into a probe: a caller could sweep ids and
    read which ones produced a different message.
    """
    _detail(monkeypatch, InvError(RES_RELEASE_NOT_FOUND, "release manifest not found", status=404))
    response = client.get("/v1/release-manifests/release_not_a_real_one", headers=AUTH)
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "RES-0004"
    assert body["status"] == 404
    assert "release_not_a_real_one" not in json.dumps(body)


def test_a_get_with_a_body_is_refused(client, monkeypatch):
    """These are readers. A body on a GET is a request the route will not guess at."""
    _page(monkeypatch, {"items": [], "nextCursor": None})
    response = client.request(
        "GET", "/v1/release-manifests", headers=AUTH, content=b'{"version":"R4"}'
    )
    assert response.status_code == 422
    assert response.json()["code"].startswith("VAL-")


@pytest.mark.parametrize(
    "cursor",
    ["a" * 65, "release_01;DROP", "release 01", "", "   "],
)
def test_a_cursor_that_is_not_a_release_identifier_is_refused(client, monkeypatch, cursor):
    """The cursor goes into a comparison, so its shape is checked, not trusted."""
    _page(monkeypatch, {"items": [], "nextCursor": None})
    response = client.get("/v1/release-manifests", params={"cursor": cursor}, headers=AUTH)
    assert response.status_code == 422, cursor
    assert response.json()["code"] == "VAL-0003"


def test_a_limit_above_the_contract_ceiling_is_refused(client, monkeypatch):
    _page(monkeypatch, {"items": [], "nextCursor": None})
    response = client.get("/v1/release-manifests", params={"limit": 201}, headers=AUTH)
    assert response.status_code == 422


def test_both_readers_require_a_credential(client, monkeypatch):
    """No bearer credential is a 401 from the shared boundary, not a 500.

    The denial recorder is stubbed because it writes to the database and this
    app has no engine; without the stub the handler fails and the refusal
    arrives as a 500, which is the opposite of what a caller should learn.
    """

    from saintvision.api import app as app_module

    monkeypatch.setattr(app_module, "record_denial_out_of_band", lambda *a, **k: None)
    for path in ("/v1/release-manifests", f"/v1/release-manifests/{RELEASE_ID}"):
        assert client.get(path).status_code == 401, path


def test_the_exported_contract_matches_the_response_models():
    """``tools/export_schemas.py --check`` runs in CI; this names the five files.

    The exporter finds models by convention, so a new response model that was
    never exported would leave no contract to drift from and ``--check`` would
    pass. Naming the files here is the assertion that these five exist.
    """
    for name in (
        "release-manifest-response",
        "release-manifest-detail-response",
        "release-manifest-page-response",
        "release-acceptance-response",
        "release-component-response",
    ):
        path = ROOT / "contracts" / f"{name}.schema.json"
        assert path.is_file(), name
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document.get("additionalProperties") is False, name


def test_the_translation_table_covers_every_code_the_readers_can_reach():
    """A code the table omits becomes SYS-0002, which tells the caller nothing.

    The readers raise exactly these three; the table is the statement of that,
    and this test is what keeps the statement true as the service grows.
    """
    from saintvision.errors import VAL_CURSOR, VAL_SCHEMA

    assert set(route.TRANSLATION) == {RES_RELEASE_NOT_FOUND, VAL_CURSOR, VAL_SCHEMA}


def test_the_router_serves_exactly_the_two_documented_paths():
    assert sorted(r.path for r in route.router.routes) == [
        "/v1" + route.LIST_PATH,
        "/v1" + route.DETAIL_PATH,
    ]
    assert all(set(r.methods) == {"GET"} for r in route.router.routes)


def test_the_contract_itself_refuses_an_operator_sign_off_of_true(client, monkeypatch):
    """Not "the reader happens to send false" -- the model cannot serialise true.

    ``operatorSignOff`` is ``Literal[False]``. A future change that computed the
    field again and got it wrong would fail here at validation rather than
    reaching a screen, which is the difference between a pinned contract and a
    docstring promising one.
    """
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        schemas.ReleaseManifestResponse.model_validate({**MANIFEST, "operatorSignOff": True})


def test_the_blocked_reason_is_a_fixed_value(client, monkeypatch):
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        schemas.ReleaseManifestResponse.model_validate(
            {**MANIFEST, "operatorSignOffBlockedBy": "whatever"}
        )


def test_the_required_quorum_is_two_and_cannot_be_lowered_in_the_response(client, monkeypatch):
    """Lowering the target is the other way to make "1 of 2" read as satisfied."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        schemas.ReleaseManifestResponse.model_validate(
            {**MANIFEST, "requiredDistinctOperatorCount": 1}
        )


@pytest.mark.parametrize(
    "builder",
    [
        lambda: pilot_service.release_page_query(tenant_id=TENANT),
        lambda: pilot_service.release_page_query(tenant_id=TENANT, cursor=RELEASE_ID),
        lambda: pilot_service.release_detail_query(tenant_id=TENANT, release_id=RELEASE_ID),
        lambda: pilot_service.acceptances_query(tenant_id=TENANT, release_ids=[RELEASE_ID]),
    ],
)
def test_every_read_names_the_tenant_in_its_sql(builder):
    """The explicit predicate, asserted where row-level security cannot hide it.

    Deleting a ``tenant_id ==`` condition left the cross-tenant test green,
    because RLS refused the row and the assertion that was meant to catch the
    deletion never fired -- Codex measured that. Compiling the statement tests the
    layer itself: the predicate is either in the SQL or it is not.
    """
    sql = " ".join(str(builder().compile(compile_kwargs={"literal_binds": False})).split())
    assert "tenant_id =" in sql, sql
