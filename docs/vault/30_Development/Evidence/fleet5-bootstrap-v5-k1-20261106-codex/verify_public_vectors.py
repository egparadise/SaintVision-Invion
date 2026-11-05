"""Read-only cross-language verification of PUBLIC EPHEMERAL TEST vectors.

This is evidence tooling, never a trusted-input/producer or production verifier.
Run with the existing main venv Python -I -B; it installs or writes nothing.
"""
import hashlib
import json
from pathlib import Path
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def verify(path: Path) -> dict:
    vectors = json.loads(path.read_bytes())["vectors"]
    assert len(vectors) == 28
    valid = rejected = 0
    for vector in vectors:
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(vector["publicKeyHex"]))
        message = bytes.fromhex(vector["messageHex"])
        signature = bytes.fromhex(vector["signatureHex"])
        key.verify(signature, message)
        valid += 1
        spki = key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        assert hashlib.sha256(spki).hexdigest() == vector["publicSPKISHA256"]
        raw = bytes.fromhex(vector["exactReferentHex"])
        assert hashlib.sha256(raw).hexdigest() == vector["exactReferentSHA256"]
        for changed_message, changed_signature in (
            (message + b"\n", signature),
            (message, bytes([signature[0] ^ 1]) + signature[1:]),
        ):
            try:
                key.verify(changed_signature, changed_message)
            except InvalidSignature:
                rejected += 1
            else:
                raise AssertionError("tampered signature/message accepted")
    # Observe the OTHER library's behavior; its acceptance is not a strictness
    # guarantee. The Go product test independently requires strict rejection.
    identity = bytes([1]) + bytes(31)
    forged = identity + bytes(32)
    try:
        Ed25519PublicKey.from_public_bytes(identity).verify(forged, b"")
        other_library_accepts_identity_forgery = True
    except InvalidSignature:
        other_library_accepts_identity_forgery = False
    return {
        "classification": "CROSS_LANGUAGE_EPHEMERAL_TEST_NOT_LIVE_PROVENANCE",
        "python": sys.version,
        "realEd25519Valid": valid,
        "tamperedRejected": rejected,
        "canonicalSPKIMatches": valid,
        "exactReferentHashesMatch": valid,
        "otherLibraryAcceptsIdentityForgery": other_library_accepts_identity_forgery,
        "otherLibraryIsNotStrictProductVerifier": True,
        "wholeProductAcceptance": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(Path(sys.argv[1])), sort_keys=True))
