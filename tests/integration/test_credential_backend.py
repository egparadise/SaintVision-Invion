"""Real Linux files and PostgreSQL registry; synthetic credentials only."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from uuid import uuid4
import psycopg
import pytest
from credential_conformance import CredentialConformance
from raises_no_skip import raises_without_skip
from saintvision.credentials.contract import CredentialContext, CredentialDenied
from saintvision.credentials.linux_file import LinuxFileCredentials
from inv.credential_registry import PostgresCredentialRegistry
from test_postgres import planned

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.credential_backend,
    pytest.mark.skipif(sys.platform != "linux", reason="Actual Linux file backend"),
]


@pytest.fixture
def credential_harness(env, tmp_path, monkeypatch):
    e = env
    root = tmp_path / "secrets"
    root.mkdir(mode=0o700)
    secret = b"synthetic-file-credential-never-a-live-token"
    path = root / (uuid4().hex + ".secret")
    path.write_bytes(secret)
    path.chmod(0o600)
    credential, version = str(uuid4()), str(uuid4())
    subject = "credential-test-requester"
    run = planned(e)["runId"]
    context = CredentialContext(e.tenant, e.project, subject, run)
    h = SimpleNamespace(
        e=e,
        root=root,
        path=path,
        secret=secret,
        context=context,
        reference=f"svcred:1:{credential}:{version}",
        purpose="llm.invoke",
        destination="provider-fixture",
        backend_reads=0,
    )
    h.other_context_values = dict(
        tenant_id=e.other,
        project_id="prj_" + "1" * 26,
        subject_id="other-requester",
        run_id="run_" + "1" * 26,
    )

    def register(v, p):
        info = p.stat()
        with psycopg.connect(e.owner) as c:
            c.execute(
                "INSERT INTO inv.credential_versions VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    e.tenant,
                    e.project,
                    credential,
                    v,
                    h.purpose,
                    h.destination,
                    p.name,
                    info.st_dev,
                    info.st_ino,
                    hashlib.sha256(p.read_bytes()).hexdigest(),
                ),
            )
            c.execute(
                "INSERT INTO inv.credential_grants VALUES(%s,%s,%s,%s,%s,%s,true,clock_timestamp()+interval '10 minutes',NULL,%s)",
                (e.tenant, e.project, credential, v, subject, run, e.epoch),
            )

    with psycopg.connect(e.owner) as c:
        c.execute(
            "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request) VALUES(%s,%s,%s,true)",
            (e.tenant, e.project, subject),
        )
    register(version, path)
    h.resolver = LinuxFileCredentials(root, PostgresCredentialRegistry(e.db))
    original_read = os.read
    registered = {(path.stat().st_dev, path.stat().st_ino)}

    def counted_read(fd, n):
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) in registered:
            h.backend_reads += 1
        return original_read(fd, n)

    monkeypatch.setattr(os, "read", counted_read)

    def mutate(action):
        changes = {
            "revoke": "UPDATE inv.credential_grants SET revoked_at=clock_timestamp() WHERE credential_id=%s",
            "disable": "UPDATE inv.credential_grants SET enabled=false WHERE credential_id=%s",
            "expire": "UPDATE inv.credential_grants SET expires_at=clock_timestamp()-interval '1 second' WHERE credential_id=%s",
            "remove_version": "DELETE FROM inv.credential_grants WHERE credential_id=%s",
            "rebind_destination": "UPDATE inv.credential_grants SET enabled=false WHERE credential_id=%s",
        }
        if action in changes:
            with psycopg.connect(e.owner) as c:
                c.execute(changes[action], (credential,))
        elif action == "revoke_grant":
            with psycopg.connect(e.owner) as c:
                c.execute(
                    "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s AND project_id=%s AND subject_id=%s",
                    (e.tenant, e.project, subject),
                )
        elif action == "rotate_keep_old":
            new = root / (uuid4().hex + ".secret")
            new.write_bytes(b"synthetic-new-version")
            new.chmod(0o600)
            register(str(uuid4()), new)
        elif action in {"root_symlink", "root_replaced"}:
            old = tmp_path / "old-root"
            root.rename(old)
            if action == "root_symlink":
                root.symlink_to(old, target_is_directory=True)
            else:
                root.mkdir(mode=0o700)
        elif action in {"file_symlink", "file_replaced", "outside_root"}:
            old = tmp_path / "old-secret"
            path.rename(old)
            if action == "file_symlink":
                path.symlink_to(old)
            elif action == "outside_root":
                os.link(old, path)
            else:
                path.write_bytes(secret)
                path.chmod(0o600)
        elif action == "public_mode":
            path.chmod(0o640)
        elif action == "wrong_owner":
            try:
                os.chown(path, 1, 1)
            except PermissionError:
                # The Linux runner drops CAP_CHOWN. Create one synthetic file as
                # uid 1 in an isolated, networkless container with a narrowly
                # mounted temp directory; GitHub-hosted runners are not
                # themselves named Docker containers, so `docker exec
                # $HOSTNAME` is not portable.
                shared = Path(tempfile.mkdtemp(prefix="credential-owner-"))
                shared.chmod(0o777)
                other = shared / "synthetic"
                try:
                    result = subprocess.run(
                        [
                            "docker",
                            "run",
                            "--rm",
                            "--network",
                            "none",
                            "--user",
                            "1:1",
                            "--mount",
                            f"type=bind,source={shared},target=/fixture",
                            "--entrypoint",
                            "sh",
                            os.environ.get("INV_TEST_ROLE_GUARD_IMAGE", "postgres:16"),
                            "-c",
                            "umask 077; printf synthetic > /fixture/synthetic",
                        ],
                        capture_output=True,
                        timeout=30,
                    )
                    assert result.returncode == 0, "Isolated owner fixture unavailable"
                    os.replace(other, path)
                finally:
                    if other.exists():
                        other.unlink()
                    shared.rmdir()
        elif action == "non_regular":
            path.unlink()
            os.mkfifo(path, 0o600)
        elif action == "oversize":
            path.write_bytes(b"x" * 65537)
        elif action == "backend_error_with_secret":

            def fail(binding):
                raise OSError(secret.decode())

            monkeypatch.setattr(h.resolver, "_read", fail)
        else:
            raise AssertionError("Unknown credential fixture action")

    h.mutate = mutate
    return h


class TestLinuxPostgresCredentials(CredentialConformance):
    pass


def resolved(h):
    return h.resolver.resolve(h.reference, h.context, h.purpose, h.destination)


@pytest.mark.parametrize("mutation", ["file_replaced", "root_replaced", "inplace"])
def test_substitution_during_real_read_is_rejected(credential_harness, monkeypatch, mutation):
    h = credential_harness
    handle = resolved(h)
    original = os.read
    changed = False

    def swap(fd, n):
        nonlocal changed
        part = original(fd, n)
        info = os.fstat(fd)
        if (
            part
            and not changed
            and (info.st_dev, info.st_ino) == (h.path.stat().st_dev, h.path.stat().st_ino)
        ):
            changed = True
            if mutation == "inplace":
                h.path.write_bytes(b"x" * len(h.secret))
            else:
                h.mutate(mutation)
        return part

    monkeypatch.setattr(os, "read", swap)
    calls = []
    with raises_without_skip(CredentialDenied):
        handle.use(lambda secret: calls.append(True))
    assert changed and not calls


def test_committed_revocation_during_read_prevents_callback(credential_harness, monkeypatch):
    h = credential_harness
    handle = resolved(h)
    read_done, resume = Event(), Event()
    original = h.resolver._read

    def paused(binding):
        content = original(binding)
        read_done.set()
        assert resume.wait(5)
        return content

    monkeypatch.setattr(h.resolver, "_read", paused)
    calls = []
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(handle.use, lambda secret: calls.append(True))
        try:
            assert read_done.wait(5)
            h.mutate("revoke")  # A separate PostgreSQL connection commits.
        finally:
            resume.set()
        with raises_without_skip(CredentialDenied):
            future.result(timeout=5)
    assert calls == []


def test_admitted_callback_does_not_lock_out_revocation(credential_harness):
    h = credential_harness
    handle = resolved(h)
    started, finish = Event(), Event()

    def callback(secret):
        started.set()
        assert finish.wait(5)
        return "already-admitted"

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(handle.use, callback)
        try:
            assert started.wait(5)
            h.mutate("revoke")
        finally:
            finish.set()
        assert future.result(timeout=5) == "already-admitted"
    with raises_without_skip(CredentialDenied):
        handle.use(lambda secret: None)


def test_registry_runtime_cannot_provision_and_other_tenant_cannot_read(credential_harness):
    h = credential_harness
    with h.e.db.transaction(h.e.other) as c:
        assert c.execute("SELECT count(*) AS n FROM inv.credential_versions").fetchone()["n"] == 0
        assert c.execute("SELECT count(*) AS n FROM inv.credential_grants").fetchone()["n"] == 0
    with h.e.db.transaction(h.e.tenant) as c:
        for table in ("credential_versions", "credential_grants"):
            for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                assert (
                    c.execute(
                        "SELECT has_table_privilege(current_user,%s,%s) AS allowed",
                        ("inv." + table, privilege),
                    ).fetchone()["allowed"]
                    is False
                )
    # The only intended failure is the append-only trigger inv.immutable_record()
    # (0001_core.sql: RAISE 'immutable record' USING ERRCODE '23514' -> CheckViolation).
    # content_sha256=repeat('0',64) is a valid column value, so nothing else here should
    # raise; pin the type AND message so a missing UPDATE grant (InsufficientPrivilege,
    # 42501), a column typo (UndefinedColumn), or a connection error can no longer pass
    # this as "immutability enforced". Matches the sibling assertion in
    # test_provisioning_integrity.py.
    with psycopg.connect(h.e.owner) as c, raises_without_skip(
        psycopg.errors.CheckViolation, match="immutable record"
    ):
        c.execute(
            "UPDATE inv.credential_versions SET content_sha256=repeat('0',64) WHERE tenant_id=%s",
            (h.e.tenant,),
        )


@pytest.mark.parametrize("change", ["epoch", "kill", "cancel"])
def test_current_execution_gate_invalidates_credential(credential_harness, change):
    from inv.db import Database

    h = credential_harness
    handle = resolved(h)
    with psycopg.connect(h.e.owner) as c:
        if change == "epoch":
            new_epoch = str(uuid4())
            c.execute("UPDATE inv.control_epoch SET epoch=%s", (new_epoch,))
        elif change == "kill":
            c.execute(
                "UPDATE inv.tenant_controls SET kill_switch=true WHERE tenant_id=%s", (h.e.tenant,)
            )
        else:
            c.execute(
                "UPDATE inv.runs SET state='cancelled',version=version+1 WHERE run_id=%s",
                (h.context.run_id,),
            )
    with raises_without_skip(CredentialDenied):
        handle.use(lambda secret: None)
    if change == "epoch":
        # Even a newly constructed service at the new epoch cannot reuse old grants.
        provider = LinuxFileCredentials(
            h.root, PostgresCredentialRegistry(Database(h.e.runtime, recovery_epoch=new_epoch))
        )
        with raises_without_skip(CredentialDenied):
            provider.resolve(h.reference, h.context, h.purpose, h.destination)
