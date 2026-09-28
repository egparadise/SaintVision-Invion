"""The ``TRACK`` error family (design #168 §5).

``ProblemDetails.code`` is ``^[A-Z]+-[0-9]{4}$`` (``contracts/v1alpha1/core.schema.json``)
and ``category`` is ``^[A-Z]+$``. ``TRACK`` is not one of the ten prefixes in
``errors.ErrorCategory``, so status and retryability are stated here per code,
the way ``api/problem.py::CanonicalProblem`` (PR #167) does for its families.
This module does not import that module: #167 is not merged, and a table of
five entries must not create a merge dependency. When #167 lands, the route
that surfaces a TRACK code builds a ``CanonicalProblem`` from :func:`entry`.

Two mappings live beside the wire facts because they are decided per code and
must not be re-derived by a collector:

* the ``mlflow_mirror_attempts.status`` a code produces;
* the evidence verdict the S10/S12 collectors report for it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Final

CANONICAL_CODE: Final[re.Pattern[str]] = re.compile(r"^[A-Z]+-[0-9]{4}$")
TRACK_CODE: Final[re.Pattern[str]] = re.compile(r"^TRACK-[0-9]{4}$")
CATEGORY: Final[str] = "TRACK"


class MirrorStatus(str, Enum):
    """``mlflow_mirror_attempts.status``. Terminal unless ``UNAVAILABLE``.

    There is no ``invalid`` status: ``TRACK-0004`` (configuration) and
    ``TRACK-0005`` (canonicalisation) are decided before any sink is called,
    so no attempt row ever carries them (design §5, Codex #172 finding 2).
    """

    MIRRORED = "mirrored"
    UNAVAILABLE = "unavailable"
    REFUSED = "refused"
    MISMATCH = "mismatch"

    @property
    def terminal(self) -> bool:
        return self is not MirrorStatus.UNAVAILABLE


class Verdict(str, Enum):
    """What the evidence collectors report. Never ``PASS`` for an unobserved value."""

    MIRRORED = "MIRRORED"
    NOT_OBSERVED = "NOT_OBSERVED"
    MEASURED_FAIL = "MEASURED_FAIL"
    INVALID_RUN = "INVALID_RUN"


@dataclass(frozen=True, slots=True)
class TrackCode:
    code: str
    status: int
    retryable: bool
    #: The attempt status this code is recorded with, or None when no attempt
    #: is made (configuration and canonicalisation failures never reach a sink).
    mirror_status: MirrorStatus | None
    verdict: Verdict
    meaning: str

    def __post_init__(self) -> None:
        if not TRACK_CODE.match(self.code):
            raise ValueError(f"{self.code!r} is not a TRACK code")
        if not CANONICAL_CODE.match(self.code):  # pragma: no cover - implied
            raise ValueError(f"{self.code!r} is not canonical")
        if not 400 <= self.status <= 599:
            raise ValueError("status must be an error status")

    @property
    def category(self) -> str:
        return self.code.split("-", 1)[0]


TRACK_UNAVAILABLE: Final[str] = "TRACK-0001"
TRACK_REFUSED: Final[str] = "TRACK-0002"
TRACK_MISMATCH: Final[str] = "TRACK-0003"
TRACK_CONFIG_INVALID: Final[str] = "TRACK-0004"
TRACK_PAYLOAD_INVALID: Final[str] = "TRACK-0005"

#: The family, stated once. Order is the design table's order.
TRACK_CODES: Final[tuple[TrackCode, ...]] = (
    TrackCode(
        TRACK_UNAVAILABLE, 503, True, MirrorStatus.UNAVAILABLE, Verdict.NOT_OBSERVED,
        "tracking server unreachable, timed out or answered 5xx",
    ),
    TrackCode(
        TRACK_REFUSED, 403, False, MirrorStatus.REFUSED, Verdict.MEASURED_FAIL,
        "401/403 from the server or the service credential was refused",
    ),
    TrackCode(
        TRACK_MISMATCH, 409, False, MirrorStatus.MISMATCH, Verdict.MEASURED_FAIL,
        "attest: the server's tag set does not match payload_sha256",
    ),
    TrackCode(
        TRACK_CONFIG_INVALID, 422, False, None, Verdict.INVALID_RUN,
        "configuration invalid: scheme, userinfo, query, prefix or client missing",
    ),
    TrackCode(
        TRACK_PAYLOAD_INVALID, 422, False, None, Verdict.INVALID_RUN,
        "payload canonicalisation failed; recorded as a defect, never an intent",
    ),
)

_BY_CODE: Final[dict[str, TrackCode]] = {c.code: c for c in TRACK_CODES}
_BY_STATUS: Final[dict[MirrorStatus, TrackCode]] = {
    c.mirror_status: c for c in TRACK_CODES if c.mirror_status is not None
}


def entry(code: str) -> TrackCode:
    """The stated facts for a TRACK code. Unknown or non-canonical codes raise."""
    if not isinstance(code, str) or not TRACK_CODE.match(code):
        raise ValueError(f"{code!r} is not a canonical TRACK code")
    try:
        return _BY_CODE[code]
    except KeyError:
        raise ValueError(f"{code!r} is not a defined TRACK code") from None


#: The one exact pairing of attempt status and error code (design §5). Every
#: consumer -- ``MirrorResult``, the DB CHECK in 0049, ``verdict_for_attempt``
#: -- is derived from or checked against this table, never re-derived.
STATUS_CODE_PAIRS: Final[dict[MirrorStatus, str | None]] = {
    MirrorStatus.MIRRORED: None,
    MirrorStatus.UNAVAILABLE: TRACK_UNAVAILABLE,
    MirrorStatus.REFUSED: TRACK_REFUSED,
    MirrorStatus.MISMATCH: TRACK_MISMATCH,
}


def code_for_status(status: MirrorStatus) -> str | None:
    """The error code an attempt with ``status`` carries; None for ``mirrored``."""
    return STATUS_CODE_PAIRS[MirrorStatus(status)]


def check_pair(status: MirrorStatus | str, error_code: str | None) -> MirrorStatus:
    """Raise unless ``(status, error_code)`` is exactly one of the design pairs."""
    status = MirrorStatus(status)
    expected = STATUS_CODE_PAIRS[status]
    if error_code != expected:
        raise ValueError(
            f"attempt status {status.value!r} carries {expected!r}, not {error_code!r}"
        )
    return status


def sql_pair_check() -> str:
    """The SQL predicate that states the same pairs, for the migration and the model."""
    # NULL-safe on purpose: ``error_code = 'TRACK-0001'`` is UNKNOWN when
    # error_code is NULL and a CHECK passes on UNKNOWN, so a failure status
    # with no code would slip through. Every non-mirrored branch therefore
    # states ``error_code IS NOT NULL`` explicitly; mirrored requires NULL.
    parts = []
    for status, code in STATUS_CODE_PAIRS.items():
        clause = "error_code IS NULL" if code is None else f"error_code IS NOT NULL AND error_code = '{code}'"
        parts.append(f"(status = '{status.value}' AND {clause})")
    return " OR ".join(parts)


def verdict_for_attempt(status: MirrorStatus | str, error_code: str | None) -> Verdict:
    """The verdict for a recorded attempt; a wrong (status, code) pair is refused."""
    status = check_pair(status, error_code)
    if status is MirrorStatus.MIRRORED:
        return Verdict.MIRRORED
    return entry(error_code).verdict


def verdict_for_unattempted(*, configured: str, has_intent: bool, has_defect: bool) -> Verdict:
    """The verdict when no attempt row exists for a canonical change.

    ``configured`` is the readiness value: ``absent`` is NOT_OBSERVED (nothing
    was ever meant to be sent), ``invalid`` is INVALID_RUN. With a configured
    sink, an intent without an attempt is pending (NOT_OBSERVED), a defect is
    INVALID_RUN, and neither is an enqueue defect (INVALID_RUN).
    """
    if configured == "absent":
        return Verdict.NOT_OBSERVED
    if configured == "invalid":
        return Verdict.INVALID_RUN
    if configured != "configured":
        raise ValueError(f"unknown readiness {configured!r}")
    if has_defect:
        return Verdict.INVALID_RUN
    if has_intent:
        return Verdict.NOT_OBSERVED
    return Verdict.INVALID_RUN
