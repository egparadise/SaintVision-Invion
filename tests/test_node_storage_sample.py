"""Actual file reads and ephemeral Ed25519 certificates, no physical Node claim."""

import base64
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
import pytest

from inv.errors import DomainError
from inv.ids import new_id
from inv.node_channels import ChannelProof, node_uri
from inv.storage_sampling import (
    Challenge,
    ConfiguredSampler,
    DOMAIN,
    MAX_FILE_BYTES,
    SampleItem,
    canonical,
    new_challenge,
    verify_sample,
)
from inv.tooling import NodePrincipal
from saintvision.services.verification import hash_file, VerificationFailed
from saintvision.storage.readroot import ReadRoot
from test_verification_readroot import directory_link

NOW = 1800000000


def cert(key, tenant, node, epoch, *, expires=NOW + 3600):
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "synthetic-node")])
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.fromtimestamp(NOW - 60, timezone.utc))
        .not_valid_after(datetime.fromtimestamp(expires, timezone.utc))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.UniformResourceIdentifier(node_uri(NodePrincipal(tenant, node), epoch))]
            ),
            critical=False,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(key, None)
    )


@pytest.fixture
def sample(tmp_path):
    root_path = tmp_path / "owned"
    root_path.mkdir()
    (root_path / "data.bin").write_bytes(b"actual bytes")
    tenant, node, epoch = str(uuid4()), new_id("nod"), str(uuid4())
    key = Ed25519PrivateKey.generate()
    certificate = cert(key, tenant, node, epoch)
    der = certificate.public_bytes(serialization.Encoding.DER)
    channel = ChannelProof(
        tenant,
        node,
        epoch,
        1,
        "https://node.invalid:18443",
        certificate.fingerprint(hashes.SHA256()).hex(),
    )
    item = SampleItem(new_id("dtl"), 1, "data.bin", 12, hashlib.sha256(b"actual bytes").hexdigest())
    challenge = new_challenge(
        channel=channel,
        project_id=new_id("prj"),
        run_id=new_id("run"),
        contribution_id=new_id("stc"),
        root_version=2,
        catalogued=7,
        items=[item],
        now=NOW,
    )
    worker = ConfiguredSampler(
        channel=channel,
        contribution_id=challenge.contribution_id,
        root_version=2,
        root=ReadRoot(root_path),
        key=key,
        certificate_der=der,
    )
    return worker, challenge


def collect(worker, challenge):
    return worker.collect(challenge, clock=lambda: NOW)


def verify(worker, challenge, envelope, **kw):
    return verify_sample(
        challenge, envelope, certificate_der=worker.certificate_der, now=kw.get("now", NOW)
    )


def resign(worker, envelope, mutate):
    data = json.loads(base64.b64decode(envelope["payload"]))
    mutate(data)
    raw = canonical(data)
    return {
        "payload": base64.b64encode(raw).decode(),
        "signature": base64.b64encode(worker.key.sign(DOMAIN + raw)).decode(),
    }


def test_real_bytes_bound_to_run_and_certificate_without_operational_write(sample):
    worker, challenge = sample
    envelope = collect(worker, challenge)
    report = verify(worker, challenge, envelope)
    assert report.sample_healthy and report.sampled == 1
    assert report.examined == 1 and report.unsampled == 6
    assert not report.recorded and not report.operational_acceptance_assessed
    assert report.payload_sha256 == hashlib.sha256(report.payload).hexdigest()
    assert challenge.run_id and challenge.digest() == report.challenge_sha256
    # Pure verification permits re-reading evidence; nonce consumption is DB work.
    assert verify(worker, challenge, envelope) == report


