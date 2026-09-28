"""The MLflow tracking sink over its REST API (S10-BE stage 2, design #168 §3).

Push-only. The sink creates an experiment, a run, its params/metrics/tags and
(for a model version) a registered model version, then reads back *only* what
it needs to attest -- the tag set of the run it wrote. Nothing read here feeds
a decision; there is no path from MLflow into lineage.

Three properties the tests hold:

* **The transport is a seam.** ``Transport.request`` is one method taking a
  method, URL, headers and body and returning a status and body. The default
  is ``urllib`` with a bounded timeout and no redirect following; the PG-free
  tests inject a fake and assert the exact requests.
* **Errors are codes, never provider text.** Every failure becomes one of the
  design's codes -- ``TRACK-0001`` (unreachable, timeout, 5xx), ``TRACK-0002``
  (401/403) -- as a :class:`MirrorResult`, or ``TRACK-0004`` as
  :class:`MlflowRequestInvalid` when the server rejects our own request (4xx
  other than auth), which is our defect, not an attempt. The server's error
  message is discarded at the transport boundary and never reaches a result,
  an exception or a log.
* **Attestation can fail.** The canonical payload bytes are stored on the run
  as the ``inv.payload`` tag; ``attest`` re-reads that tag and digests it. A
  tag that changed, or vanished, is a ``MISMATCH``; a run that is gone is
  ``UNVERIFIABLE``; nothing here says ``VERIFIED`` without a digest it computed
  from what the server returned.

The secret is used from memory only: ``authenticate`` runs the credential
handle's callback once, keeps the bearer value in a private attribute, and
never returns, logs or reprs it.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Final, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..tracking.canonical import UriError, canonical_json, normalize_tracking_uri
from ..tracking.codes import (
    TRACK_CONFIG_INVALID,
    TRACK_REFUSED,
    TRACK_UNAVAILABLE,
    MirrorStatus,
)
from .contract import Attestation, AttestationResult, AuthResult, ProbeResult
from .reference import redact_text
from .tracking import TRACKING_CONTRACT_VERSION, MirrorFailure, MirrorRecord, MirrorResult

API: Final[str] = "/api/2.0/mlflow"
TAG_INTENT: Final[str] = "inv.intent_id"
TAG_PAYLOAD: Final[str] = "inv.payload"
TAG_PAYLOAD_SHA256: Final[str] = "inv.payload_sha256"
TAG_SUBJECT_KIND: Final[str] = "inv.subject_kind"
#: Written last, after params, metrics and the model version: its value is the
#: payload digest, and only a FINISHED run carrying it is "mirrored". A run
#: without it is a partial remote write that the next delivery resumes
#: (Codex #176 finding 1).
TAG_COMPLETE: Final[str] = "inv.mirror_complete"
_LOOPBACK_HOSTS: Final[frozenset[str]] = frozenset({"127.0.0.1", "localhost", "::1"})
_MAX_BODY: Final[int] = 1 << 20


class MlflowRequestInvalid(Exception):
    """The server rejected a request we built (4xx other than 401/403).

    Our defect, therefore ``TRACK-0004`` and no attempt row: the outbox
    consumer lets it propagate and the event is retried or parked by the
    existing outbox policy. Carries the HTTP status only.
    """

    code = TRACK_CONFIG_INVALID

    def __init__(self, status: int, operation: str) -> None:
        super().__init__(f"{operation}: http {status}")
        self.status = status
        self.operation = operation


class Transport(Protocol):
    def request(
        self, method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> tuple[int, bytes]:
        """Perform one request. Raise :class:`TransportError` on no response."""


class TransportError(Exception):
    """No HTTP response (connection refused, DNS, timeout). Carries no text."""


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


@dataclass
class UrllibTransport:
    """The default transport: bounded timeout, no redirects, bounded body."""

    timeout_seconds: int = 5

    def __post_init__(self) -> None:
        if self.timeout_seconds < 1:
            raise ValueError("timeout must be at least one second")
        self._opener = build_opener(_NoRedirects())

    def request(self, method, url, headers, body):
        request = Request(url, data=body, method=method, headers=headers)
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                return response.status, response.read(_MAX_BODY)
        except HTTPError as error:
            # A response with an error status is still a response: the status
            # is kept, the body (which may echo our request) is discarded.
            return error.code, b""
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise TransportError(type(exc).__name__) from None


@dataclass(frozen=True, slots=True)
class _Response:
    status: int
    payload: dict[str, Any]


class MlflowSink:
    """A :class:`TrackingSink` over the MLflow REST API."""

    name: str = "mlflow"
    contract_version: str = TRACKING_CONTRACT_VERSION

    def __init__(
        self,
        tracking_uri: str,
        *,
        experiment_prefix: str,
        transport: Transport | None = None,
        timeout_seconds: int = 5,
        allow_insecure_loopback: bool = False,
    ) -> None:
        self._base = self._accept_uri(tracking_uri, allow_insecure_loopback)
        if not experiment_prefix:
            raise ValueError("an experiment prefix is required")
        self._prefix = experiment_prefix
        self._transport: Transport = transport or UrllibTransport(timeout_seconds)
        self._authorization: str | None = None  # bearer value; never logged or returned

    def __repr__(self) -> str:
        return f"<MlflowSink {self._base}>"

    @staticmethod
    def _accept_uri(uri: str, allow_insecure_loopback: bool) -> str:
        try:
            return normalize_tracking_uri(uri)
        except UriError:
            parts = urlsplit(uri.strip())
            if (
                allow_insecure_loopback
                and parts.scheme == "http"
                and parts.hostname in _LOOPBACK_HOSTS
                and not parts.query and not parts.fragment and parts.username is None
            ):
                # Only a hosted lane talking to a container on this host may
                # use plain http, and only to a loopback address (never the
                # configuration path, which stays https-only: TRACK-0004).
                return f"http://{parts.hostname}{':' + str(parts.port) if parts.port else ''}{parts.path.rstrip('/')}"
            raise

    # ------------------------------------------------------------ transport

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None, *, query: dict[str, str] | None = None) -> _Response:
        url = self._base + path
        if query:
            url += "?" + urlencode(query)
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self._authorization is not None:
            headers["Authorization"] = self._authorization
        status, raw = self._transport.request(method, url, headers, data)
        payload: dict[str, Any] = {}
        if 200 <= status < 300 and raw:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = ""
            try:
                decoded = json.loads(text)
                payload = decoded if isinstance(decoded, dict) else {"value": decoded}
            except ValueError:
                # ``GET /version`` answers plain text ("2.17.2"), not JSON
                # (hosted run 36376769104); keep a short text body as a value.
                stripped = text.strip()
                payload = {"value": stripped} if stripped and len(stripped) <= 64 else {}
        return _Response(status, payload)

    @staticmethod
    def _failure(status: int, operation: str) -> MirrorResult:
        if status in (401, 403):
            return MirrorResult(MirrorStatus.REFUSED, error_code=TRACK_REFUSED, detail=f"{operation}: http {status}")
        if status >= 500:
            return MirrorResult(MirrorStatus.UNAVAILABLE, error_code=TRACK_UNAVAILABLE, detail=f"{operation}: http {status}")
        raise MlflowRequestInvalid(status, operation)

    # ------------------------------------------------------------- contract

    def probe(self) -> ProbeResult:
        try:
            version = self._call("GET", "/version")
        except TransportError:
            return ProbeResult(reachable=False)
        api_version = None
        if version.status == 200:
            value = version.payload.get("value")
            api_version = value if isinstance(value, str) and value else None
        return ProbeResult(reachable=version.status < 500, api_version=api_version)

    def authenticate(self, secret_handle: Any) -> AuthResult:
        if secret_handle is None:
            self._authorization = None
            return AuthResult(authenticated=False, failure_code=TRACK_REFUSED)
        use = getattr(secret_handle, "use", None)
        if not callable(use):
            return AuthResult(authenticated=False, failure_code=TRACK_REFUSED)

        def keep(content: bytes) -> bool:
            token = content.decode("utf-8", errors="strict").strip()
            if not token or any(c.isspace() for c in token):
                return False
            self._authorization = "Bearer " + token
            return True

        try:
            ok = use(keep)
        except Exception:  # noqa: BLE001 - CredentialDenied and anything else: refused, no text
            ok = False
        if not ok:
            self._authorization = None
            return AuthResult(authenticated=False, failure_code=TRACK_REFUSED)
        return AuthResult(authenticated=True, principal_ref="service-credential")

    def find(self, intent_id: str) -> str | None:
        """The *complete* run tagged with ``intent_id``, or None.

        A run that exists but lacks the completion marker (or is not FINISHED)
        is a partial remote write: it is not returned here, so the worker calls
        ``mirror``, which resumes it, and it never attests as mirrored. A
        failure to ask is raised as :class:`MirrorFailure` with the coded
        result, so the worker records it instead of creating a duplicate.
        """
        found = self._find_any(intent_id)
        if found is None:
            return None
        run_id, complete = found
        return run_id if complete else None

    def _find_any(self, intent_id: str) -> tuple[str, bool] | None:
        try:
            experiment_ids = self._experiment_ids()
            if not experiment_ids:
                return None
            response = self._call(
                "POST", f"{API}/runs/search",
                {"experiment_ids": experiment_ids, "filter": f"tags.`{TAG_INTENT}` = '{intent_id}'", "max_results": 2},
            )
        except TransportError as exc:
            raise MirrorFailure(MirrorResult(MirrorStatus.UNAVAILABLE, error_code=TRACK_UNAVAILABLE, detail=str(exc))) from None
        if response.status != 200:
            raise MirrorFailure(self._failure(response.status, "runs/search"))
        runs = response.payload.get("runs") or []
        if not runs:
            return None
        run = runs[0]
        run_id = run.get("info", {}).get("run_id")
        if not isinstance(run_id, str) or not run_id:
            return None
        return run_id, self._is_complete(run)

    @staticmethod
    def _is_complete(run: dict[str, Any]) -> bool:
        tags = {t.get("key"): t.get("value") for t in run.get("data", {}).get("tags", [])}
        expected = tags.get(TAG_PAYLOAD_SHA256)
        return bool(expected) and tags.get(TAG_COMPLETE) == expected and run.get("info", {}).get("status") == "FINISHED"

    def mirror(self, record: MirrorRecord) -> MirrorResult:
        try:
            return self._mirror(record)
        except MirrorFailure as failure:
            return failure.result
        except TransportError as exc:
            return MirrorResult(MirrorStatus.UNAVAILABLE, error_code=TRACK_UNAVAILABLE, detail=str(exc))

    def _mirror(self, record: MirrorRecord) -> MirrorResult:
        found = self._find_any(record.intent_id)
        if found is not None and found[1]:
            return MirrorResult(MirrorStatus.MIRRORED, reference_id=found[0], response_payload_sha256=record.payload_sha256)

        now_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
        if found is None:
            experiment_id = self._ensure_experiment(record.experiment)
            if isinstance(experiment_id, MirrorResult):
                return experiment_id
            run_id = self._create_run(record, experiment_id, now_ms)
            if isinstance(run_id, MirrorResult):
                return run_id
        else:
            run_id = found[0]                       # partial write: resume it, never a second run

        # Every step below is idempotent on the server (the same params and
        # metrics are accepted again; a model version for this run is created
        # at most once) and the completion marker is written last, so a fault
        # at any step leaves a run the next delivery resumes rather than trusts.
        payload = record.payload
        params = [{"key": k, "value": self._param_value(v)} for k, v in (payload.get("params") or {}).items() if v is not None]
        metrics = [
            {"key": m["key"], "value": float(m["value"]), "timestamp": int(m.get("timestamp_ms", now_ms)), "step": int(m.get("step", 0))}
            for m in (payload.get("metrics") or [])
        ]
        if params or metrics:
            logged = self._call("POST", f"{API}/runs/log-batch", {"run_id": run_id, "params": params, "metrics": metrics})
            if logged.status != 200:
                return self._failure(logged.status, "runs/log-batch")

        if record.subject_kind == "model_version":
            registry = self._register_model_version(record, run_id)
            if registry is not None:
                return registry

        marked = self._call("POST", f"{API}/runs/set-tag", {"run_id": run_id, "key": TAG_COMPLETE, "value": record.payload_sha256})
        if marked.status != 200:
            return self._failure(marked.status, "runs/set-tag")
        finished = self._call("POST", f"{API}/runs/update", {"run_id": run_id, "status": "FINISHED", "end_time": now_ms})
        if finished.status != 200:
            return self._failure(finished.status, "runs/update")
        return MirrorResult(MirrorStatus.MIRRORED, reference_id=run_id, response_payload_sha256=record.payload_sha256)

    def _create_run(self, record: MirrorRecord, experiment_id: str, now_ms: int) -> str | MirrorResult:
        canonical = canonical_json(record.payload).decode("utf-8")
        tags = {
            TAG_INTENT: record.intent_id,
            TAG_PAYLOAD_SHA256: record.payload_sha256,
            TAG_SUBJECT_KIND: record.subject_kind,
            TAG_PAYLOAD: canonical,
            **{k: str(v) for k, v in (record.payload.get("tags") or {}).items()},
        }
        run_name, _ = self.redact(f"{record.subject_kind}:{record.intent_id}")
        created = self._call(
            "POST", f"{API}/runs/create",
            {"experiment_id": experiment_id, "run_name": run_name, "start_time": now_ms,
             "tags": [{"key": k, "value": v} for k, v in tags.items()]},
        )
        if created.status != 200:
            return self._failure(created.status, "runs/create")
        run_id = created.payload.get("run", {}).get("info", {}).get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise MlflowRequestInvalid(created.status, "runs/create:no-run-id")
        return run_id

    def redact(self, content: str) -> tuple[str, bool]:
        return redact_text(content)

    def attest(self, reference_id: str) -> Attestation:
        try:
            response = self._call("GET", f"{API}/runs/get", query={"run_id": reference_id})
        except TransportError:
            return Attestation(result=AttestationResult.UNVERIFIABLE, detail="unreachable")
        if response.status != 200:
            return Attestation(result=AttestationResult.UNVERIFIABLE, detail=f"http {response.status}")
        run = response.payload.get("run", {})
        tags = {t.get("key"): t.get("value") for t in run.get("data", {}).get("tags", [])}
        stored = tags.get(TAG_PAYLOAD)
        claimed = tags.get(TAG_PAYLOAD_SHA256)
        if not self._is_complete(run):
            # A partial write: not verified, not a mismatch -- the next delivery resumes it.
            return Attestation(result=AttestationResult.UNVERIFIABLE, request_sha256=claimed, detail="incomplete mirror")
        if not isinstance(stored, str) or not stored:
            return Attestation(result=AttestationResult.MISMATCH, request_sha256=claimed, detail="payload tag absent")
        digest = hashlib.sha256(stored.encode("utf-8")).hexdigest()
        result = AttestationResult.VERIFIED if digest == claimed else AttestationResult.MISMATCH
        return Attestation(
            result=result,
            request_sha256=claimed,
            response_sha256=digest,
            provider_claims={TAG_INTENT: tags.get(TAG_INTENT)},
        )

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _param_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)[:500]

    def _experiment_ids(self) -> list[str]:
        # All experiments this principal can see, not only the prefixed ones:
        # idempotency must not depend on the experiment naming convention.
        response = self._call("POST", f"{API}/experiments/search", {"max_results": 1000})
        if response.status != 200:
            raise MirrorFailure(self._failure(response.status, "experiments/search"))
        return [
            e["experiment_id"] for e in response.payload.get("experiments") or []
            if isinstance(e, dict) and isinstance(e.get("experiment_id"), str)
        ]

    def _ensure_experiment(self, name: str) -> str | MirrorResult:
        found = self._call("GET", f"{API}/experiments/get-by-name", query={"experiment_name": name})
        if found.status == 200:
            experiment_id = found.payload.get("experiment", {}).get("experiment_id")
            if isinstance(experiment_id, str) and experiment_id:
                return experiment_id
        elif found.status in (401, 403) or found.status >= 500:
            return self._failure(found.status, "experiments/get-by-name")
        created = self._call("POST", f"{API}/experiments/create", {"name": name})
        if created.status != 200:
            return self._failure(created.status, "experiments/create")
        experiment_id = created.payload.get("experiment_id")
        if not isinstance(experiment_id, str) or not experiment_id:
            raise MlflowRequestInvalid(created.status, "experiments/create:no-id")
        return experiment_id

    def _register_model_version(self, record: MirrorRecord, run_id: str) -> MirrorResult | None:
        """Registered model + version tagged with our identity; our stage is a tag only (§1)."""
        params = record.payload.get("params") or {}
        tags = record.payload.get("tags") or {}
        name = f"{self._prefix}/{params.get('model_id', 'unknown')}"
        existing = self._call("POST", f"{API}/model-versions/search", {"filter": f"run_id = '{run_id}'", "max_results": 1})
        if existing.status != 200:
            return self._failure(existing.status, "model-versions/search")
        if existing.payload.get("model_versions"):
            return None                              # resumed delivery: the version already exists
        created = self._call("POST", f"{API}/registered-models/create", {"name": name})
        if created.status not in (200, 400):        # 400 = RESOURCE_ALREADY_EXISTS
            return self._failure(created.status, "registered-models/create")
        version = self._call(
            "POST", f"{API}/model-versions/create",
            {"name": name, "source": str(params.get("uri", "")), "run_id": run_id,
             "tags": [{"key": k, "value": str(v)} for k, v in tags.items()]},
        )
        if version.status != 200:
            return self._failure(version.status, "model-versions/create")
        return None
