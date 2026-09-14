"""Internal signed sample protocol; no HTTP route or operational DB writes.

The issuer must persist the exact Challenge with a real authorized Run. The
eventual commit must lock/recheck channel, epoch, contribution/catalog versions
and consume its nonce atomically with existing Run Evidence and StorageCheck.
Signature verification alone does NOT provide those transactional guarantees.
The Node adapter must supply a locally configured root/key and authenticated
request authority; none of those can be selected by an untrusted request.
"""

import base64
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import PurePosixPath
import re
import secrets
import time
from types import SimpleNamespace
from uuid import UUID

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from saintvision.storage.readroot import ReadRoot
from saintvision.storage.sampling import check_sample
from .errors import DomainError
from .node_channels import ChannelProof, certificate_identity, endpoint_parts
from .node_transport import strict_json
from .tooling import NodePrincipal

PROTOCOL = "node-storage-sample-v1"
DOMAIN = b"saintvision/node-storage-sample/v1\x00"
MAX_FILES = 32
MAX_FILE_BYTES = 1024 * 1024
MAX_PAYLOAD = 65536


def reject():
    raise DomainError("VERIFY-0030", "Signed storage sample rejected", 422)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def identifier(value, prefix):
    if not isinstance(value, str) or not re.fullmatch(prefix + r"_[0-9A-HJKMNP-TV-Z]{26}", value):
        reject()


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        reject()


def sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        reject()


@dataclass(frozen=True)
class SampleItem:
    location_id: str
    version: int
    relative_path: str
    byte_size: int
    checksum_sha256: str | None


@dataclass(frozen=True)
class Challenge:
    channel: ChannelProof
    project_id: str
    run_id: str
    contribution_id: str
    root_version: int
    catalogued: int
    items: tuple[SampleItem, ...]
    nonce: str
    issued_at: int
    expires_at: int

    def validate(self, now):
        if not isinstance(self.channel, ChannelProof):
            reject()
        for value in (self.channel.tenant_id, self.channel.recovery_epoch):
            try:
                if str(UUID(value)) != value:
                    reject()
            except (TypeError, ValueError, AttributeError):
                reject()
        endpoint_parts(self.channel.endpoint)
        identifier(self.channel.node_id, "nod")
        identifier(self.project_id, "prj")
        identifier(self.run_id, "run")
        identifier(self.contribution_id, "stc")
        integer(self.channel.version, 1, 2**31 - 1)
        integer(self.root_version, 1, 2**31 - 1)
        sha(self.channel.certificate_sha256)
        sha(self.nonce)
        integer(now, 0, 2**53 - 1)
        integer(self.issued_at, 0, now)
        integer(self.expires_at, now + 1, self.issued_at + 30)
        if type(self.items) is not tuple or not 1 <= len(self.items) <= MAX_FILES:
            reject()
        integer(self.catalogued, len(self.items), 2**53 - 1)
        seen = set()
        paths = set()
        for item in self.items:
            if not isinstance(item, SampleItem):
                reject()
            identifier(item.location_id, "dtl")
            integer(item.version, 1, 2**31 - 1)
            integer(item.byte_size, 0, MAX_FILE_BYTES)
            if item.checksum_sha256 is not None:
                sha(item.checksum_sha256)
            path = item.relative_path
            if (
                not isinstance(path, str)
                or not 1 <= len(path) <= 1024
                or any(ord(c) < 32 for c in path)
                or any(c in path for c in ("\\", ":", "%"))
                or PurePosixPath(path).is_absolute()
                or any(p in ("", ".", "..") for p in path.split("/"))
                or item.location_id in seen
                or path in paths
            ):
                reject()
            seen.add(item.location_id)
            paths.add(path)
        if len(canonical(asdict(self))) > MAX_PAYLOAD:
            reject()

    def digest(self):
        return hashlib.sha256(DOMAIN + canonical(asdict(self))).hexdigest()


def new_challenge(
    *, channel, project_id, run_id, contribution_id, root_version, catalogued, items, now=None
):
    now = int(time.time()) if now is None else now
    value = Challenge(
        channel,
        project_id,
        run_id,
        contribution_id,
        root_version,
        catalogued,
        tuple(items),
        secrets.token_hex(32),
        now,
        now + 30,
    )
    value.validate(now)
    return value


def certificate_key(certificate_der, channel, now):
    if type(certificate_der) is not bytes or not 1 <= len(certificate_der) <= 16384:
        reject()
    fingerprint, _ = certificate_identity(
        certificate_der,
        NodePrincipal(channel.tenant_id, channel.node_id),
        channel.recovery_epoch,
        now=datetime.fromtimestamp(now, timezone.utc),
    )
    if fingerprint != channel.certificate_sha256:
        reject()
    key = x509.load_der_x509_certificate(certificate_der).public_key()
    if not isinstance(key, Ed25519PublicKey):
        reject()
    return key


