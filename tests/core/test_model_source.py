"""Byte provenance and orchestration tests, not a substitute for PostgreSQL locks."""
import base64
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import hashlib
from types import SimpleNamespace
from uuid import uuid4

import pytest

from inv.approvals import Principal
from inv.errors import DomainError
from inv.ids import new_id
from inv.model_manifest import canonical
from inv.model_runtime import ModelRuntimeStore, approved_model
from inv.model_source import SOURCE_FILE, capture_channels, frozen_sources, source_content, source_records
from inv.policy import action_digest
from inv.workspace_files import FORMAT, decode_snapshot
from test_model_remote import remote


def snapshot(wid, records, *, marker=True):
    data = source_content(records)
    return canonical(dict(format=FORMAT, workspaceId=wid, directories=["model"], files=[
        dict(path=SOURCE_FILE, executable=False, sha256=hashlib.sha256(data).hexdigest(),
             sizeBytes=len(data), dataBase64=base64.b64encode(data).decode())
    ] if marker else []))


def test_private_metadata_only_bound_by_hash_in_workspace(remote):
    _, _, locations, channels, _, _ = remote
    records = source_records(locations, channels)
    wid = new_id("wsp")
    raw = snapshot(wid, records)
    assert frozen_sources(raw, wid, records, channels[0].tenant_id, channels[0].recovery_epoch) == (locations, channels)
    assert channels[0].endpoint.encode() not in source_content(records)
    assert locations[0].relative_path.encode() not in source_content(records)


@pytest.mark.parametrize("fault", ["drop-channels", "drop-one", "drop-marker", "changed-version", "foreign-tenant", "foreign-epoch"])
def test_remote_provenance_cannot_downgrade_or_be_rebound(remote, fault):
    _, _, locations, channels, _, _ = remote
    records = source_records(locations, channels)
    wid = new_id("wsp")
    raw = snapshot(wid, records, marker=fault != "drop-marker")
    if fault in {"drop-channels", "drop-one"}:
        for row in records if fault == "drop-channels" else records[:1]:
            del row["channel"]
    elif fault == "changed-version":
        for row in records:
            row["channel"]["version"] += 1
    tenant, epoch = channels[0].tenant_id, channels[0].recovery_epoch
    if fault == "foreign-tenant": tenant = str(uuid4())
    if fault == "foreign-epoch": epoch = str(uuid4())
    with pytest.raises(DomainError):
        frozen_sources(raw, wid, records, tenant, epoch)


def test_legacy_local_snapshot_has_no_remote_authority(remote):
    _, _, locations, channels, _, _ = remote
    records = source_records(locations)
    wid = new_id("wsp")
    assert frozen_sources(snapshot(wid, records, marker=False), wid, records,
        channels[0].tenant_id, channels[0].recovery_epoch) == (locations, ())


@pytest.fixture
def preparing(remote, monkeypatch):
    reader, body, locations, channels, calls, data = remote
    epoch, tenant = channels[0].recovery_epoch, channels[0].tenant_id
    state = SimpleNamespace(in_tx=False, inserts=[], scopes=0)
    class Conn:
        def execute(self, sql, params=()):
            if "INSERT INTO inv.model_runtime_inputs" in sql:
                state.inserts.append(params)
            return SimpleNamespace(fetchone=lambda: None)
    @contextmanager
    def transaction(tenant_id):
        assert tenant_id == tenant and not state.in_tx
        state.in_tx = True
        try: yield Conn()
        finally: state.in_tx = False
    db = SimpleNamespace(recovery_epoch=epoch, transaction=transaction)
    store = ModelRuntimeStore(db, reader)
    store.auth = SimpleNamespace(_ledger=lambda *a: None, _grant=lambda *a: None,
                                 _save=lambda *a: a[-1])
    monkeypatch.setattr("inv.model_runtime.event", lambda *a: None)
    monkeypatch.setattr("inv.model_runtime.assert_fences", lambda *a: None)
    state.captured = (1, {"node_id": channels[0].node_id,
        "manifest_sha256": hashlib.sha256(canonical(body)).hexdigest()}, body, locations, channels)
    def scope(*args):
        assert state.in_tx
        state.scopes += 1
        return state.captured
    monkeypatch.setattr(store, "_scope", scope)
    original = reader.read
    def read(*args, **kwargs):
        assert not state.in_tx, "Network read under DB transaction"
        return original(*args, **kwargs)
    monkeypatch.setattr(reader, "read", read)
    workload = dict(apiVersion="inv.saintvision.ai/v1alpha1", kind="Workload",
        workloadId=new_id("wld"), tenantId=tenant, projectId=new_id("prj"),
        workspaceId=new_id("wsp"), resources=dict(cpuMillis=1, memoryBytes=1,gpuCount=0,minVramBytes=0),
        imageDigest="sha256:" + "a" * 64, command=["synthetic-command"], timeoutSeconds=30)
    def prepare():
        return store.prepare(Principal(tenant, "synthetic"), workload["projectId"],
                             new_id("run"), workload, {}, key="synthetic")
    return SimpleNamespace(state=state, prepare=prepare, reader=reader, workload=workload, channels=channels)


