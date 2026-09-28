"""Run the S11-ST PG-free fault tier and emit raw JSON plus JUnit.

The Linux LocalObjects cases exercise the product provider. Retention and backup
cases exercise the reviewed operator-tool boundary. Product findings are data:
the process still exits zero after every case and cleanup receipt is emitted.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import tarfile
from typing import Any, Callable
from unittest import mock
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE = ROOT / "services" / "control-plane" / "src"
sys.path.insert(0, str(CONTROL_PLANE))
sys.path.insert(0, str(ROOT / "tools"))

from inv.errors import DomainError  # noqa: E402
from inv.object_store import LocalObjectStore, LocalObjects  # noqa: E402
import inv.object_store as object_store  # noqa: E402
import pitr_archive_retention as retention  # noqa: E402
from verify_backup_artifact import BackupArtifactInvalid, verify_physical_backup_archive  # noqa: E402


SCHEMA_VERSION = "1.1.0"
RUN_PURPOSE = "s11-storage-failure-pg-free"
EXECUTION_LAYER = "pg-free"
PRODUCER_PATH = "tools/run_s11_storage_failure_pg_free.py"
BACKUP_VERIFIER_PATH = "tools/verify_backup_artifact.py"
UNIVERSE_SHA256 = "5d700981ee429ebbfc66b8ed28d8dc9e37e16e327a673d6061bdec5e7e334fd9"
PG_FREE_SHA256 = "f69d161e19a791cdead64f16fae813dd470b0eabe0ed0f7a58ceed9ed4298799"
UNIVERSE_CASES = (
    "BAK-01/postgresql/archive-command-false",
    "BAK-02/local/retention-rmtree",
    "BAK-02/local/retention-unlink",
    "BAK-03/local/backup-exit0-empty",
    "BAK-03/local/backup-exit0-truncated",
    "BAK-03/postgresql/archive-command-true-empty",
    "CAP-01/postgresql/concurrent-8",
    "CAP-01/postgresql/single",
    "CAP-02/local/edquot-new-key",
    "CAP-02/local/enospc-new-key",
    "CAP-02/s3/http-507-new-key",
    "OBJ-01/local/body-byte",
    "OBJ-01/s3/body-byte",
    "OBJ-02/local/append",
    "OBJ-02/local/truncate",
    "OBJ-02/s3/size-metadata",
    "OBJ-03/s3/metadata-digest",
    "OBJ-04/local/directory-fsync-eio",
    "OBJ-04/local/file-fsync-eio",
    "OBJ-04/local/write-enospc",
    "OBJ-04/s3/ambiguous-put-different-byte",
    "OBJ-04/s3/success-partial",
)
PG_FREE_CASES = (
    "BAK-02/local/retention-rmtree",
    "BAK-02/local/retention-unlink",
    "BAK-03/local/backup-exit0-empty",
    "BAK-03/local/backup-exit0-truncated",
    "CAP-02/local/edquot-new-key",
    "CAP-02/local/enospc-new-key",
    "OBJ-01/local/body-byte",
    "OBJ-02/local/append",
    "OBJ-02/local/truncate",
    "OBJ-04/local/directory-fsync-eio",
    "OBJ-04/local/file-fsync-eio",
    "OBJ-04/local/write-enospc",
)


EXPECTED: dict[str, dict[str, Any]] = {
    "OBJ-01/local/body-byte": {"kind": "problem", "code": "VERIFY-0010", "status": 422, "retryable": False},
    "OBJ-02/local/append": {"kind": "problem", "code": "STORE-0003", "status": 422, "retryable": False},
    "OBJ-02/local/truncate": {"kind": "problem", "code": "STORE-0003", "status": 422, "retryable": False},
    "OBJ-04/local/directory-fsync-eio": {"kind": "problem", "code": "STORE-0001", "status": 503, "retryable": True},
    "OBJ-04/local/file-fsync-eio": {"kind": "problem", "code": "STORE-0001", "status": 503, "retryable": True},
    "OBJ-04/local/write-enospc": {"kind": "problem", "code": "STORE-0001", "status": 503, "retryable": True},
    "CAP-02/local/edquot-new-key": {"kind": "problem", "code": "STORE-0001", "status": 503, "retryable": True},
    "CAP-02/local/enospc-new-key": {"kind": "problem", "code": "STORE-0001", "status": 503, "retryable": True},
    "BAK-02/local/retention-rmtree": {"kind": "failureClass", "failureClass": "RETENTION_APPLY_PARTIAL", "retryable": True},
    "BAK-02/local/retention-unlink": {"kind": "failureClass", "failureClass": "RETENTION_APPLY_PARTIAL", "retryable": True},
    "BAK-03/local/backup-exit0-empty": {"kind": "failureClass", "failureClass": "BACKUP_ARTIFACT_INVALID", "retryable": False},
    "BAK-03/local/backup-exit0-truncated": {"kind": "failureClass", "failureClass": "BACKUP_ARTIFACT_INVALID", "retryable": False},
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    if isinstance(exc, retention.RetentionApplyPartial):
        return {
            "kind": "failureClass",
            "failureClass": retention.PARTIAL_FAILURE_CLASS,
            "retryable": True,
        }
    if isinstance(exc, OSError):
        return {"kind": "osError", "errno": int(exc.errno or 0)}
    if isinstance(exc, BackupArtifactInvalid):
        return {"kind": "failureClass", "failureClass": "BACKUP_ARTIFACT_INVALID", "retryable": False}
    return {"kind": "unexpected", "class": type(exc).__name__}


def _receipt(identity: str, actual: dict[str, Any], **extra: Any) -> dict[str, Any]:
    expected = EXPECTED[identity]
    matched = actual == expected
    value = {
        "caseIdentity": identity,
        "executionLayer": EXECUTION_LAYER,
        "provider": "local",
        "injectionObserved": True,
        "attemptedCount": 1,
        "expectedFindingCount": 0,
        "observedFindingCount": 0 if matched else 1,
        "expectedSurface": expected,
        "actualSurface": actual,
        "matched": matched,
        "beforeSha256": None,
        "afterSha256": None,
        "dbRowDelta": None,
        "readyTransitionCount": None,
        "quotaOvershootBytes": None,
        "committedObjectLossCount": None,
        "partialResidueCount": None,
        "tempResidueCount": None,
        "cleanupResidueCount": None,
        "redacted": True,
    }
    value.update(extra)
    receipt_finding = any(
        isinstance(value[name], int) and not isinstance(value[name], bool) and value[name] > 0
        for name in (
            "quotaOvershootBytes", "committedObjectLossCount", "partialResidueCount",
            "tempResidueCount", "cleanupResidueCount",
        )
    )
    if identity.startswith("BAK-02/") and value["beforeSha256"] != value["afterSha256"]:
        receipt_finding = True
    value["matched"] = actual == expected and not receipt_finding
    value["observedFindingCount"] = 0 if value["matched"] else 1
    return value


def _local_mutation(identity: str) -> dict[str, Any]:
    data = b"saintvision-storage-evidence"
    digest = _sha(data)
    key = "obj-" + "1" * 32
    with tempfile.TemporaryDirectory(prefix="s11-storage-") as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        provider = LocalObjects(root)
        with provider.locked() as handle:
            handle.put(key, data, digest)
        path = root / key
        path.chmod(0o600)
        if identity.endswith("body-byte"):
            path.write_bytes(b"x" * len(data))
        elif identity.endswith("append"):
            path.write_bytes(data + b"x")
        else:
            path.write_bytes(data[:-1])
        path.chmod(0o400)
        if stat.S_IMODE(path.stat().st_mode) != 0o400:
            raise RuntimeError("LocalObjects mutation fixture mode was not restored")
        try:
            with provider.locked() as handle:
                handle.read(key, digest, len(data))
        except BaseException as exc:  # evidence records the closed surface
            actual = _surface(exc)
        else:
            actual = _surface(None)
        after = path.read_bytes()
        return _receipt(
            identity,
            actual,
            beforeSha256=digest,
            afterSha256=_sha(after),
        )


def _local_write_fault(identity: str) -> dict[str, Any]:
    data = b"saintvision-storage-evidence"
    digest = _sha(data)
    key = "obj-" + "2" * 32
    original_open = object_store.os.open
    original_fsync = object_store.os.fsync
    original_fdopen = object_store.os.fdopen
    requested_errno = errno.EDQUOT if "edquot" in identity else errno.ENOSPC

    def failing_open(path, flags, *args, **kwargs):
        if flags & os.O_CREAT:
            raise OSError(requested_errno, os.strerror(requested_errno))
        return original_open(path, flags, *args, **kwargs)

    def failing_fsync(fd):
        mode = os.fstat(fd).st_mode
        if identity.endswith("file-fsync-eio") and stat.S_ISREG(mode):
            raise OSError(errno.EIO, os.strerror(errno.EIO))
        if identity.endswith("directory-fsync-eio") and stat.S_ISDIR(mode):
            raise OSError(errno.EIO, os.strerror(errno.EIO))
        return original_fsync(fd)

    class WriteFailingStream:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, exc_type, exc, traceback):
            return self.stream.__exit__(exc_type, exc, traceback)

        def fileno(self):
            return self.stream.fileno()

        def write(self, _data):
            raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))

        def flush(self):
            return self.stream.flush()

    def failing_fdopen(fd, *args, **kwargs):
        return WriteFailingStream(original_fdopen(fd, *args, **kwargs))

    with tempfile.TemporaryDirectory(prefix="s11-storage-") as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        # Exercise the registered product boundary.  ``LocalObjects`` is the
        # low-level, locked filesystem handle; host failures are deliberately
        # translated to STORE-0001 by ``LocalObjectStore`` before they reach a
        # caller or an evidence receipt.
        provider = LocalObjectStore(LocalObjects(root))
        if identity.endswith("write-enospc"):
            patcher = mock.patch.object(object_store.os, "fdopen", side_effect=failing_fdopen)
        elif "fsync" in identity:
            patcher = mock.patch.object(object_store.os, "fsync", side_effect=failing_fsync)
        else:
            patcher = mock.patch.object(object_store.os, "open", side_effect=failing_open)
        try:
            with patcher:
                provider.put(key, data, digest)
        except BaseException as exc:
            actual = _surface(exc)
        else:
            actual = _surface(None)
        canonical = root / key
        after = canonical.read_bytes() if canonical.is_file() else None
        residue = len(list(root.glob("tmp-*")))
        canonical_residue = canonical.exists() and not (
            identity.endswith("directory-fsync-eio") and after == data
        )
        return _receipt(
            identity,
            actual,
            afterSha256=_sha(after) if after is not None else None,
            quotaOvershootBytes=len(after or b"") if identity.startswith("CAP-02/") else None,
            partialResidueCount=1 if canonical_residue else 0,
            tempResidueCount=residue,
            cleanupResidueCount=(1 if canonical_residue else 0) + residue,
        )


def _retention_fault(identity: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="s11-retention-") as temporary:
        root = Path(temporary)
        archive = root / "archive"
        backups = root / "backups"
        archive.mkdir()
        backups.mkdir()
        retained_archive = {
            "000000010000000000000010": b"boundary",
            "000000010000000000000011": b"after-boundary",
            "00000002.history": b"history",
            "000000010000000000000012.partial": b"partial",
        }
        retained_backups = {
            "latest-backup": (
                b"START WAL LOCATION: 0/10000010 (file 000000010000000000000010)\n"
                b"START TIME: 2026-09-27 00:00:00 +00\n"
            )
        }
        deletion_backups = {
            "old-backup-a": (
                b"START WAL LOCATION: 0/10000001 (file 000000010000000000000001)\n"
                b"START TIME: 2026-07-01 00:00:00 +00\n"
            ),
            "old-backup-b": (
                b"START WAL LOCATION: 0/10000002 (file 000000010000000000000002)\n"
                b"START TIME: 2026-07-02 00:00:00 +00\n"
            ),
        }
        for name, data in retained_archive.items():
            (archive / name).write_bytes(data)
        for name, data in retained_backups.items():
            target = backups / name
            target.mkdir()
            (target / "backup_label").write_bytes(data)
        for name, data in deletion_backups.items():
            target = backups / name
            target.mkdir()
            (target / "backup_label").write_bytes(data)

        for name in ("000000010000000000000001", "000000010000000000000002"):
            (archive / name).write_bytes(b"wal")
        plan_ = retention.plan(
            retention.load_archive(archive),
            retention.load_backups(backups),
            retention_days=35,
            now=datetime.fromisoformat("2026-09-28T00:00:00+00:00"),
        )
        if plan_.delete_archive != [
            "000000010000000000000001",
            "000000010000000000000002",
        ] or plan_.delete_backups != ["old-backup-a", "old-backup-b"]:
            raise AssertionError("the BAK-02 fixture no longer yields the reviewed retention plan")

        def retained_digest() -> str:
            digest = hashlib.sha256()
            for base, expected in ((archive, retained_archive), (backups, retained_backups)):
                for name in sorted(expected):
                    target = base / name
                    digest.update(name.encode("utf-8") + b"\0")
                    if target.is_dir():
                        target = target / "backup_label"
                    try:
                        data = target.read_bytes()
                    except FileNotFoundError:
                        data = b"<missing>"
                    digest.update(data + b"\0")
            return digest.hexdigest()

        before = retained_digest()
        injected = 0
        if identity.endswith("unlink"):
            original_unlink = Path.unlink

            def interrupted_unlink(path, *args, **kwargs):
                nonlocal injected
                injected += 1
                if injected == 2:
                    raise OSError(errno.EIO, "injected")
                return original_unlink(path, *args, **kwargs)

            patcher = mock.patch.object(Path, "unlink", new=interrupted_unlink)
        else:
            original_rmtree = shutil.rmtree

            def interrupted_rmtree(path, *args, **kwargs):
                nonlocal injected
                injected += 1
                if injected == 2:
                    raise OSError(errno.EIO, "injected")
                return original_rmtree(path, *args, **kwargs)

            patcher = mock.patch.object(shutil, "rmtree", new=interrupted_rmtree)
        try:
            with patcher:
                retention.apply(plan_, archive, backups)
        except (OSError, retention.RetentionApplyPartial) as exc:
            actual = _surface(exc)
        else:
            actual = {"kind": "success"}
        after = retained_digest()
        return _receipt(
            identity,
            actual,
            beforeSha256=before,
            afterSha256=after,
        )


def _valid_physical_backup_tar() -> bytes:
    stream = io.BytesIO()
    members = {
        "PG_VERSION": b"16\n",
        "backup_label": b"START WAL LOCATION: 0/1000000 (file 000000010000000000000001)\n",
        "global/pg_control": b"x" * 8192,
    }
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return stream.getvalue()


def _truncated_physical_backup_tar() -> bytes:
    valid = _valid_physical_backup_tar()
    with tarfile.open(fileobj=io.BytesIO(valid), mode="r:") as archive:
        control = archive.getmember("global/pg_control")
    return valid[: control.offset_data + control.size // 2]


def _backup_fault(identity: str) -> dict[str, Any]:
    if identity.endswith("empty"):
        data = b""
    else:
        data = _truncated_physical_backup_tar()
    with tempfile.TemporaryDirectory(prefix="s11-backup-") as temporary:
        artifact = Path(temporary) / "base-backup.tar"
        artifact.write_bytes(data)
        try:
            verify_physical_backup_archive(artifact)
        except BaseException as exc:
            actual = _surface(exc)
        else:
            actual = _surface(None)
        return _receipt(identity, actual, afterSha256=_sha(data))


def execute_case(identity: str) -> dict[str, Any]:
    if identity.startswith(("OBJ-01/", "OBJ-02/")):
        return _local_mutation(identity)
    if identity.startswith(("OBJ-04/", "CAP-02/")):
        return _local_write_fault(identity)
    if identity.startswith("BAK-02/"):
        return _retention_fault(identity)
    if identity.startswith("BAK-03/"):
        return _backup_fault(identity)
    raise ValueError("case identity is not in the PG-free tier")


def build_report(
    executor: Callable[[str], dict[str, Any]],
    *,
    source_run_id: str,
    source_head_sha: str,
    checkout_tree_sha: str,
    producer_blob: str,
    backup_verifier_blob: str,
    clean_checkout: bool,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    cases = [executor(identity) for identity in PG_FREE_CASES]
    findings = sum(int(case.get("observedFindingCount", 0)) for case in cases)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "runPurpose": RUN_PURPOSE,
        "executionLayer": EXECUTION_LAYER,
        "sourceRunId": source_run_id,
        "sourceHeadSha": source_head_sha,
        "checkoutTreeSha": checkout_tree_sha,
        "cleanCheckout": clean_checkout,
        "producerFile": {"path": PRODUCER_PATH, "blob": producer_blob},
        "injectorFile": {"path": PRODUCER_PATH, "blob": producer_blob},
        "backupVerifierFile": {"path": BACKUP_VERIFIER_PATH, "blob": backup_verifier_blob},
        "startedAt": started_at,
        "finishedAt": finished_at,
        "universeCaseIdentitiesSha256": UNIVERSE_SHA256,
        "tierCaseIdentitiesSha256": PG_FREE_SHA256,
        "caseCount": len(cases),
        "findingCount": findings,
        "cases": cases,
        "redacted": True,
    }


def junit_xml(report: dict[str, Any]) -> bytes:
    suite = ET.Element(
        "testsuite",
        name="s11-storage-pg-free",
        tests=str(report["caseCount"]),
        failures=str(report["findingCount"]),
        errors="0",
        skipped="0",
    )
    for case in report["cases"]:
        node = ET.SubElement(suite, "testcase", name=case["caseIdentity"], classname="s11.storage.pg_free")
        if not case["matched"]:
            failure = ET.SubElement(node, "failure", message="expected and observed surface differ")
            failure.text = json.dumps({"expected": case["expectedSurface"], "actual": case["actualSurface"]}, sort_keys=True)
    return ET.tostring(suite, encoding="utf-8", xml_declaration=True)


def _git(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, timeout=15)
    if completed.returncode:
        raise RuntimeError("git provenance is unavailable")
    return completed.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--finished-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args(argv)
    if sys.platform != "linux":
        print("S11 storage PG-free LocalObjects tier requires Linux", file=sys.stderr)
        return 3
    source = _git("rev-parse", "HEAD")
    tree = _git("rev-parse", "HEAD^{tree}")
    clean = not _git("status", "--porcelain")
    if not clean:
        print("producer checkout is dirty", file=sys.stderr)
        return 2
    report = build_report(
        execute_case,
        source_run_id=args.source_run_id,
        source_head_sha=source,
        checkout_tree_sha=tree,
        producer_blob=_git("rev-parse", f"HEAD:{PRODUCER_PATH}"),
        backup_verifier_blob=_git("rev-parse", f"HEAD:{BACKUP_VERIFIER_PATH}"),
        clean_checkout=True,
        started_at=args.started_at,
        finished_at=args.finished_at,
    )
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.junit.write_bytes(junit_xml(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
