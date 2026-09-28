"""Strict product ObjectStore settings and credential boundary."""

import json
import os
from pathlib import Path

import pytest

import inv.object_store_config as config_module
from inv.configuration_readiness import configured_s01_readiness
from inv.object_store_config import (
    configured_object_store,
    parse_object_store_configuration,
    read_object_store_credentials,
    unresolved_object_store,
)


def block(**changes):
    value = {
        "providerId": "s3-compatible-v1",
        "endpoint": "https://objects.example.invalid:9443",
        "bucket": "saintvision-artifacts",
        "region": "us-east-1",
        "credentialFile": "/run/saintvision/object-store.json",
        "prefix": "saintvision/product",
    }
    value.update(changes)
    return value


@pytest.mark.parametrize(
    "damage",
    [
        {**block(), "bukcet": "typo"},
        {key: value for key, value in block().items() if key != "bucket"},
        block(providerId="UPPER_NOT_STABLE"),
        block(providerId="local-bounded-v1"),
        block(prefix="../outside"),
        block(region=""),
    ],
)
def test_nested_object_store_keys_and_server_owned_identity_are_strict(damage):
    with pytest.raises(ValueError, match="Invalid objectStore settings"):
        parse_object_store_configuration(damage)


def test_legacy_endpoint_and_new_block_cannot_both_be_enabled():
    with pytest.raises(ValueError, match="Duplicate legacy"):
        configured_s01_readiness(
            {"objectStoreEndpoint": "https://legacy.invalid", "objectStore": block()}
        )


def test_readiness_names_endpoint_bucket_and_credential_without_values(monkeypatch):
    monkeypatch.setattr(
        config_module,
        "read_object_store_credentials",
        lambda _path: (_ for _ in ()).throw(ValueError("private-secret")),
    )
    configuration = parse_object_store_configuration(
        block(endpoint="not-a-url", bucket="INVALID_BUCKET")
    )
    assert unresolved_object_store(configuration) == [
        "INV_OBJECT_STORE_BUCKET",
        "INV_OBJECT_STORE_CREDENTIAL_FILE",
        "INV_OBJECT_STORE_ENDPOINT",
    ]
    provider = configured_s01_readiness(
        {"objectStore": block(endpoint="not-a-url", bucket="INVALID_BUCKET")}
    )
    assert provider() == [
        "INV_NODE_MTLS_CA_BUNDLE",
        "INV_OBJECT_STORE_BUCKET",
        "INV_OBJECT_STORE_CREDENTIAL_FILE",
        "INV_OBJECT_STORE_ENDPOINT",
    ]


def test_endpoint_path_is_blocked_because_sigv4_uses_root_path_style(monkeypatch):
    monkeypatch.setattr(
        config_module,
        "read_object_store_credentials",
        lambda _path: ("synthetic-access", "synthetic-secret"),
    )
    configuration = parse_object_store_configuration(
        block(endpoint="https://objects.example.invalid/base-path")
    )
    assert unresolved_object_store(configuration) == ["INV_OBJECT_STORE_ENDPOINT"]


@pytest.mark.parametrize(
    "value",
    [
        {"accessKeyId": "access"},
        {"accessKeyId": "access", "secretAccessKey": "secret", "extra": True},
        {"accessKeyId": "", "secretAccessKey": "secret"},
    ],
)
def test_credential_json_is_exact_and_errors_never_echo_values(monkeypatch, value):
    monkeypatch.setattr(config_module, "_private_file", lambda _path: json.dumps(value).encode())
    with pytest.raises(ValueError) as error:
        read_object_store_credentials("/run/saintvision/object-store.json")
    assert "access" not in str(error.value) and "secret" not in str(error.value)


def _accept_test_path(monkeypatch):
    monkeypatch.setattr(
        config_module,
        "_CONFIG_PATH",
        type("AnyPath", (), {"fullmatch": lambda self, value: True})(),
    )


def test_private_credential_file_rejects_hardlinks(tmp_path, monkeypatch):
    _accept_test_path(monkeypatch)
    original = tmp_path / "credentials.json"
    original.write_text(
        json.dumps({"accessKeyId": "access", "secretAccessKey": "secret"}),
        encoding="utf-8",
    )
    original.chmod(0o600)
    hardlink = tmp_path / "hardlink.json"
    os.link(original, hardlink)
    with pytest.raises(ValueError, match="credential file"):
        read_object_store_credentials(str(original))


def test_private_credential_file_rejects_symlinks(tmp_path, monkeypatch):
    _accept_test_path(monkeypatch)
    original = tmp_path / "credentials.json"
    original.write_text(
        json.dumps({"accessKeyId": "access", "secretAccessKey": "secret"}),
        encoding="utf-8",
    )
    original.chmod(0o600)
    symlink = tmp_path / "symlink.json"
    try:
        symlink.symlink_to(original)
    except OSError:
        pytest.skip("symlinks unavailable on this host")
    with pytest.raises(ValueError, match="credential file"):
        read_object_store_credentials(str(symlink))


def test_ready_configuration_builds_the_product_provider_without_echoing_secret(monkeypatch):
    monkeypatch.setattr(
        config_module,
        "read_object_store_credentials",
        lambda _path: ("synthetic-access", "synthetic-secret"),
    )
    configuration = parse_object_store_configuration(block())
    assert unresolved_object_store(configuration) == []
    provider = configured_object_store(configuration, transport=object())
    assert provider.provider_id == "s3-compatible-v1"
    assert provider.prefix == "saintvision/product"
    assert provider.client.config.secret_key == "synthetic-secret"
