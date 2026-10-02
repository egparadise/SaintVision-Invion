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

from .build_execution import PRODUCT_ENABLE_SETTING, PRODUCT_ENABLE_VALUE
from .db import Database
from .dispatch import DeliveryWorker
from .identity import strict_object, trusted_file
from .node_transport import NodeDelivery, NodeTLSClient

WORKER_KEYS = frozenset({"tenantId", "tls", "outputRoot", "buildExecution"})
TLS_KEYS = frozenset({"ca_file", "certificate_file", "key_file", "timeout"})
BUILD_EXECUTION_KEYS = frozenset(
    {
        "buildctlPath",
        "address",
        "sourceRoot",
        "referenceHealthReceipt",
        "productReceiptDirectory",
        "builderInstanceId",
        "builderProfileId",
        "providerRecoveryEpoch",
        "nodeId",
    }
)


def validated_worker_configuration(value):
    """Return a strict worker document without constructing transports."""

    config = strict_object(value)
    if not {"tenantId", "tls"} <= set(config) or set(config) - WORKER_KEYS:
        raise ValueError("Exact worker configuration required")
    tenant = str(UUID(config["tenantId"]))
    if tenant != config["tenantId"]:
        raise ValueError("Canonical worker tenantId required")
    tls = config["tls"]
    if not isinstance(tls, dict):
        raise ValueError("Exact worker TLS configuration required")
    if not {"ca_file", "certificate_file", "key_file"} <= set(tls) or set(tls) - TLS_KEYS:
        raise ValueError("Exact worker TLS configuration required")
    if any(
        not isinstance(tls[name], str) or not tls[name]
        for name in ("ca_file", "certificate_file", "key_file")
    ):
        raise ValueError("Worker TLS paths must be non-empty strings")
    if "timeout" in tls and (
        type(tls["timeout"]) not in (int, float) or not 0.1 <= tls["timeout"] <= 40
    ):
        raise ValueError("Worker TLS timeout out of range")
    if "outputRoot" in config and (
        not isinstance(config["outputRoot"], str) or not config["outputRoot"]
    ):
        raise ValueError("Worker outputRoot must be a non-empty string")
    if "buildExecution" in config:
        build = config["buildExecution"]
        if not isinstance(build, dict):
            raise ValueError("Exact build execution configuration required")
        if set(build) != BUILD_EXECUTION_KEYS or any(
            not isinstance(build[name], str) or not build[name]
            for name in BUILD_EXECUTION_KEYS - {"providerRecoveryEpoch"}
        ):
            raise ValueError("Exact build execution configuration required")
        if type(build["providerRecoveryEpoch"]) is not int or build["providerRecoveryEpoch"] < 1:
            raise ValueError("Measured provider recovery epoch required")
    return config


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
        config = validated_worker_configuration(trusted_file(os.environ["INV_WORKER_CONFIG"]))
        tenant = config["tenantId"]
        db = Database(
            os.environ["INV_RUNTIME_DSN"],
            recovery_epoch=os.environ["INV_RECOVERY_EPOCH"],
        )
        delivery = NodeDelivery(db, NodeTLSClient(**config["tls"]))
        output_provider = _output_provider(config)
        # Migrations and tenant/epoch privileges are checked before serving work.
        with db.transaction(tenant) as conn:
            conn.execute("SELECT command_id FROM inv.execution_deliveries LIMIT 0")
        build_runtime = None
        if os.environ.get(PRODUCT_ENABLE_SETTING) == PRODUCT_ENABLE_VALUE:
            from .build_product_runtime import configured_tenant_product_runtime

            if "buildExecution" not in config:
                raise ValueError("Build execution configuration unavailable")
            build_runtime = configured_tenant_product_runtime(
                db,
                tenant,
                config["buildExecution"],
                tls=config["tls"],
                environment=os.environ,
            )
    except Exception:
        raise SystemExit("Explicit delivery worker configuration unavailable") from None
    worker = DeliveryWorker(db, delivery, output_provider=output_provider)
    if args.once:
        try:
            if build_runtime is not None:
                build_runtime.once(tenant)
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

    def consume_builds():
        while not stop.is_set():
            try:
                outcome = build_runtime.once(tenant)
            except Exception:
                outcome = "unavailable"
            stop.wait(0.1 if outcome not in (None, "unavailable") else 1.0)

    # Five bounded control lanes remain available when execution lanes block in
    # network I/O. They can only cancel, never reserve another execution. Queue
    # leases coordinate all lanes and additional worker processes.
    with ThreadPoolExecutor(max_workers=8 if build_runtime is not None else 7) as executor:
        futures = [executor.submit(consume) for _ in range(2)]
        futures += [executor.submit(consume, True) for _ in range(5)]
        if build_runtime is not None:
            futures.append(executor.submit(consume_builds))
        for future in futures:
            future.result()


if __name__ == "__main__":
    main()
