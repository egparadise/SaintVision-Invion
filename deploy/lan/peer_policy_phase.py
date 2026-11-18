"""Closed normal :3 peer phases; actual Node-signed floor observations only."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import ExtendedKeyUsageOID

SCHEMA = "saintvision-lan-leaf-rotation:3"
BATCH_SCHEMA = "saintvision-lan-leaf-rotation-batch:3"
MAX_VERSION = 9007199254740991
CLOCK_SKEW_SECONDS = 30
FRESH_SECONDS = 120
MIN_EXPIRY_SECONDS = 600
PEER_FIELDS = {
    "currentPeerPolicyVersion", "currentPeerPolicySHA256",
    "overlapPeerPolicyVersion", "overlapPeerPolicySHA256",
    "finalPeerPolicyVersion", "finalPeerPolicySHA256", "floorObservationSHA256",
}
EXTRA_FILES = ("previous-node-cert.pem", "previous-peer-policy.json", "peer-floor-observation.json")
FLOOR_KEYS = {
    "schemaVersion", "tenantId", "nodeId", "recoveryEpoch", "nonce", "observedAt",
    "certificateDER_SHA256", "peerPolicyVersion", "peerPolicySHA256", "floorSHA256",
    "journalIdentitySHA256", "journalUID", "nodeSignature",
    "servingPID", "servingProcessSHA256", "servingExecutableSHA256", "plainServingProcess",
}
DOMAIN = b"saintvision/node-peer-policy-floor/v2\x00"
HEX = re.compile(r"[0-9a-f]{64}\Z")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def floor_canonical(value):
    """M2:2 exact Go encoding/json.Marshal map body; no trailing newline.

    M2 numbers are integers, so floats/custom JSON values are rejected instead
    of approximating Go's floating-point formatting. Outer receipts are separate.
    """
    def check(item):
        if isinstance(item,str):
            item.encode('utf-8','strict')
        elif item is None or type(item) is bool:
            pass
        elif type(item) is int:
            if not -MAX_VERSION <= item <= MAX_VERSION:
                raise ValueError('M2 integer exceeds its exact wire range')
        elif isinstance(item,list):
            for child in item:check(child)
        elif isinstance(item,dict):
            for key,child in item.items():
                if not isinstance(key,str):raise ValueError('M2 object keys must be strings')
                check(key);check(child)
        else:
            raise ValueError('M2 canonical body contains a non-wire value')
    check(value)
    encoded=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    for character,escaped in (('&',r'\u0026'),('<',r'\u003c'),('>',r'\u003e'),('\u2028',r'\u2028'),('\u2029',r'\u2029')):
        encoded=encoded.replace(character,escaped)
    return encoded.encode('utf-8','strict')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate private protocol field")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Invalid number")))


def version(value, increment=0):
    if type(value) is not int or not 1 <= value <= MAX_VERSION - increment:
        raise ValueError("Peer/channel version is invalid or overflows")
    return value + increment


def versions(manifest):
    p = version(manifest["currentPeerPolicyVersion"], 2) - 2
    if manifest["overlapPeerPolicyVersion"] != p + 1 or manifest["finalPeerPolicyVersion"] != p + 2:
        raise ValueError("Peer phases must be exact independent P+1/P+2")
    version(manifest["overlapPeerPolicyVersion"])
    version(manifest["finalPeerPolicyVersion"])
    version(manifest["targetChannelVersion"])
    if manifest["targetChannelVersion"] != version(manifest["currentChannelVersion"], 1):
        raise ValueError("Channel CAS must remain exactly C+1")
    for key in PEER_FIELDS - {"currentPeerPolicyVersion", "overlapPeerPolicyVersion", "finalPeerPolicyVersion"}:
        if not isinstance(manifest.get(key), str) or not HEX.fullmatch(manifest[key]):
            raise ValueError("Peer phase digest is invalid")


def binding(manifest):
    return {key: manifest[key] for key in sorted(PEER_FIELDS)} if manifest["schemaVersion"] == SCHEMA else {}


def signed_shape(value, body, signature):
    return (isinstance(value, dict) and set(value) == {*body, signature}
            and canonical({k:v for k,v in value.items() if k != signature}) == canonical(body))


def current_policy(raw, *, version_number, scope, control_fingerprint, now):
    value = strict(raw)
    if (not isinstance(value, dict) or set(value) != {"version", "tenantId", "nodeId", "recoveryEpoch", "expiresAt", "clientFingerprints"}
            or type(value["version"]) is not int or value["version"] != version_number
            or (value["tenantId"], value["nodeId"], value["recoveryEpoch"]) != (scope["tenantId"], scope["nodeId"], scope.get("recoveryEpoch", scope.get("epoch")))
            or value["clientFingerprints"] != [control_fingerprint]):
        raise ValueError("Current peer policy scope, version or CP pin differs")
    expiry = datetime.fromisoformat(value["expiresAt"].replace("Z", "+00:00"))
    if expiry.tzinfo is None or not now < expiry <= now + timedelta(days=7):
        raise ValueError("Current peer authority is expired or unbounded; separate offline recovery required")
    return value


def validate_policy(raw, manifest, phase, *, now=None, before_write=False):
    value = strict(raw)
    expected = {
        "version": manifest[phase + "PeerPolicyVersion"],
        "tenantId": manifest["tenantId"], "nodeId": manifest["nodeId"],
        "recoveryEpoch": manifest["recoveryEpoch"],
        "expiresAt": manifest["overlapExpiresAt"] if phase == "overlap" else manifest["certificateNotAfter"],
        "clientFingerprints": ([manifest["currentControlCertificateSHA256"], manifest["nextControlCertificateSHA256"]]
                               if phase == "overlap" else [manifest["nextControlCertificateSHA256"]]),
    }
    if value != expected or type(value.get("version")) is not int or digest(raw) != manifest[phase + "PeerPolicySHA256"]:
        raise ValueError("Exact peer phase policy differs")
    if before_write:
        now = now or datetime.now(timezone.utc)
        expiry = datetime.fromisoformat(value["expiresAt"].replace("Z", "+00:00"))
        if expiry.tzinfo is None or not now + timedelta(seconds=MIN_EXPIRY_SECONDS + CLOCK_SKEW_SECONDS) < expiry <= now + timedelta(days=7, seconds=-CLOCK_SKEW_SECONDS):
            raise ValueError("Peer policy expiry is unsafe before active publication")
    return value


def verify_floor(value, certificate_raw, scope, *, nonce=None, now=None, fresh=True):
    if not isinstance(value, dict) or set(value) != FLOOR_KEYS or value["schemaVersion"] != "saintvision-node-peer-policy-floor:2":
        raise ValueError("Actual Node floor observation shape differs")
    version(value["peerPolicyVersion"])
    if type(value["observedAt"]) is not int or type(value["journalUID"]) is not int or not 0 <= value["journalUID"] <= 4294967295:
        raise ValueError("Actual Node floor observation integer differs")
    if type(value["servingPID"]) is not int or value["servingPID"] < 1 or value["plainServingProcess"] is not True:
        raise ValueError("Actual serving plain Node process is unproved")
    for key in ("nonce", "certificateDER_SHA256", "peerPolicySHA256", "floorSHA256", "journalIdentitySHA256", "servingProcessSHA256", "servingExecutableSHA256"):
        if not isinstance(value[key], str) or not HEX.fullmatch(value[key]):
            raise ValueError("Actual Node floor observation digest differs")
    if nonce is not None and value["nonce"] != nonce:
        raise ValueError("Actual Node floor observation nonce differs")
    if (value["tenantId"], value["nodeId"], value["recoveryEpoch"]) != (scope["tenantId"], scope["nodeId"], scope.get("recoveryEpoch", scope.get("epoch"))):
        raise ValueError("Actual Node floor identity differs")
    cert = x509.load_pem_x509_certificate(certificate_raw)
    observed = datetime.fromtimestamp(value["observedAt"], timezone.utc)
    uri = f'spiffe://saintvision.ai/tenant/{value["tenantId"]}/node/{value["nodeId"]}/epoch/{value["recoveryEpoch"]}'
    if (cert.fingerprint(hashes.SHA256()).hex() != value["certificateDER_SHA256"]
            or cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
            or cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.UniformResourceIdentifier) != [uri]
            or ExtendedKeyUsageOID.SERVER_AUTH not in cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
            or not cert.not_valid_before_utc <= observed < cert.not_valid_after_utc):
        raise ValueError("Actual Node floor certificate binding differs")
    if fresh:
        now = now or datetime.now(timezone.utc)
        if not -CLOCK_SKEW_SECONDS <= (now - observed).total_seconds() <= FRESH_SECONDS:
            raise ValueError("Actual Node floor observation is stale or clock-uncertain")
    signature = value["nodeSignature"]
    if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{128}", signature):
        raise ValueError("Actual Node floor signature differs")
    body = {key: item for key, item in value.items() if key != "nodeSignature"}
    cert.public_key().verify(bytes.fromhex(signature), DOMAIN + floor_canonical(body))
    return value


def match_floor(value, manifest, phase):
    if (value["peerPolicyVersion"], value["peerPolicySHA256"]) != (manifest[phase + "PeerPolicyVersion"], manifest[phase + "PeerPolicySHA256"]):
        raise ValueError("Actual durable peer floor differs from the frozen phase")
    expected_der = manifest["currentNodeCertificateSHA256" if phase == "current" else "nextNodeCertificateSHA256"]
    if value["certificateDER_SHA256"] != expected_der:
        raise ValueError("Actual phase Node DER differs from the frozen certificate")
    return value


def commit_body(manifest, raw):
    return {"schemaVersion": SCHEMA, "rotationId": manifest["rotationId"], "proposalDigest": digest(raw),
            "nodeId": manifest["nodeId"], "channelVersion": manifest["targetChannelVersion"],
            "certificateSHA256": manifest["nextNodeCertificateSHA256"], "committed": True, **binding(manifest)}
