"""Historical storage GET with real JWT/DB, current authority and corrupt history."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest
from fastapi.testclient import TestClient

from inv.app import create_app
from inv.errors import DomainError
from inv.identity import public_subject
from inv.storage_view import StorageObservationView
from jwt_support import jwt_fixture
from test_storage_commit import sample, prepare, accept, counts

pytestmark = pytest.mark.postgres


@pytest.fixture
def storage_subject():
    return public_subject("https://synthetic-idp.invalid/realm", "requester")


@pytest.fixture
def view(sample, tmp_path):
    a = sample
    a.jwt = jwt_fixture(tmp_path, a.e.tenant)
    assert a.jwt.subject("requester") == a.principal.subject_id
    a.http = TestClient(
        create_app(a.e.db, a.jwt.auth, allowed_origins=["https://web.invalid"]),
        raise_server_exceptions=False,
    )
    a.headers = {"Authorization": "Bearer " + a.jwt.token()}
    a.url = f"/v1/projects/{a.e.project}/runs/{a.run}/storage-samples/{a.request}"
    yield a
    a.http.close()


def get(a):
    return a.http.get(a.url, headers=a.headers)


def test_get_pending_then_recorded_is_read_only_and_redacts_inputs(view):
    a = view
    _, envelope = prepare(a)
    response = get(a)
    assert response.status_code == 200, response.text
    before = response.json()
    assert before["status"] == "pending" and before["observation"] is None
    assert counts(a) == (0, 0, 0)
    committed = accept(a, envelope)
    response = get(a)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "recorded"
    assert result["observation"]["integrityVerified"] and result["observation"]["sampleHealthy"]
    assert result["observation"]["evidenceId"] == committed["evidenceId"]
    assert result["currentHealth"] == "unknown" and not result["operationalAcceptanceAssessed"]
    assert response.headers["cache-control"] == "no-store"
    for private in [
        "root_path",
        "normalized_path",
        "certificateDer",
        "nonce",
        "signature",
        "data.bin",
        str(a.root),
        a.principal.subject_id,
    ]:
        assert private not in response.text
    assert get(a).json() == result and counts(a) == (1, 1, 1)
    assert a.e.runs.get(a.e.tenant, a.run)["state"] == "draft"


@pytest.mark.parametrize(
    "change",
    [
        "UPDATE inv.project_grants SET enabled=false",
        "UPDATE inv.business_subjects SET enabled=false",
        "UPDATE public.project_members SET role_code='viewer'",
        "UPDATE public.users SET status='suspended'",
    ],
)
def test_current_permission_revocation_hides_stored_result(view, change):
    a = view
    _, envelope = prepare(a)
    accept(a, envelope)
    with psycopg.connect(a.e.owner) as c:
        c.execute(change + " WHERE tenant_id=%s", (a.e.tenant,))
    response = get(a)
    assert response.status_code == 403, response.text
    assert counts(a) == (1, 1, 1)


def test_recorded_history_survives_terminal_run_and_channel_retirement(view):
    a = view
    _, envelope = prepare(a)
    accept(a, envelope)
    with psycopg.connect(a.e.owner) as c:
        c.execute(
            "UPDATE inv.runs SET state='cancelled',version=version+1 WHERE run_id=%s", (a.run,)
        )
        c.execute(
            "UPDATE inv.node_channels SET enabled=false,version=version+1 WHERE tenant_id=%s",
            (a.e.tenant,),
        )
        c.execute(
            "UPDATE public.storage_contributions SET status='revoked',revoked_at=now() WHERE contribution_id=%s",
            (a.contribution,),
        )
    result = get(a)
    assert result.status_code == 200, result.text
    assert result.json()["observation"]["sampleHealthy"]
    assert result.json()["currentHealth"] == "unknown"


def test_missing_or_invalid_identity_never_reads(view):
    a = view
    prepare(a)
    assert a.http.get(a.url).status_code == 401
    assert a.http.get(a.url, headers={"Authorization": "Bearer broken"}).status_code == 401
    assert (
        a.http.get(a.url, headers={"Authorization": "Bearer " + a.jwt.token("other")}).status_code
        == 403
    )
    assert a.http.get(a.url.replace(a.request, "bad-id"), headers=a.headers).status_code == 400
    assert a.http.get(a.url.replace(a.request, str(uuid4())), headers=a.headers).status_code == 404


def test_expired_unconsumed_request_does_not_renew_on_get(view, monkeypatch):
    from inv.storage_sampling import new_challenge

    a = view

    def old(**kwargs):
        kwargs["now"] -= 60
        return new_challenge(**kwargs)

    monkeypatch.setattr("inv.storage_commit.new_challenge", old)
    a.store.issue(a.principal, a.e.project, a.run, a.contribution, request_id=a.request)
    result = get(a)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "expired" and result.json()["observation"] is None
    assert counts(a) == (0, 0, 0)


@pytest.mark.parametrize(
    "field", ["healthy", "evidenceId", "signature", "challenge", "sampled", "evidence_hash"]
)
def test_tampered_stored_records_cannot_be_reported_verified(view, field):
    a = view
    _, envelope = prepare(a)
    committed = accept(a, envelope)
    # Corruption injection uses only the disposable DB owner. Runtime cannot
    # bypass these immutable triggers or mutate recorded observations.
    with psycopg.connect(a.e.owner) as c:
        if field == "evidence_hash":
            c.execute("ALTER TABLE inv.evidence DISABLE TRIGGER USER")
            c.execute(
                "UPDATE inv.evidence SET envelope=jsonb_set(envelope,'{outputSha256}',to_jsonb(repeat('0',64))) WHERE evidence_id=%s",
                (committed["evidenceId"],),
            )
            c.execute("ALTER TABLE inv.evidence ENABLE TRIGGER USER")
        else:
            c.execute("ALTER TABLE public.storage_checks DISABLE TRIGGER USER")
            detail = c.execute(
                "SELECT detail FROM public.storage_checks WHERE check_id=%s",
                (committed["checkId"],),
            ).fetchone()[0]
            if field == "healthy":
                c.execute(
                    "UPDATE public.storage_checks SET healthy=false WHERE check_id=%s",
                    (committed["checkId"],),
                )
            elif field == "sampled":
                c.execute(
                    "UPDATE public.storage_checks SET sampled_count=0 WHERE check_id=%s",
                    (committed["checkId"],),
                )
            else:
                if field == "evidenceId":
                    detail["evidenceId"] = "evd_" + "0" * 26
                elif field == "signature":
                    detail["envelope"]["signature"] = "A" * 86 + "=="
                elif field == "challenge":
                    detail["challenge"]["nonce"] = "0" * 64
                c.execute(
                    "UPDATE public.storage_checks SET detail=%s WHERE check_id=%s",
                    (Jsonb(detail), committed["checkId"]),
                )
            c.execute("ALTER TABLE public.storage_checks ENABLE TRIGGER USER")
    response = get(a)
    assert response.status_code == 409, response.text
    assert "certificateDer" not in response.text


def test_read_holds_current_grant_until_verified_response(view, monkeypatch):
    a = view
    _, envelope = prepare(a)
    accept(a, envelope)
    original = StorageObservationView._verified
    attempted = []

    def competing_revoke():
        with psycopg.connect(a.e.owner) as c:
            c.execute("SET lock_timeout='100ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                c.execute(
                    "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s", (a.e.tenant,)
                )
        attempted.append(True)

    def verified(*args):
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(competing_revoke).result(timeout=5)
        return original(*args)

    monkeypatch.setattr(StorageObservationView, "_verified", staticmethod(verified))
    response = get(a)
    assert response.status_code == 200, response.text
    assert attempted == [True]


def test_current_owner_change_and_other_tenant_cannot_read(view):
    from inv.approvals import Principal
    from inv.ids import new_id

    a = view
    _, envelope = prepare(a)
    accept(a, envelope)
    with pytest.raises(DomainError):
        StorageObservationView(a.e.db).result(
            Principal(a.e.other, a.principal.subject_id), a.e.project, a.run, a.request
        )
    with psycopg.connect(a.e.owner) as c:
        other = new_id("usr")
        c.execute(
            "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,'other')",
            (a.e.tenant, other, "other:" + uuid4().hex),
        )
        c.execute(
            "UPDATE public.storage_contributions SET registered_by_user_id=%s WHERE contribution_id=%s",
            (other, a.contribution),
        )
    assert get(a).status_code == 403


def test_recorded_mismatch_is_historical_failure_not_current_health(view):
    a = view
    (a.root / "data.bin").write_bytes(b"broken bytes")
    _, envelope = prepare(a)
    accept(a, envelope)
    response = get(a)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["observation"]["integrityVerified"]
    assert not result["observation"]["sampleHealthy"]
    assert result["observation"]["mismatches"] == 1 and result["currentHealth"] == "unknown"


def test_history_timestamp_is_independent_of_database_session_timezone(view, monkeypatch):
    from contextlib import contextmanager

    a = view
    _, envelope = prepare(a)
    accept(a, envelope)
    original = a.e.db.transaction

    @contextmanager
    def korea(*args, **kwargs):
        with original(*args, **kwargs) as c:
            c.execute("SET LOCAL TIME ZONE 'Asia/Seoul'")
            yield c

    monkeypatch.setattr(a.e.db, "transaction", korea)
    response = get(a)
    assert response.status_code == 200, response.text
    assert response.json()["observation"]["integrityVerified"]
