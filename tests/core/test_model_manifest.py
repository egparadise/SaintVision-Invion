"""Full-byte integrity, strict ranges and trusted local roots."""

from dataclasses import replace
from copy import deepcopy
import hashlib

import pytest
from inv.errors import DomainError
from inv.ids import new_id
from model_support import model_body
from inv.model_manifest import ConfiguredModelVerifier, LocationSnapshot, RootBinding, manifest_copy
from saintvision.storage.readroot import ReadRoot


def test_schema_accepts_exact_database_shard_limit():
    body = model_body(
        new_id("nod"), [new_id("dtl") for _ in range(1024)], [b"x"] * 1024
    )
    assert manifest_copy(body) == body


def test_schema_rejects_excess_shards_before_reading_files(material, monkeypatch):
    _, _, verifier, _ = material
    body = model_body(
        new_id("nod"), [new_id("dtl") for _ in range(1025)], [b"x"] * 1025
    )

    def forbidden_open(*args, **kwargs):
        pytest.fail("Oversized manifest reached file I/O")

    monkeypatch.setattr(ReadRoot, "open", forbidden_open)
    for operation in (lambda: manifest_copy(body), lambda: verifier.verify(body, [])):
        with pytest.raises(DomainError) as error:
            operation()
        assert (error.value.code, error.value.status) == ("VAL-0002", 422)
        assert error.value.detail == "ModelManifest: invalid contract"


@pytest.fixture
def material(tmp_path):
    node, contribution = new_id("nod"), new_id("stc")
    locations = [new_id("dtl"), new_id("dtl")]
    chunks = [b"first-shard", b"second-shard"]
    manifest = model_body(node, locations, chunks)
    snapshots = []
    for i, chunk in enumerate(chunks):
        (tmp_path / f"{i}.bin").write_bytes(chunk)
        snapshots.append(
            LocationSnapshot(
                locations[i],
                1,
                contribution,
                1,
                node,
                f"{i}.bin",
                len(chunk),
                hashlib.sha256(chunk).hexdigest(),
            )
        )
    verifier = ConfiguredModelVerifier([RootBinding(node, contribution, 1, ReadRoot(tmp_path))])
    return manifest, snapshots, verifier, tmp_path


def test_real_shards_verify_in_order_and_original_body_is_not_aliased(material):
    body, snapshots, verifier, _ = material
    before = deepcopy(body)
    assert len(verifier.verify(body, snapshots)) == 64
    copied = manifest_copy(body)
    copied["shards"][0]["offset"] = 2
    assert body == before


@pytest.mark.parametrize(
    "fault",
    [
        "gap",
        "overlap",
        "order",
        "total",
        "missing-replica",
        "duplicate-replica",
        "wrong-index",
        "raw-key",
        "extra-field",
    ],
)
def test_manifest_rejects_ambiguous_or_unbounded_authority(material, fault):
    body, _, _, _ = material
    if fault == "gap":
        body["shards"][1]["offset"] += 1
    if fault == "overlap":
        body["shards"][1]["offset"] -= 1
    if fault == "order":
        body["shards"].reverse()
    if fault == "total":
        body["totalBytes"] += 1
    if fault == "missing-replica":
        body["replicas"].pop()
    if fault == "duplicate-replica":
        body["replicas"].append(deepcopy(body["replicas"][0]))
    if fault == "wrong-index":
        body["replicas"][0]["shardIndex"] = 999
    if fault == "raw-key":
        body["keyRef"] = "raw-secret-must-never-be-accepted"
    if fault == "extra-field":
        body["approved"] = True
    with pytest.raises(DomainError):
        manifest_copy(body)


@pytest.mark.parametrize(
    "fault",
    [
        "corrupt",
        "truncated",
        "oversized",
        "wrong-whole-hash",
        "unverified",
        "missing-root",
        "traversal",
        "wrong-version",
        "budget",
    ],
)
def test_actual_byte_verification_refuses_faults(material, fault):
    body, snapshots, verifier, root = material
    if fault == "corrupt":
        (root / "0.bin").write_bytes(b"x" * len(b"first-shard"))
    if fault == "truncated":
        (root / "0.bin").write_bytes(b"x")
    if fault == "oversized":
        (root / "0.bin").write_bytes(b"x" * 100)
    if fault == "wrong-whole-hash":
        body["contentHash"] = "0" * 64
    if fault == "unverified":
        body["replicas"][0]["state"] = "unverified"
    if fault == "missing-root":
        snapshots[0] = replace(snapshots[0], contribution_id=new_id("stc"))
    if fault == "traversal":
        snapshots[0] = replace(snapshots[0], relative_path="../outside.bin")
    if fault == "wrong-version":
        snapshots[0] = replace(snapshots[0], contribution_version=2)
    if fault == "budget":
        verifier.max_read_bytes = 1
    with pytest.raises(DomainError):
        verifier.verify(body, snapshots)


def test_hashes_stream_across_the_chunk_boundary(material):
    body, snapshots, verifier, root = material
    content = b"a" * (1024 * 1024 + 37)
    (root / "0.bin").write_bytes(content)
    body["shards"][0]["byteLength"] = len(content)
    body["shards"][0]["sha256"] = hashlib.sha256(content).hexdigest()
    body["shards"][1]["offset"] = len(content)
    body["totalBytes"] = len(content) + snapshots[1].byte_size
    body["contentHash"] = hashlib.sha256(content + (root / "1.bin").read_bytes()).hexdigest()
    snapshots[0] = replace(snapshots[0], byte_size=len(content), sha256=body["shards"][0]["sha256"])
    assert verifier.verify(body, snapshots)


def test_vf_model_uri_is_explicit_and_does_not_change_legacy_uris():
    from inv.storage import parse_uri

    model = new_id("mdl")
    uri = parse_uri("inv://models/" + model + "/1.0.0/weights.bin")
    assert (uri.name, uri.version, uri.subpath) == (model, "1.0.0", "weights.bin")
    legacy = parse_uri("inv://models/old-name@1.0.0/weights.bin")
    assert (legacy.name, legacy.version) == ("old-name", "1.0.0")
    for suffix in ("", "/latest", "/current", "/head"):
        with pytest.raises(DomainError):
            parse_uri("inv://models/" + model + suffix)


def test_manifest_cannot_turn_a_mutable_alias_into_an_immutable_version(material):
    body = material[0]
    body["version"] = "latest"
    with pytest.raises(DomainError):
        manifest_copy(body)


def test_encryption_without_a_configured_provider_never_claims_verified_bytes(material):
    body, snapshots, verifier, _ = material
    body["encryption"] = "aes256-gcm"
    body["keyRef"] = (
        "svcred:1:11111111-1111-1111-1111-111111111111:22222222-2222-2222-2222-222222222222"
    )
    with pytest.raises(DomainError, match="Encrypted model verifier"):
        verifier.verify(body, snapshots)


def test_frozen_shards_are_verified_bytes_and_remain_stable(material):
    body, snapshots, verifier, root = material
    digest, chunks = verifier.freeze(body, snapshots)
    assert digest == verifier.verify(body, snapshots)
    assert chunks == {0: b"first-shard", 1: b"second-shard"}
    (root / "0.bin").write_bytes(b"replacement")
    assert chunks[0] == b"first-shard"
    with pytest.raises(DomainError):
        verifier.freeze(body, snapshots)


@pytest.mark.parametrize("limit", [True, 0, 1, 32769])
def test_model_freeze_cannot_expand_node_input_budget(material, limit):
    body, snapshots, verifier, _ = material
    with pytest.raises(DomainError):
        verifier.freeze(body, snapshots, max_content=limit)
