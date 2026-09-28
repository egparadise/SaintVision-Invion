"""PG-free: the MLflow REST sink over a fake transport (S10-BE stage 2).

The fake records every request and answers from a small in-memory model of
the tracking server, so the tests can assert the exact wire format, the
canonical payload tag, idempotent retry, and the error mapping -- without a
network and without the ``mlflow`` package.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

import pytest

from saintvision.adapters.contract import AttestationResult
from saintvision.adapters.mlflow_sink import (
    TAG_INTENT,
    TAG_PAYLOAD,
    TAG_PAYLOAD_SHA256,
    MlflowRequestInvalid,
    MlflowSink,
    TransportError,
    UrllibTransport,
)
from saintvision.adapters.tracking import canonical_record, run_tracking_conformance
from saintvision.tracking.canonical import canonical_bytes
from saintvision.tracking.codes import MirrorStatus

PROVIDER_TEXT = "Internal provider stack trace: /srv/mlflow/secret-path token=abc"


@dataclass
class FakeMlflow:
    """Enough of the MLflow REST API for the sink, plus request capture."""

    requests: list[tuple[str, str, dict]] = field(default_factory=list)
    experiments: dict[str, str] = field(default_factory=dict)          # name -> id
    runs: dict[str, dict] = field(default_factory=dict)                 # run_id -> {experiment_id, tags, params, metrics, status}
    registered: set[str] = field(default_factory=set)
    versions: list[dict] = field(default_factory=list)
    #: (status, body) to answer the next N requests with, then normal.
    faults: list[tuple[int, bytes]] = field(default_factory=list)
    raise_transport: bool = False
    seen_auth: list[str | None] = field(default_factory=list)
    version_text: str = "2.17.2"

    def request(self, method, url, headers, body):
        parts = urlsplit(url)
        payload = json.loads(body) if body else {}
        self.requests.append((method, parts.path, payload))
        self.seen_auth.append(headers.get("Authorization"))
        if self.raise_transport:
            raise TransportError("ConnectionRefusedError")
        if self.faults:
            status, text = self.faults.pop(0)
            return status, text
        return self._route(method, parts, payload)

    def _ok(self, obj):
        return 200, json.dumps(obj).encode("utf-8")

    def _route(self, method, parts, payload):
        path = parts.path
        query = {k: v[0] for k, v in parse_qs(parts.query).items()}
        if path == "/version":
            return 200, json.dumps(self.version_text).encode("utf-8")
        if path.endswith("/experiments/search"):
            assert "filter" not in payload                       # every visible experiment is searched
            return self._ok({"experiments": [{"experiment_id": i, "name": n} for n, i in self.experiments.items()]})
        if path.endswith("/experiments/get-by-name"):
            name = query["experiment_name"]
            if name in self.experiments:
                return self._ok({"experiment": {"experiment_id": self.experiments[name], "name": name}})
            return 404, b'{"error_code":"RESOURCE_DOES_NOT_EXIST","message":"' + PROVIDER_TEXT.encode() + b'"}'
        if path.endswith("/experiments/create"):
            name = payload["name"]
            if name in self.experiments:
                return 400, b'{"error_code":"RESOURCE_ALREADY_EXISTS"}'
            self.experiments[name] = f"exp-{len(self.experiments) + 1}"
            return self._ok({"experiment_id": self.experiments[name]})
        if path.endswith("/runs/search"):
            wanted = payload["filter"].split("'")[1]
            hits = [
                {"info": {"run_id": rid}} for rid, run in self.runs.items()
                if run["experiment_id"] in payload["experiment_ids"] and run["tags"].get(TAG_INTENT) == wanted
            ]
            return self._ok({"runs": hits})
        if path.endswith("/runs/create"):
            run_id = f"run-{len(self.runs) + 1:04d}"
            self.runs[run_id] = {
                "experiment_id": payload["experiment_id"],
                "tags": {t["key"]: t["value"] for t in payload.get("tags", [])},
                "params": {}, "metrics": [], "status": "RUNNING", "name": payload.get("run_name"),
            }
            return self._ok({"run": {"info": {"run_id": run_id}}})
        if path.endswith("/runs/log-batch"):
            run = self.runs[payload["run_id"]]
            run["params"].update({p["key"]: p["value"] for p in payload.get("params", [])})
            run["metrics"].extend(payload.get("metrics", []))
            return self._ok({})
        if path.endswith("/runs/update"):
            self.runs[payload["run_id"]]["status"] = payload["status"]
            return self._ok({})
        if path.endswith("/runs/get"):
            run = self.runs.get(query["run_id"])
            if run is None:
                return 404, b'{"error_code":"RESOURCE_DOES_NOT_EXIST"}'
            return self._ok({"run": {"info": {"run_id": query["run_id"]}, "data": {"tags": [{"key": k, "value": v} for k, v in run["tags"].items()]}}})
        if path.endswith("/registered-models/create"):
            if payload["name"] in self.registered:
                return 400, b'{"error_code":"RESOURCE_ALREADY_EXISTS"}'
            self.registered.add(payload["name"])
            return self._ok({"registered_model": {"name": payload["name"]}})
        if path.endswith("/model-versions/create"):
            self.versions.append(payload)
            return self._ok({"model_version": {"name": payload["name"], "version": str(len(self.versions))}})
        return 404, b"unknown route"


@dataclass
class _Handle:
    secret: bytes

    def use(self, callback):
        return callback(self.secret)


def _sink(server: FakeMlflow, **kw) -> MlflowSink:
    return MlflowSink("https://mlflow.lab.example/", experiment_prefix="inv", transport=server, **kw)


# ---------------------------------------------------------------- construction


def test_the_configuration_path_stays_https_only():
    with pytest.raises(ValueError):
        MlflowSink("http://mlflow.lab.example/", experiment_prefix="inv", transport=FakeMlflow())
    with pytest.raises(ValueError):
        MlflowSink("http://mlflow.lab.example/", experiment_prefix="inv", transport=FakeMlflow(), allow_insecure_loopback=True)
    loop = MlflowSink("http://127.0.0.1:5000/", experiment_prefix="inv", transport=FakeMlflow(), allow_insecure_loopback=True)
    assert repr(loop) == "<MlflowSink http://127.0.0.1:5000>"
    assert repr(_sink(FakeMlflow())) == "<MlflowSink https://mlflow.lab.example>"


def test_the_default_transport_is_bounded_and_never_follows_redirects():
    transport = UrllibTransport(timeout_seconds=3)
    assert transport.timeout_seconds == 3
    with pytest.raises(ValueError):
        UrllibTransport(timeout_seconds=0)
    handler = transport._opener.handlers
    assert any(type(h).__name__ == "_NoRedirects" for h in handler)


# ---------------------------------------------------------------- request format


def test_mirror_writes_experiment_run_batch_and_finish_in_order_with_the_canonical_payload_tag():
    server = FakeMlflow()
    sink = _sink(server)
    record = canonical_record("mmi_0000000000000000000000000A")
    result = sink.mirror(record)
    assert result.status is MirrorStatus.MIRRORED and result.reference_id == "run-0001"
    paths = [p for _, p, _ in server.requests]
    assert paths == [
        "/api/2.0/mlflow/experiments/search",       # find (idempotency) first
        "/api/2.0/mlflow/experiments/get-by-name",
        "/api/2.0/mlflow/experiments/create",
        "/api/2.0/mlflow/runs/create",
        "/api/2.0/mlflow/runs/log-batch",
        "/api/2.0/mlflow/runs/update",
    ]
    create = next(p for m, path, p in server.requests if path.endswith("/runs/create"))
    tags = {t["key"]: t["value"] for t in create["tags"]}
    assert tags[TAG_INTENT] == record.intent_id
    assert tags[TAG_PAYLOAD_SHA256] == record.payload_sha256
    assert tags[TAG_PAYLOAD] == canonical_bytes(record.payload).decode("utf-8")
    assert hashlib.sha256(tags[TAG_PAYLOAD].encode("utf-8")).hexdigest() == record.payload_sha256
    assert tags["inv.tenant_id"] == "t"
    assert create["experiment_id"] == "exp-1" and server.experiments == {record.experiment: "exp-1"}
    batch = next(p for m, path, p in server.requests if path.endswith("/runs/log-batch"))
    assert batch["params"] == [{"key": "suite", "value": "conformance"}, {"key": "version", "value": "1.0.0"}]
    assert batch["metrics"] == [{"key": "gate_passed", "value": 1.0, "timestamp": 0, "step": 0}]
    assert server.runs["run-0001"]["status"] == "FINISHED"


def test_param_values_are_strings_and_metric_values_numbers():
    server = FakeMlflow()
    sink = _sink(server)
    payload = {"params": {"byte_size": 1024, "flag": True, "none": None}, "metrics": [{"key": "m", "value": 0.5, "step": 2, "timestamp_ms": 7}]}
    from saintvision.adapters.tracking import MirrorRecord
    from saintvision.tracking.canonical import payload_sha256

    sink.mirror(MirrorRecord("mmi_x", "eval_run", "inv/t/p", payload, payload_sha256(payload)))
    batch = next(p for m, path, p in server.requests if path.endswith("/runs/log-batch"))
    assert batch["params"] == [{"key": "byte_size", "value": "1024"}, {"key": "flag", "value": "true"}]
    assert batch["metrics"] == [{"key": "m", "value": 0.5, "timestamp": 7, "step": 2}]


def test_a_model_version_also_registers_a_model_version_with_our_stage_as_a_tag():
    server = FakeMlflow()
    sink = _sink(server)
    payload = {"params": {"model_id": "mdl_1", "uri": "inv://models/x@1", "version": "1.0.0"}, "tags": {"inv.stage": "released", "inv.model_version_id": "mdv_1"}}
    from saintvision.adapters.tracking import MirrorRecord
    from saintvision.tracking.canonical import payload_sha256

    result = sink.mirror(MirrorRecord("mmi_m", "model_version", "inv/t/p", payload, payload_sha256(payload)))
    assert result.status is MirrorStatus.MIRRORED
    assert server.registered == {"inv/mdl_1"}
    assert server.versions[0]["source"] == "inv://models/x@1" and server.versions[0]["run_id"] == "run-0001"
    assert {t["key"]: t["value"] for t in server.versions[0]["tags"]}["inv.stage"] == "released"
    assert not any(path.endswith("/model-versions/transition-stage") for _, path, _ in server.requests)
    # Registering again for another intent: the model exists (400) and that is fine.
    sink.mirror(MirrorRecord("mmi_n", "model_version", "inv/t/p", payload, payload_sha256(payload)))
    assert len(server.versions) == 2


# ---------------------------------------------------------------- idempotency


def test_find_before_mirror_makes_redelivery_create_no_second_run():
    server = FakeMlflow()
    sink = _sink(server)
    record = canonical_record("mmi_0000000000000000000000000B")
    first = sink.mirror(record)
    creates = lambda: sum(1 for _, p, _ in server.requests if p.endswith("/runs/create"))
    assert creates() == 1
    assert sink.find(record.intent_id) == first.reference_id
    again = sink.mirror(record)
    assert again.reference_id == first.reference_id and creates() == 1
    assert sink.find("mmi_never") is None


# ---------------------------------------------------------------- error mapping


def test_no_response_is_unavailable_0001_and_carries_no_provider_text():
    server = FakeMlflow(raise_transport=True)
    result = _sink(server).mirror(canonical_record())
    assert (result.status, result.error_code) == (MirrorStatus.UNAVAILABLE, "TRACK-0001")
    assert PROVIDER_TEXT not in (result.detail or "")
    assert _sink(server).probe().reachable is False


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_5xx_is_unavailable_0001(status):
    server = FakeMlflow(faults=[(status, PROVIDER_TEXT.encode())])
    result = _sink(server).mirror(canonical_record())
    assert (result.status, result.error_code) == (MirrorStatus.UNAVAILABLE, "TRACK-0001")
    assert PROVIDER_TEXT not in (result.detail or "")


@pytest.mark.parametrize("status", [401, 403])
def test_auth_failures_are_refused_0002(status):
    server = FakeMlflow(faults=[(status, PROVIDER_TEXT.encode())])
    result = _sink(server).mirror(canonical_record())
    assert (result.status, result.error_code) == (MirrorStatus.REFUSED, "TRACK-0002")
    assert PROVIDER_TEXT not in (result.detail or "")


def test_a_rejected_request_of_our_own_is_0004_and_no_result():
    """A 4xx that is not auth means we built a bad request: our defect, no attempt."""
    server = FakeMlflow()
    sink = _sink(server)
    # Let find/get-by-name/create pass, then reject runs/create with 400.
    server.faults = [(200, b'{"experiments":[]}'), (404, b"{}"), (200, b'{"experiment_id":"exp-9"}'), (400, PROVIDER_TEXT.encode())]
    with pytest.raises(MlflowRequestInvalid) as exc:
        sink.mirror(canonical_record())
    assert exc.value.code == "TRACK-0004" and exc.value.status == 400
    assert PROVIDER_TEXT not in str(exc.value)


def test_failures_map_at_the_step_where_they_happen():
    server = FakeMlflow()
    sink = _sink(server)
    server.faults = [(200, b'{"experiments":[]}'), (503, b"")]      # get-by-name unavailable
    result = sink.mirror(canonical_record("mmi_0000000000000000000000000C"))
    assert result.status is MirrorStatus.UNAVAILABLE and "get-by-name" in result.detail
    server.faults = [(200, b'{"experiments":[]}'), (404, b"{}"), (200, b'{"experiment_id":"exp-1"}'), (200, b'{"run":{"info":{"run_id":"run-x"}}}'), (403, b"")]
    result = sink.mirror(canonical_record("mmi_0000000000000000000000000D"))
    assert result.status is MirrorStatus.REFUSED and "log-batch" in result.detail


# ---------------------------------------------------------------- attest


def test_attest_digests_the_stored_payload_tag_and_notices_tampering_or_absence():
    server = FakeMlflow()
    sink = _sink(server)
    record = canonical_record("mmi_0000000000000000000000000E")
    result = sink.mirror(record)
    good = sink.attest(result.reference_id)
    assert good.result is AttestationResult.VERIFIED
    assert good.response_sha256 == record.payload_sha256 == good.request_sha256
    server.runs[result.reference_id]["tags"][TAG_PAYLOAD] += " "
    assert sink.attest(result.reference_id).result is AttestationResult.MISMATCH
    del server.runs[result.reference_id]["tags"][TAG_PAYLOAD]
    assert sink.attest(result.reference_id).result is AttestationResult.MISMATCH
    assert sink.attest("run-never").result is AttestationResult.UNVERIFIABLE
    server.raise_transport = True
    assert sink.attest(result.reference_id).result is AttestationResult.UNVERIFIABLE


# ---------------------------------------------------------------- authentication


def test_authenticate_uses_the_handle_once_and_the_token_is_only_ever_a_header():
    server = FakeMlflow()
    sink = _sink(server)
    result = sink.authenticate(_Handle(b"s3cr3t-token\n"))
    assert result.authenticated and result.principal_ref == "service-credential"
    assert "s3cr3t" not in repr(sink) and "s3cr3t" not in repr(result)
    sink.probe()
    assert server.seen_auth[-1] == "Bearer s3cr3t-token"
    assert sink.authenticate(None).failure_code == "TRACK-0002"
    sink.probe()
    assert server.seen_auth[-1] is None                     # cleared, not remembered
    assert sink.authenticate(_Handle(b"has space\n")).failure_code == "TRACK-0002"
    assert sink.authenticate(_Handle(b"")).failure_code == "TRACK-0002"
    assert sink.authenticate("not-a-handle").failure_code == "TRACK-0002"

    class Denying:
        def use(self, callback):
            raise RuntimeError(PROVIDER_TEXT)

    denied = sink.authenticate(Denying())
    assert denied.failure_code == "TRACK-0002" and PROVIDER_TEXT not in repr(denied)


def test_probe_reports_the_server_version():
    server = FakeMlflow()
    probe = _sink(server).probe()
    assert probe.reachable and probe.api_version == "2.17.2"


# ---------------------------------------------------------------- the contract suite


def test_the_rest_sink_passes_the_tracking_conformance_suite_over_the_fake():
    report = run_tracking_conformance(_sink(FakeMlflow()))
    assert report.conformant, [(c.name, c.detail) for c in report.failures()]
    assert report.passed == 12
