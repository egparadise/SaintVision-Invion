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


def _output_provider(config):
    """Select exactly one legacy-local or canonical API-configured provider."""

    from .object_store import LocalObjects

    local = LocalObjects(config["outputRoot"]) if config.get("outputRoot") else None
    api_config_path = os.environ.get("INV_API_CONFIG")
    if not api_config_path:
        return local
    api_settings = strict_object(trusted_file(api_config_path))
    readiness = api_settings.get("configurationReadiness")
    from .configuration_readiness import configured_s01_readiness

    # Validate the same strict nested surface even when this worker ultimately
    # remains on the rollout-compatible Local provider.
    configured_s01_readiness(readiness)
    remote = None
    if isinstance(readiness, dict) and "objectStore" in readiness:
        from .object_store_config import (
            configured_object_store,
            parse_object_store_configuration,
            unresolved_object_store,
        )

        parsed = parse_object_store_configuration(readiness["objectStore"])
        if unresolved_object_store(parsed):
            raise ValueError("ObjectStore configuration is not ready")
        remote = configured_object_store(parsed)
    if local is not None and remote is not None:
        raise ValueError("Duplicate legacy and objectStore providers")
    return remote or local


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    try:
        config = strict_object(trusted_file(os.environ["INV_WORKER_CONFIG"]))
        if not {"tenantId", "tls"} <= set(config) or set(config) - {
            "tenantId",
            "tls",
            "outputRoot",
        }:
            raise ValueError()
        tenant = str(UUID(config["tenantId"]))
        db = Database(
            os.environ["INV_RUNTIME_DSN"],
            recovery_epoch=os.environ["INV_RECOVERY_EPOCH"],
        )
        delivery = NodeDelivery(db, NodeTLSClient(**config["tls"]))
        output_provider = _output_provider(config)
        # Migrations and tenant/epoch privileges are checked before serving work.
        with db.transaction(tenant) as conn:
            conn.execute("SELECT command_id FROM inv.execution_deliveries LIMIT 0")
    except Exception:
        raise SystemExit("Explicit delivery worker configuration unavailable") from None
    worker = DeliveryWorker(db, delivery, output_provider=output_provider)
    if args.once:
        try:
            print(worker.once(tenant))
        except Exception:
            raise SystemExit("Delivery worker temporarily unavailable") from None
        return
    stop = Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    def consume(control_only=False):
        while not stop.is_set():
            try:
                outcome = worker.once(tenant, control_only=control_only)
            except Exception:
                outcome = "unavailable"
            # No raw exception, request, permit, identity token or key is logged.
            stop.wait(0.1 if outcome == "stopped" else 1.0)

    # Five bounded control lanes remain available when execution lanes block in
    # network I/O. They can only cancel, never reserve another execution. Queue
    # leases coordinate all lanes and additional worker processes.
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = [executor.submit(consume) for _ in range(2)]
        futures += [executor.submit(consume, True) for _ in range(5)]
        for future in futures:
            future.result()


if __name__ == "__main__":
    main()
