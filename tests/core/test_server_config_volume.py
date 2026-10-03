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


def write_minimal_worker_bundle(directory):
    (directory / "api.json").write_text(
        json.dumps({"identity": {"jwks_file": "/run/saintvision/jwks.json"}})
    )
    (directory / "jwks.json").write_text("{}")
    (directory / "worker.json").write_text(
        json.dumps(
            {
                "tenantId": "11111111-1111-4111-8111-111111111111",
                "tls": {
                    "ca_file": "/run/saintvision-worker/node-ca.pem",
                    "certificate_file": "/run/saintvision-worker/worker.pem",
                    "key_file": "/run/saintvision-worker/worker.key",
                },
            }
        )
    )
    for name in ("node-ca.pem", "worker.pem", "worker.key"):
        (directory / name).write_text("synthetic")


@pytest.mark.parametrize("target_name", ["worker.json", "worker.key"])
def test_configuration_symlinks_are_rejected(tmp_path, target_name):
    write_minimal_worker_bundle(tmp_path)
    target = tmp_path / target_name
    backing = tmp_path / f"{target_name}.backing"
    target.replace(backing)
    try:
        target.symlink_to(backing.name)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable on this host: {error}")
    with pytest.raises(ValueError, match="Bounded regular configuration files required"):
        module.collect(tmp_path)


@pytest.mark.parametrize("target_name", ["worker.json", "worker.key"])
def test_configuration_hardlinks_are_rejected(tmp_path, target_name):
    write_minimal_worker_bundle(tmp_path)
    os.link(tmp_path / target_name, tmp_path / f"{target_name}.alias")
    with pytest.raises(ValueError, match="Bounded regular configuration files required"):
        module.collect(tmp_path)


@pytest.mark.parametrize("target_name", ["worker.json", "worker.key"])
def test_configuration_directories_are_rejected(tmp_path, target_name):
    write_minimal_worker_bundle(tmp_path)
    target = tmp_path / target_name
    target.unlink()
    target.mkdir()
    with pytest.raises(ValueError, match="Bounded regular configuration files required"):
        module.collect(tmp_path)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO creation is unavailable")
@pytest.mark.parametrize("target_name", ["worker.json", "worker.key"])
def test_configuration_fifos_are_rejected_without_reading(tmp_path, target_name):
    write_minimal_worker_bundle(tmp_path)
    target = tmp_path / target_name
    target.unlink()
    os.mkfifo(target)
    with pytest.raises(ValueError, match="Bounded regular configuration files required"):
        module.collect(tmp_path)


@pytest.mark.parametrize("target_name", ["worker.json", "worker.key"])
def test_configuration_files_over_64_kib_are_rejected(tmp_path, target_name):
    write_minimal_worker_bundle(tmp_path)
    (tmp_path / target_name).write_bytes(b"x" * 65537)
    with pytest.raises(ValueError, match="Bounded regular configuration files required"):
        module.collect(tmp_path)


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
    api_files, api_private, worker_files, worker_private = module.collect(tmp_path)
    assert set(api_files) == {"api.json", "jwks.json"} and not api_private
    assert not worker_files and not worker_private


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
    api_files, api_private, worker_files, worker_private = module.collect(tmp_path)
    assert set(api_files) == {"api.json", "jwks.json", "node-mtls-ca.pem"}
    assert not api_private and not worker_files and not worker_private


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
    api_files, api_private, worker_files, worker_private = module.collect(tmp_path)
    assert set(api_files) == {"api.json", "jwks.json", "object-store.json"}
    assert api_private == {"object-store.json"}
    assert not worker_files and not worker_private


