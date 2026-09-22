"""Actual PostgreSQL authorization, atomic evidence and durable nonce consumption."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4
import hashlib

import psycopg
import pytest
import inv.storage_commit as storage_commit
from inv.approvals import Principal
from inv.errors import DomainError
from inv.ids import new_id
from inv.node_channels import NodeChannels, node_uri, provision_channel
from inv.storage_commit import StorageSampleStore
from inv.storage_sampling import ConfiguredSampler
from inv.tooling import NodePrincipal
from saintvision.storage.readroot import ReadRoot
from pki_support import authority, issue

pytestmark = pytest.mark.postgres


def register_owner(e, contribution, root, *, subject=None):
    user = new_id("usr")
    subject = subject or "oidc:" + hashlib.sha256(uuid4().bytes).hexdigest()
    with psycopg.connect(e.owner) as c:
        c.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'storage test')",
            (e.tenant, uuid4().hex),
        )
        c.execute(
            "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,'owner')",
            (e.tenant, user, subject),
        )
        c.execute(
            "INSERT INTO public.projects(tenant_id,project_id,code,display_name) VALUES(%s,%s,'storage','storage')",
            (e.tenant, e.project),
        )
        c.execute(
            "INSERT INTO public.project_members(tenant_id,project_id,user_id,role_code) VALUES(%s,%s,%s,'owner')",
            (e.tenant, e.project, user),
        )
        c.execute(
            "INSERT INTO inv.business_projects(tenant_id,project_id) VALUES(%s,%s)",
            (e.tenant, e.project),
        )
        c.execute(
            "INSERT INTO inv.business_subjects(tenant_id,subject_id,user_id) VALUES(%s,%s,%s)",
            (e.tenant, subject, user),
        )
        c.execute(
            "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request) VALUES(%s,%s,%s,true)",
            (e.tenant, e.project, subject),
        )
        c.execute(
            """INSERT INTO public.nodes(node_id,tenant_id,hostname,os_type,os_version,agent_version,status,enrolled_at,heartbeat_sequence,version)
          VALUES(%s,%s,'synthetic','linux','test','test','active',now(),0,1)""",
            (e.node, e.tenant),
        )
        c.execute(
            """INSERT INTO public.storage_contributions(contribution_id,tenant_id,node_id,declared_path,normalized_path,mode,status,registered_by_user_id)
          VALUES(%s,%s,%s,%s,%s,'read_only','active',%s)""",
            (contribution, e.tenant, e.node, str(root), str(root), user),
        )
        c.execute(
            """INSERT INTO public.data_locations(location_id,tenant_id,contribution_id,uri,kind,relative_path,byte_size,checksum_sha256)
          VALUES(%s,%s,%s,'file:data.bin','dataset','data.bin',12,%s)""",
            (new_id("dtl"), e.tenant, contribution, hashlib.sha256(b"actual bytes").hexdigest()),
        )
    return Principal(e.tenant, subject), user


@pytest.fixture
def storage_subject():
    return None


@pytest.fixture
def sample(env, tmp_path, storage_subject):
    e = env
    root = tmp_path / "contributed"
    root.mkdir()
    (root / "data.bin").write_bytes(b"actual bytes")
    contribution = new_id("stc")
    principal, user = register_owner(e, contribution, root, subject=storage_subject)
    node = NodePrincipal(e.tenant, e.node)
    certificate = issue(authority(), node_uri(node, e.epoch), server=True)
    with psycopg.connect(e.owner) as c:
        provision_channel(
            c,
            node,
            epoch=e.epoch,
            endpoint="https://127.0.0.1:18443",
            certificate_der=certificate.der,
            expected_version=0,
        )
    run = e.runs.create(e.tenant, e.project)
    store = StorageSampleStore(e.db)
    channel = NodeChannels(e.db).snapshot(node, observation_only=True)
    sampler = ConfiguredSampler(
        channel, contribution, 1, ReadRoot(root), certificate.key, certificate.der
    )
    return SimpleNamespace(
        e=e,
        root=root,
        contribution=contribution,
        principal=principal,
        user=user,
        certificate=certificate,
        run=run["runId"],
        store=store,
        sampler=sampler,
        request=str(uuid4()),
    )


def prepare(a):
    challenge = a.store.issue(a.principal, a.e.project, a.run, a.contribution, request_id=a.request)
    return challenge, a.sampler.collect(challenge)


def accept(a, envelope):
    return a.store.accept(a.principal, a.e.project, a.run, a.request, envelope, a.certificate.der)


def counts(a):
    with a.e.db.transaction(a.e.tenant) as c:
        return tuple(
            c.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"]
            for table in (
                "inv.evidence",
                "public.storage_checks",
                "inv.storage_sample_consumptions",
            )
        )


def test_atomic_existing_evidence_and_check_without_run_completion(sample):
    a = sample
    challenge, envelope = prepare(a)
    assert (
        a.store.issue(a.principal, a.e.project, a.run, a.contribution, request_id=a.request)
        == challenge
    )
    result = accept(a, envelope)
    assert not result["replayed"] and counts(a) == (1, 1, 1)
    assert a.e.runs.get(a.e.tenant, a.run)["state"] == "draft"
    with a.e.db.transaction(a.e.tenant) as c:
        evidence = c.execute("SELECT envelope FROM inv.evidence").fetchone()["envelope"]
        check = c.execute("SELECT * FROM public.storage_checks").fetchone()
        assert evidence["inputSha256"] == challenge.digest() and evidence["result"] == "succeeded"
        assert check["healthy"] and check["detail"]["evidenceId"] == result["evidenceId"]
        assert check["detail"]["envelope"] == envelope
        assert not check["detail"]["operationalAcceptanceAssessed"]
    assert accept(a, envelope) == {**result, "replayed": True}
    assert counts(a) == (1, 1, 1)


def test_generated_evidence_envelope_is_rejected_before_storage_commit(sample, monkeypatch):
    """The storage write path must reject a malformed envelope it generated itself."""
    a = sample
    _, envelope = prepare(a)
    original = storage_commit.verify_sample

    def malformed(*args, **kwargs):
        return replace(original(*args, **kwargs), payload_sha256="not-a-sha256")

    monkeypatch.setattr(storage_commit, "verify_sample", malformed)

    with pytest.raises(DomainError, match="EvidenceEnvelope: invalid contract"):
        accept(a, envelope)
    assert counts(a) == (0, 0, 0)


def test_storage_commit_rejects_invalid_EvidenceEnvelope_atomically(sample, monkeypatch):
    """Generated "EvidenceEnvelope" is schema-checked inside the real PG transaction."""
    a = sample
    _, envelope = prepare(a)
    monkeypatch.setattr("inv.storage_commit.new_id", lambda _prefix: "invalid")
    with pytest.raises(DomainError, match="EvidenceEnvelope: invalid contract"):
        accept(a, envelope)
    assert counts(a) == (0, 0, 0)


def test_concurrent_duplicate_has_one_durable_consumption(sample):
    a = sample
    _, envelope = prepare(a)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: accept(a, envelope), range(2)))
    assert sorted(r["replayed"] for r in results) == [False, True]
    assert len({r["evidenceId"] for r in results}) == 1 and counts(a) == (1, 1, 1)


def test_changed_response_cannot_reconsume_nonce(sample):
    a = sample
    challenge, envelope = prepare(a)
    accept(a, envelope)
    (a.root / "data.bin").write_bytes(b"broken bytes")
    with pytest.raises(DomainError):
        accept(a, a.sampler.collect(challenge))
    assert counts(a) == (1, 1, 1)


@pytest.mark.parametrize(
    "change",
    [
        "UPDATE inv.project_grants SET enabled=false",
        "UPDATE inv.business_subjects SET enabled=false",
        "UPDATE public.project_members SET role_code='viewer'",
        "UPDATE public.storage_contributions SET status='revoked',revoked_at=now()",
        "UPDATE public.storage_contributions SET version=version+1",
        "UPDATE public.storage_contributions SET normalized_path=normalized_path||'/other'",
        "UPDATE public.nodes SET status='retired'",
        "UPDATE inv.node_channels SET enabled=false,version=version+1",
        "UPDATE inv.node_channels SET version=version+1",
        "UPDATE inv.runs SET state='cancelled',version=version+1",
        "UPDATE public.data_locations SET checksum_sha256=repeat('0',64),version=version+1",
    ],
)
def test_current_authority_and_catalog_changes_reject_without_partial_records(sample, change):
    a = sample
    _, envelope = prepare(a)
    with psycopg.connect(a.e.owner) as c:
        c.execute(change + " WHERE tenant_id=%s", (a.e.tenant,))
    with pytest.raises(DomainError):
        accept(a, envelope)
    assert counts(a) == (0, 0, 0)


def test_failed_outbox_rolls_back_all_three_records(sample, monkeypatch):
    a = sample
    _, envelope = prepare(a)

    def fail(*args):
        raise RuntimeError("synthetic last-write failure")

    with monkeypatch.context() as m:
        m.setattr("inv.storage_commit.event", fail)
        with pytest.raises(RuntimeError):
            accept(a, envelope)
    assert counts(a) == (0, 0, 0)
    assert not accept(a, envelope)["replayed"]


def test_bad_signature_never_consumes_and_valid_response_can_retry(sample):
    a = sample
    _, envelope = prepare(a)
    with pytest.raises(DomainError):
        accept(a, {**envelope, "signature": "A" * 86 + "=="})
    assert counts(a) == (0, 0, 0)
    accept(a, envelope)


def test_mismatch_is_recorded_as_failed_observation_not_failed_run(sample):
    a = sample
    (a.root / "data.bin").write_bytes(b"broken bytes")
    _, envelope = prepare(a)
    accept(a, envelope)
    with a.e.db.transaction(a.e.tenant) as c:
        assert not c.execute("SELECT healthy FROM public.storage_checks").fetchone()["healthy"]
        assert (
            c.execute("SELECT envelope FROM inv.evidence").fetchone()["envelope"]["result"]
            == "failed"
        )
    assert a.e.runs.get(a.e.tenant, a.run)["state"] == "draft"


def test_tenant_isolation_and_immutable_history(sample):
    a = sample
    _, envelope = prepare(a)
    accept(a, envelope)
    for table in (
        "inv.storage_sample_requests",
        "inv.storage_sample_consumptions",
        "public.storage_checks",
    ):
        with a.e.db.transaction(a.e.other) as c:
            assert c.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"] == 0
        with psycopg.connect(a.e.owner) as c, pytest.raises(psycopg.errors.CheckViolation):
            c.execute("DELETE FROM " + table + " WHERE tenant_id=%s", (a.e.tenant,))
    with a.e.db.transaction(a.e.tenant) as c:
        privileges = c.execute(
            """SELECT has_column_privilege(current_user,'public.storage_contributions','normalized_path','UPDATE') AS mutate,
          has_table_privilege(current_user,'inv.storage_sample_consumptions','DELETE') AS erase"""
        ).fetchone()
        assert privileges == {"mutate": False, "erase": False}


def test_request_id_cannot_change_sample_limit(sample):
    a = sample
    prepare(a)
    with pytest.raises(DomainError):
        a.store.issue(
            a.principal, a.e.project, a.run, a.contribution, request_id=a.request, sample=1
        )


def test_current_project_requester_is_not_automatically_folder_owner(sample):
    a = sample
    _, envelope = prepare(a)
    with psycopg.connect(a.e.owner) as c:
        other = new_id("usr")
        c.execute(
            "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,'other')",
            (a.e.tenant, other, "other:" + uuid4().hex),
        )
        c.execute(
            "UPDATE public.storage_contributions SET registered_by_user_id=%s WHERE tenant_id=%s",
            (other, a.e.tenant),
        )
    with pytest.raises(DomainError):
        accept(a, envelope)
    assert counts(a) == (0, 0, 0)


def test_expiry_at_final_verification_rolls_back_writes(sample, monkeypatch):
    from inv.storage_sampling import verify_sample

    a = sample
    challenge, envelope = prepare(a)
    calls = []

    def elapsed(expected, body, **kwargs):
        calls.append(True)
        if len(calls) == 2:
            kwargs["now"] = challenge.expires_at + 1
        return verify_sample(expected, body, **kwargs)

    monkeypatch.setattr("inv.storage_commit.verify_sample", elapsed)
    with pytest.raises(DomainError):
        accept(a, envelope)
    assert len(calls) == 2 and counts(a) == (0, 0, 0)


def test_cross_tenant_accept_cannot_use_known_request_id(sample):
    a = sample
    _, envelope = prepare(a)
    with pytest.raises(DomainError):
        a.store.accept(
            Principal(a.e.other, a.principal.subject_id),
            a.e.project,
            a.run,
            a.request,
            envelope,
            a.certificate.der,
        )
    assert counts(a) == (0, 0, 0)