def test_remote_prepare_binds_provenance_to_approval_digest_outside_transaction(preparing):
    a = preparing
    result = a.prepare()
    assert a.state.scopes == 2 and len(a.state.inserts) == 1
    args = a.state.inserts[0]
    raw, records = args[7], args[8].obj
    _, files = decode_snapshot(raw, a.workload["workspaceId"])
    assert files[SOURCE_FILE] == source_content(records)
    assert result["workload"]["modelInput"]["inputSha256"] == hashlib.sha256(raw).hexdigest()
    altered = deepcopy(result["workload"])
    altered["modelInput"]["inputSha256"] = "0" * 64
    assert action_digest(altered) != action_digest(result["workload"])
    assert result["requiresApproval"]


@pytest.mark.parametrize("fault", ["channel", "location", "scope-denied", "receipt"])
def test_mutation_during_network_io_cannot_commit(preparing, monkeypatch, fault):
    a = preparing
    original = a.reader.read
    def read(*args, **kwargs):
        result = original(*args, **kwargs)
        capture = list(a.state.captured)
        if fault == "channel":
            capture[4] = (replace(capture[4][0], version=2),)
        elif fault == "location":
            capture[3] = (replace(capture[3][0], location_version=2),) + capture[3][1:]
        elif fault == "receipt":
            return replace(result, channels=(replace(result.channels[0], version=2),))
        else:
            raise DomainError("AUTH-0011", "Synthetic revoked grant", 403)
        a.state.captured = tuple(capture)
        return result
    monkeypatch.setattr(a.reader, "read", read)
    with pytest.raises(DomainError):
        a.prepare()
    assert not a.state.inserts


@pytest.mark.parametrize("fault", [None, "rotated", "revoked", "location", "downgrade", "approval-current", "approval-revoked"])
def test_admission_rechecks_remote_authority_before_returning_bytes(preparing, monkeypatch, fault):
    a = preparing
    frozen = a.prepare()["workload"]
    args = a.state.inserts[0]
    row = dict(zip(("tenant_id", "project_id", "run_id", "input_id", "recovery_epoch",
                    "requester_id", "workload", "snapshot", "locations"), args))
    row["workload"], row["locations"] = row["workload"].obj, row["locations"].obj
    _, binding, body, locations, channels = a.state.captured
    binding = {**binding, "input": {"leases": []}}
    conn = SimpleNamespace(execute=lambda *a: SimpleNamespace(fetchone=lambda: row))
    monkeypatch.setattr("inv.model_runtime.require_model_reference", lambda *a: None)
    monkeypatch.setattr("inv.model_runtime.bound_input", lambda *a: binding)
    monkeypatch.setattr("inv.model_runtime.manifest", lambda *a: body)
    monkeypatch.setattr("inv.model_runtime._capture", lambda *a: (
        (replace(locations[0], location_version=2),) + locations[1:] if fault == "location" else locations))
    checked = []
    def current(*args):
        checked.append(True)
        if fault == "revoked":
            raise DomainError("NODE-0033", "Synthetic revoked channel", 403)
        return (replace(channels[0], version=2),) if fault == "rotated" else channels
    monkeypatch.setattr("inv.model_runtime.capture_channels", current)
    monkeypatch.setattr("inv.model_runtime.permission", lambda *a, **k: None)
    def approval_channel(conn, channel):
        checked.append(True)
        if fault == "approval-revoked":
            raise DomainError("NODE-0033", "Synthetic revoked channel", 403)
        assert channel == channels[0]
    monkeypatch.setattr("inv.model_runtime.assert_channel", approval_channel)
    if fault == "downgrade":
        for location in row["locations"]: del location["channel"]
    def admit():
        return approved_model(conn, {"run_id": args[2]}, frozen, args[4],
                              node_id=None if fault in {"approval-current", "approval-revoked"} else binding["node_id"],
                              proofs={}, database=object())
    if fault and fault != "approval-current":
        with pytest.raises(DomainError): admit()
    else:
        assert base64.b64decode(admit()["dataBase64"]) == args[7]
        assert checked == [True]


@pytest.mark.parametrize("fault", [None, "missing", "tenant", "epoch", "disabled", "expired"])
def test_channel_capture_checks_scope_enabled_and_expiry(remote, fault):
    from dataclasses import asdict
    from datetime import datetime, timedelta, timezone
    _, _, locations, channels, _, _ = remote
    channel = channels[0]
    now = datetime.now(timezone.utc)
    row = dict(asdict(channel), enabled=True, certificate_not_after=now + timedelta(minutes=1))
    if fault == "tenant": row["tenant_id"] = str(uuid4())
    if fault == "epoch": row["recovery_epoch"] = str(uuid4())
    if fault == "disabled": row["enabled"] = False
    if fault == "expired": row["certificate_not_after"] = now
    statements = []
    def execute(sql, args=()):
        statements.append(sql)
        answer = {"now": now} if "clock_timestamp" in sql else None if fault == "missing" else row
        return SimpleNamespace(fetchone=lambda: answer)
    conn = SimpleNamespace(execute=execute)
    def capture():
        return capture_channels(conn, channel.tenant_id, channel.recovery_epoch, locations)
    if fault:
        with pytest.raises(DomainError): capture()
    else:
        assert capture() == channels
    assert "FOR SHARE" in statements[0]  # SQL intent only; real locks need PG.
