"""The delivery worker consumes the API's one strict ObjectStore source."""

import json

import pytest

import inv.object_store as object_store
import inv.object_store_config as object_store_config
import inv.worker as worker


def block(**changes):
    value = {
        "providerId": "s3-compatible-v1",
        "endpoint": "https://objects.example.invalid",
        "bucket": "saintvision-artifacts",
        "region": "us-east-1",
        "credentialFile": "/run/saintvision/object-store.json",
        "prefix": "saintvision/product",
    }
    value.update(changes)
    return value


def api(readiness):
    return json.dumps({"configurationReadiness": readiness}).encode()


def test_worker_preserves_legacy_local_provider_without_api_config(monkeypatch):
    sentinel = object()
    monkeypatch.delenv("INV_API_CONFIG", raising=False)
    monkeypatch.setattr(object_store, "LocalObjects", lambda root: sentinel)
    assert worker._output_provider({"outputRoot": "/srv/objects"}) is sentinel
    assert worker._output_provider({}) is None


def test_worker_builds_s3_from_the_same_api_configuration(monkeypatch):
    monkeypatch.setenv("INV_API_CONFIG", "/run/saintvision/api.json")
    monkeypatch.setattr(worker, "trusted_file", lambda _path: api({"objectStore": block()}))
    monkeypatch.setattr(
        object_store_config,
        "read_object_store_credentials",
        lambda _path: ("synthetic-access", "synthetic-secret"),
    )
    provider = worker._output_provider({})
    assert provider.provider_id == "s3-compatible-v1"
    assert provider.prefix == "saintvision/product"


def test_worker_refuses_local_and_s3_dual_write(monkeypatch):
    monkeypatch.setenv("INV_API_CONFIG", "/run/saintvision/api.json")
    monkeypatch.setattr(worker, "trusted_file", lambda _path: api({"objectStore": block()}))
    monkeypatch.setattr(object_store, "LocalObjects", lambda _root: object())
    monkeypatch.setattr(
        object_store_config,
        "read_object_store_credentials",
        lambda _path: ("synthetic-access", "synthetic-secret"),
    )
    with pytest.raises(ValueError, match="Duplicate legacy"):
        worker._output_provider({"outputRoot": "/srv/objects"})


@pytest.mark.parametrize(
    "readiness",
    [
        {"objectStore": block(bukcet="typo")},
        {"objectStore": block(endpoint="not-a-url")},
        {
            "objectStoreEndpoint": "https://legacy.invalid",
            "objectStore": block(),
        },
    ],
)
def test_worker_refuses_invalid_or_unready_canonical_settings(monkeypatch, readiness):
    monkeypatch.setenv("INV_API_CONFIG", "/run/saintvision/api.json")
    monkeypatch.setattr(worker, "trusted_file", lambda _path: api(readiness))
    monkeypatch.setattr(
        object_store_config,
        "read_object_store_credentials",
        lambda _path: ("synthetic-access", "synthetic-secret"),
    )
    with pytest.raises(ValueError):
        worker._output_provider({})
