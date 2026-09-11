"""Explicit five-node pilot observation loop; liveness never returns a Lease."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import os
import signal
from threading import Event
from uuid import UUID
from .db import Database
from .identity import strict_object, trusted_file
from .node_transport import NodeTLSClient
from .observation import NodeObservation
from .tooling import NodePrincipal


class ObservationWorker:
    def __init__(self, database, client):
        self.db, self.observer = database, NodeObservation(database, client)

    def once(self, tenant):
        self.observer.mark_offline(tenant)
        with self.db.transaction(tenant) as conn:
            rows = conn.execute(
                "SELECT node_id FROM inv.node_channels WHERE enabled AND recovery_epoch=%s::uuid ORDER BY node_id LIMIT 6",
                (self.db.recovery_epoch,),
            ).fetchall()
        if len(rows) > 5:
            raise ValueError("Explicit pilot observer supports at most five nodes")

        def poll(row):
            try:
                self.observer.poll_resources(NodePrincipal(tenant, row["node_id"]))
                return True
            except Exception:
                return False

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(poll, rows))
        self.observer.mark_offline(tenant)
        return {"observed": sum(results), "unavailable": len(results) - sum(results)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    try:
        config = strict_object(trusted_file(os.environ["INV_OBSERVER_CONFIG"]))
        if set(config) != {"tenantId", "tls"}:
            raise ValueError()
        tenant = str(UUID(config["tenantId"]))
        tls = dict(config["tls"])
        tls["timeout"] = 5
        db = Database(
            os.environ["INV_RUNTIME_DSN"],
            recovery_epoch=os.environ["INV_RECOVERY_EPOCH"],
        )
        worker = ObservationWorker(db, NodeTLSClient(**tls))
        with db.transaction(tenant) as conn:
            conn.execute("SELECT node_id FROM inv.node_resource_snapshots LIMIT 0")
    except Exception:
        raise SystemExit("Explicit observer configuration unavailable") from None
    if args.once:
        try:
            print(worker.once(tenant))
        except Exception:
            raise SystemExit("Observation temporarily unavailable") from None
        return
    stop = Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        try:
            worker.once(tenant)
        except Exception:
            pass
        stop.wait(5)


if __name__ == "__main__":
    main()
