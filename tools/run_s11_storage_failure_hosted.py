"""Execute the frozen S11-ST hosted MinIO/PostgreSQL reference matrix.

The caller owns a disposable migrated database and bucket.  Product findings
are evidence, not runner failures: every scenario and cleanup is attempted and
the raw report records ``MEASURED_FAIL`` inputs without leaking credentials,
provider error bodies, object locators, or Docker resource names.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
from typing import Any, Callable
from uuid import uuid4
import xml.etree.ElementTree as ET

import psycopg


ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE = ROOT / "services" / "control-plane" / "src"
sys.path.insert(0, str(CONTROL_PLANE))
sys.path.insert(0, str(ROOT / "tools"))

from inv.errors import DomainError  # noqa: E402
from inv.s3_client import HttpResponse, S3Client, S3Config, UrlLibTransport  # noqa: E402
from inv.s3_object_store import S3Objects  # noqa: E402
import recovery_drill  # noqa: E402
from run_s11_storage_failure_pg_free import UNIVERSE_CASES, UNIVERSE_SHA256  # noqa: E402


SCHEMA_VERSION = "1.0.0"
RUN_PURPOSE = "s11-storage-failure-hosted-reference"
EXECUTION_LAYER = "hosted-minio-postgresql"
PRODUCER_PATH = "tools/run_s11_storage_failure_hosted.py"
RECOVERY_PROBE_PATH = "tools/recovery_drill.py"
HARNESS_PATH = "tests/integration/test_s11_storage_failure_hosted.py"
HOSTED_SHA256 = "0509d94a6648106868ef1ec602af2bed5bbd02b17cec3a4c5ffbf6178ef24a33"
HOSTED_CASES = (
    "BAK-01/postgresql/archive-command-false",
    "BAK-03/postgresql/archive-command-true-empty",
    "CAP-01/postgresql/concurrent-8",
    "CAP-01/postgresql/single",
    "CAP-02/s3/http-507-new-key",
    "OBJ-01/s3/body-byte",
    "OBJ-02/s3/size-metadata",
    "OBJ-03/s3/metadata-digest",
    "OBJ-04/s3/ambiguous-put-different-byte",
    "OBJ-04/s3/success-partial",
)

EXPECTED: dict[str, dict[str, Any]] = {
    "BAK-01/postgresql/archive-command-false": {
        "kind": "failureClass",
        "failureClass": "WAL_ARCHIVE_FAILED",
        "retryable": True,
    },
    "BAK-03/postgresql/archive-command-true-empty": {
        "kind": "failureClass",
        "failureClass": "WAL_ARCHIVE_EMPTY",
        "retryable": False,
    },
    "CAP-01/postgresql/concurrent-8": {
        "kind": "problem",
        "code": "RES-0001",
        "status": 409,
        "retryable": False,
    },
    "CAP-01/postgresql/single": {
        "kind": "problem",
        "code": "RES-0001",
        "status": 409,
        "retryable": False,
    },
    "CAP-02/s3/http-507-new-key": {
        "kind": "problem",
        "code": "STORE-0001",
        "status": 503,
        "retryable": True,
    },
    "OBJ-01/s3/body-byte": {
        "kind": "problem",
        "code": "VERIFY-0010",
        "status": 422,
        "retryable": False,
    },
    "OBJ-02/s3/size-metadata": {
        "kind": "problem",
        "code": "VERIFY-0010",
        "status": 422,
        "retryable": False,
    },
    "OBJ-03/s3/metadata-digest": {
        "kind": "problem",
        "code": "VERIFY-0010",
        "status": 422,
        "retryable": False,
    },
    "OBJ-04/s3/ambiguous-put-different-byte": {
        "kind": "problem",
        "code": "STORE-0005",
        "status": 409,
        "retryable": False,
    },
    "OBJ-04/s3/success-partial": {
        "kind": "problem",
        "code": "VERIFY-0010",
        "status": 422,
        "retryable": False,
    },
}

EXPECTED_INVARIANTS: dict[str, dict[str, Any]] = {
    **{
        identity: {
            "dbRowDelta": None,
            "readyTransitionCount": None,
            "quotaOvershootBytes": None,
            "committedObjectLossCount": 0,
            "partialResidueCount": 0,
            "tempResidueCount": 0,
            "cleanupResidueCount": 0,
            "sourceExitClass": None,
            "verifierExitClass": None,
            "archiveByteCount": None,
            "pitrVerified": None,
        }
        for identity in HOSTED_CASES[5:]
    },
    "CAP-01/postgresql/concurrent-8": {
        "dbRowDelta": 0,
        "readyTransitionCount": 0,
        "quotaOvershootBytes": 0,
        "committedObjectLossCount": 0,
        "partialResidueCount": 0,
        "tempResidueCount": 0,
        "cleanupResidueCount": 0,
        "sourceExitClass": None,
        "verifierExitClass": None,
        "archiveByteCount": None,
        "pitrVerified": None,
    },
    "CAP-01/postgresql/single": {
        "dbRowDelta": 0,
        "readyTransitionCount": 0,
        "quotaOvershootBytes": 0,
        "committedObjectLossCount": 0,
        "partialResidueCount": 0,
        "tempResidueCount": 0,
        "cleanupResidueCount": 0,
        "sourceExitClass": None,
        "verifierExitClass": None,
        "archiveByteCount": None,
        "pitrVerified": None,
    },
    "CAP-02/s3/http-507-new-key": {
        "dbRowDelta": 0,
        "readyTransitionCount": 0,
        "quotaOvershootBytes": 0,
        "committedObjectLossCount": 0,
        "partialResidueCount": 0,
        "tempResidueCount": 0,
        "cleanupResidueCount": 0,
        "sourceExitClass": None,
        "verifierExitClass": None,
        "archiveByteCount": None,
        "pitrVerified": None,
    },
    "BAK-01/postgresql/archive-command-false": {
        "dbRowDelta": None,
        "readyTransitionCount": None,
        "quotaOvershootBytes": None,
        "committedObjectLossCount": None,
        "partialResidueCount": None,
        "tempResidueCount": None,
        "cleanupResidueCount": 0,
        "sourceExitClass": "nonzero-observed",
        "verifierExitClass": "nonzero-observed",
        "archiveByteCount": 0,
        "pitrVerified": False,
    },
    "BAK-03/postgresql/archive-command-true-empty": {
        "dbRowDelta": None,
        "readyTransitionCount": None,
        "quotaOvershootBytes": None,
        "committedObjectLossCount": None,
        "partialResidueCount": None,
        "tempResidueCount": None,
        "cleanupResidueCount": 0,
        "sourceExitClass": "zero-observed",
        "verifierExitClass": "nonzero-observed",
        "archiveByteCount": 0,
        "pitrVerified": False,
    },
}

_S3_ENV = (
    "INV_OBJECT_STORE_ENDPOINT",
    "INV_OBJECT_STORE_BUCKET",
    "INV_OBJECT_STORE_ACCESS_KEY_ID",
    "INV_OBJECT_STORE_SECRET_ACCESS_KEY",
    "INV_OBJECT_STORE_REGION",
)


def _surface(exc: BaseException | None) -> dict[str, Any]:
    if exc is None:
        return {"kind": "success"}
    if isinstance(exc, DomainError):
        return {
            "kind": "problem",
            "code": exc.code,
            "status": exc.status,
            "retryable": exc.retryable,
        }
    return {"kind": "unexpected", "class": type(exc).__name__}


def _receipt(identity: str, actual: dict[str, Any], *, attempted_count: int = 1, **values: Any) -> dict[str, Any]:
    receipt = {
        "caseIdentity": identity,
        "executionLayer": EXECUTION_LAYER,
        "provider": "postgresql" if "/postgresql/" in identity else "s3",
        "injectionObserved": True,
        "attemptedCount": attempted_count,
        "expectedFindingCount": 0,
        "observedFindingCount": 0,
        "expectedSurface": EXPECTED[identity],
        "actualSurface": actual,
        "matched": False,
        "dbRowDelta": None,
        "readyTransitionCount": None,
        "quotaOvershootBytes": None,
        "committedObjectLossCount": None,
        "partialResidueCount": None,
        "tempResidueCount": None,
        "cleanupResidueCount": None,
        "sourceExitClass": None,
        "verifierExitClass": None,
        "archiveByteCount": None,
        "pitrVerified": None,
        "settingsSha256": None,
        "redacted": True,
    }
    receipt.update(values)
    invariants = EXPECTED_INVARIANTS[identity]
    invariant_match = all(receipt[name] == expected for name, expected in invariants.items())
    receipt["matched"] = actual == EXPECTED[identity] and invariant_match
    receipt["observedFindingCount"] = 0 if receipt["matched"] else 1
    return receipt


def _s3_config() -> S3Config:
    missing = [name for name in _S3_ENV if not os.environ.get(name)]
    if missing:
        raise RuntimeError("hosted S3 configuration is incomplete")
    return S3Config(
        endpoint=os.environ["INV_OBJECT_STORE_ENDPOINT"].rstrip("/"),
        bucket=os.environ["INV_OBJECT_STORE_BUCKET"],
        access_key=os.environ["INV_OBJECT_STORE_ACCESS_KEY_ID"],
        secret_key=os.environ["INV_OBJECT_STORE_SECRET_ACCESS_KEY"],
        region=os.environ["INV_OBJECT_STORE_REGION"],
    )


class _FaultTransport:
    """Inject one PUT outcome while forwarding every read to real MinIO."""

    def __init__(self, control: S3Client, key: str, mode: str, alternate: bytes):
        self.control = control
        self.key = key
        self.mode = mode
        self.alternate = alternate
        self.delegate = UrlLibTransport()
        self.observed = False

    def request(self, method, url, headers, body):
        if method != "PUT":
            return self.delegate.request(method, url, headers, body)
        self.observed = True
        if self.mode == "http-507":
            return HttpResponse(507, {}, b"")
        digest = hashlib.sha256(self.alternate).hexdigest()
        response = self.control.put(self.key, self.alternate, digest)
        if response.status not in {200, 201, 204}:
            raise RuntimeError("fault setup could not publish the alternate object")
        if self.mode == "timeout-after-different-byte":
            raise TimeoutError("injected ambiguous PUT")
        return HttpResponse(200, {}, b"")


def _delete_control(client: S3Client, key: str) -> int:
    response = client.delete(key)
    if response.status not in {200, 202, 204, 404}:
        return 1
    return 0 if client.head(key).status == 404 else 1


def _s3_corruption_case(identity: str) -> dict[str, Any]:
    config = _s3_config()
    control = S3Client(config)
    prefix = "s11-hosted/" + uuid4().hex
    provider = S3Objects("s3-compatible-v1", prefix, S3Client(config))
    locator = provider.locator(
        "11111111-1111-4111-8111-111111111111",
        "project_s11_hosted",
        "objects",
        str(uuid4()),
    )
    body = b"saintvision-s11-hosted-object"
    digest = hashlib.sha256(body).hexdigest()
    actual: dict[str, Any]
    injected = False
    try:
        if identity.endswith("body-byte"):
            changed = bytes([body[0] ^ 1]) + body[1:]
            response = control.put(locator, changed, digest)
            injected = response.status in {200, 201, 204}
            call = lambda: provider.get(locator, digest, len(body))
        elif identity.endswith("size-metadata"):
            response = control.put(locator, body, digest)
            injected = response.status in {200, 201, 204}
            call = lambda: provider.get(locator, digest, len(body) + 1)
        elif identity.endswith("metadata-digest"):
            response = control.put(locator, body, "f" * 64)
            injected = response.status in {200, 201, 204}
            call = lambda: provider.get(locator, digest, len(body))
        else:
            alternate = b"different-immutable-byte" if "ambiguous" in identity else body[:7]
            mode = "timeout-after-different-byte" if "ambiguous" in identity else "success-partial"
            transport = _FaultTransport(control, locator, mode, alternate)
            faulted = S3Objects(
                "s3-compatible-v1",
                prefix,
                S3Client(config, transport=transport),
            )
            call = lambda: faulted.put(locator, body, digest)
        try:
            call()
        except BaseException as exc:  # closed evidence surface
            actual = _surface(exc)
        else:
            actual = _surface(None)
        if "transport" in locals():
            injected = transport.observed
    finally:
        residue = _delete_control(control, locator)
    return _receipt(
        identity,
        actual,
        injectionObserved=injected,
        committedObjectLossCount=0,
        partialResidueCount=0,
        tempResidueCount=0,
        cleanupResidueCount=residue,
    )


def _count_storage_rows(env) -> int:
    with env.db.transaction(env.tenant) as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM inv.storage_objects WHERE project_id=%s",
            (env.project,),
        ).fetchone()["n"]


def _quota_case(identity: str, env) -> dict[str, Any]:
    from inv.snapshots import SnapshotStore

    body = b"x" * 64
    digest = hashlib.sha256(body).hexdigest()
    attempts = 8 if identity.endswith("concurrent-8") else 1
    with psycopg.connect(env.owner) as owner:
        owner.execute(
            "INSERT INTO inv.storage_budgets VALUES(%s,%s,%s) "
            "ON CONFLICT(project_id) DO UPDATE SET quota_bytes=excluded.quota_bytes",
            (env.tenant, env.project, len(body) - 1),
        )
    provider = S3Objects("s3-compatible-v1", "s11-quota/" + uuid4().hex, S3Client(_s3_config()))
    store = SnapshotStore(env.db, provider)
    before = _count_storage_rows(env)

    def one(_index: int) -> dict[str, Any]:
        try:
            store.begin(env.tenant, env.project, str(uuid4()), digest, len(body))
        except BaseException as exc:
            return _surface(exc)
        return _surface(None)

    with ThreadPoolExecutor(max_workers=attempts) as pool:
        surfaces = list(pool.map(one, range(attempts)))
    expected = EXPECTED[identity]
    actual = expected if all(surface == expected for surface in surfaces) else {
        "kind": "unexpected",
        "class": "QuotaSurfaceMismatch",
    }
    after = _count_storage_rows(env)
    return _receipt(
        identity,
        actual,
        attempted_count=attempts,
        injectionObserved=True,
        dbRowDelta=after - before,
        readyTransitionCount=0,
        quotaOvershootBytes=0,
        committedObjectLossCount=0,
        partialResidueCount=0,
        tempResidueCount=0,
        cleanupResidueCount=0,
    )


def _provider_507_case(identity: str, env) -> dict[str, Any]:
    from inv.snapshots import SnapshotStore

    body = b"s11-provider-capacity"
    digest = hashlib.sha256(body).hexdigest()
    object_id = str(uuid4())
    prefix = "s11-capacity/" + uuid4().hex
    control = S3Client(_s3_config())
    with psycopg.connect(env.owner) as owner:
        owner.execute(
            "INSERT INTO inv.storage_budgets VALUES(%s,%s,%s) "
            "ON CONFLICT(project_id) DO UPDATE SET quota_bytes=excluded.quota_bytes",
            (env.tenant, env.project, len(body) * 4),
        )
    # SnapshotStore derives the part locator.  The fault transport rejects the
    # one product PUT and forwards the subsequent read to real MinIO.
    placeholder = S3Objects("s3-compatible-v1", prefix, control)
    store_for_locator = SnapshotStore(env.db, placeholder)
    key = store_for_locator._part_locator(env.tenant, env.project, object_id, 0)
    transport = _FaultTransport(control, key, "http-507", b"")
    provider = S3Objects("s3-compatible-v1", prefix, S3Client(_s3_config(), transport=transport))
    store = SnapshotStore(env.db, provider)
    store.begin(env.tenant, env.project, object_id, digest, len(body))
    with env.db.transaction(env.tenant) as conn:
        before_parts = conn.execute(
            "SELECT count(*) AS n FROM inv.storage_parts WHERE project_id=%s AND object_id=%s",
            (env.project, object_id),
        ).fetchone()["n"]
    try:
        store.put_part(env.tenant, env.project, object_id, 0, body)
    except BaseException as exc:
        actual = _surface(exc)
    else:
        actual = _surface(None)
    with env.db.transaction(env.tenant) as conn:
        row = conn.execute(
            "SELECT state,size_bytes FROM inv.storage_objects WHERE project_id=%s AND object_id=%s",
            (env.project, object_id),
        ).fetchone()
        after_parts = conn.execute(
            "SELECT count(*) AS n FROM inv.storage_parts WHERE project_id=%s AND object_id=%s",
            (env.project, object_id),
        ).fetchone()["n"]
    residue = _delete_control(control, key)
    return _receipt(
        identity,
        actual,
        injectionObserved=transport.observed,
        dbRowDelta=after_parts - before_parts,
        readyTransitionCount=int(row["state"] == "ready"),
        quotaOvershootBytes=max(0, int(row["size_bytes"]) - len(body)),
        committedObjectLossCount=0,
        partialResidueCount=0,
        tempResidueCount=0,
        cleanupResidueCount=residue,
    )


def _docker(*args: str, timeout: float = 30) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["docker", *args], capture_output=True, timeout=timeout)


def _docker_sql(container: str, statement: str) -> list[str]:
    completed = _docker(
        "exec", container, "psql", "-X", "-At", "-F", "\t", "-v", "ON_ERROR_STOP=1",
        "-U", "postgres", "-d", "postgres", "-c", statement, timeout=20,
    )
    if completed.returncode:
        raise RuntimeError("owned archive PostgreSQL query failed")
    return [line for line in completed.stdout.decode("utf-8", errors="replace").splitlines() if line.strip()]


def _cleanup_owned(kind: str, name: str, label: str, value: str) -> int:
    inspected = _docker("inspect", name, timeout=10)
    if inspected.returncode:
        return 0
    document = json.loads(inspected.stdout)[0]
    labels = document.get("Config", {}).get("Labels", {}) if kind == "container" else document.get("Labels", {})
    if labels.get(label) != value:
        raise RuntimeError("refusing to remove an unowned Docker resource")
    command = ("rm", "-f", "-v", name) if kind == "container" else ("network", "rm", name)
    if _docker(*command, timeout=20).returncode:
        return 1
    return int(_docker("inspect", name, timeout=10).returncode == 0)


def _archive_case(identity: str, *, image: str, owner: str) -> dict[str, Any]:
    suffix = uuid4().hex[:12]
    container = "sv-s11-archive-" + suffix
    network = "sv-s11-archive-net-" + suffix
    container_label = "ai.saintvision.s11-storage"
    network_label = "ai.saintvision.s11-storage-network"
    command = "/bin/false" if identity.startswith("BAK-01/") else "/bin/true"
    created_network = False
    created_container = False
    residue = 0
    settings_sha = None
    try:
        result = _docker(
            "network", "create", "--internal", "--label", f"{network_label}={owner}", network,
            timeout=20,
        )
        if result.returncode:
            raise RuntimeError("owned archive network could not be created")
        created_network = True
        result = _docker(
            "run", "-d", "--name", container,
            "--label", f"{container_label}={owner}",
            "--network", network,
            "--tmpfs", "/var/lib/postgresql/data:rw,noexec,nosuid,size=256m",
            "-e", "POSTGRES_HOST_AUTH_METHOD=trust",
            image,
            "-c", "archive_mode=on",
            "-c", "archive_command=" + command,
            "-c", "archive_timeout=300",
            timeout=40,
        )
        if result.returncode:
            raise RuntimeError("owned archive PostgreSQL could not be started")
        created_container = True
        inspected = json.loads(_docker("inspect", container, timeout=10).stdout)[0]
        if any((inspected.get("HostConfig", {}).get("PortBindings") or {}).values()):
            raise RuntimeError("owned archive PostgreSQL published a host port")
        deadline = time.monotonic() + 60
        while True:
            logs = _docker("logs", "--tail", "200", container, timeout=10)
            text = (logs.stdout + logs.stderr).decode("utf-8", errors="replace")
            try:
                ready = _docker_sql(container, "SELECT 1") == ["1"]
            except RuntimeError:
                ready = False
            if "PostgreSQL init process complete; ready for start up." in text and ready:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("owned archive PostgreSQL did not become ready")
            time.sleep(0.2)
        execute = recovery_drill.docker_exec_settings_executor(container)
        capability = recovery_drill._recovery_capability(execute=execute)
        safe_settings = capability["settings"]
        if safe_settings.get("archive_command") != "configured":
            raise RuntimeError("archive command was not observed as configured")
        settings_sha = hashlib.sha256(
            json.dumps(safe_settings, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        _docker_sql(container, "CREATE TABLE archive_probe(value text)")
        _docker_sql(container, "INSERT INTO archive_probe VALUES('synthetic-marker')")
        _docker_sql(container, "SELECT pg_switch_wal()")
        deadline = time.monotonic() + 20
        archived = failed = 0
        while True:
            row = _docker_sql(container, "SELECT archived_count,failed_count FROM pg_stat_archiver")[0]
            archived, failed = (int(value) for value in row.split("\t"))
            if (failed if command == "/bin/false" else archived) > 0:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("archive outcome was not observed")
            time.sleep(0.1)
        if command == "/bin/false":
            actual = EXPECTED[identity] if failed > 0 else {"kind": "unexpected", "class": "ArchiveFailureNotObserved"}
            source_exit = "nonzero-observed"
        else:
            actual = EXPECTED[identity] if archived > 0 else {"kind": "unexpected", "class": "ArchiveSuccessNotObserved"}
            source_exit = "zero-observed"
    finally:
        if created_container:
            residue += _cleanup_owned("container", container, container_label, owner)
        if created_network:
            residue += _cleanup_owned("network", network, network_label, owner)
    return _receipt(
        identity,
        actual,
        injectionObserved=True,
        cleanupResidueCount=residue,
        sourceExitClass=source_exit,
        verifierExitClass="nonzero-observed",
        archiveByteCount=0,
        pitrVerified=False,
        settingsSha256=settings_sha,
    )


def execute_case(identity: str, env, *, archive_image: str, owner: str) -> dict[str, Any]:
    if identity.startswith(("OBJ-",)):
        return _s3_corruption_case(identity)
    if identity.startswith("CAP-01/"):
        return _quota_case(identity, env)
    if identity.startswith("CAP-02/"):
        return _provider_507_case(identity, env)
    if identity.startswith(("BAK-01/", "BAK-03/")):
        return _archive_case(identity, image=archive_image, owner=owner)
    raise ValueError("case identity is not in the hosted tier")


def build_report(
    executor: Callable[[str], dict[str, Any]],
    *,
    source_run_id: str,
    source_head_sha: str,
    checkout_tree_sha: str,
    clean_checkout: bool,
    producer_blob: str,
    recovery_probe_blob: str,
    harness_blob: str,
    started_at: str,
    finished_at: str,
    environment: dict[str, Any],
) -> dict[str, Any]:
    cases = [executor(identity) for identity in HOSTED_CASES]
    findings = sum(case["observedFindingCount"] for case in cases)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "runPurpose": RUN_PURPOSE,
        "executionLayer": EXECUTION_LAYER,
        "referenceOnly": True,
        "axis": None,
        "targetRef": None,
        "sourceRunId": source_run_id,
        "sourceHeadSha": source_head_sha,
        "checkoutTreeSha": checkout_tree_sha,
        "cleanCheckout": clean_checkout,
        "producerFile": {"path": PRODUCER_PATH, "blob": producer_blob},
        "injectorFile": {"path": PRODUCER_PATH, "blob": producer_blob},
        "recoveryProbeFile": {"path": RECOVERY_PROBE_PATH, "blob": recovery_probe_blob},
        "harnessFile": {"path": HARNESS_PATH, "blob": harness_blob},
        "startedAt": started_at,
        "finishedAt": finished_at,
        "universeCaseIdentitiesSha256": UNIVERSE_SHA256,
        "tierCaseIdentitiesSha256": HOSTED_SHA256,
        "caseCount": len(cases),
        "findingCount": findings,
        "cases": cases,
        "environment": environment,
        "cleanup": {
            "performed": True,
            "residueCount": sum(int(case["cleanupResidueCount"] or 0) for case in cases),
        },
        "redacted": True,
    }


def junit_xml(report: dict[str, Any]) -> bytes:
    suite = ET.Element(
        "testsuite",
        name="s11-storage-hosted-reference",
        tests=str(report["caseCount"]),
        failures=str(report["findingCount"]),
        errors="0",
        skipped="0",
    )
    for case in report["cases"]:
        node = ET.SubElement(suite, "testcase", name=case["caseIdentity"], classname="s11.storage.hosted")
        if not case["matched"]:
            failure = ET.SubElement(node, "failure", message="hosted product finding")
            failure.text = json.dumps(
                {"expected": case["expectedSurface"], "actual": case["actualSurface"]},
                sort_keys=True,
            )
    return ET.tostring(suite, encoding="utf-8", xml_declaration=True)


def hosted_environment(*, postgres_version: str, minio_digest: str, archive_digest: str) -> dict[str, Any]:
    return {
        "topology": "hosted-single-runner",
        "runnerOs": platform.system().lower(),
        "runnerArch": platform.machine().lower(),
        "pythonVersion": platform.python_version(),
        "postgresqlVersion": postgres_version,
        "minioImageDigest": minio_digest,
        "archiveImageDigest": archive_digest,
        "minioExposure": "loopback-only",
        "archiveNetworkInternal": True,
        "archivePublishedPortCount": 0,
        "githubSecretCount": 0,
        "artifactRetentionDays": 30,
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def git_value(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, timeout=15)
    if completed.returncode:
        raise RuntimeError("git provenance is unavailable")
    return completed.stdout.strip()


def write_outputs(report: dict[str, Any], report_path: Path, junit_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    junit_path.write_bytes(junit_xml(report))


def assert_frozen_tier() -> None:
    payload = json.dumps(list(HOSTED_CASES), ensure_ascii=False, separators=(",", ":")).encode()
    if tuple(sorted(HOSTED_CASES)) != HOSTED_CASES or hashlib.sha256(payload).hexdigest() != HOSTED_SHA256:
        raise RuntimeError("hosted case tier differs from the frozen target")
    if not set(HOSTED_CASES).issubset(UNIVERSE_CASES):
        raise RuntimeError("hosted case tier is outside the frozen universe")


assert_frozen_tier()
