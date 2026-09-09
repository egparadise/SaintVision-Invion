"""Identifier generation and validation.

Contract (PLAN-DB-001): primary IDs are ``prefix + ULID`` text, tenant is UUID,
traceId is a 32 character lowercase hex string (W3C traceparent trace-id, ADR-004).

ULID is generated here rather than pulled in as a dependency because the runtime
dependency set is locked in S01 (PLAN-BACKEND-001) and is not ours to widen yet.
"""

from __future__ import annotations

import re
import secrets
import time
import uuid
from typing import Final

# Crockford base32 without I, L, O, U.
_CROCKFORD: Final[str] = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CROCKFORD_INDEX: Final[dict[str, int]] = {c: i for i, c in enumerate(_CROCKFORD)}

ULID_LENGTH: Final[int] = 26
_ULID_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
_TRACE_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{32}$")
_SPAN_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{16}$")

#: Entity prefixes. A prefix is part of the contract: it is stored, not derived,
#: so renaming one is a breaking change (공통 계약 §13).
PREFIXES: Final[dict[str, str]] = {
    "user": "usr",
    "role": "rol",
    "project": "prj",
    "node": "nod",
    "bootstrap_token": "nbt",
    "capability": "cap",
    "offer": "ofr",
    "snapshot": "rsn",
    "storage_contribution": "stc",
    "data_location": "dtl",
    "audit_event": "aud",
    "idempotency": "idm",
    "evidence": "evd",
    "run": "run",
    "step": "stp",
    # S03
    "workspace": "wsp",
    "volume": "vol",
    "workload": "wkl",
    "attempt": "att",
    "checkpoint": "ckp",
    "approval": "apv",
    "outbox": "obx",
    "inbox": "ibx",
    "artifact": "art",
    "upload": "upl",
    # S09
    "bundle": "bnd",
    "run_record": "rec",
    "eval_suite": "evs",
    "eval_case": "evc",
    "eval_run": "evr",
    # S10
    "dataset": "dst",
    "dataset_version": "dsv",
    "commit": "cmt",
    "image": "img",
    "model": "mdl",
    "model_version": "mdv",
    "deployment": "dpl",
    # S12
    "backup": "bkp",
    "drill": "drl",
    "storage_check": "chk",
    "release": "rel",
    "acceptance": "acc",
    "permission_snapshot": "psn",
    # discovery, pools and distributed placement
    "announcement": "anc",
    "pool": "pol",
    "plan": "pln",
}

_PREFIX_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z]{3}$")


def _encode_crockford(value: int, length: int) -> str:
    out = [""] * length
    for i in range(length - 1, -1, -1):
        out[i] = _CROCKFORD[value & 0x1F]
        value >>= 5
    return "".join(out)


def new_ulid(*, now_ms: int | None = None) -> str:
    """Return a 26 character ULID.

    The 48 bit timestamp makes IDs sort by creation time, which is what makes
    them usable as cursor pagination keys (PLAN-BACKEND-001).
    """
    ts = int(time.time() * 1000) if now_ms is None else now_ms
    if not 0 <= ts < (1 << 48):
        raise ValueError("ULID timestamp out of range")
    randomness = secrets.randbits(80)
    return _encode_crockford(ts, 10) + _encode_crockford(randomness, 16)


def new_id(kind: str) -> str:
    """Return ``prefix_ULID`` for a known entity kind."""
    try:
        prefix = PREFIXES[kind]
    except KeyError:
        raise ValueError(f"unknown entity kind: {kind}") from None
    return f"{prefix}_{new_ulid()}"


def parse_id(value: str) -> tuple[str, str]:
    """Split ``prefix_ULID`` into its parts, validating both."""
    if not isinstance(value, str) or value.count("_") != 1:
        raise ValueError("id must be exactly one prefix and one ULID joined by '_'")
    prefix, ulid = value.split("_", 1)
    if not _PREFIX_RE.match(prefix):
        raise ValueError("id prefix must be three lowercase letters")
    if not _ULID_RE.match(ulid):
        raise ValueError("id body must be a 26 character Crockford base32 ULID")
    return prefix, ulid


def is_id(value: object, kind: str | None = None) -> bool:
    """Return whether ``value`` is a well formed ID, optionally of a given kind."""
    if not isinstance(value, str):
        return False
    try:
        prefix, _ = parse_id(value)
    except ValueError:
        return False
    if kind is None:
        return True
    return prefix == PREFIXES.get(kind)


def ulid_timestamp_ms(value: str) -> int:
    """Return the millisecond timestamp encoded in a ULID or prefixed ID."""
    ulid = value.split("_", 1)[1] if "_" in value else value
    if not _ULID_RE.match(ulid):
        raise ValueError("not a ULID")
    ts = 0
    for char in ulid[:10]:
        ts = (ts << 5) | _CROCKFORD_INDEX[char]
    return ts


def new_tenant_id() -> uuid.UUID:
    """Tenant identity is a UUID, not a prefixed ULID (PLAN-DB-001)."""
    return uuid.uuid4()


def new_trace_id() -> str:
    """32 hex characters. Never all zeroes, per W3C trace context."""
    while True:
        candidate = secrets.token_hex(16)
        if candidate != "0" * 32:
            return candidate


def new_span_id() -> str:
    while True:
        candidate = secrets.token_hex(8)
        if candidate != "0" * 16:
            return candidate


def is_trace_id(value: object) -> bool:
    return isinstance(value, str) and bool(_TRACE_ID_RE.match(value))


def is_span_id(value: object) -> bool:
    return isinstance(value, str) and bool(_SPAN_ID_RE.match(value))
