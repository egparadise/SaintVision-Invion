"""Real PostgreSQL authority races; transport is synthetic, never equipment proof."""
import base64
import hashlib

import psycopg
import pytest

from inv.errors import DomainError
from inv.model_remote import ConfiguredRemoteModelReader
from inv.model_runtime import ModelRuntimeStore
from inv.node_transport import NodeTLSClient
from test_model_runtime import (runtime, locality, model, sample, storage_subject,
                                approval, freeze, authorize, claim)

pytestmark = pytest.mark.postgres


@pytest.fixture
def remote_runtime(runtime, monkeypatch):
    a = runtime
    client = object.__new__(NodeTLSClient)
    def read(channel, request):
        data = b"actual bytes"
        return dict(request, dataBase64=base64.b64encode(data).decode(),
                    chunkSha256=hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(client, "read_chunk", read)
    a.remote_reader = ConfiguredRemoteModelReader(client)
    a.runtime_store = ModelRuntimeStore(a.e.db, a.remote_reader)
    return a


def test_remote_frozen_input_reaches_approved_admission(remote_runtime):
    assert claim(authorize(remote_runtime)).may_start


@pytest.mark.parametrize("assignment", ["enabled=false,version=version+1", "version=version+1"])
def test_channel_changed_during_read_never_commits(remote_runtime, monkeypatch, assignment):
    a = remote_runtime
    original = a.remote_reader.read
    def read(*args, **kwargs):
        result = original(*args, **kwargs)
        # Must finish while reader is running: network phase holds no channel lock.
        with psycopg.connect(a.e.owner) as c:
            c.execute("SET LOCAL lock_timeout='500ms'")
            c.execute("UPDATE inv.node_channels SET " + assignment + " WHERE node_id=%s", (a.e.node,))
        return result
    monkeypatch.setattr(a.remote_reader, "read", read)
    with pytest.raises(DomainError): freeze(a)
    with a.e.db.transaction(a.e.tenant) as c:
        assert not c.execute("SELECT 1 FROM inv.model_runtime_inputs WHERE run_id=%s", (a.target,)).fetchone()


@pytest.mark.parametrize("assignment", ["enabled=false,version=version+1", "version=version+1",
    "certificate_not_after=clock_timestamp()-interval '1 second',version=version+1"])
def test_channel_change_after_approval_prevents_claim(remote_runtime, assignment):
    a = remote_runtime
    approved = authorize(a)
    with psycopg.connect(a.e.owner) as c:
        c.execute("UPDATE inv.node_channels SET " + assignment + " WHERE node_id=%s", (a.e.node,))
    with pytest.raises(DomainError): claim(approved)
