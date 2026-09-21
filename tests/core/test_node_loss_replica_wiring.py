"""The liveness product path must hand node loss to replica repair."""

import datetime as dt
import uuid
from types import SimpleNamespace

from saintvision.services import nodes


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Session:
    def __init__(self, rows):
        self.rows = rows
        self.flushed = False

    def scalars(self, _query):
        return _Rows(self.rows)

    def flush(self):
        self.flushed = True


def test_liveness_sweep_invokes_replica_repair_for_each_departed_node(monkeypatch):
    tenant = uuid.uuid4()
    node = SimpleNamespace(
        node_id="node-lost",
        status="active",
        enrolled_at=dt.datetime(2026, 9, 22, tzinfo=dt.timezone.utc)
        - dt.timedelta(minutes=2),
        last_heartbeat_at=None,
    )
    session = _Session([node])
    calls = []

    monkeypatch.setattr(
        nodes,
        "select",
        lambda *_args, **_kwargs: SimpleNamespace(where=lambda *_a, **_k: None),
    )
    monkeypatch.setattr(
        "saintvision.services.replica_repair.mark_node_replicas_unavailable",
        lambda *args, **kwargs: calls.append(kwargs) or 1,
    )

    changed = nodes.mark_lost_nodes(
        session,
        tenant_id=tenant,
        now=dt.datetime(2026, 9, 22, 1, 0, tzinfo=dt.timezone.utc),
        timeout_seconds=60,
    )

    assert changed == 1
    assert node.status == "lost"
    assert calls == [
        {
            "tenant_id": tenant,
            "node_id": "node-lost",
            "now": dt.datetime(2026, 9, 22, 1, 0, tzinfo=dt.timezone.utc),
        }
    ]
    assert session.flushed
