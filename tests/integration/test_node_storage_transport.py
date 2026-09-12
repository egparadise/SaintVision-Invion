"""Real Go daemon, pinned mTLS, actual files and Python signature verification."""

import base64
from dataclasses import asdict, replace
import hashlib
import json
import os
import select
import subprocess
import time
from urllib.parse import urlsplit

import pytest
from inv.errors import DomainError
from inv.ids import new_id
from inv.node_channels import NodeChannels
from inv.storage_sampling import SampleItem, canonical, new_challenge, verify_sample
from test_node_delivery import remote, policy
from test_node_runtime import node_runtime
from test_approvals import approval

pytestmark = pytest.mark.postgres


def challenge_for(a, name="data.bin"):
    return new_challenge(
        channel=NodeChannels(a.e.db).snapshot(a.node, observation_only=True),
        project_id=a.e.project,
        run_id=a.run["runId"],
        contribution_id=a.contribution,
        root_version=1,
        catalogued=3,
        items=[SampleItem(new_id("dtl"), 1, name, 12, hashlib.sha256(b"actual bytes").hexdigest())],
    )


@pytest.fixture
def storage_remote(remote):
    a = remote
    a.root = a.path / "contributed"
    a.root.mkdir()
    (a.root / "data.bin").write_bytes(b"actual bytes")
    a.contribution = new_id("stc")
    challenge = challenge_for(a)
    a.storage_policy = a.path / "storage-policy.json"
    a.storage_policy.write_bytes(
        canonical(
            dict(
                channel=asdict(challenge.channel),
                contribution_id=a.contribution,
                root_version=1,
                root=str(a.root),
            )
        )
    )
    a.storage_policy.chmod(0o600)
    args = list(a.daemon.args)
    args[args.index("--listen") + 1] = urlsplit(a.endpoint).netloc
    args += ["--storage-policy", str(a.storage_policy)]
    a.daemon.terminate()
    a.daemon.communicate(timeout=12)
    a.daemon = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    ready, _, _ = select.select([a.daemon.stdout], [], [], 10)
    assert ready, "storage Node startup timed out"
    line = a.daemon.stdout.readline()
    assert line, "storage Node startup rejected: " + a.daemon.stderr.read()
    assert "https://" + json.loads(line)["listening"] == a.endpoint
    return a


def collect(a, challenge=None):
    challenge = challenge or challenge_for(a)
    envelope, certificate = a.client.storage_sample(challenge.channel, challenge)
    assert certificate == a.server_cert.der
    return verify_sample(challenge, envelope, certificate_der=certificate), envelope, challenge


def test_go_mtls_signed_sample_verified_by_python_without_operational_record(storage_remote):
    a = storage_remote
    with a.e.db.transaction(a.e.tenant) as c:
        before = c.execute("SELECT count(*) AS n FROM inv.evidence").fetchone()["n"]
    report, _, _ = collect(a)
    assert report.sample_healthy and report.examined == 1 and report.unsampled == 2
    assert not report.recorded and not report.operational_acceptance_assessed
    with a.e.db.transaction(a.e.tenant) as c:
        assert c.execute("SELECT count(*) AS n FROM inv.evidence").fetchone()["n"] == before
    assert not list((a.path / "state").glob("*.intent"))


@pytest.mark.parametrize(
    "fault",
    ["corrupt", "missing", "size", "unknown", "oversized", "symlink", "hardlink", "parent-link"],
)
def test_go_file_failures_never_become_healthy(storage_remote, fault):
    a = storage_remote
    challenge = challenge_for(a)
    path = a.root / "data.bin"
    if fault == "corrupt":
        path.write_bytes(b"broken bytes")
    elif fault == "missing":
        path.unlink()
    elif fault == "size":
        challenge = replace(challenge, items=(replace(challenge.items[0], byte_size=13),))
    elif fault == "unknown":
        challenge = replace(challenge, items=(replace(challenge.items[0], checksum_sha256=None),))
    elif fault == "oversized":
        with path.open("wb") as f:
            f.truncate(1048577)
    elif fault in {"symlink", "hardlink"}:
        outside = a.path / "outside.bin"
        outside.write_bytes(b"actual bytes")
        path.unlink()
        (os.symlink if fault == "symlink" else os.link)(outside, path)
    else:
        outside = a.path / "outside"
        outside.mkdir()
        (outside / "data.bin").write_bytes(b"actual bytes")
        os.symlink(outside, a.root / "linked")
        challenge = replace(
            challenge, items=(replace(challenge.items[0], relative_path="linked/data.bin"),)
        )
    report, _, _ = collect(a, challenge)
    assert not report.sample_healthy
    assert report.unverifiable == int(fault == "unknown")


def test_unicode_manifest_has_same_cross_language_digest(storage_remote):
    a = storage_remote
    name = "샘플😀.bin"
    (a.root / name).write_bytes(b"actual bytes")
    assert collect(a, challenge_for(a, name))[0].sample_healthy


def test_local_policy_change_and_root_replacement_fail_closed(storage_remote):
    a = storage_remote
    original = a.storage_policy.read_bytes()
    a.storage_policy.write_bytes(original + b" ")
    with pytest.raises(DomainError):
        collect(a)
    a.storage_policy.write_bytes(original)
    a.root.rename(a.path / "previous-root")
    a.root.mkdir()
    (a.root / "data.bin").write_bytes(b"actual bytes")
    with pytest.raises(DomainError):
        collect(a)


def test_revoked_mtls_client_cannot_collect(storage_remote):
    a = storage_remote
    policy(a, 2, [])
    with pytest.raises(DomainError):
        collect(a)


@pytest.mark.parametrize(
    "fault", ["root_version", "contribution", "expired", "duplicate", "path", "extra"]
)
def test_go_rejects_invalid_request_even_when_sent_without_python_checks(storage_remote, fault):
    a = storage_remote
    challenge = challenge_for(a)
    value = json.loads(canonical(asdict(challenge)))
    if fault == "root_version":
        value["root_version"] += 1
    elif fault == "contribution":
        value["contribution_id"] = new_id("stc")
    elif fault == "expired":
        value.update(issued_at=int(time.time()) - 40, expires_at=int(time.time()) - 10)
    elif fault == "duplicate":
        value["items"] *= 2
    elif fault == "path":
        value["items"][0]["relative_path"] = "../outside.bin"
    else:
        value["ignored"] = True
    request = {"challenge": base64.b64encode(canonical(value)).decode()}
    with pytest.raises(DomainError):
        a.client._request(
            challenge.channel, request, "/v1/storage/sample", "NodeStorageSignedSample"
        )


def test_default_node_does_not_enable_storage_read(remote):
    a = remote
    a.contribution = new_id("stc")
    with pytest.raises(DomainError):
        collect(a)
