"""Fail-closed observation of the two unresolved S01 operational inputs.

The values come from the production ``api.json`` and its immutable configuration
volume.  The public response only contains the stable setting names below.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from cryptography import x509


NODE_CA = "INV_NODE_MTLS_CA_BUNDLE"
OBJECT_STORE = "INV_OBJECT_STORE_ENDPOINT"
SETTING_NAMES = frozenset({NODE_CA, OBJECT_STORE})
_CONFIG_KEYS = frozenset({"nodeMtlsCaBundle", "objectStoreEndpoint"})
_MAX_CA_BUNDLE_BYTES = 1_048_576


def _ca_bundle_ready(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        path = Path(value)
        if not path.is_absolute() or not path.is_file():
            return False
        raw = path.read_bytes()
        if not raw or len(raw) > _MAX_CA_BUNDLE_BYTES:
            return False
        certificates = x509.load_pem_x509_certificates(raw)
    except (OSError, ValueError, TypeError):
        return False
    for certificate in certificates:
        try:
            if certificate.extensions.get_extension_for_class(
                x509.BasicConstraints
            ).value.ca:
                return True
        except x509.ExtensionNotFound:
            continue
    return False


def _endpoint_ready(value: object) -> bool:
    if not isinstance(value, str) or value != value.strip() or not value:
        return False
    try:
        parsed = urlsplit(value)
        # Reading .port also rejects malformed/non-numeric/out-of-range ports.
        _ = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname is not None
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
    )


def configured_s01_readiness(value: object | None):
    """Build the production observer; unknown config keys refuse startup."""
    if value is None:
        config: dict[str, object] = {}
    elif isinstance(value, dict) and set(value) <= _CONFIG_KEYS:
        config = dict(value)
    else:
        raise ValueError("Invalid configurationReadiness settings")

    def unresolved() -> list[str]:
        missing = []
        if not _ca_bundle_ready(config.get("nodeMtlsCaBundle")):
            missing.append(NODE_CA)
        if not _endpoint_ready(config.get("objectStoreEndpoint")):
            missing.append(OBJECT_STORE)
        return sorted(missing)

    return unresolved
