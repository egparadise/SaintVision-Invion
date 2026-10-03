"""No credential files outside the explicit configuration may enter a volume."""

import importlib.util
import json
import os
import time
from uuid import uuid4
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "prepare_server_config", ROOT / "tools/prepare_server_config.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize(
    "reference",
    [
        "/outside/key",
        "/run/saintvision/../key",
        "/run/saintvision/api.json",
        "/run/saintvision/a/b",
    ],
)
def test_outside_and_aliased_references_refused(tmp_path, reference):
    (tmp_path / "api.json").write_text(json.dumps({"identity": {"jwks_file": reference}}))
    with pytest.raises(ValueError):
        module.collect(tmp_path)


def test_unreferenced_private_files_never_copied(tmp_path):
    (tmp_path / "api.json").write_text(
        json.dumps({"identity": {"jwks_file": "/run/saintvision/jwks.json"}})
    )
    (tmp_path / "jwks.json").write_text("{}")
    (tmp_path / "unrelated-key.pem").write_text("synthetic-unrelated-secret")
    files, private = module.collect(tmp_path)
    assert set(files) == {"api.json", "jwks.json"} and not private


def test_operational_ca_bundle_is_copied_only_when_api_json_references_it(tmp_path):
    config = {
        "identity": {"jwks_file": "/run/saintvision/jwks.json"},
        "configurationReadiness": {
            "nodeMtlsCaBundle": "/run/saintvision/node-mtls-ca.pem",
            "objectStoreEndpoint": "http://minio:9000",
        },
    }
    (tmp_path / "api.json").write_text(json.dumps(config))
    (tmp_path / "jwks.json").write_text("{}")
    (tmp_path / "node-mtls-ca.pem").write_text("synthetic-public-ca")
    files, private = module.collect(tmp_path)
    assert set(files) == {"api.json", "jwks.json", "node-mtls-ca.pem"}
    assert not private


def test_object_store_credential_is_the_only_new_private_file(tmp_path):
    config = {
        "identity": {"jwks_file": "/run/saintvision/jwks.json"},
        "configurationReadiness": {
            "objectStore": {
                "providerId": "s3-compatible-v1",
                "endpoint": "https://objects.example.invalid",
                "bucket": "saintvision-artifacts",
                "region": "us-east-1",
                "credentialFile": "/run/saintvision/object-store.json",
                "prefix": "saintvision/product",
            }
        },
    }
    (tmp_path / "api.json").write_text(json.dumps(config))
    (tmp_path / "jwks.json").write_text("{}")
    (tmp_path / "object-store.json").write_text(
        json.dumps({"accessKeyId": "synthetic", "secretAccessKey": "secret"})
    )
    files, private = module.collect(tmp_path)
    assert set(files) == {"api.json", "jwks.json", "object-store.json"}
    assert private == {"object-store.json"}


def test_worker_json_and_only_its_flat_tls_references_enter_volume(tmp_path):
    (tmp_path / "api.json").write_text(
        json.dumps({"identity": {"jwks_file": "/run/saintvision/jwks.json"}})
    )
    worker = {
        "tenantId": "11111111-1111-4111-8111-111111111111",
        "tls": {
            "ca_file": "/run/saintvision/node-ca.pem",
            "certificate_file": "/run/saintvision/worker.pem",
            "key_file": "/run/saintvision/worker.key",
        },
        "buildExecution": {
            "buildctlPath": "/usr/bin/buildctl",
            "address": "unix:///run/user/65532/buildkit/buildkitd.sock",
            "sourceRoot": "/workspaces",
            "referenceHealthReceipt": "/run/saintvision/buildkit-health.json",
            "productReceiptDirectory": "/var/lib/saintvision/build-receipts",
            "builderInstanceId": "builder-rootless-01",
            "builderProfileId": "buildkit-rootless-v1",
            "providerRecoveryEpoch": 7,
            "nodeId": "nod_00000000000000000000000000",
        },
    }
    (tmp_path / "worker.json").write_text(json.dumps(worker))
    for name in ("jwks.json", "node-ca.pem", "worker.pem", "worker.key"):
        (tmp_path / name).write_text("synthetic")
    (tmp_path / "unreferenced.key").write_text("must-not-enter")

    files, private = module.collect(tmp_path)

    assert set(files) == {
        "api.json",
        "worker.json",
        "jwks.json",
        "node-ca.pem",
        "worker.pem",
        "worker.key",
    }
    assert private == {"worker.key"}


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update({"productReceiptDirectory": "/private/receipts"}),
        lambda value: value.update({"tls": {"key_file": "/private/key"}}),
        lambda value: value.pop("sourceRoot"),
        lambda value: value.__setitem__("providerRecoveryEpoch", "1"),
    ],
)
def test_api_build_plan_authority_is_minimal_non_secret_and_exact(tmp_path, mutation):
    authority = {
        "buildctlPath": "/usr/bin/buildctl",
        "address": "unix:///run/user/65532/buildkit/buildkitd.sock",
        "sourceRoot": "/workspaces",
        "referenceHealthReceipt": "/run/saintvision/buildkit-health.json",
        "builderInstanceId": "builder-rootless-01",
        "builderProfileId": "buildkit-rootless-v1",
        "providerRecoveryEpoch": 7,
        "nodeId": "nod_00000000000000000000000000",
    }
    mutation(authority)
    (tmp_path / "api.json").write_text(
        json.dumps(
            {
                "identity": {"jwks_file": "/run/saintvision/jwks.json"},
                "buildPlanAuthority": authority,
            }
        )
    )
    (tmp_path / "jwks.json").write_text("{}")
    with pytest.raises(ValueError, match="build plan authority"):
        module.collect(tmp_path)