@pytest.mark.parametrize("change", ["corrupt", "size", "missing", "unknown_hash", "oversized"])
def test_sample_does_not_turn_unverified_bytes_into_health(sample, change):
    worker, challenge = sample
    path = worker.root.path / "data.bin"
    if change == "corrupt":
        path.write_bytes(b"broken bytes")
    elif change == "size":
        challenge = replace(challenge, items=(replace(challenge.items[0], byte_size=13),))
    elif change == "missing":
        path.unlink()
    elif change == "unknown_hash":
        challenge = replace(challenge, items=(replace(challenge.items[0], checksum_sha256=None),))
    else:
        with path.open("wb") as f:
            f.truncate(MAX_FILE_BYTES + 1)
    report = verify(worker, challenge, collect(worker, challenge))
    assert not report.sample_healthy
    assert report.unverifiable == (1 if change == "unknown_hash" else 0)
    assert report.mismatches == (0 if change == "unknown_hash" else 1)


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_id", new_id("run")),
        ("project_id", new_id("prj")),
        ("contribution_id", new_id("stc")),
        ("root_version", 3),
        ("nonce", "ab" * 32),
        ("catalogued", 8),
        ("issued_at", NOW - 1),
        ("expires_at", NOW + 29),
    ],
)
def test_other_challenge_cannot_reuse_signature(sample, field, value):
    worker, challenge = sample
    envelope = collect(worker, challenge)
    with pytest.raises(DomainError):
        verify(worker, replace(challenge, **{field: value}), envelope)


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", str(uuid4())),
        ("node_id", new_id("nod")),
        ("recovery_epoch", str(uuid4())),
        ("version", 2),
        ("endpoint", "https://elsewhere.invalid"),
        ("certificate_sha256", "00" * 32),
    ],
)
def test_channel_scope_change_refused_before_read_and_on_verification(
    sample, monkeypatch, field, value
):
    worker, challenge = sample
    envelope = collect(worker, challenge)
    changed = replace(challenge, channel=replace(challenge.channel, **{field: value}))
    reads = []
    monkeypatch.setattr("inv.storage_sampling.check_sample", lambda *a, **kw: reads.append(True))
    with pytest.raises(DomainError):
        collect(worker, changed)
    assert reads == []
    with pytest.raises(DomainError):
        verify(worker, changed, envelope)


@pytest.mark.parametrize(
    "field,value",
    [
        ("relative_path", "different.bin"),
        ("version", 2),
        ("byte_size", 11),
        ("checksum_sha256", "00" * 32),
        ("location_id", new_id("dtl")),
    ],
)
def test_catalog_mutation_cannot_reuse_signature(sample, field, value):
    worker, challenge = sample
    envelope = collect(worker, challenge)
    changed = replace(challenge, items=(replace(challenge.items[0], **{field: value}),))
    with pytest.raises(DomainError):
        verify(worker, changed, envelope)


@pytest.mark.parametrize(
    "path",
    [
        "../secret",
        "/etc/passwd",
        "C:/secret",
        "x\\secret",
        "x/../secret",
        "./data.bin",
        "x//data.bin",
        "%2e%2e/secret",
        "data.bin\x00",
    ],
)
def test_unsafe_manifest_rejected_before_read(sample, monkeypatch, path):
    worker, challenge = sample
    changed = replace(challenge, items=(replace(challenge.items[0], relative_path=path),))
    reads = []
    monkeypatch.setattr("inv.storage_sampling.check_sample", lambda *a, **kw: reads.append(True))
    with pytest.raises(DomainError):
        collect(worker, changed)
    assert reads == []


def test_directory_link_escape_is_signed_as_failed_observation(sample, tmp_path):
    worker, challenge = sample
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "data.bin").write_bytes(b"actual bytes")
    directory_link(worker.root.path / "linked", outside)
    challenge = replace(
        challenge, items=(replace(challenge.items[0], relative_path="linked/data.bin"),)
    )
    report = verify(worker, challenge, collect(worker, challenge))
    assert not report.sample_healthy and report.mismatches == 1


@pytest.mark.parametrize(
    "change", ["empty", "duplicate", "bool_version", "over_count", "over_size", "long_ttl"]
)
def test_invalid_or_unbounded_challenge_refused(sample, change):
    worker, challenge = sample
    changes = {
        "empty": {"items": ()},
        "duplicate": {"items": challenge.items * 2},
        "bool_version": {"root_version": True},
        "over_count": {"items": challenge.items * 33},
        "over_size": {"items": (replace(challenge.items[0], byte_size=MAX_FILE_BYTES + 1),)},
        "long_ttl": {"expires_at": NOW + 31},
    }
    with pytest.raises(DomainError):
        collect(worker, replace(challenge, **changes[change]))


@pytest.mark.parametrize("now", [NOW - 1, NOW + 30, NOW + 31])
def test_expired_or_future_challenge_refused(sample, now):
    worker, challenge = sample
    envelope = collect(worker, challenge)
    with pytest.raises(DomainError):
        verify(worker, challenge, envelope, now=now)


def test_expiry_during_read_does_not_produce_signature(sample):
    worker, challenge = sample
    ticks = iter([NOW, NOW + 30])
    with pytest.raises(DomainError):
        worker.collect(challenge, clock=lambda: next(ticks))


def test_unrelated_key_cannot_collect_or_sign(sample):
    worker, challenge = sample
    envelope = collect(worker, challenge)
    worker = replace(worker, key=Ed25519PrivateKey.generate())
    with pytest.raises(DomainError):
        collect(worker, challenge)
    raw = base64.b64decode(envelope["payload"])
    envelope["signature"] = base64.b64encode(worker.key.sign(DOMAIN + raw)).decode()
    with pytest.raises(DomainError):
        verify(worker, challenge, envelope)


