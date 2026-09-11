from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
import sys
from uuid import uuid4
import psycopg
import pytest
from inv.errors import DomainError
from inv.object_store import LocalObjects, ObjectHandle, PART_BYTES
from inv.snapshots import SnapshotStore, object_key, part_key
from test_postgres import running

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        sys.platform != "linux", reason="Linux private-directory provider"
    ),
]


@pytest.fixture
def storage(env, tmp_path):
    root = tmp_path / "objects"
    root.mkdir(mode=0o700)
    with psycopg.connect(env.owner) as conn:
        conn.execute(
            "INSERT INTO inv.storage_budgets VALUES(%s,%s,%s)",
            (env.tenant, env.project, 128 * 1024 * 1024),
        )
    return SnapshotStore(env.db, LocalObjects(root))


def begin(e, s, data=b"synthetic checkpoint"):
    oid = str(uuid4())
    s.begin(e.tenant, e.project, oid, hashlib.sha256(data).hexdigest(), len(data))
    return oid


def published(e, s, data=b"synthetic checkpoint"):
    oid = begin(e, s, data)
    for index, offset in enumerate(range(0, len(data), PART_BYTES)):
        s.put_part(e.tenant, e.project, oid, index, data[offset : offset + PART_BYTES])
    s.finalize(e.tenant, e.project, oid)
    return oid


def test_restart_resumes_parts_and_concurrent_finalize(env, storage):
    s, e = storage, env
    data = b"a" * PART_BYTES + b"last part"
    oid = begin(e, s, data)
    s.put_part(e.tenant, e.project, oid, 0, data[:PART_BYTES])
    s = SnapshotStore(e.db, LocalObjects(s.provider.root))
    assert [p["part_index"] for p in s.status(e.tenant, e.project, oid)["parts"]] == [0]
    with pytest.raises(DomainError, match="STORE-0006"):
        s.finalize(e.tenant, e.project, oid)
    s.put_part(e.tenant, e.project, oid, 1, data[PART_BYTES:])
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(lambda _: s.finalize(e.tenant, e.project, oid), range(4))
        )
    assert results == [hashlib.sha256(data).hexdigest()] * 4


def test_same_part_is_idempotent_but_different_bytes_conflict(env, storage):
    e, s = env, storage
    oid = begin(e, s, b"abc")
    assert s.put_part(e.tenant, e.project, oid, 0, b"abc") == s.put_part(
        e.tenant, e.project, oid, 0, b"abc"
    )
    with pytest.raises(DomainError, match="IDEM-0001"):
        s.put_part(e.tenant, e.project, oid, 0, b"xyz")


def test_declared_hash_cannot_publish_wrong_bytes(env, storage):
    e, s = env, storage
    oid = begin(e, s, b"abc")
    s.put_part(e.tenant, e.project, oid, 0, b"xyz")
    with pytest.raises(DomainError, match="VERIFY-0010"):
        s.finalize(e.tenant, e.project, oid)
    assert s.status(e.tenant, e.project, oid)["state"] == "uploading"


def test_publication_before_metadata_crash_is_recoverable(env, storage, monkeypatch):
    e, s = env, storage
    oid = begin(e, s, b"abc")
    s.put_part(e.tenant, e.project, oid, 0, b"abc")
    original = ObjectHandle.put

    def crash(files, name, data, digest):
        original(files, name, data, digest)
        raise RuntimeError("synthetic crash after fsync")

    monkeypatch.setattr(ObjectHandle, "put", crash)
    with pytest.raises(RuntimeError):
        s.finalize(e.tenant, e.project, oid)
    assert s.status(e.tenant, e.project, oid)["state"] == "uploading"
    monkeypatch.setattr(ObjectHandle, "put", original)
    s.finalize(e.tenant, e.project, oid)
    assert s.status(e.tenant, e.project, oid)["state"] == "ready"


def test_checkpoint_restore_pins_bytes_and_emits_only_one_event(env, storage):
    e, s = env, storage
    run, _, proofs = running(e)
    oid = published(e, s)
    content = s.checkpoint(e.tenant, run["runId"], "step", oid, proofs=proofs)
    assert s.checkpoint(e.tenant, run["runId"], "step", oid, proofs=proofs) == content
    restarted = SnapshotStore(e.db, LocalObjects(s.provider.root))
    assert (
        restarted.restore(e.tenant, e.project, run["runId"], 1, "step")
        == b"synthetic checkpoint"
    )
    with pytest.raises(DomainError, match="STORE-0007"):
        s.collect(e.tenant, e.project, oid)
    with e.db.transaction(e.tenant) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM inv.outbox WHERE run_id=%s AND event_type='inv.run.checkpoint_published'",
                (run["runId"],),
            ).fetchone()["n"]
            == 1
        )


