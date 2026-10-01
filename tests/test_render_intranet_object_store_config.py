import json

import render_intranet_object_store_config as subject


def block(**overrides):
    value = {
        "providerId": "s3-compatible-intranet-v1",
        "endpoint": "https://objects.internal.invalid",
        "bucket": "saintvision-objects",
        "region": "us-east-1",
        "credentialFile": "/run/saintvision/object-store.json",
        "prefix": "saintvision/product",
    }
    value.update(overrides)
    return value


def test_renders_exact_six_key_block_without_reading_credentials():
    result = subject.render(
        {"identity": {"issuer": "https://id.invalid"}},
        block(),
        node_ca_bundle="/run/saintvision/intranet-ca.pem",
    )
    configured = result["configurationReadiness"]["objectStore"]
    assert set(configured) == {
        "providerId",
        "endpoint",
        "bucket",
        "region",
        "credentialFile",
        "prefix",
    }
    assert result["configurationReadiness"]["nodeMtlsCaBundle"] == (
        "/run/saintvision/intranet-ca.pem"
    )
    assert "secret" not in json.dumps(result).lower()


def test_unknown_inner_key_and_legacy_endpoint_refuse():
    invalid = block(typo=True)
    for source, candidate in (
        ({}, invalid),
        ({"objectStoreEndpoint": "https://legacy.invalid"}, block()),
        ({"configurationReadiness": {"objectStoreEndpoint": "legacy"}}, block()),
    ):
        try:
            subject.render(source, candidate, node_ca_bundle=None)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid configuration was accepted")


def test_endpoint_bucket_and_credential_path_are_fail_closed():
    for candidate in (
        block(endpoint="http://user:secret@objects.invalid"),
        block(endpoint="http://objects.invalid/path"),
        block(bucket="UPPERCASE"),
        block(credentialFile="/tmp/object-store.json"),
    ):
        try:
            subject.render({}, candidate, node_ca_bundle=None)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid external field was accepted")


def test_cli_refuses_to_overwrite_existing_output(tmp_path, capsys):
    source = tmp_path / "api.json"
    output = tmp_path / "rendered.json"
    source.write_text(json.dumps({"identity": {}}), encoding="utf-8")
    output.write_text("sentinel\n", encoding="utf-8")

    assert subject.main(
        [
            "--input",
            str(source),
            "--output",
            str(output),
            "--endpoint",
            "http://storage.internal.invalid:9000",
        ]
    ) == 2
    assert output.read_text(encoding="utf-8") == "sentinel\n"
    assert "sentinel" not in capsys.readouterr().out
