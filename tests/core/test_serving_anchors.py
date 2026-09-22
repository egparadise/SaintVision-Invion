"""Serving-anchor tests: prove each bound kernel response's SERVING function actually invokes the
contract validator, so removing the anchor breaks a test (bucket 2 -> bucket 1 in the serving-anchor
audit). Complements the fixture<->schema tests (which prove the validator rejects bad shapes) by
proving the serving path reaches the validator. Modeled on Codex's
test_shard_runtime_status_is_anchored_before_serving.

Mechanism: monkeypatch the module's anchor (`_checked` for result_view, `validate_contract` for the
others) with a recorder that captures the contract name and returns the value, drive the serving
function to the anchor with minimal stubs, and assert the RESPONSE contract name was recorded. If the
serving code drops or renames its anchor call, the name is absent and the test fails (proven by
removing the anchor on a sample -- see the review doc).
"""
import datetime as _dt
import base64
import uuid
from types import SimpleNamespace

import pytest

from inv import model_view as mv_mod
from inv import result_view as rv_mod
from inv import storage_view as sv_mod
from inv import workspace_editor as we_mod
from inv.errors import DomainError
from inv.model_view import ModelCommitObservation
from inv.result_view import ResultView
from inv.storage_view import StorageObservationView
from inv.workspace_editor import WorkspaceEditor


class _Cursor:
    def __init__(self, one=None, many=None):
        self._one, self._many = one, many

    def fetchone(self):
        return self._one

    def fetchall(self):
        return [] if self._many is None else self._many


class _Conn:
    def __init__(self, one=None, many=None):
        self._one, self._many = one, many

    def execute(self, *_a, **_k):
        return _Cursor(self._one, self._many)


class _QConn:
    """Connection returning queued fetchone results in order (multi-query serving paths)."""

    def __init__(self, ones):
        self._ones = list(ones)

    def execute(self, *_a, **_k):
        return _Cursor(one=self._ones.pop(0) if self._ones else None)


class _CM:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self._conn

    def __exit__(self, *_a):
        return False


class _DB:
    def __init__(self, conn=None):
        self._conn = conn or _Conn()

    def transaction(self, _tenant):
        return _CM(self._conn)


class _Principal:
    tenant_id = uuid.UUID("00000000-0000-4000-8000-000000000001")
    subject_id = "usr_test"


def _record_checked(monkeypatch):
    rec = []
    monkeypatch.setattr(rv_mod, "_checked", lambda name, value: (rec.append(name), value)[1])
    return rec


def _stub_scope(monkeypatch, run):
    monkeypatch.setattr(ResultView, "_scope", lambda self, conn, principal, project, run_id: run)
    monkeypatch.setattr(ResultView, "_current", staticmethod(lambda conn, run: None))
    monkeypatch.setattr(ResultView, "_output", staticmethod(lambda row: None))


_RUN = {"project_id": "prj_x", "state": "succeeded", "version": 1, "attempt": 1, "updated_at": _dt.datetime(2026, 9, 22, tzinfo=_dt.timezone.utc)}


def test_result_view_result_anchors_run_result_view(monkeypatch):
    rec = _record_checked(monkeypatch)
    _stub_scope(monkeypatch, _RUN)
    ResultView(_DB()).result(_Principal(), "run_x")
    assert "RunResultView" in rec


def test_result_view_artifacts_anchors_run_artifact_list(monkeypatch):
    rec = _record_checked(monkeypatch)
    _stub_scope(monkeypatch, _RUN)
    monkeypatch.setattr(ResultView, "_files", staticmethod(lambda row, artifact: None))
    ResultView(_DB()).artifacts(_Principal(), "run_x")
    assert "RunArtifactList" in rec


def test_result_view_logs_anchors_run_log_view(monkeypatch):
    rec = _record_checked(monkeypatch)
    _stub_scope(monkeypatch, _RUN)
    ResultView(_DB()).logs(_Principal(), "run_x")
    assert "RunLogView" in rec


def test_result_view_attempts_anchors_run_attempt_list(monkeypatch):
    rec = _record_checked(monkeypatch)
    _stub_scope(monkeypatch, _RUN)
    ResultView(_DB(_Conn(many=[]))).attempts(_Principal(), "run_x")
    assert "RunAttemptList" in rec


def test_workspace_editor_view_anchors_workspace_edit_view(monkeypatch):
    rec = []
    monkeypatch.setattr(we_mod, "validate_contract", lambda name, value=None: rec.append(name))
    WorkspaceEditor._view(str(uuid.uuid4()), 1, b"{}")
    assert "WorkspaceEditView" in rec


