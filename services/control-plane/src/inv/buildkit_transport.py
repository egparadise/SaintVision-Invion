"""Measured, fail-closed client for a rootless BuildKit service.

This is the first concrete transport stage for S08-BE.  It can measure a
rootless daemon and perform a reference OCI roundtrip, but it deliberately
cannot be passed to :class:`BuildExecutionAdapter` for product dispatch yet.
The product adapter needs a physical cleanup receipt, database lease release,
and durable Evidence persistence before that connection can be enabled.

The reference path is intentionally narrow: a clean, exact Git tree; no
secrets; no network; no cache import/export; no registry push; and an OCI file
export only.  Its report is ``ci-reference`` evidence, never a BuildReceipt or
an operational acceptance claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Mapping, Protocol, Sequence

from .build_governance import BuildProviderObservation
from .contracts import validate_contract
from .errors import DomainError
from .policy import action_digest


TRANSPORT_ENABLE_SETTING = "INV_BUILDKIT_REFERENCE_ENABLED"
_HEX_40 = re.compile(r"[0-9a-f]{40}")
_HEX_64 = re.compile(r"[0-9a-f]{64}")
_IMAGE_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_HEALTH_KEYS = frozenset(
    {
        "schemaVersion",
        "builderInstanceId",
        "builderProfileId",
        "recoveryEpoch",
        "address",
        "pid",
        "hostUid",
        "processStartTicks",
        "rootless",
        "privileged",
        "hostAccess",
        "entitlements",
        "devices",
        "binds",
        "observedAt",
        "buildkitVersion",
        "rootlesskitVersion",
        "runtimeIdentity",
        "isolation",
    }
)
_ISOLATION_KEYS = frozenset(
    {
        "userNamespace",
        "seccompMode",
        "lsm",
        "noNewPrivileges",
        "cgroupMode",
    }
)


class CommandRunner(Protocol):
    def run(
        self,
        arguments: Sequence[str],
        *,
        cwd: Path,
        timeout: int,
        environment: Mapping[str, str],
    ) -> subprocess.CompletedProcess[str]: ...


class SubprocessCommandRunner:
    """No-shell command runner used by the concrete client."""

    def run(self, arguments, *, cwd, timeout, environment):
        return subprocess.run(
            list(arguments),
            cwd=cwd,
            env=dict(environment),
            timeout=timeout,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )


@dataclass(frozen=True)
class BuildkitTransportConfiguration:
    buildctl_path: Path
    address: str
    source_root: Path
    health_receipt_path: Path
    builder_instance_id: str
    builder_profile_id: str
    recovery_epoch: int
    freshness_seconds: int = 15


@dataclass(frozen=True)
class MeasuredBuilder:
    provider: BuildProviderObservation
    worker_id: str
    platforms: tuple[str, ...]
    buildkit_version: str
    rootlesskit_version: str
    isolation: dict
    process_measurement: dict


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise DomainError("RES-0003", "BuildKit health observation is invalid", 409)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise DomainError("RES-0003", "BuildKit health observation is invalid", 409) from None
    if parsed.tzinfo is None:
        raise DomainError("RES-0003", "BuildKit health observation is invalid", 409)
    return parsed


def _protected_json(path: Path) -> dict:
    """Read one small, non-linked operator receipt without following symlinks."""

    try:
        before = path.lstat()
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            observed = os.fstat(descriptor)
            if (
                not stat.S_ISREG(observed.st_mode)
                or observed.st_nlink != 1
                or observed.st_size > 16384
                or (os.name != "nt" and observed.st_mode & 0o077)
                or (before.st_dev, before.st_ino) != (observed.st_dev, observed.st_ino)
            ):
                raise ValueError()
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read(16385)
        finally:
            os.close(descriptor)
        value = json.loads(raw)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        raise DomainError(
            "RES-0006", "BuildKit health receipt is unavailable", 503, retryable=True
        ) from None
    if not isinstance(value, dict):
        raise DomainError("RES-0006", "BuildKit health receipt is unavailable", 503, retryable=True)
    return value


def _parse_workers(output: str) -> tuple[dict, ...]:
    try:
        stripped = output.strip()
        decoded = json.loads(stripped)
        values = decoded if isinstance(decoded, list) else [decoded]
    except (json.JSONDecodeError, TypeError):
        try:
            values = [json.loads(line) for line in output.splitlines() if line.strip()]
        except json.JSONDecodeError:
            raise DomainError(
                "RES-0006", "BuildKit worker inventory is invalid", 503, retryable=True
            ) from None
    if not values or any(not isinstance(value, dict) for value in values):
        raise DomainError("RES-0006", "BuildKit worker inventory is invalid", 503, retryable=True)
    return tuple(values)


class RootlessBuildkitTransport:
    """Concrete buildctl transport, restricted to a CI reference roundtrip.

    ``dispatch`` remains fail-closed so a caller cannot confuse this stage with
    product execution.  ``reference_roundtrip`` is the only executable method.
    """

    def __init__(
        self,
        configuration: BuildkitTransportConfiguration,
        *,
        runner: CommandRunner | None = None,
        environment: Mapping[str, str] | None = None,
        now=lambda: datetime.now(timezone.utc),
    ):
        self.configuration = configuration
        self._runner = runner or SubprocessCommandRunner()
        self._environment = dict(environment if environment is not None else os.environ)
        self._now = now

    @classmethod
    def configured(
        cls,
        configuration: BuildkitTransportConfiguration,
        *,
        environment: Mapping[str, str] | None = None,
        **kwargs,
    ) -> "RootlessBuildkitTransport":
        values = environment if environment is not None else os.environ
        if values.get(TRANSPORT_ENABLE_SETTING) != "1":
            raise DomainError(
                "RES-0006", "BuildKit reference transport is disabled", 503, retryable=True
            )
        return cls(configuration, environment=values, **kwargs)

    def _run(self, arguments: Sequence[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
        result = self._runner.run(
            arguments,
            cwd=self.configuration.source_root,
            timeout=timeout,
            environment={
                "PATH": self._environment.get("PATH", ""),
                "HOME": self._environment.get("HOME", ""),
                "XDG_RUNTIME_DIR": self._environment.get("XDG_RUNTIME_DIR", ""),
                "BUILDKIT_PROGRESS": "plain",
            },
        )
        if result.returncode != 0:
            raise DomainError("RES-0006", "Rootless BuildKit command failed", 503, retryable=True)
        return result

    def _health(self) -> dict:
        receipt = _protected_json(self.configuration.health_receipt_path)
        isolation = receipt.get("isolation")
        if (
            set(receipt) != _HEALTH_KEYS
            or receipt.get("schemaVersion") != 1
            or receipt.get("builderInstanceId") != self.configuration.builder_instance_id
            or receipt.get("builderProfileId") != self.configuration.builder_profile_id
            or receipt.get("recoveryEpoch") != self.configuration.recovery_epoch
            or receipt.get("address") != self.configuration.address
            or type(receipt.get("pid")) is not int
            or receipt["pid"] <= 1
            or type(receipt.get("hostUid")) is not int
            or receipt["hostUid"] <= 0
            or type(receipt.get("processStartTicks")) is not int
            or receipt["processStartTicks"] <= 0
            or receipt.get("rootless") is not True
            or receipt.get("privileged") is not False
            or receipt.get("hostAccess") is not False
            or receipt.get("entitlements") != []
            or receipt.get("devices") != []
            or receipt.get("binds") != []
            or not isinstance(receipt.get("buildkitVersion"), str)
            or not receipt["buildkitVersion"]
            or not isinstance(receipt.get("rootlesskitVersion"), str)
            or not receipt["rootlesskitVersion"]
            or not isinstance(receipt.get("runtimeIdentity"), str)
            or not receipt["runtimeIdentity"].startswith("sha256:")
            or not _HEX_64.fullmatch(receipt["runtimeIdentity"].removeprefix("sha256:"))
            or not isinstance(isolation, dict)
            or set(isolation) != _ISOLATION_KEYS
            or isolation.get("userNamespace") is not True
            or isolation.get("seccompMode") not in {"filter", "unavailable-ci-reference"}
            or isolation.get("lsm") not in {"apparmor", "selinux", "unavailable-ci-reference"}
            or type(isolation.get("noNewPrivileges")) is not bool
            or isolation.get("cgroupMode") not in {"v2", "unavailable-ci-reference"}
        ):
            raise DomainError(
                "RES-0006", "BuildKit health receipt is not qualified", 503, retryable=True
            )
        observed_at = _parse_timestamp(receipt.get("observedAt"))
        now = self._now()
        age = (now - observed_at).total_seconds()
        if now.tzinfo is None or not 0 <= age <= self.configuration.freshness_seconds:
            raise DomainError("RES-0003", "BuildKit health observation is stale", 409)
        return receipt

    def measure(self) -> MeasuredBuilder:
        receipt = self._health()
        result = self._run(
            (
                str(self.configuration.buildctl_path),
                "--addr",
                self.configuration.address,
                "debug",
                "workers",
                "--format",
                "{{json .}}",
            ),
            timeout=10,
        )
        workers = _parse_workers(result.stdout)
        if len(workers) != 1:
            raise DomainError(
                "RES-0006", "BuildKit worker inventory is not exclusive", 503, retryable=True
            )
        worker = workers[0]
        worker_id = worker.get("ID") or worker.get("id")
        platforms = worker.get("Platforms") or worker.get("platforms")
        if (
            not isinstance(worker_id, str)
            or not worker_id
            or not isinstance(platforms, list)
            or not platforms
            or any(not isinstance(item, str) or not item for item in platforms)
        ):
            raise DomainError(
                "RES-0006", "BuildKit worker inventory is invalid", 503, retryable=True
            )
        measurement = {
            "health": receipt,
            "workerId": worker_id,
            "platforms": sorted(set(platforms)),
        }
        provider = BuildProviderObservation(
            builder_instance_id=receipt["builderInstanceId"],
            builder_profile_id=receipt["builderProfileId"],
            observation_digest=_canonical_digest(measurement),
            recovery_epoch=receipt["recoveryEpoch"],
            observed_at=_parse_timestamp(receipt["observedAt"]),
        )
        return MeasuredBuilder(
            provider,
            worker_id,
            tuple(sorted(set(platforms))),
            receipt["buildkitVersion"],
            receipt["rootlesskitVersion"],
            dict(receipt["isolation"]),
            {
                "pid": receipt["pid"],
                "hostUid": receipt["hostUid"],
                "processStartTicks": receipt["processStartTicks"],
                "address": receipt["address"],
                "observedAt": receipt["observedAt"],
                "rootless": receipt["rootless"],
                "privileged": receipt["privileged"],
                "hostAccess": receipt["hostAccess"],
                "entitlements": list(receipt["entitlements"]),
                "runtimeIdentity": receipt["runtimeIdentity"],
            },
        )

    def observe(self, _plan: dict) -> BuildProviderObservation:
        return self.measure().provider

    def dispatch(self, _admitted) -> dict:
        raise DomainError(
            "RES-0006",
            "BuildKit product dispatch awaits cleanup and Evidence persistence binding",
            503,
            retryable=True,
        )

    def cancel_and_quarantine(self, _admitted, _reason_code: str) -> None:
        raise DomainError(
            "VERIFY-0022",
            "BuildKit product cleanup is not connected",
            409,
        )

    def _git(self, *arguments: str) -> str:
        result = self._run(
            ("git", "-C", str(self.configuration.source_root), *arguments), timeout=15
        )
        return result.stdout.strip()

    def _source_directory(self, relative: str) -> Path:
        root = self.configuration.source_root.resolve(strict=True)
        candidate = (root / relative).resolve(strict=True)
        try:
            candidate.relative_to(root)
        except ValueError:
            raise DomainError("VAL-0003", "Build source path escapes the checkout", 422) from None
        if not candidate.is_dir():
            raise DomainError("VAL-0003", "Build context is not a directory", 422)
        return candidate

    def _source_file(self, relative: str) -> Path:
        root = self.configuration.source_root.resolve(strict=True)
        candidate = (root / relative).resolve(strict=True)
        try:
            candidate.relative_to(root)
        except ValueError:
            raise DomainError("VAL-0003", "Build source path escapes the checkout", 422) from None
        observed = candidate.stat()
        if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
            raise DomainError("VAL-0003", "Build Dockerfile is not a private regular file", 422)
        return candidate

    def reference_roundtrip(self, request: dict, plan: dict, output_directory: Path) -> dict:
        """Build one OCI archive and return redacted reference-only evidence."""

        validate_contract("BuildRequest", request)
        validate_contract("BuildPlan", plan)
        measured = self.measure()
        if (
            plan["builderInstanceId"] != measured.provider.builder_instance_id
            or plan["builderProfileId"] != measured.provider.builder_profile_id
            or plan["builderObservationDigest"] != measured.provider.observation_digest
            or plan["recoveryEpoch"] != measured.provider.recovery_epoch
            or request["targetPlatform"] not in measured.platforms
        ):
            raise DomainError("VERIFY-0002", "BuildKit provider binding differs", 422)
        if (
            request["secretRefIds"]
            or request["networkPolicyId"] != "none"
            or plan["networkMode"] != "none"
            or plan["networkPolicyId"] != "none"
            or plan["egressAllowlistDigest"] != "0" * 64
            or plan["devices"]
            or plan["binds"]
            or plan["rootless"] is not True
            or plan["privileged"] is not False
            or plan["hostAccess"] is not False
        ):
            raise DomainError("AUTH-0012", "Reference BuildKit policy denied", 403)

        head = self._git("rev-parse", "HEAD")
        tree = self._git("rev-parse", "HEAD^{tree}")
        dirty = self._git("status", "--porcelain=v1", "--untracked-files=all")
        if (
            not _HEX_40.fullmatch(head)
            or not _HEX_40.fullmatch(tree)
            or head != request["sourceCommitSha"]
            or tree != request["sourceTreeSha"]
            or dirty
        ):
            raise DomainError("VERIFY-0002", "Build source checkout differs", 422)

        context = self._source_directory(request["contextPath"])
        dockerfile = self._source_file(request["dockerfilePath"])
        if dockerfile.parent != context and context not in dockerfile.parents:
            raise DomainError("VAL-0003", "Build Dockerfile is outside its context", 422)

        output_directory = output_directory.resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        archive = output_directory / "rootless-buildkit-roundtrip.oci.tar"
        metadata = output_directory / "rootless-buildkit-metadata.json"
        report = output_directory / "rootless-buildkit-reference.json"
        for path in (archive, metadata, report):
            path.unlink(missing_ok=True)

        started_at = self._now()
        arguments = (
            str(self.configuration.buildctl_path),
            "--addr",
            self.configuration.address,
            "build",
            "--frontend",
            "dockerfile.v0",
            "--local",
            f"context={context}",
            "--local",
            f"dockerfile={dockerfile.parent}",
            "--opt",
            f"filename={dockerfile.name}",
            "--opt",
            f"platform={request['targetPlatform']}",
            "--opt",
            f"target={request['targetStage']}",
            "--opt",
            "force-network-mode=none",
            "--output",
            f"type=oci,dest={archive},oci-mediatypes=true,name=saintvision.invalid/reference:{plan['traceId']}",
            "--metadata-file",
            str(metadata),
        )
        self._run(arguments, timeout=request["timeoutSeconds"])
        finished_at = self._now()
        try:
            metadata_value = json.loads(metadata.read_text(encoding="utf-8"))
            image_digest = metadata_value["containerimage.digest"]
            config_digest = metadata_value["containerimage.config.digest"]
            archive_sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            raise DomainError(
                "VERIFY-0002", "BuildKit output metadata is incomplete", 422
            ) from None
        if (
            not archive.is_file()
            or archive.stat().st_size <= 0
            or not isinstance(image_digest, str)
            or not _IMAGE_DIGEST.fullmatch(image_digest)
            or not isinstance(config_digest, str)
            or not _IMAGE_DIGEST.fullmatch(config_digest)
            or not _HEX_64.fullmatch(archive_sha256)
        ):
            raise DomainError("VERIFY-0002", "BuildKit output metadata is incomplete", 422)

        value = {
            "schemaVersion": 1,
            "targetKind": "ci-reference",
            "verdict": "MEASURED_PASS",
            "operationalAcceptanceAssessed": False,
            "productDispatchEnabled": False,
            "sourceCommitSha": head,
            "sourceTreeSha": tree,
            "builderInstanceId": measured.provider.builder_instance_id,
            "builderProfileId": measured.provider.builder_profile_id,
            "builderObservationDigest": measured.provider.observation_digest,
            "workerId": measured.worker_id,
            "platforms": list(measured.platforms),
            "buildkitVersion": measured.buildkit_version,
            "rootlesskitVersion": measured.rootlesskit_version,
            "isolation": measured.isolation,
            "processMeasurement": measured.process_measurement,
            "imageDigest": image_digest,
            "configDigest": config_digest,
            "ociArchiveSha256": archive_sha256,
            "commandArgumentsSha256": _canonical_digest(list(arguments)),
            "startedAt": started_at.isoformat(),
            "finishedAt": finished_at.isoformat(),
            "limitations": [
                "reference-only-no-product-consumer",
                "lease-release-not-bound",
                "evidence-persistence-not-bound",
                "lan-builder-acceptance-blocked-external",
            ],
        }
        report.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return value
