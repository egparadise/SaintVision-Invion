"""Strict ``INV_MLFLOW_*`` settings and their readiness (design #168 §4, F-R4).

Readiness is one of ``absent``, ``configured`` and ``invalid`` from a single
strict source with no fallback, the ``objectStore`` pattern. The distinction
that matters most is the last one: a tracking URI that is set while the
``mlflow`` client is not installed is ``invalid`` with detail ``client-missing``,
never ``absent``. Reporting it as absent would let a half-configured operator
setting read as "mirroring was not asked for".

Nothing here contacts a server or reads a secret.
"""

from __future__ import annotations

import importlib.util
import os
import re
from dataclasses import dataclass
from typing import Callable, Final, Mapping

from .canonical import UriError, normalize_tracking_uri, tracking_uri_sha256
from .codes import TRACK_CONFIG_INVALID

ENV_TRACKING_URI: Final[str] = "INV_MLFLOW_TRACKING_URI"
ENV_DESTINATION: Final[str] = "INV_MLFLOW_DESTINATION"
ENV_EXPERIMENT_PREFIX: Final[str] = "INV_MLFLOW_EXPERIMENT_PREFIX"
ENV_TIMEOUT_SECONDS: Final[str] = "INV_MLFLOW_TIMEOUT_SECONDS"

DEFAULT_TIMEOUT_SECONDS: Final[int] = 5
_DESTINATION: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_PREFIX: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9-]{1,32}$")

READINESS_VALUES: Final[tuple[str, ...]] = ("absent", "configured", "invalid")


def mlflow_client_present() -> bool:
    """Whether the ``mlflow`` package can be imported. Does not import it."""
    return importlib.util.find_spec("mlflow") is not None


@dataclass(frozen=True, slots=True)
class TrackingReadiness:
    """``configurationReadiness.mlflow``: value plus the reason when invalid."""

    value: str
    detail: str | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.value not in READINESS_VALUES:
            raise ValueError(f"unknown readiness {self.value!r}")
        if (self.value == "invalid") != (self.detail is not None):
            raise ValueError("invalid readiness carries a detail; the others do not")
        if self.value == "invalid" and self.error_code != TRACK_CONFIG_INVALID:
            raise ValueError("invalid readiness is TRACK-0004")

    @property
    def configured(self) -> bool:
        return self.value == "configured"

    def to_dict(self) -> dict[str, str]:
        out = {"value": self.value}
        if self.detail is not None:
            out["detail"] = self.detail
        if self.error_code is not None:
            out["errorCode"] = self.error_code
        return out


@dataclass(frozen=True, slots=True)
class TrackingSettings:
    """The resolved settings when readiness is ``configured``."""

    tracking_uri: str
    tracking_uri_sha256: str
    destination: str
    experiment_prefix: str
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class TrackingConfiguration:
    readiness: TrackingReadiness
    settings: TrackingSettings | None = None

    def __post_init__(self) -> None:
        if self.readiness.configured != (self.settings is not None):
            raise ValueError("settings are present exactly when readiness is configured")


def _invalid(detail: str) -> TrackingConfiguration:
    return TrackingConfiguration(
        TrackingReadiness("invalid", detail=detail, error_code=TRACK_CONFIG_INVALID)
    )


def resolve(
    env: Mapping[str, str] | None = None,
    *,
    client_present: Callable[[], bool] | None = None,
) -> TrackingConfiguration:
    """Resolve the configuration strictly from ``env`` (default ``os.environ``).

    ``absent`` requires every ``INV_MLFLOW_*`` variable to be unset or empty.
    A destination or prefix without a URI is ``invalid`` (``partial``), not
    absent: a partially entered configuration is a mistake to surface.
    """
    source = os.environ if env is None else env
    raw_uri = (source.get(ENV_TRACKING_URI) or "").strip()
    raw_destination = (source.get(ENV_DESTINATION) or "").strip()
    raw_prefix = (source.get(ENV_EXPERIMENT_PREFIX) or "").strip()
    raw_timeout = (source.get(ENV_TIMEOUT_SECONDS) or "").strip()

    if not raw_uri:
        if raw_destination or raw_prefix or raw_timeout:
            return _invalid("partial")
        return TrackingConfiguration(TrackingReadiness("absent"))

    try:
        uri = normalize_tracking_uri(raw_uri)
    except UriError as exc:
        return _invalid(f"uri:{_uri_detail(exc)}")
    if not raw_destination or not _DESTINATION.match(raw_destination):
        return _invalid("destination")
    if not raw_prefix or not _PREFIX.match(raw_prefix):
        return _invalid("prefix")
    timeout = DEFAULT_TIMEOUT_SECONDS
    if raw_timeout:
        if not raw_timeout.isdigit() or int(raw_timeout) < 1:
            return _invalid("timeout")
        timeout = int(raw_timeout)
    # Looked up at call time so a test can substitute the module attribute.
    present = client_present if client_present is not None else mlflow_client_present
    if not present():
        return _invalid("client-missing")

    return TrackingConfiguration(
        TrackingReadiness("configured"),
        TrackingSettings(
            tracking_uri=uri,
            tracking_uri_sha256=tracking_uri_sha256(uri),
            destination=raw_destination,
            experiment_prefix=raw_prefix,
            timeout_seconds=timeout,
        ),
    )


def _uri_detail(exc: UriError) -> str:
    message = str(exc)
    for label in ("https", "userinfo", "query", "host", "port", "empty"):
        if label in message:
            return label
    return "invalid"