@pytest.mark.parametrize(
    "change",
    [
        "omit",
        "duplicate",
        "extra",
        "bool_size",
        "future",
        "claim_health",
        "wrong_hash_type",
        "unpaired",
    ],
)
def test_valid_signature_with_invalid_content_is_not_accepted(sample, change):
    worker, challenge = sample
    envelope = collect(worker, challenge)

    def mutate(data):
        row = data["observations"][0]
        if change == "omit":
            data["observations"] = []
        elif change == "duplicate":
            data["observations"] *= 2
        elif change == "extra":
            row["path"] = "secret"
        elif change == "bool_size":
            row["byteSize"] = True
        elif change == "future":
            data["observedAt"] = NOW + 1
        elif change == "claim_health":
            data["healthy"] = True
        elif change == "wrong_hash_type":
            row["sha256"] = []
        elif change == "unpaired":
            row["byteSize"] = None

    with pytest.raises(DomainError):
        verify(worker, challenge, resign(worker, envelope, mutate))


def test_expired_certificate_and_different_pin_rejected(sample):
    worker, challenge = sample
    envelope = collect(worker, challenge)
    expired = cert(
        worker.key,
        worker.channel.tenant_id,
        worker.channel.node_id,
        worker.channel.recovery_epoch,
        expires=NOW,
    )
    with pytest.raises(DomainError):
        verify_sample(
            challenge,
            envelope,
            certificate_der=expired.public_bytes(serialization.Encoding.DER),
            now=NOW,
        )
    unrelated = cert(
        worker.key, worker.channel.tenant_id, worker.channel.node_id, worker.channel.recovery_epoch
    )
    with pytest.raises(DomainError):
        verify_sample(
            challenge,
            envelope,
            certificate_der=unrelated.public_bytes(serialization.Encoding.DER),
            now=NOW,
        )


def test_byte_budget_rejects_before_stream_read(sample, monkeypatch):
    worker, _ = sample

    class NoRead:
        def seek(self, *a):
            pytest.fail("must reject before seek/read")

        def read(self, *a):
            pytest.fail("must reject before read")

    from contextlib import contextmanager

    @contextmanager
    def oversized(*a):
        yield NoRead(), MAX_FILE_BYTES + 1

    monkeypatch.setattr(worker.root, "open", oversized)
    with pytest.raises(VerificationFailed):
        hash_file(
            worker.root.path / "data.bin",
            allowed_root=worker.root,
            os_type="windows" if __import__("os").name == "nt" else "linux",
            max_bytes=MAX_FILE_BYTES,
        )


@pytest.mark.parametrize(
    "change",
    ["tamper", "bad_base64", "too_large", "short_signature", "extra_field", "wrong_domain"],
)
def test_wire_corruption_and_signature_domain_rejected(sample, change):
    worker, challenge = sample
    envelope = collect(worker, challenge)
    if change == "tamper":
        raw = base64.b64decode(envelope["payload"]).replace(b"observedAt", b"observedOn")
        envelope["payload"] = base64.b64encode(raw).decode()
    elif change == "bad_base64":
        envelope["payload"] = "!"
    elif change == "too_large":
        envelope["payload"] = "A" * 90000
    elif change == "short_signature":
        envelope["signature"] = base64.b64encode(b"short").decode()
    elif change == "extra_field":
        envelope["healthy"] = True
    else:
        envelope["signature"] = base64.b64encode(
            worker.key.sign(base64.b64decode(envelope["payload"]))
        ).decode()
    with pytest.raises(DomainError):
        verify(worker, challenge, envelope)


@pytest.mark.parametrize("field,value", [("root_version", 3), ("contribution_id", new_id("stc"))])
def test_root_configuration_mismatch_rejected_before_read(sample, monkeypatch, field, value):
    worker, challenge = sample
    reads = []
    monkeypatch.setattr("inv.storage_sampling.check_sample", lambda *a, **kw: reads.append(True))
    with pytest.raises(DomainError):
        collect(worker, replace(challenge, **{field: value}))
    assert reads == []


@pytest.mark.parametrize("budget", [-1, True, 1.5, "10"])
def test_invalid_byte_budget_rejected(sample, budget):
    worker, _ = sample
    with pytest.raises(VerificationFailed):
        hash_file(worker.root.path / "data.bin", allowed_root=worker.root, max_bytes=budget)
