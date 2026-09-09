"""Explicit operator-configured delivery service. Bounded threads and I/O.

No tenant discovery, signing-key fallback, public queue API or diagnostic payload
logging. SIGTERM waits for the existing bounded mTLS calls, without re-execution.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import os
import signal
from threading import Event
from uuid import UUID
from .db import Database
from .dispatch import DeliveryWorker
from .identity import strict_object, trusted_file
from .node_transport import NodeDelivery, NodeTLSClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    try:
        config = strict_object(trusted_file(os.environ["INV_WORKER_CONFIG"]))
        if set(config) != {"tenantId", "tls"}:
            raise ValueError()
        tenant = str(UUID(config["tenantId"]))
        db = Database(
            os.environ["INV_RUNTIME_DSN"],
            recovery_epoch=os.environ["INV_RECOVERY_EPOCH"],
        )
        delivery = NodeDelivery(db, NodeTLSClient(**config["tls"]))
        # Migrations and tenant/epoch privileges are checked before serving work.
        with db.transaction(tenant) as conn:
            conn.execute("SELECT command_id FROM inv.execution_deliveries LIMIT 0")
    except Exception:
        raise SystemExit("Explicit delivery worker configuration unavailable") from None
    worker = DeliveryWorker(db, delivery)
    if args.once:
        try:
            print(worker.once(tenant))
        except Exception:
            raise SystemExit("Delivery worker temporarily unavailable") from None
        return
    stop = Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    def consume():
        while not stop.is_set():
            try:
                outcome = worker.once(tenant)
            except Exception:
                outcome = "unavailable"
            # No raw exception, request, permit, identity token or key is logged.
            stop.wait(0.1 if outcome == "stopped" else 1.0)

    # A second worker can claim the cancellation control operation while the
    # first waits on an active execution. Both obey the durable DB protocol.
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(consume) for _ in range(2)]
        for future in futures:
            future.result()


if __name__ == "__main__":
    main()
