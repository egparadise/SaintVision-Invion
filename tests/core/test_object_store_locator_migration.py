"""PG-free migration/replay guards for immutable ObjectStore identity."""

import hashlib
import json
from pathlib import Path
from uuid import UUID

import pytest

from inv.errors import DomainError
from inv.snapshots import attach_checkpoint, checkpoint_content, checkpoint_digest
from tools.migration_graph import chain


ROOT = Path(__file__).resolve().parents[2]
OBJECT = "22222222-2222-4222-8222-222222222222"


def _row(provider="local-bounded-v1"):
    return {
        "object_id": UUID(OBJECT),
        "content_hash": "a" * 64,
        "size_bytes": 17,
        "provider_id": provider,
        "locator": "not-public",
    }


def test_existing_local_checkpoint_content_and_digest_are_byte_for_byte_stable():
    expected = {
        "objectId": OBJECT,
        "sha256": "a" * 64,
        "sizeBytes": 17,
        "provider": "local-bounded-v1",
    }
    content = checkpoint_content(_row())
    old_digest = hashlib.sha256(
        json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert content == expected
    assert checkpoint_digest(content) == old_digest


def test_same_provider_replay_is_stable_and_provider_change_conflicts_identity():
    first = checkpoint_content(_row())
    same = checkpoint_content(_row())
    changed = checkpoint_content(_row("s3-compatible-v1"))
    assert checkpoint_digest(first) == checkpoint_digest(same)
    assert checkpoint_digest(first) != checkpoint_digest(changed)
    assert set(first) == {"objectId", "sha256", "sizeBytes", "provider"}


def test_both_checkpoint_producers_use_the_persisted_provider_helper():
    snapshots = (ROOT / "services/control-plane/src/inv/snapshots.py").read_text(encoding="utf-8")
    workspace = (ROOT / "services/control-plane/src/inv/workspace_resume.py").read_text(
        encoding="utf-8"
    )
    assert "content = checkpoint_content(row)" in snapshots
    assert "content = checkpoint_content(obj)" in workspace
    assert "return attach_checkpoint(" in snapshots
    assert "attach_checkpoint(" in workspace
    assert '"provider": "local-bounded-v1"' not in snapshots
    assert '"provider": "local-bounded-v1"' not in workspace


class _Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class _Conn:
    def __init__(self, prior=None):
        self.prior = prior
        self.statements = []

    def execute(self, statement, params):
        self.statements.append((statement, params))
        if statement.startswith("SELECT content_hash FROM inv.checkpoints"):
            return _Result(
                None if self.prior is None else {"content_hash": self.prior}
            )
        return _Result()


def _attach(conn, monkeypatch, content):
    emitted = []
    monkeypatch.setattr(
        "inv.snapshots.event", lambda *args: emitted.append(args[3:])
    )
    result = attach_checkpoint(
        conn,
        tenant="11111111-1111-4111-8111-111111111111",
        project="prj_test",
        run_id="run_test",
        attempt=1,
        step_id="step-1",
        object_id=OBJECT,
        content=content,
        event_name="inv.test.checkpoint",
        event_payload=lambda value: {"contentHash": value},
    )
    return result, emitted


def test_checkpoint_first_publish_inserts_content_pin_and_one_event(monkeypatch):
    content = checkpoint_content(_row())
    conn = _Conn()
    result, emitted = _attach(conn, monkeypatch, content)
    sql = [statement for statement, _ in conn.statements]
    assert result == content
    assert sum(statement.startswith("INSERT INTO inv.checkpoints") for statement in sql) == 1
    assert sum(statement.startswith("INSERT INTO inv.checkpoint_objects") for statement in sql) == 1
    assert emitted == [("inv.test.checkpoint", {"contentHash": checkpoint_digest(content)})]


def test_checkpoint_same_provider_replay_is_quiet_and_keeps_pin_idempotent(monkeypatch):
    content = checkpoint_content(_row())
    conn = _Conn(checkpoint_digest(content))
    result, emitted = _attach(conn, monkeypatch, content)
    sql = [statement for statement, _ in conn.statements]
    assert result == content
    assert not any(statement.startswith("INSERT INTO inv.checkpoints") for statement in sql)
    assert sum(statement.startswith("INSERT INTO inv.checkpoint_objects") for statement in sql) == 1
    assert "ON CONFLICT DO NOTHING" in sql[-1]
    assert emitted == []


def test_checkpoint_provider_change_is_graph_conflict_without_write_or_event(monkeypatch):
    local = checkpoint_content(_row())
    s3 = checkpoint_content(_row("s3-compatible-v1"))
    conn = _Conn(checkpoint_digest(local))
    with pytest.raises(DomainError, match="GRAPH-0004"):
        _attach(conn, monkeypatch, s3)
    assert len(conn.statements) == 1


def test_migration_backfills_exact_local_locator_and_makes_it_immutable():
    sql = (
        ROOT / "services/control-plane/src/inv/migrations/0026_object_store_locator.sql"
    ).read_text(encoding="utf-8")
    assert "provider_id = 'local-bounded-v1'" in sql
    assert "locator = 'obj-' || replace(object_id::text, '-', '')" in sql
    assert "NEW.provider_id,NEW.locator" in sql
    assert "OLD.provider_id,OLD.locator" in sql
    assert "UNIQUE(provider_id, locator)" in sql
    assert "ALTER COLUMN provider_id SET NOT NULL" in sql
    assert "ALTER COLUMN locator SET NOT NULL" in sql


def test_object_store_locator_revision_is_irreversible_and_the_chain_has_one_head():
    """0048 was the head when this file was written; the coordinator's fixed order
    0047 -> 0048 -> 0049 -> 0050 -> 0051 -> 0052 -> 0053 -> 0054 has since put the MLflow mirror (PR #172), the
    dataset digest index (PR #174), the service credentials (PR #176), the model
    version digest scope (PR for #191 F1), the eval-suite project scope (W5,
    0053) and the model version measurements (W3 seam, 0054) above it. The
    properties of 0048 are
    unchanged and the chain still has exactly one head."""
    revisions = chain()
    locator = next(r for r in revisions if r.revision == "0048_object_store_locator")
    assert locator.down_revision == "0047_audit_events_isolation"
    assert locator.irreversible is True
    assert locator.recovery_note and "restore" in locator.recovery_note.lower()
    mirror = next(r for r in revisions if r.revision == "0049_mlflow_mirror")
    assert mirror.down_revision == "0048_object_store_locator"
    digest_index = next(r for r in revisions if r.revision == "0050_dataset_digest_lookup")
    assert digest_index.down_revision == "0049_mlflow_mirror"
    credentials = next(r for r in revisions if r.revision == "0051_service_credentials")
    assert credentials.down_revision == "0050_dataset_digest_lookup"
    head = revisions[-1]
    digest_scope = next(r for r in revisions if r.revision == "0052_model_version_digest_scope")
    assert digest_scope.down_revision == "0051_service_credentials"      # #191 F1, above 0051 (PR #176)
    # Narrowing the digest scope cannot be undone; the refusal says why.
    assert digest_scope.irreversible is True
    assert digest_scope.recovery_note and "forward fix" in digest_scope.recovery_note.lower()
    eval_scope = next(r for r in revisions if r.revision == "0053_eval_suite_project_scope")
    assert eval_scope.down_revision == "0052_model_version_digest_scope"   # W5 (G-04·G-05 §5-1), above 0052
    measurements = next(r for r in revisions if r.revision == "0054_model_version_measurements")
    assert measurements.down_revision == "0053_eval_suite_project_scope"   # W3 seam (#209 v1.1), above 0053
    assert head.revision == "0061_build_preparations"
    assert head.down_revision == "0060_build_execution_admissions"


def test_definer_policy_tracks_object_store_locator_head_without_catalog_drift():
    policy = json.loads(
        (ROOT / "tools/definer-policy.json").read_text(encoding="utf-8")
    )
    assert policy["revision"] == chain()[-1].revision == "0061_build_preparations"