def test_api_build_plan_authority_adds_no_secret_file_to_server_volume(tmp_path):
    authority = {
        "buildctlPath": "/usr/bin/buildctl",
        "address": "unix:///run/user/65532/buildkit/buildkitd.sock",
        "sourceRoot": "/workspaces",
        "referenceHealthReceipt": "/run/saintvision/buildkit-health.json",
        "builderInstanceId": "builder-rootless-01",
        "builderProfileId": "buildkit-rootless-v1",
        "providerRecoveryEpoch": 7,
        "nodeId": "nod_00000000000000000000000000",
    }
    (tmp_path / "api.json").write_text(
        json.dumps(
            {
                "identity": {"jwks_file": "/run/saintvision/jwks.json"},
                "buildPlanAuthority": authority,
            }
        )
    )
    (tmp_path / "jwks.json").write_text("{}")
    files, private = module.collect(tmp_path)
    assert set(files) == {"api.json", "jwks.json"}
    assert private == set()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda worker: worker.update({"unknown": True}),
        lambda worker: worker.update({"tenantId": "not-a-uuid"}),
        lambda worker: worker["tls"].update({"key_file": "/outside/worker.key"}),
        lambda worker: worker["tls"].update({"key_file": "/run/saintvision/worker.json"}),
        lambda worker: worker.update({"buildExecution": {"nodeId": "node"}}),
    ],
)
def test_worker_configuration_is_strict_and_flat(tmp_path, mutation):
    (tmp_path / "api.json").write_text(
        json.dumps({"identity": {"jwks_file": "/run/saintvision/jwks.json"}})
    )
    (tmp_path / "jwks.json").write_text("{}")
    worker = {
        "tenantId": "11111111-1111-4111-8111-111111111111",
        "tls": {
            "ca_file": "/run/saintvision/node-ca.pem",
            "certificate_file": "/run/saintvision/worker.pem",
            "key_file": "/run/saintvision/worker.key",
        },
    }
    mutation(worker)
    (tmp_path / "worker.json").write_text(json.dumps(worker))
    with pytest.raises(ValueError):
        module.collect(tmp_path)


@pytest.mark.parametrize(
    "object_store",
    [
        {"providerId": "s3-compatible-v1", "bukcet": "typo"},
        {
            "providerId": "s3-compatible-v1",
            "endpoint": "https://objects.example.invalid",
            "bucket": "saintvision-artifacts",
            "region": "us-east-1",
            "credentialFile": "/outside/secret.json",
            "prefix": "saintvision/product",
        },
    ],
)
def test_object_store_unknown_keys_missing_keys_and_outside_credentials_are_rejected(
    tmp_path, object_store
):
    (tmp_path / "api.json").write_text(
        json.dumps(
            {
                "identity": {"jwks_file": "/run/saintvision/jwks.json"},
                "configurationReadiness": {"objectStore": object_store},
            }
        )
    )
    (tmp_path / "jwks.json").write_text("{}")
    with pytest.raises(ValueError):
        module.collect(tmp_path)


@pytest.mark.parametrize("expired", [False, True])
def test_real_volume_copy_or_failure_cleanup(tmp_path, expired):
    image = os.environ.get("INV_TEST_CONFIG_IMAGE")
    if not image:
        pytest.skip("Explicit pinned local candidate image required")
    from jwt_support import jwt_fixture

    identity = jwt_fixture(tmp_path, str(uuid4()))
    if expired:
        identity.bundle["expiresAt"] = int(time.time()) - 1
        identity.path.write_text(json.dumps(identity.bundle))
    (tmp_path / "api.json").write_text(
        json.dumps(
            {
                "identity": {
                    "tenant_id": identity.tenant,
                    "issuer": identity.issuer,
                    "audience": identity.audience,
                    "client_ids": ["synthetic-web"],
                    "jwks_file": "/run/saintvision/jwks.json",
                }
            }
        )
    )
    original = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    volume = "sv-config-test-" + uuid4().hex
    try:
        if expired:
            with pytest.raises(RuntimeError):
                module.prepare(tmp_path, volume, image)
            assert volume not in module.docker("volume", "ls", "--format", "{{.Name}}").splitlines()
        else:
            receipt = module.prepare(tmp_path, volume, image)
            assert receipt["filesVerified"] == 2 and receipt["serverStarted"] is False
            with pytest.raises(ValueError, match="never be overwritten"):
                module.prepare(tmp_path, volume, image)
        assert original == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    finally:
        if volume in module.docker("volume", "ls", "--format", "{{.Name}}").splitlines():
            label = module.docker(
                "volume", "inspect", "--format", '{{index .Labels "ai.saintvision.config"}}', volume
            )
            assert len(label) == 32
            module.docker("volume", "rm", volume)
