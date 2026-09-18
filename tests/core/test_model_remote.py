import base64
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
from uuid import uuid4

import pytest

from inv.errors import DomainError
from inv.ids import new_id
from inv.model_manifest import LocationSnapshot, canonical
from inv.model_remote import ConfiguredRemoteModelReader
from inv.node_channels import ChannelProof
from inv.node_transport import NodeTLSClient
from model_support import model_body
from test_node_tls import peer  # Synthetic loopback mTLS fixture; no real Node.


@pytest.fixture
def remote(monkeypatch):
    node, contribution = new_id("nod"), new_id("stc")
    tenant, epoch = str(uuid4()), str(uuid4())
    data = (b"first", b"second")
    manifest = model_body(node, [new_id("dtl"), new_id("dtl")], data)
    locations = tuple(LocationSnapshot(r["locationId"], 1, contribution, 1,
        node, "ignored/operator/path", len(data[i]), hashlib.sha256(data[i]).hexdigest())
        for i, r in enumerate(manifest["replicas"]))
    channel = ChannelProof(tenant, node, epoch, 1, "https://node.invalid:443", "a" * 64)
    # No socket or credentials. Production requires the operator's NodeTLSClient.
    client = object.__new__(NodeTLSClient)
    calls = []
    def read(bound_channel, request):
        calls.append((bound_channel, deepcopy(request)))
        chunk = next(d for d in data if hashlib.sha256(d).hexdigest() == request["sha256"])
        return dict(request, dataBase64=base64.b64encode(chunk).decode(),
                    chunkSha256=hashlib.sha256(chunk).hexdigest())
    monkeypatch.setattr(client, "read_chunk", read)
    return ConfiguredRemoteModelReader(client), manifest, locations, (channel,), calls, data


def invoke(remote, *, body=None, locations=None, channels=None):
    reader, original, locs, peers, _, _ = remote
    return reader.read(original if body is None else body,
                       locs if locations is None else locations,
                       peers if channels is None else channels,
                       tenant_id=peers[0].tenant_id, recovery_epoch=peers[0].recovery_epoch)


def test_exact_bytes_pinned_channels_and_immutable_receipt(remote):
    result = invoke(remote)
    _, body, locations, channels, calls, data = remote
    assert result.shards == data
    assert result.channels == channels and result.locations == locations
    assert result.manifest_hash == hashlib.sha256(canonical(body)).hexdigest()
    assert calls[0][1]["nonce"] != calls[1][1]["nonce"]
    assert all(c == channels[0] and r["offset"] == 0 for c, r in calls)
    assert all("path" not in r and "url" not in r for _, r in calls)
    with pytest.raises(FrozenInstanceError):
        result.manifest_hash = "x"
    assert not hasattr(result, "executionAuthorized")


@pytest.mark.parametrize("field,value", [
    ("tenant_id", str(uuid4())), ("recovery_epoch", str(uuid4())),
    ("node_id", new_id("nod")), ("version", 0), ("version", True),
    ("endpoint", "http://node.invalid"), ("endpoint", "https://user:secret@node.invalid"),
    ("certificate_sha256", "invalid"),
])
def test_wrong_channel_rejected_before_network(remote, field, value):
    channels = (replace(remote[3][0], **{field: value}),)
    with pytest.raises(DomainError):
        invoke(remote, channels=channels)
    assert not remote[4]


@pytest.mark.parametrize("field,value", [
    ("location_version", 2), ("node_id", new_id("nod")),
    ("sha256", "0" * 64), ("byte_size", 100),
])
def test_late_location_mismatch_never_reads_first_shard(remote, field, value):
    locations = (remote[2][0], replace(remote[2][1], **{field: value}))
    with pytest.raises(DomainError):
        invoke(remote, locations=locations)
    assert not remote[4]