@dataclass(frozen=True)
class ConfiguredSampler:
    """Trusted local configuration, never constructed from a remote body."""

    channel: ChannelProof
    contribution_id: str
    root_version: int
    root: ReadRoot
    key: Ed25519PrivateKey
    certificate_der: bytes

    def __post_init__(self):
        if not isinstance(self.root, ReadRoot) or not isinstance(self.key, Ed25519PrivateKey):
            reject()

    def collect(self, challenge, *, clock=time.time):
        now = int(clock())
        challenge.validate(now)
        if (challenge.channel, challenge.contribution_id, challenge.root_version) != (
            self.channel,
            self.contribution_id,
            self.root_version,
        ):
            reject()
        public_key = certificate_key(self.certificate_der, self.channel, now)
        if public_key.public_bytes_raw() != self.key.public_key().public_bytes_raw():
            reject()
        result = check_sample(
            SimpleNamespace(normalized_path=str(self.root.path)),
            challenge.items,
            len(challenge.items),
            allowed_root=self.root,
            max_bytes=MAX_FILE_BYTES,
        )
        observed = int(clock())
        challenge.validate(observed)  # No signature on expired/long-running work.
        if observed < now:
            reject()
        certificate_key(self.certificate_der, self.channel, observed)
        payload = canonical(
            {
                "protocol": PROTOCOL,
                "challengeSha256": challenge.digest(),
                "observedAt": observed,
                "observations": result["observations"],
            }
        )
        if len(payload) > MAX_PAYLOAD:
            reject()
        return {
            "payload": base64.b64encode(payload).decode("ascii"),
            "signature": base64.b64encode(self.key.sign(DOMAIN + payload)).decode("ascii"),
        }


@dataclass(frozen=True)
class VerifiedSample:
    challenge_sha256: str
    payload_sha256: str
    payload: bytes
    observed_at: int
    examined: int
    unsampled: int
    sampled: int
    mismatches: int
    unverifiable: int
    sample_healthy: bool
    # Only a later transaction can provide these guarantees.
    recorded: bool = False
    operational_acceptance_assessed: bool = False


def verify_sample(challenge, envelope, *, certificate_der, now=None):
    now = int(time.time()) if now is None else now
    challenge.validate(now)
    if type(envelope) is not dict or set(envelope) != {"payload", "signature"}:
        reject()
    decoded = {}
    for field, limit in (("payload", MAX_PAYLOAD), ("signature", 64)):
        value = envelope[field]
        if not isinstance(value, str) or len(value) > 4 * ((limit + 2) // 3):
            reject()
        try:
            raw = base64.b64decode(value, validate=True)
        except (ValueError, TypeError):
            reject()
        if len(raw) > limit or base64.b64encode(raw).decode("ascii") != value:
            reject()
        decoded[field] = raw
    payload = decoded["payload"]
    try:
        certificate_key(certificate_der, challenge.channel, now).verify(
            decoded["signature"], DOMAIN + payload
        )
    except (InvalidSignature, ValueError):
        reject()
    result = strict_json(payload)
    if (
        type(result) is not dict
        or set(result) != {"protocol", "challengeSha256", "observedAt", "observations"}
        or result["protocol"] != PROTOCOL
        or result["challengeSha256"] != challenge.digest()
        or canonical(result) != payload
    ):
        reject()
    integer(result["observedAt"], challenge.issued_at, now)
    certificate_key(certificate_der, challenge.channel, result["observedAt"])
    observations = result["observations"]
    if type(observations) is not list or len(observations) != len(challenge.items):
        reject()
    sampled = mismatches = unverifiable = 0
    for item, observation in zip(challenge.items, observations):
        if (
            type(observation) is not dict
            or set(observation) != {"locationId", "sha256", "byteSize"}
            or observation["locationId"] != item.location_id
            or ((observation["sha256"] is None) != (observation["byteSize"] is None))
        ):
            reject()
        actual_hash, size = observation["sha256"], observation["byteSize"]
        if actual_hash is not None:
            sha(actual_hash)
            integer(size, 0, MAX_FILE_BYTES)
        if item.checksum_sha256 is None:
            if actual_hash is not None:
                reject()
            unverifiable += 1
        else:
            sampled += 1
            mismatches += int(actual_hash != item.checksum_sha256 or size != item.byte_size)
    return VerifiedSample(
        challenge.digest(),
        hashlib.sha256(payload).hexdigest(),
        payload,
        result["observedAt"],
        len(observations),
        challenge.catalogued - len(observations),
        sampled,
        mismatches,
        unverifiable,
        bool(sampled and not mismatches and not unverifiable),
    )