def test_model_view_get_anchors_model_commit_observation(monkeypatch):
    # model_view.get is guarded by grant/permission/manifest-consistency; stub those to reach the anchor.
    rec = []
    monkeypatch.setattr(mv_mod, "validate_contract", lambda name, value=None: rec.append(name))
    monkeypatch.setattr(mv_mod, "permission", lambda *a, **k: {"userId": "u"})

    class _Grant:
        def __init__(self, _db):
            pass

        def _grant(self, *a, **k):
            return None

    monkeypatch.setattr(mv_mod, "ApprovalStore", _Grant)
    body = {
        "modelId": "mdl_x", "version": "1.0.0", "format": "safetensors",
        "totalBytes": 1, "shards": [{}], "licensePolicy": "apache-2.0", "classification": "internal",
    }
    monkeypatch.setattr(mv_mod, "manifest_copy", lambda manifest: body)
    row = {
        "manifest": {},
        "manifest_sha256": mv_mod.hashlib.sha256(mv_mod.canonical(body)).hexdigest(),
        "source_run_id": "run_x", "committed_at": _dt.datetime(2026, 9, 21), "recovery_epoch": uuid.uuid4(),
    }
    ModelCommitObservation(_DB(_QConn([row]))).get(_Principal(), "prj_x", "mdl_x", "1.0.0")
    assert "ModelCommitObservation" in rec


class _FakeChallenge:
    def __init__(self, tid, project, run_id, contribution_id):
        self.expires_at = 9999999999
        self.issued_at = 0
        self.project_id = project
        self.run_id = run_id
        self.contribution_id = contribution_id

        class _Ch:
            tenant_id = tid

        self.channel = _Ch()

    def validate(self, _issued_at):
        return None

    def digest(self):
        return "sha"


def test_storage_view_result_anchors_storage_observation_view(monkeypatch):
    # storage_view.result is guarded by grant/permission/challenge crypto; stub those and let the final
    # consumption row be absent (observation None) to reach the anchor.
    rec = []
    monkeypatch.setattr(sv_mod, "validate_contract", lambda name, value=None: rec.append(name))
    monkeypatch.setattr(sv_mod, "permission", lambda *a, **k: {"userId": "u"})

    class _Grant:
        def __init__(self, _db):
            pass

        def _grant(self, *a, **k):
            return None

    monkeypatch.setattr(sv_mod, "ApprovalStore", _Grant)
    p = _Principal()
    monkeypatch.setattr(
        sv_mod, "decode_challenge", lambda _c: _FakeChallenge(p.tenant_id, "prj_x", "run_x", "stc_x")
    )
    req = str(uuid.uuid4())
    run = {"run_id": "run_x"}
    pending = {
        "project_id": "prj_x", "run_id": "run_x", "subject_id": p.subject_id,
        "contribution_id": "stc_x", "challenge": b"c", "challenge_sha256": "sha",
        "created_at": _dt.datetime(2026, 9, 21),
    }
    root = {"registered_by_user_id": "u"}
    now = {"now": 1.0}
    StorageObservationView(_DB(_QConn([run, pending, root, now, None]))).result(
        p, "prj_x", "run_x", req
    )
    assert "StorageObservationView" in rec


def test_storage_view_rejects_invalid_evidence_envelope_at_serving_anchor(monkeypatch):
    """The stored-envelope verification branch must execute the real contract validator."""
    p = _Principal()
    checked_at = _dt.datetime(2026, 9, 22, tzinfo=_dt.timezone.utc)
    certificate = base64.b64encode(b"synthetic-certificate").decode()
    detail = {
        "scope": "node-storage-sample-v1",
        "requestId": "req_x",
        "evidenceId": "evd_x",
        "challenge": {},
        "certificateDer": certificate,
        "unverifiable": 0,
        "examined": 1,
        "unsampled": 0,
        "cataloguedAtIssue": 1,
        "operationalAcceptanceAssessed": False,
        "envelope": {"payload": "cA==", "signature": "cw=="},
    }
    pending = {
        "run_id": "run_x",
        "contribution_id": "stc_x",
        "request_id": "req_x",
        "subject_id": p.subject_id,
        "challenge": {},
    }
    response_hash = sv_mod.hashlib.sha256(
        sv_mod.canonical({"envelope": detail["envelope"], "certificate": certificate})
    ).hexdigest()
    row = {
        "checked_at": checked_at,
        "response_sha256": response_hash,
        "evidence_run": "run_x",
        "envelope": {"result": "not-a-result"},
        "contribution_id": "stc_x",
        "evidence_id": "evd_x",
        "check_id": "chk_x",
        "detail": detail,
        "reachable": True,
        "healthy": True,
        "sampled_count": 1,
        "mismatch_count": 0,
    }
    challenge = SimpleNamespace(catalogued=1, digest=lambda: "challenge-digest")
    verified = SimpleNamespace(
        sampled=1,
        mismatches=0,
        unverifiable=0,
        examined=1,
        unsampled=0,
        sample_healthy=True,
        observed_at=int(checked_at.timestamp()),
        payload_sha256="a" * 64,
    )
    monkeypatch.setattr(sv_mod, "verify_sample", lambda *a, **k: verified)
    original = sv_mod.validate_contract
    calls = []

    def record_and_validate(name, value=None):
        calls.append(name)
        return original(name, value)

    monkeypatch.setattr(sv_mod, "validate_contract", record_and_validate)
    with pytest.raises(DomainError, match="VERIFY-0032"):
        sv_mod.StorageObservationView._verified(p, pending, challenge, row, int(checked_at.timestamp()))
    assert "EvidenceEnvelope" in calls
