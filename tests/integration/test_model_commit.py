"""Actual PostgreSQL RLS, full bytes, cancellation races and immutable references.

Run transitions are fixture setup, not evidence of a real Node model execution.
"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest
from inv.approvals import Principal
from inv.errors import DomainError
from inv.leases import Allocation
from inv.model_commit import ModelManifestStore
from inv.model_manifest import ConfiguredModelVerifier, RootBinding
from saintvision.storage.readroot import ReadRoot
from model_support import model_body
from test_storage_commit import sample, storage_subject

pytestmark = pytest.mark.postgres


@pytest.fixture
def model(sample):
    a = sample
    with psycopg.connect(a.e.owner) as c:
        location = c.execute(
            "SELECT location_id FROM public.data_locations WHERE contribution_id=%s",
            (a.contribution,),
        ).fetchone()[0]
    for target in ("validated", "planned"):
        current = a.e.runs.get(a.e.tenant, a.run)
        a.e.runs.transition(a.e.tenant, a.run, target, expected_version=current["version"])
    leases = a.e.leases.reserve(
        a.e.tenant,
        a.e.project,
        a.run,
        [Allocation(a.e.resource, 1)],
        key="model-lease",
        ttl_seconds=300,
    )
    a.proofs = {row["leaseId"]: row["fencingToken"] for row in leases}
    for target in ("scheduled", "running"):
        current = a.e.runs.get(a.e.tenant, a.run)
        a.e.runs.transition(
            a.e.tenant, a.run, target, expected_version=current["version"], proofs=a.proofs
        )
    a.body = model_body(a.e.node, [location], [b"actual bytes"])
    a.verifier = ConfiguredModelVerifier(
        [RootBinding(a.e.node, a.contribution, 1, ReadRoot(a.root))]
    )
    a.store = ModelManifestStore(a.e.db, a.verifier)
    a.key = uuid4().hex
    return a


def commit(a, *, key=None, body=None):
    return a.store.commit(
        a.principal, a.e.project, a.run, body or a.body, a.proofs, key=key or a.key
    )


def count(a):
    with psycopg.connect(a.e.owner) as c:
        return c.execute(
            "SELECT count(*) FROM inv.model_manifests WHERE tenant_id=%s", (a.e.tenant,)
        ).fetchone()[0]


def test_real_bytes_commit_and_restart_duplicate_are_durable(model):
    a = model
    first = commit(a)
    assert first["committed"] and first["requiresExecutionRevalidation"]
    a.store = ModelManifestStore(a.e.db, a.verifier)
    assert commit(a) == first and count(a) == 1
    assert (
        a.store.get(a.principal, a.e.project, a.body["modelId"], a.body["version"])["manifest"]
        == a.body
    )
    with psycopg.connect(a.e.owner) as c:
        assert (
            c.execute(
                "SELECT count(*) FROM inv.outbox WHERE run_id=%s AND event_type='inv.model.manifest_committed'",
                (a.run,),
            ).fetchone()[0]
            == 1
        )


def test_caller_verified_flag_does_not_make_corrupt_bytes_committable(model):
    a = model
    (a.root / "data.bin").write_bytes(b"corrupt data")
    with pytest.raises(DomainError):
        commit(a)
    assert count(a) == 0


def test_same_key_with_different_manifest_is_rejected(model):
    a = model
    commit(a)
    changed = deepcopy(a.body)
    changed["licensePolicy"] = "changed"
    with pytest.raises(DomainError, match="different request content"):
        commit(a, body=changed)
    assert count(a) == 1


def test_concurrent_same_key_has_one_commit_and_one_event(model, monkeypatch):
    a = model
    barrier = Barrier(2)
    original = a.verifier.verify

    def verify(*args):
        barrier.wait(timeout=10)
        return original(*args)

    monkeypatch.setattr(a.verifier, "verify", verify)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result(timeout=15) for f in [pool.submit(commit, a), pool.submit(commit, a)]]
    assert results[0] == results[1] and count(a) == 1
    with psycopg.connect(a.e.owner) as c:
        assert (
            c.execute(
                "SELECT count(*) FROM inv.outbox WHERE run_id=%s AND event_type='inv.model.manifest_committed'",
                (a.run,),
            ).fetchone()[0]
            == 1
        )


def test_different_key_cannot_replace_a_committed_model_version(model):
    a = model
    commit(a)
    with pytest.raises(DomainError, match="already committed"):
        commit(a, key=uuid4().hex)
    assert count(a) == 1


@pytest.mark.parametrize(
    "fault",
    ["cancel", "version", "grant", "lease", "epoch", "location", "contribution", "lost-node"],
)
def test_authority_and_catalog_are_rechecked_after_file_io(model, monkeypatch, fault):
    a = model
    original = a.verifier.verify
    changes = {
        "cancel": (
            "UPDATE inv.runs SET state='cancelled',version=version+1 WHERE run_id=%s",
            a.run,
        ),
        "version": (
            "UPDATE inv.runs SET state='verifying',version=version+1 WHERE run_id=%s",
            a.run,
        ),
        "grant": ("UPDATE inv.project_grants SET enabled=false WHERE project_id=%s", a.e.project),
        "lease": (
            "UPDATE inv.resource_leases SET granted_at=clock_timestamp()-interval '10 seconds',expires_at=clock_timestamp()-interval '1 second' WHERE run_id=%s",
            a.run,
        ),
        "epoch": ("UPDATE inv.control_epoch SET epoch=%s", str(uuid4())),
        "location": (
            "UPDATE public.data_locations SET version=version+1 WHERE contribution_id=%s",
            a.contribution,
        ),
        "contribution": (
            "UPDATE public.storage_contributions SET version=version+1 WHERE contribution_id=%s",
            a.contribution,
        ),
        "lost-node": ("UPDATE inv.nodes SET status='offline' WHERE node_id=%s", a.e.node),
    }

    def verify(*args):
        result = original(*args)
        query, value = changes[fault]
        with psycopg.connect(a.e.owner) as c:
            c.execute(query, (value,))
        return result

    monkeypatch.setattr(a.verifier, "verify", verify)
    with pytest.raises(DomainError):
        commit(a)
    assert count(a) == 0


@pytest.mark.parametrize("stale", [False, True])
def test_stale_or_missing_fence_cannot_even_start_file_io(model, monkeypatch, stale):
    a = model

    def forbidden(*args):
        pytest.fail("Read performed without execution authority")

    monkeypatch.setattr(a.verifier, "verify", forbidden)
    a.proofs = {key: value + "0" for key, value in a.proofs.items()} if stale else {}
    with pytest.raises(DomainError):
        commit(a)
    assert count(a) == 0


def test_manifest_rls_and_immutable_reference_protect_existing_catalog(model):
    a = model
    commit(a)
    with a.e.db.transaction(a.e.other) as c:
        assert c.execute("SELECT count(*) AS n FROM inv.model_manifests").fetchone()["n"] == 0
    with pytest.raises(DomainError):
        a.store.get(
            Principal(a.e.other, "unrelated"), a.e.project, a.body["modelId"], a.body["version"]
        )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with a.e.db.transaction(a.e.tenant) as c:
            c.execute("DELETE FROM inv.model_manifests WHERE project_id=%s", (a.e.project,))
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with psycopg.connect(a.e.owner) as c:
            c.execute(
                "DELETE FROM public.data_locations WHERE contribution_id=%s", (a.contribution,)
            )
    assert count(a) == 1


def test_durable_success_replay_is_not_a_new_execution_after_cancel(model, monkeypatch):
    a = model
    result = commit(a)
    with psycopg.connect(a.e.owner) as c:
        c.execute(
            "UPDATE inv.runs SET state='cancelled',version=version+1 WHERE run_id=%s", (a.run,)
        )

    def forbidden(*args):
        pytest.fail("Durable replay must not read or execute again")

    monkeypatch.setattr(a.verifier, "verify", forbidden)
    assert commit(a) == result and count(a) == 1
