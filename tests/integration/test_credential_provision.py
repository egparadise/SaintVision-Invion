"""Operator provisioning against actual Linux files and disposable PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4
import os
import json
import subprocess
import sys
import psycopg
import pytest
import importlib.util
from pathlib import Path

_admin_path = Path(__file__).resolve().parents[2] / "tools" / "provision_credentials.py"
_admin_spec = importlib.util.spec_from_file_location("credential_admin_under_test", _admin_path)
admin = importlib.util.module_from_spec(_admin_spec)
_admin_spec.loader.exec_module(admin)
from saintvision.credentials.contract import CredentialDenied
from test_credential_backend import credential_harness

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(sys.platform != "linux", reason="Linux credentials"),
]


def manifest(h, action, *, version=None, path=None):
    c = h.context
    m = dict(
        tenant=c.tenant_id,
        project=c.project_id,
        subject=c.subject_id,
        run=c.run_id,
        epoch=h.e.epoch,
        credential=h.reference.split(":")[2],
        version=version or h.reference.split(":")[3],
    )
    if action in {"register", "rotate"}:
        m.update(file=(path or h.path).name, purpose=h.purpose, destination=h.destination)
    if action in {"grant", "rotate"}:
        m["expires"] = (datetime.now(timezone.utc) + timedelta(minutes=8)).isoformat()
    if action == "rotate":
        m["oldVersion"] = h.reference.split(":")[3]
    return m


def call(h, m, action, apply=True):
    return admin.provision(h.e.owner, h.root, m, action, apply=apply)


def newfile(h):
    p = h.root / (uuid4().hex + ".secret")
    p.write_bytes(b"synthetic-rotated-token")
    p.chmod(0o600)
    return p


def read(h, ref):
    return h.resolver.resolve(ref, h.context, h.purpose, h.destination).use(lambda b: b)


def count(h, table, version):
    assert table in ("credential_versions", "credential_grants")
    with psycopg.connect(h.e.owner) as c:
        return c.execute(
            "SELECT count(*) FROM inv." + table + " WHERE tenant_id=%s AND version_id=%s",
            (h.e.tenant, version),
        ).fetchone()[0]


def test_register_check_is_read_only_and_grant_is_explicit(credential_harness):
    h = credential_harness
    v = str(uuid4())
    p = newfile(h)
    reg = manifest(h, "register", version=v, path=p)
    result = call(h, reg, "register", apply=False)
    assert result["status"] == "checked" and count(h, "credential_versions", v) == 0
    result = call(h, reg, "register")
    assert result["status"] == "applied"
    assert call(h, reg, "register")["status"] == "unchanged"
    with pytest.raises(CredentialDenied):
        read(h, result["reference"])
    grant = manifest(h, "grant", version=v)
    assert call(h, grant, "grant", apply=False)["status"] == "checked"
    assert count(h, "credential_grants", v) == 0
    assert call(h, grant, "grant")["status"] == "applied"
    assert call(h, grant, "grant")["status"] == "unchanged"
    assert read(h, result["reference"]) == b"synthetic-rotated-token"


def test_rotation_replay_keeps_old_reference_revoked(credential_harness):
    h = credential_harness
    old = h.resolver.resolve(h.reference, h.context, h.purpose, h.destination)
    m = manifest(h, "rotate", version=str(uuid4()), path=newfile(h))
    result = call(h, m, "rotate")
    assert read(h, result["reference"]) == b"synthetic-rotated-token"
    with pytest.raises(CredentialDenied):
        old.use(lambda b: b)
    assert call(h, m, "rotate")["status"] == "unchanged"
    assert h.path.read_bytes() == h.secret


def test_revoke_does_not_need_file_and_cannot_be_reactivated(credential_harness):
    h = credential_harness
    m = manifest(h, "revoke")
    h.path.unlink()
    assert call(h, m, "revoke")["status"] == "applied"
    assert call(h, m, "revoke")["status"] == "unchanged"
    with pytest.raises(CredentialDenied):
        read(h, h.reference)
    h.path.write_bytes(h.secret)
    h.path.chmod(0o600)
    with pytest.raises(admin.ProvisioningDenied):
        call(h, manifest(h, "grant"), "grant")


def test_competing_rotations_only_one_can_replace_the_old_grant(credential_harness):
    h = credential_harness
    manifests = [manifest(h, "rotate", version=str(uuid4()), path=newfile(h)) for _ in range(2)]
    barrier = Barrier(2)

    def rotate(m):
        barrier.wait(timeout=5)
        try:
            return call(h, m, "rotate")["reference"]
        except admin.ProvisioningDenied:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(rotate, manifests))
    assert sum(r is not None for r in results) == 1
    assert sum(count(h, "credential_grants", m["version"]) for m in manifests) == 1
    assert sum(count(h, "credential_versions", m["version"]) for m in manifests) == 1
    with pytest.raises(CredentialDenied):
        read(h, h.reference)


def test_audit_failure_rolls_back_rotation(credential_harness, monkeypatch):
    h = credential_harness
    m = manifest(h, "rotate", version=str(uuid4()), path=newfile(h))

    def fail(*a, **kw):
        raise RuntimeError("synthetic-private-detail")

    monkeypatch.setattr(admin, "event", fail)
    with pytest.raises(admin.ProvisioningDenied) as error:
        call(h, m, "rotate")
    assert "synthetic-private-detail" not in str(error.value)
    assert count(h, "credential_versions", m["version"]) == 0
    assert count(h, "credential_grants", m["version"]) == 0
    assert read(h, h.reference) == h.secret


@pytest.mark.parametrize(
    "change",
    [
        "tenant",
        "project",
        "subject",
        "run",
        "epoch",
        "expired",
        "destination",
        "oldVersion",
        "public_mode",
        "symlink",
    ],
)
def test_invalid_rotation_leaves_old_grant_and_no_new_version(credential_harness, change):
    h = credential_harness
    p = newfile(h)
    m = manifest(h, "rotate", version=str(uuid4()), path=p)
    if change in ("tenant", "epoch", "oldVersion"):
        m[change] = str(uuid4())
    elif change == "project":
        m["project"] = "prj_" + "1" * 26
    elif change == "run":
        m["run"] = "run_" + "1" * 26
    elif change == "subject":
        m["subject"] = "different-subject"
    elif change == "expired":
        m["expires"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    elif change == "destination":
        m["destination"] = "other-destination"
    elif change == "public_mode":
        p.chmod(0o640)
    elif change == "symlink":
        p.unlink()
        p.symlink_to(h.path)
    # ProvisioningDenied carries one fixed message for every policy rejection, so per-cause
    # discrimination is impossible here; the real proof that the right thing happened is the
    # no-state-change pair below (no new version, secret intact). Pin the message so a
    # DB/internal failure (now ProvisioningDatabaseError / ProvisioningInternalError after
    # the 25051e3 split) can no longer pass as a policy denial.
    with pytest.raises(admin.ProvisioningDenied, match="Credential provisioning refused"):
        call(h, m, "rotate")
    assert count(h, "credential_versions", m["version"]) == 0
    assert read(h, h.reference) == h.secret


def test_runtime_database_role_cannot_provision(credential_harness):
    h = credential_harness
    m = manifest(h, "revoke")
    with pytest.raises(admin.ProvisioningDenied):
        admin.provision(h.e.db._dsn, h.root, m, "revoke", apply=True)
    assert read(h, h.reference) == h.secret


def test_revocation_survives_kill_switch_and_project_disable(credential_harness):
    h = credential_harness
    with psycopg.connect(h.e.owner) as c:
        c.execute(
            "UPDATE inv.tenant_controls SET kill_switch=true WHERE tenant_id=%s", (h.e.tenant,)
        )
        c.execute("UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s", (h.e.tenant,))
    assert call(h, manifest(h, "revoke"), "revoke")["status"] == "applied"


def test_cli_default_check_and_no_sensitive_output(credential_harness, tmp_path):
    h = credential_harness
    m = manifest(h, "register", version=str(uuid4()), path=newfile(h))
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(m))
    args = [
        sys.executable,
        str(admin.ROOT / "tools/provision_credentials.py"),
        "register",
        "--manifest",
        str(path),
        "--root",
        str(h.root),
    ]
    r = subprocess.run(
        args,
        env={**os.environ, "INV_CREDENTIAL_ADMIN_DSN": h.e.owner},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 0
    assert json.loads(r.stdout)["status"] == "checked"
    assert count(h, "credential_versions", m["version"]) == 0
    assert h.e.owner not in r.stdout + r.stderr and h.secret.decode() not in r.stdout + r.stderr
    applied = subprocess.run(
        args + ["--apply"],
        env={**os.environ, "INV_CREDENTIAL_ADMIN_DSN": h.e.owner},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert applied.returncode == 0
    assert json.loads(applied.stdout)["status"] == "applied"
    assert count(h, "credential_versions", m["version"]) == 1
    assert count(h, "credential_grants", m["version"]) == 0
    path.write_text("{ malformed synthetic-private-detail")
    r = subprocess.run(
        args,
        env={**os.environ, "INV_CREDENTIAL_ADMIN_DSN": h.e.owner},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 2 and "synthetic-private-detail" not in r.stdout + r.stderr


def test_exact_grant_replay_after_revocation_is_refused(credential_harness):
    h = credential_harness
    v = str(uuid4())
    call(h, manifest(h, "register", version=v, path=newfile(h)), "register")
    grant = manifest(h, "grant", version=v)
    result = call(h, grant, "grant")
    assert read(h, result["reference"]) == b"synthetic-rotated-token"
    call(h, manifest(h, "revoke", version=v), "revoke")
    with pytest.raises(admin.ProvisioningDenied):
        call(h, grant, "grant")
    with pytest.raises(CredentialDenied):
        read(h, result["reference"])


def test_existing_version_cannot_be_rebound_to_another_file(credential_harness):
    h = credential_harness
    changed = manifest(h, "register", path=newfile(h))
    with pytest.raises(admin.ProvisioningDenied):
        call(h, changed, "register")
    assert read(h, h.reference) == h.secret
