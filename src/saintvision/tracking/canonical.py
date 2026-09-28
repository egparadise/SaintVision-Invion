"""Canonical payload bytes and tracking URI normalisation (design #168 §2.1, §2.2).

``payload_sha256`` is what the attest step compares against the tag set the
tracking server hands back, so two callers that mean the same thing must
produce the same bytes. The rules are stated once, here, and the design's
determinism tests hold them:

* dict keys are strings, NFC-normalised, and must not collide after NFC;
* strings are NFC-normalised, nested as well as top level;
* ``bool`` is checked before numbers so ``True`` stays ``true`` and is never
  folded into ``1``;
* an integral float within ``2**53`` becomes an int, so ``1.0``, ``-0.0`` and
  ``1e3`` are ``1``, ``0`` and ``1000``; any other float is ``repr``;
* NaN, infinities, ``Decimal``, ``datetime``, ``bytes`` and ``None`` inside a
  list are refused; ``None`` as a dict value drops the field;
* metrics are ``{key, value, step, timestamp_ms}`` records sorted by
  ``(key, step)``; tag values must be strings.

Every refusal is :class:`CanonicalizationError` with a ``reason_class`` from a
closed set, which is what ``mlflow_mirror_defects`` records (``TRACK-0005``).
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from typing import Any, Final
from urllib.parse import quote, unquote, urlsplit

#: The closed set of refusal reasons recorded on a defect row.
REASON_CLASSES: Final[tuple[str, ...]] = (
    "nan-or-infinity",
    "key-collision",
    "unsupported-type",
    "non-string-tag",
    "list-null",
)

_MAX_EXACT_FLOAT: Final[int] = 2**53


class CanonicalizationError(ValueError):
    """The payload cannot be canonicalised. ``reason_class`` is closed-set."""

    def __init__(self, reason_class: str, message: str) -> None:
        if reason_class not in REASON_CLASSES:
            raise ValueError(f"unknown reason class {reason_class!r}")
        super().__init__(message)
        self.reason_class = reason_class


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def canonicalize(value: Any) -> Any:
    """Return the canonical form of ``value`` (pure; never mutates the input)."""
    # bool first: it is a subclass of int and must not become a number.
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, str):
        return _nfc(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise CanonicalizationError("nan-or-infinity", "NaN and infinity are not representable")
        if value.is_integer() and abs(value) <= _MAX_EXACT_FLOAT:
            return int(value)
        return repr(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError("unsupported-type", "dict keys must be strings")
            nkey = _nfc(key)
            if nkey in out:
                raise CanonicalizationError("key-collision", f"key collides after NFC: {nkey!r}")
            canon = canonicalize(item)
            if canon is None:
                # A None value drops the field; but a collision with a dropped
                # key is still a collision, so reserve the key before deciding.
                out[nkey] = None
                continue
            out[nkey] = canon
        return {k: v for k, v in sorted(out.items()) if v is not None}
    if isinstance(value, (list, tuple)):
        items = []
        for item in value:
            if item is None:
                raise CanonicalizationError("list-null", "None inside a list is not representable")
            items.append(canonicalize(item))
        return items
    raise CanonicalizationError(
        "unsupported-type", f"{type(value).__name__} is not representable; convert it first"
    )


def canonical_metrics(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalise a metric list: required keys, integer step/timestamp, sorted."""
    out = []
    for metric in metrics:
        if not isinstance(metric, dict) or "key" not in metric or "value" not in metric:
            raise CanonicalizationError("unsupported-type", "a metric needs key and value")
        key = metric["key"]
        if not isinstance(key, str):
            raise CanonicalizationError("unsupported-type", "metric key must be a string")
        step = metric.get("step", 0)
        timestamp_ms = metric.get("timestamp_ms", 0)
        for name, number in (("step", step), ("timestamp_ms", timestamp_ms)):
            if isinstance(number, bool) or not isinstance(number, int):
                raise CanonicalizationError("unsupported-type", f"metric {name} must be an int")
        raw = metric["value"]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise CanonicalizationError("unsupported-type", "metric value must be numeric")
        value = canonicalize(raw)
        out.append({"key": _nfc(key), "value": value, "step": step, "timestamp_ms": timestamp_ms})
    out.sort(key=lambda m: (m["key"], m["step"]))
    return out


def canonical_tags(tags: dict[str, Any]) -> dict[str, str]:
    """Tags are string to string; anything else is refused as ``non-string-tag``."""
    if not isinstance(tags, dict):
        raise CanonicalizationError("non-string-tag", "tags must be a mapping")
    for key, value in tags.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise CanonicalizationError("non-string-tag", "tag keys and values must be strings")
    return canonicalize(tags)


def canonical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Canonicalise a mirror payload, applying the metric and tag rules."""
    if not isinstance(payload, dict):
        raise CanonicalizationError("unsupported-type", "payload must be a mapping")
    working = dict(payload)
    if "metrics" in working and working["metrics"] is not None:
        if not isinstance(working["metrics"], (list, tuple)):
            raise CanonicalizationError("unsupported-type", "metrics must be a list")
        working["metrics"] = canonical_metrics(list(working["metrics"]))
    if "tags" in working and working["tags"] is not None:
        working["tags"] = canonical_tags(working["tags"])
    return canonicalize(working)


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    canonical = canonical_payload(payload)
    return json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def payload_sha256(payload: dict[str, Any]) -> str:
    """The digest stored on an intent and compared at attest."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


# --------------------------------------------------------------------------
# Tracking URI (§2.2)
# --------------------------------------------------------------------------


class UriError(ValueError):
    """The tracking URI is not acceptable (``TRACK-0004``)."""


def normalize_tracking_uri(uri: str) -> str:
    """Return the normalised ``https`` URI or raise :class:`UriError`.

    Lower-cases scheme and host (IDNA-encoded), drops the default port,
    re-encodes the path and strips its trailing slash; refuses userinfo, a
    query, a fragment and any scheme other than https.
    """
    if not isinstance(uri, str) or not uri.strip():
        raise UriError("tracking URI is empty")
    parts = urlsplit(uri.strip())
    scheme = parts.scheme.lower()
    if scheme != "https":
        raise UriError("tracking URI must use https")
    if parts.username is not None or parts.password is not None:
        raise UriError("tracking URI must not carry userinfo")
    if parts.query or parts.fragment:
        raise UriError("tracking URI must not carry a query or fragment")
    if "?" in uri or "#" in uri:
        raise UriError("tracking URI must not carry a query or fragment")
    host = parts.hostname
    if not host:
        raise UriError("tracking URI has no host")
    try:
        host = host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise UriError("tracking URI host is not encodable") from exc
    try:
        port = parts.port
    except ValueError as exc:
        raise UriError("tracking URI port is invalid") from exc
    netloc = host if port in (None, 443) else f"{host}:{port}"
    path = quote(unquote(parts.path), safe="/-._~!$&'()*+,;=:@")
    path = path.rstrip("/")
    return f"https://{netloc}{path}"


def tracking_uri_sha256(uri: str) -> str:
    return hashlib.sha256(normalize_tracking_uri(uri).encode("utf-8")).hexdigest()