def test_worker_json_and_only_its_flat_tls_references_enter_volume(tmp_path):
    (tmp_path / "api.json").write_text(
        json.dumps({"identity": {"jwks_file": "/run/saintvision/jwks.json"}})
    )
    worker = {
        "tenantId": "11111111-1111-4111-8111-111111111111",
        "tls": {
            "ca_file": "/run/saintvision-worker/node-ca.pem",
            "certificate_file": "/run/saintvision-worker/worker.pem",
            "key_file": "/run/saintvision-worker/worker.key",
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

    api_files, api_private, worker_files, worker_private = module.collect(tmp_path)

    assert set(api_files) == {"api.json", "jwks.json"}
    assert not api_private
    assert set(worker_files) == {
        "worker.json",
        "node-ca.pem",
        "worker.pem",
        "worker.key",
    }
    assert worker_private == {"worker.key"}


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
    api_files, api_private, worker_files, worker_private = module.collect(tmp_path)
    assert set(api_files) == {"api.json", "jwks.json"}
    assert api_private == set()
    assert not worker_files and not worker_private


@pytest.mark.parametrize(
    "mutation",
    [
        lambda worker: worker.update({"unknown": True}),
        lambda worker: worker.update({"tenantId": "not-a-uuid"}),
        lambda worker: worker["tls"].update({"key_file": "/outside/worker.key"}),
        lambda worker: worker["tls"].update({"key_file": "/run/saintvision/worker.key"}),
        lambda worker: worker["tls"].update({"key_file": "/run/saintvision-worker/worker.json"}),
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
            "ca_file": "/run/saintvision-worker/node-ca.pem",
            "certificate_file": "/run/saintvision-worker/worker.pem",
            "key_file": "/run/saintvision-worker/worker.key",
        },
    }
    mutation(worker)
    (tmp_path / "worker.json").write_text(json.dumps(worker))
    with pytest.raises(ValueError):
        module.collect(tmp_path)


def test_api_and_worker_references_cannot_copy_the_same_source_file(tmp_path):
    (tmp_path / "api.json").write_text(
        json.dumps(
            {
                "identity": {"jwks_file": "/run/saintvision/jwks.json"},
                "workspace": {
                    "signingKeyFile": "/run/saintvision/worker.key",
                    "tls": {
                        "ca_file": "/run/saintvision/api-ca.pem",
                        "certificate_file": "/run/saintvision/api.pem",
                        "key_file": "/run/saintvision/api.key",
                    },
                },
            }
        )
    )
    (tmp_path / "worker.json").write_text(
        json.dumps(
            {
                "tenantId": "11111111-1111-4111-8111-111111111111",
                "tls": {
                    "ca_file": "/run/saintvision-worker/node-ca.pem",
                    "certificate_file": "/run/saintvision-worker/worker.pem",
                    "key_file": "/run/saintvision-worker/worker.key",
                },
            }
        )
    )
    for name in (
        "jwks.json",
        "worker.key",
        "api-ca.pem",
        "api.pem",
        "api.key",
        "node-ca.pem",
        "worker.pem",
    ):
        (tmp_path / name).write_text("synthetic")
    with pytest.raises(ValueError, match="distinct files"):
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


def test_worker_document_requires_a_distinct_worker_volume(tmp_path):
    (tmp_path / "api.json").write_text(
        json.dumps({"identity": {"jwks_file": "/run/saintvision/jwks.json"}})
    )
    (tmp_path / "jwks.json").write_text("{}")
    (tmp_path / "worker.json").write_text(
        json.dumps(
            {
                "tenantId": "11111111-1111-4111-8111-111111111111",
                "tls": {
                    "ca_file": "/run/saintvision-worker/node-ca.pem",
                    "certificate_file": "/run/saintvision-worker/worker.pem",
                    "key_file": "/run/saintvision-worker/worker.key",
                },
            }
        )
    )
    for name in ("node-ca.pem", "worker.pem", "worker.key"):
        (tmp_path / name).write_text("synthetic")
    with pytest.raises(ValueError, match="Separate worker configuration volume required"):
        module.prepare(tmp_path, "sv-api-config", "sha256:" + "0" * 64)


def test_api_and_worker_volume_names_must_be_distinct(tmp_path):
    with pytest.raises(ValueError, match="volumes must differ"):
        module.prepare(
            tmp_path,
            "sv-config",
            "sha256:" + "0" * 64,
            worker_volume="sv-config",
        )


def test_worker_volume_without_worker_document_is_rejected_before_docker(tmp_path):
    (tmp_path / "api.json").write_text(
        json.dumps({"identity": {"jwks_file": "/run/saintvision/jwks.json"}})
    )
    (tmp_path / "jwks.json").write_text("{}")
    with pytest.raises(ValueError, match="Worker configuration required"):
        module.prepare(
            tmp_path,
            "sv-api-config",
            "sha256:" + "0" * 64,
            worker_volume="sv-worker-config",
        )


def test_failed_worker_verification_cleans_only_both_new_owned_volumes(tmp_path, monkeypatch):
    (tmp_path / "api.json").write_text(
        json.dumps({"identity": {"jwks_file": "/run/saintvision/jwks.json"}})
    )
    (tmp_path / "jwks.json").write_text("{}")
    (tmp_path / "worker.json").write_text(
        json.dumps(
            {
                "tenantId": "11111111-1111-4111-8111-111111111111",
                "tls": {
                    "ca_file": "/run/saintvision-worker/node-ca.pem",
                    "certificate_file": "/run/saintvision-worker/worker.pem",
                    "key_file": "/run/saintvision-worker/worker.key",
                },
            }
        )
    )
    for name in ("node-ca.pem", "worker.pem", "worker.key"):
        (tmp_path / name).write_text("synthetic")
    labels = {}
    removed = []

    def fake_docker(*args, payload=None):
        assert payload is None
        if args[:2] == ("volume", "ls"):
            return "operator-existing-volume"
        if args[:2] == ("volume", "create"):
            labels[args[-1]] = next(
                value.split("=", 1)[1]
                for value in args
                if value.startswith("ai.saintvision.config=")
            )
            return args[-1]
        if args[:2] == ("volume", "inspect"):
            return labels[args[-1]]
        if args[:2] == ("volume", "rm"):
            removed.append(args[-1])
            labels.pop(args[-1])
            return args[-1]
        raise AssertionError(args)

    def fail_worker(_volume, _image, _files, _private, *, target, verify):
        assert verify
        if target == module.WORKER_ROOT:
            raise RuntimeError("synthetic worker verification failure")

    monkeypatch.setattr(module, "docker", fake_docker)
    monkeypatch.setattr(module, "_write_and_verify", fail_worker)
    with pytest.raises(RuntimeError, match="worker verification"):
        module.prepare(
            tmp_path,
            "sv-api-config",
            "sha256:" + "0" * 64,
            worker_volume="sv-worker-config",
        )
    assert removed == ["sv-worker-config", "sv-api-config"]
    assert labels == {}


def test_real_container_mounts_hide_worker_credentials_from_api(tmp_path):
    image = os.environ.get("INV_TEST_CONFIG_IMAGE")
    if not image:
        pytest.skip("Explicit pinned local candidate image required")
    from jwt_support import jwt_fixture
    from pki_support import authority, credentials, issue

    identity = jwt_fixture(tmp_path, str(uuid4()))
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
    ca = authority()
    client = issue(ca, "spiffe://saintvision.test/worker")
    tls_files = credentials(tmp_path, ca, client, prefix="worker")
    (tmp_path / "worker.json").write_text(
        json.dumps(
            {
                "tenantId": "11111111-1111-4111-8111-111111111111",
                "tls": {
                    name: "/run/saintvision-worker/" + path.name for name, path in tls_files.items()
                },
            }
        )
    )
    api_volume = "sv-api-config-test-" + uuid4().hex
    worker_volume = "sv-worker-config-test-" + uuid4().hex
    try:
        receipt = module.prepare(
            tmp_path,
            api_volume,
            image,
            worker_volume=worker_volume,
        )
        assert receipt["apiFilesVerified"] == 2
        assert receipt["workerFilesVerified"] == 4
        module.docker(
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--user",
            "65532:65532",
            "--mount",
            f"type=volume,source={api_volume},target=/run/saintvision,readonly",
            image,
            "python",
            "-c",
            "from pathlib import Path; "
            "assert Path('/run/saintvision/api.json').is_file(); "
            "assert not Path('/run/saintvision/worker.json').exists(); "
            "assert not Path('/run/saintvision/worker-key.pem').exists(); "
            "assert not Path('/run/saintvision-worker').exists()",
        )
        module.docker(
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--user",
            "65532:65532",
            "--mount",
            f"type=volume,source={api_volume},target=/run/saintvision,readonly",
            "--mount",
            f"type=volume,source={worker_volume},target=/run/saintvision-worker,readonly",
            image,
            "python",
            "-c",
            "from pathlib import Path; "
            "assert Path('/run/saintvision/api.json').is_file(); "
            "assert Path('/run/saintvision-worker/worker.json').is_file(); "
            "assert Path('/run/saintvision-worker/worker-key.pem').is_file()",
        )
    finally:
        existing = set(module.docker("volume", "ls", "--format", "{{.Name}}").splitlines())
        for volume in (api_volume, worker_volume):
            if volume in existing:
                label = module.docker(
                    "volume",
                    "inspect",
                    "--format",
                    '{{index .Labels "ai.saintvision.config"}}',
                    volume,
                )
                assert len(label) == 32
                module.docker("volume", "rm", volume)
