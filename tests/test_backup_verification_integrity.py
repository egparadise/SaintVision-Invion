"""Actual files and DB commits: rejected verification cannot become success."""

import datetime as dt
import hashlib
import sys
import concurrent.futures
import threading
from uuid import uuid4
import pytest
from sqlalchemy import select
from saintvision.db.models import BackupRecord
from saintvision.db.session import tenant_scope
from saintvision.services import pilot as service, verification
from saintvision.errors import InvError
from test_pilot import pilot

NOW = dt.datetime(2026, 9, 12, tzinfo=dt.timezone.utc)


@pytest.fixture(autouse=True)
def native_hash(monkeypatch):
    original = verification.hash_file

    def native(path, **kwargs):
        kwargs["os_type"] = "windows" if sys.platform == "win32" else "linux"
        return original(path, **kwargs)

    monkeypatch.setattr(verification, "hash_file", native)


def create(factory, tenant, size):
    with factory() as s, s.begin(), tenant_scope(s, tenant):
        row = service.record_backup(
            s,
            tenant_id=tenant,
            kind="logical",
            location_ref="vol://synthetic-backup",
            byte_size=size,
            now=NOW,
        )
        key = row.backup_id
    return key


def read(factory, tenant, key):
    with factory() as s, s.begin(), tenant_scope(s, tenant):
        row = s.get(BackupRecord, key)
        return row.verified, row.checksum_sha256, row.byte_size


def test_sweep_size_failure_stays_unverified_after_commit(app_sessionmaker, pilot, tmp_path):
    tenant = pilot["tenant_a"]
    key = create(app_sessionmaker, tenant, 99)
    p = tmp_path / "short.dump"
    p.write_bytes(b"short")
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, tenant):
        result = verification.verify_pending_backups(
            s, tenant_id=tenant, now=NOW, resolve_path=lambda row: p
        )
    assert key in result["failed"] and key not in result["verified"]
    assert read(app_sessionmaker, tenant, key) == (False, None, 99)


def test_caught_direct_size_error_does_not_mutate_record(app_sessionmaker, pilot, tmp_path):
    tenant = pilot["tenant_a"]
    key = create(app_sessionmaker, tenant, 99)
    p = tmp_path / "short.dump"
    p.write_bytes(b"short")
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, tenant):
        with pytest.raises(InvError):
            verification.verify_backup_bytes(s, tenant_id=tenant, backup_id=key, path=p, now=NOW)
    assert read(app_sessionmaker, tenant, key) == (False, None, 99)


def test_reverification_checks_stored_digest_without_caller_hint(app_sessionmaker, pilot, tmp_path):
    tenant = pilot["tenant_a"]
    key = create(app_sessionmaker, tenant, 4)
    p = tmp_path / "backup.dump"
    p.write_bytes(b"good")
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, tenant):
        verification.verify_backup_bytes(s, tenant_id=tenant, backup_id=key, path=p, now=NOW)
    before = read(app_sessionmaker, tenant, key)
    p.write_bytes(b"evil")
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, tenant):
        with pytest.raises(InvError):
            verification.verify_backup_bytes(s, tenant_id=tenant, backup_id=key, path=p, now=NOW)
    assert read(app_sessionmaker, tenant, key) == before


def test_foreign_tenant_is_denied_before_file_read(app_sessionmaker, pilot, tmp_path, monkeypatch):
    key = create(app_sessionmaker, pilot["tenant_a"], 4)
    p = tmp_path / "backup.dump"
    p.write_bytes(b"good")
    reads = []
    original = verification.hash_file

    def observe(*a, **kw):
        reads.append(True)
        return original(*a, **kw)

    monkeypatch.setattr(verification, "hash_file", observe)
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, pilot["tenant_b"]):
        with pytest.raises(InvError):
            verification.verify_backup_bytes(
                s, tenant_id=pilot["tenant_b"], backup_id=key, path=p, now=NOW
            )
    assert reads == []