def test_stale_fence_cannot_pin_and_cancel_cannot_publish_checkpoint(env, storage):
    e, s = env, storage
    run, _, proofs = running(e)
    oid = published(e, s)
    with pytest.raises(DomainError):
        s.checkpoint(
            e.tenant, run["runId"], "step", oid, proofs={key: "stale" for key in proofs}
        )
    e.runs.transition(
        e.tenant, run["runId"], "cancelled", expected_version=run["version"]
    )
    with pytest.raises(DomainError, match="GRAPH-0002"):
        s.checkpoint(e.tenant, run["runId"], "step", oid, proofs=proofs)
    s.collect(e.tenant, e.project, oid)


def test_cross_tenant_and_project_cannot_read_checkpoint(env, storage):
    e, s = env, storage
    run, _, proofs = running(e)
    oid = published(e, s)
    s.checkpoint(e.tenant, run["runId"], "step", oid, proofs=proofs)
    for tenant, project in [(e.other, e.project), (e.tenant, "missing")]:
        with pytest.raises(DomainError, match="RES-0004"):
            s.restore(tenant, project, run["runId"], 1, "step")


def test_restore_rehashes_and_refuses_corruption(env, storage):
    e, s = env, storage
    run, _, proofs = running(e)
    oid = published(e, s, b"abc")
    s.checkpoint(e.tenant, run["runId"], "step", oid, proofs=proofs)
    path = s.provider.root / object_key(oid)
    path.chmod(0o600)
    path.write_bytes(b"xyz")
    path.chmod(0o400)
    with pytest.raises(DomainError, match="VERIFY-0010"):
        s.restore(e.tenant, e.project, run["runId"], 1, "step")


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
def test_open_handle_rejects_links_and_special_files(env, storage, tmp_path, kind):
    e, s = env, storage
    oid = begin(e, s, b"abc")
    outside = tmp_path / "outside"
    outside.write_bytes(b"abc")
    outside.chmod(0o400)
    part = s.provider.root / part_key(oid, 0)
    if kind == "symlink":
        part.symlink_to(outside)
    elif kind == "hardlink":
        os.link(outside, part)
    else:
        os.mkfifo(part, 0o400)
    with pytest.raises((OSError, DomainError)):
        s.put_part(e.tenant, e.project, oid, 0, b"abc")
    assert outside.read_bytes() == b"abc"


def test_quota_reservation_is_atomic_and_released_only_after_delete(env, storage):
    e, s = env, storage
    with psycopg.connect(e.owner) as conn:
        conn.execute(
            "UPDATE inv.storage_budgets SET quota_bytes=3 WHERE project_id=%s",
            (e.project,),
        )

    def reserve(_):
        try:
            return begin(e, s, b"abc")
        except DomainError as error:
            assert error.code == "RES-0001"
            return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(reserve, range(8)))
    ids = [r for r in results if r]
    assert len(ids) == 1
    s.collect(e.tenant, e.project, ids[0])
    assert begin(e, s, b"abc")


def test_gc_tombstone_recovers_unlink_crash(env, storage, monkeypatch):
    e, s = env, storage
    oid = published(e, s)
    original = ObjectHandle.remove

    def crash(files, name):
        original(files, name)
        raise RuntimeError("synthetic unlink crash")

    monkeypatch.setattr(ObjectHandle, "remove", crash)
    with pytest.raises(RuntimeError):
        s.collect(e.tenant, e.project, oid)
    assert s.status(e.tenant, e.project, oid)["state"] == "deleting"
    with pytest.raises(DomainError):
        s.finalize(e.tenant, e.project, oid)
    monkeypatch.setattr(ObjectHandle, "remove", original)
    s.collect(e.tenant, e.project, oid)
    assert s.status(e.tenant, e.project, oid)["state"] == "deleted"


def test_checkpoint_gc_race_has_one_safe_winner(env, storage):
    e, s = env, storage
    run, _, proofs = running(e)
    oid = published(e, s)

    def pin():
        try:
            s.checkpoint(e.tenant, run["runId"], "step", oid, proofs=proofs)
            return "pinned"
        except DomainError as error:
            assert error.code == "STORE-0005"
            return "deleted"

    def gc():
        try:
            s.collect(e.tenant, e.project, oid)
            return "deleted"
        except DomainError as error:
            assert error.code == "STORE-0007"
            return "pinned"

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = executor.submit(pin), executor.submit(gc)
        assert first.result() == second.result()


def test_zero_byte_snapshot_can_be_verified(env, storage):
    oid = published(env, storage, b"")
    assert storage.status(env.tenant, env.project, oid)["sizeBytes"] == 0