@pytest.mark.parametrize("fault", ["duplicate-location", "missing-location", "duplicate-channel", "too-large", "too-many"])
def test_preflight_budgets_and_unique_identity(remote, fault):
    body, locations, channels = deepcopy(remote[1]), remote[2], remote[3]
    if fault == "duplicate-location":
        locations += locations[:1]
    elif fault == "missing-location":
        locations = locations[:1]
    elif fault == "duplicate-channel":
        channels += channels
    else:
        count = 9 if fault == "too-many" else 1
        body = model_body(channels[0].node_id, [new_id("dtl") for _ in range(count)],
                          [b"x" if count == 9 else b"x" * 32769 for _ in range(count)])
    with pytest.raises(DomainError):
        invoke(remote, body=body, locations=locations, channels=channels)
    assert not remote[4]


@pytest.mark.parametrize("fault", ["nonce", "self-consistent-forgery", "timeout", "whole-hash"])
def test_failed_read_returns_no_receipt_and_never_retries(remote, monkeypatch, fault):
    reader, body, _, _, calls, _ = remote
    original = reader.client.read_chunk
    def bad(channel, request):
        result = original(channel, request)
        if fault == "nonce":
            result["nonce"] = "0" * 64
        elif fault == "self-consistent-forgery":
            fake = b"z" * request["sizeBytes"]
            result["dataBase64"] = base64.b64encode(fake).decode()
            result["chunkSha256"] = hashlib.sha256(fake).hexdigest()
        elif fault == "timeout":
            raise DomainError("NODE-0030", "Node delivery deadline exceeded", 503)
        return result
    monkeypatch.setattr(reader.client, "read_chunk", bad)
    if fault == "whole-hash":
        body["contentHash"] = "0" * 64
    with pytest.raises(DomainError):
        invoke(remote)
    assert len(calls) == (2 if fault == "whole-hash" else 1)


def test_unconfigured_transport_rejected():
    with pytest.raises(ValueError):
        ConfiguredRemoteModelReader(object())


@pytest.mark.parametrize("failure", [None, "pin", "redirect"])
def test_reader_over_real_loopback_mtls(peer, monkeypatch, failure):
    data = b"synthetic-remote-model"
    location_id = new_id("dtl")
    body = model_body(peer.node.node_id, [location_id], [data])
    digest = hashlib.sha256(data).hexdigest()
    location = LocationSnapshot(location_id, 1, new_id("stc"), 1,
                                peer.node.node_id, "unused", len(data), digest)
    nonce = "b" * 64
    monkeypatch.setattr("inv.model_remote.secrets.token_hex", lambda _: nonce)
    peer.state.result = dict(sha256=digest, sizeBytes=len(data), offset=0, nonce=nonce,
        dataBase64=base64.b64encode(data).decode(), chunkSha256=digest)
    channel = peer.channel
    if failure == "pin":
        channel = replace(channel, certificate_sha256="c" * 64)
    elif failure == "redirect":
        peer.state.status = 302
    reader = ConfiguredRemoteModelReader(peer.client)
    def read():
        return reader.read(body, (location,), (channel,),
                           tenant_id=peer.node.tenant_id, recovery_epoch=peer.epoch)
    if failure:
        with pytest.raises(DomainError):
            read()
    else:
        assert read().shards == (data,)
    assert peer.state.requests == (0 if failure == "pin" else 1)


def test_every_replica_checked_even_when_one_good_copy_exists(remote, monkeypatch):
    reader, body, locations, channels, calls, _ = remote
    second_node = new_id("nod")
    second_location = replace(locations[0], location_id=new_id("dtl"), node_id=second_node)
    second_channel = replace(channels[0], node_id=second_node)
    body["replicas"].append(dict(body["replicas"][0], locationId=second_location.location_id,
                                 nodeId=second_node))
    original = reader.client.read_chunk
    def read(channel, request):
        result = original(channel, request)
        if channel.node_id == second_node:
            result["chunkSha256"] = "0" * 64
        return result
    monkeypatch.setattr(reader.client, "read_chunk", read)
    with pytest.raises(DomainError):
        invoke(remote, locations=locations + (second_location,), channels=channels + (second_channel,))
    assert any(channel.node_id == second_node for channel, _ in calls)