def test_two_initial_verifiers_cannot_replace_each_others_digest(app_sessionmaker, pilot, tmp_path):
    tenant = pilot["tenant_a"]
    key = create(app_sessionmaker, tenant, 4)
    paths = [tmp_path / "a.dump", tmp_path / "b.dump"]
    for p, b in zip(paths, [b"aaaa", b"bbbb"]):
        p.write_bytes(b)
    gate = threading.Barrier(2)

    def verify(path):
        gate.wait(timeout=5)
        with app_sessionmaker() as s, s.begin(), tenant_scope(s, tenant):
            try:
                verification.verify_backup_bytes(
                    s, tenant_id=tenant, backup_id=key, path=path, now=NOW
                )
            except InvError:
                return False
        return True

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(verify, paths))
    assert sorted(results) == [False, True]
    assert (
        read(app_sessionmaker, tenant, key)[1]
        == hashlib.sha256(paths[results.index(True)].read_bytes()).hexdigest()
    )


def test_failure_after_promotion_rolls_back_only_that_verification(
    app_sessionmaker, pilot, tmp_path, monkeypatch
):
    tenant = pilot["tenant_a"]
    key = create(app_sessionmaker, tenant, 4)
    p = tmp_path / "backup.dump"
    p.write_bytes(b"good")
    original = service.verify_backup

    def fail(*a, **kw):
        original(*a, **kw)
        raise RuntimeError("injected after promotion")

    monkeypatch.setattr(service, "verify_backup", fail)
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, tenant):
        with pytest.raises(RuntimeError, match="injected"):
            verification.verify_backup_bytes(s, tenant_id=tenant, backup_id=key, path=p, now=NOW)
    assert read(app_sessionmaker, tenant, key) == (False, None, 4)


def test_sweep_continues_after_resolver_error_without_promoting_failure(
    app_sessionmaker, pilot, tmp_path
):
    tenant = pilot["tenant_a"]
    bad = create(app_sessionmaker, tenant, 4)
    good = create(app_sessionmaker, tenant, 4)
    p = tmp_path / "backup.dump"
    p.write_bytes(b"good")

    def resolve(row):
        if row.backup_id == bad:
            raise OSError("synthetic private location unavailable")
        return p

    with app_sessionmaker() as s, s.begin(), tenant_scope(s, tenant):
        result = verification.verify_pending_backups(
            s, tenant_id=tenant, now=NOW, resolve_path=resolve
        )
    assert bad in result["failed"] and good in result["verified"]
    assert read(app_sessionmaker, tenant, bad) == (False, None, 4)
    assert read(app_sessionmaker, tenant, good)[0] is True


def test_caller_hint_cannot_replace_stored_baseline(app_sessionmaker, pilot, tmp_path, monkeypatch):
    tenant = pilot["tenant_a"]
    key = create(app_sessionmaker, tenant, 4)
    p = tmp_path / "backup.dump"
    p.write_bytes(b"good")
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, tenant):
        verification.verify_backup_bytes(s, tenant_id=tenant, backup_id=key, path=p, now=NOW)
    original = read(app_sessionmaker, tenant, key)

    def forbidden(*a, **kw):
        raise AssertionError("contradictory hint must be refused before IO")

    monkeypatch.setattr(verification, "hash_file", forbidden)
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, tenant):
        with pytest.raises(InvError):
            verification.verify_backup_bytes(
                s, tenant_id=tenant, backup_id=key, path=p, expected_sha256="f" * 64, now=NOW
            )
    assert read(app_sessionmaker, tenant, key) == original


@pytest.mark.parametrize("limit", [0, -1, 101, True])
def test_invalid_batch_limit_is_refused_before_work(app_sessionmaker, pilot, limit):
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, pilot["tenant_a"]):
        with pytest.raises(InvError):
            verification.verify_pending_backups(
                s,
                tenant_id=pilot["tenant_a"],
                now=NOW,
                resolve_path=lambda r: pytest.fail("must not resolve"),
                limit=limit,
            )
