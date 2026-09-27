"""PG-free contract tests for the redacted S01 Storage roundtrip verifier."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "verify_storage_roundtrip", ROOT / "tools" / "verify_storage_roundtrip.py"
)
verifier = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(verifier)


ENV = {
    "INV_OBJECT_STORE_ENDPOINT": "http://storage.invalid:9000",
    "INV_OBJECT_STORE_BUCKET": "saintvision-roundtrip",
    "INV_OBJECT_STORE_ACCESS_KEY_ID": "synthetic-access",
    "INV_OBJECT_STORE_SECRET_ACCESS_KEY": "synthetic-secret",
    "INV_OBJECT_STORE_REGION": "us-east-1",
    "INV_OBJECT_STORE_TARGET_KIND": "ci-candidate",
    "GITHUB_SHA": "a" * 40,
    "GITHUB_HEAD_SHA": "b" * 40,
}
PAYLOAD = b"saintvision-storage-roundtrip\n"


class FakeTransport:
    def __init__(
        self, *, downloaded=PAYLOAD, metadata=None, delete_status=204, survives_delete=False
    ):
        self.downloaded = downloaded
        self.metadata = metadata
        self.delete_status = delete_status
        self.survives_delete = survives_delete
        self.calls = []
        self.deleted = False

    def request(self, method, url, headers, body):
        self.calls.append((method, url, dict(headers), body))
        if method == "PUT":
            return verifier.HttpResponse(200, {}, b"")
        if method == "DELETE":
            self.deleted = self.delete_status in {200, 204}
            return verifier.HttpResponse(self.delete_status, {}, b"")
        if method == "GET" and self.deleted and not self.survives_delete:
            return verifier.HttpResponse(404, {}, b"")
        if method == "GET":
            digest = verifier.hashlib.sha256(PAYLOAD).hexdigest()
            return verifier.HttpResponse(
                200,
                {"x-amz-meta-content-sha256": self.metadata or digest},
                self.downloaded,
            )
        raise AssertionError(f"unexpected method: {method}")


def test_missing_endpoint_bucket_or_credentials_is_blocked_without_network():
    transport = FakeTransport()
    evidence, exit_code = verifier.execute(
        {"INV_OBJECT_STORE_TARGET_KIND": "ci-candidate"},
        transport=transport,
        payload=PAYLOAD,
    )

    assert exit_code == 3
    assert evidence["status"] == "BLOCKED"
    assert evidence["checks"] == {
        "put": False,
        "get": False,
        "bodySha256": False,
        "metadataSha256": False,
        "delete": False,
        "cleanupVerified": False,
    }
    assert transport.calls == []


def test_environment_credentials_complete_the_real_byte_and_product_header_chain():
    transport = FakeTransport()
    evidence, exit_code = verifier.execute(ENV, transport=transport, payload=PAYLOAD)

    assert exit_code == 0
    assert evidence["status"] == "PASS"
    assert evidence["payloadBytes"] == len(PAYLOAD)
    assert evidence["targetKind"] == "ci-candidate"
    assert evidence["codeSha"] == "b" * 40
    assert all(evidence["checks"].values())
    assert evidence["cleanupVerified"] is True
    assert [call[0] for call in transport.calls] == ["PUT", "GET", "DELETE", "GET"]

    put = transport.calls[0]
    assert put[2]["x-amz-content-sha256"] == verifier.hashlib.sha256(PAYLOAD).hexdigest()
    assert put[2]["x-amz-meta-content-sha256"] == put[2]["x-amz-content-sha256"]
    assert put[2]["authorization"].startswith("AWS4-HMAC-SHA256 Credential=synthetic-access/")

    serialized = json.dumps(evidence, sort_keys=True)
    for forbidden in (
        ENV["INV_OBJECT_STORE_ENDPOINT"],
        ENV["INV_OBJECT_STORE_BUCKET"],
        ENV["INV_OBJECT_STORE_ACCESS_KEY_ID"],
        ENV["INV_OBJECT_STORE_SECRET_ACCESS_KEY"],
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize("damage", ["body", "metadata"])
def test_digest_drift_fails_but_still_deletes_the_owned_object(damage):
    transport = FakeTransport(
        downloaded=b"different" if damage == "body" else PAYLOAD,
        metadata="0" * 64 if damage == "metadata" else None,
    )
    evidence, exit_code = verifier.execute(ENV, transport=transport, payload=PAYLOAD)

    assert exit_code == 1
    assert evidence["status"] == "FAIL"
    assert evidence["checks"]["delete"] is True
    assert evidence["checks"]["cleanupVerified"] is True
    assert [call[0] for call in transport.calls][-2:] == ["DELETE", "GET"]


def test_cleanup_failure_can_never_report_pass():
    transport = FakeTransport(delete_status=500)
    evidence, exit_code = verifier.execute(ENV, transport=transport, payload=PAYLOAD)

    assert exit_code == 1
    assert evidence["status"] == "FAIL"
    assert evidence["checks"]["delete"] is False
    assert evidence["cleanupVerified"] is False


def test_delete_204_but_object_still_present_can_never_report_pass():
    transport = FakeTransport(survives_delete=True)
    evidence, exit_code = verifier.execute(ENV, transport=transport, payload=PAYLOAD)

    assert exit_code == 1
    assert evidence["status"] == "FAIL"
    assert evidence["checks"]["delete"] is True
    assert evidence["cleanupVerified"] is False
    assert [call[0] for call in transport.calls][-2:] == ["DELETE", "GET"]


def test_volume_credential_reference_is_flat_private_and_never_echoed(monkeypatch):
    observed = []

    def read_credentials(path):
        observed.append(str(path))
        return json.dumps(
            {
                "accessKeyId": "volume-access",
                "secretAccessKey": "volume-secret",
                "region": "us-east-1",
            }
        ).encode()

    monkeypatch.setattr(verifier, "_trusted_credential_file", read_credentials)
    env = {
        "INV_OBJECT_STORE_ENDPOINT": ENV["INV_OBJECT_STORE_ENDPOINT"],
        "INV_OBJECT_STORE_BUCKET": ENV["INV_OBJECT_STORE_BUCKET"],
        "INV_OBJECT_STORE_CREDENTIAL_FILE": "/run/saintvision/object-store.json",
        "INV_OBJECT_STORE_TARGET_KIND": "operational",
        "GITHUB_SHA": "b" * 40,
    }
    evidence, exit_code = verifier.execute(env, transport=FakeTransport(), payload=PAYLOAD)

    assert exit_code == 0 and evidence["status"] == "PASS"
    assert evidence["targetKind"] == "operational"
    assert observed == ["/run/saintvision/object-store.json"]
    assert "volume-access" not in json.dumps(evidence)
    assert "volume-secret" not in json.dumps(evidence)


@pytest.mark.parametrize(
    "path",
    [
        "/etc/object-store.json",
        "/run/saintvision/../secret",
        "/run/saintvision/a/b",
    ],
)
def test_outside_or_nested_credential_file_is_blocked_before_read(monkeypatch, path):
    monkeypatch.setattr(
        verifier,
        "_trusted_credential_file",
        lambda _path: (_ for _ in ()).throw(AssertionError("must not read")),
    )
    env = {
        "INV_OBJECT_STORE_ENDPOINT": ENV["INV_OBJECT_STORE_ENDPOINT"],
        "INV_OBJECT_STORE_BUCKET": ENV["INV_OBJECT_STORE_BUCKET"],
        "INV_OBJECT_STORE_CREDENTIAL_FILE": path,
        "INV_OBJECT_STORE_TARGET_KIND": "operational",
    }
    evidence, exit_code = verifier.execute(env, transport=FakeTransport(), payload=PAYLOAD)

    assert exit_code == 3 and evidence["status"] == "BLOCKED"


def test_junit_and_json_outputs_contain_only_the_redacted_evidence(tmp_path):
    evidence, exit_code = verifier.execute(ENV, transport=FakeTransport(), payload=PAYLOAD)
    json_path = tmp_path / "evidence.json"
    junit_path = tmp_path / "evidence.xml"
    verifier.write_outputs(evidence, json_path, junit_path)

    assert exit_code == 0
    assert json.loads(json_path.read_text(encoding="utf-8")) == evidence
    text = junit_path.read_text(encoding="utf-8")
    assert 'tests="1"' in text and 'failures="0"' in text
    assert "synthetic-secret" not in text
    assert ENV["INV_OBJECT_STORE_ENDPOINT"] not in text


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://user:password@storage.invalid:9000",
        "http://storage.invalid:9000/path",
        "http://storage.invalid:bad-port",
        "http://storage.invalid:9000/#fragment",
    ],
)
def test_ambiguous_endpoint_is_blocked_before_network(endpoint):
    transport = FakeTransport()
    evidence, exit_code = verifier.execute(
        {**ENV, "INV_OBJECT_STORE_ENDPOINT": endpoint},
        transport=transport,
        payload=PAYLOAD,
    )

    assert exit_code == 3 and evidence["status"] == "BLOCKED"
    assert transport.calls == []


def test_environment_and_volume_credentials_together_are_blocked(monkeypatch):
    monkeypatch.setattr(
        verifier,
        "_trusted_credential_file",
        lambda _path: (_ for _ in ()).throw(AssertionError("must not read")),
    )
    transport = FakeTransport()
    evidence, exit_code = verifier.execute(
        {**ENV, "INV_OBJECT_STORE_CREDENTIAL_FILE": "/run/saintvision/object-store.json"},
        transport=transport,
        payload=PAYLOAD,
    )

    assert exit_code == 3 and evidence["status"] == "BLOCKED"
    assert transport.calls == []


@pytest.mark.parametrize("target_kind", [None, "", "candidate", "production"])
def test_target_kind_is_required_and_closed_to_two_values(target_kind):
    env = dict(ENV)
    if target_kind is None:
        env.pop("INV_OBJECT_STORE_TARGET_KIND")
    else:
        env["INV_OBJECT_STORE_TARGET_KIND"] = target_kind

    with pytest.raises(verifier.Blocked):
        verifier.execute(env, transport=FakeTransport(), payload=PAYLOAD)
