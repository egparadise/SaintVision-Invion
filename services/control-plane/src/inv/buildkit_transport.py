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
from pathlib import PurePosixPath
import re
import stat
import subprocess
import tarfile
from typing import Mapping, Protocol, Sequence

from .build_governance import BuildProviderObservation
from .contracts import validate_contract
from .errors import DomainError
from .policy import action_digest


TRANSPORT_ENABLE_SETTING = "INV_BUILDKIT_REFERENCE_ENABLED"
_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_HEX_40 = re.compile(r"[0-9a-f]{40}")
_HEX_64 = re.compile(r"[0-9a-f]{64}")
_IMAGE_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_PLATFORM_COMPONENT = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}")
_OCI_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
_OCI_CONFIG_MEDIA_TYPE = "application/vnd.oci.image.config.v1+json"
_OCI_LAYER_MEDIA_TYPES = frozenset(
    {
        "application/vnd.oci.image.layer.v1.tar",
        "application/vnd.oci.image.layer.v1.tar+gzip",
        "application/vnd.oci.image.layer.v1.tar+zstd",
    }
)
_MAX_OCI_ARCHIVE_BYTES = 512 * 1024 * 1024
_HEALTH_KEYS = frozenset(
    {
        "schemaVersion",
        "builderInstanceId",
        "builderProfileId",
        "recoveryEpoch",
        "address",
        "pid",
        "processUid",
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
        "fieldSources",
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
_CONTAINER_FIELD_SOURCES = {
    "pid": "container-proc-buildkitd",
    "processStartTicks": "container-proc-buildkitd",
    "rootless": "container-proc-user-namespace",
    "privileged": "docker-inspect-host-config",
    "hostAccess": "docker-inspect-rootless-boundary",
    "entitlements": "docker-inspect-config-command",
    "devices": "docker-inspect-host-config",
    "binds": "docker-inspect-host-config",
    "runtimeIdentity": "docker-repo-digest",
    "seccompMode": "docker-inspect-unconfined",
    "lsm": "docker-inspect-unconfined",
}
_PROCESS_FIELD_SOURCES = {
    "pid": "caller-passed-buildkitd-process",
    "processStartTicks": "proc-buildkitd-process",
    "rootless": "proc-uid-map",
    "privileged": "caller-asserted-reference-boundary",
    "hostAccess": "caller-asserted-reference-boundary",
    "entitlements": "caller-asserted-reference-boundary",
    "devices": "caller-asserted-reference-boundary",
    "binds": "caller-asserted-reference-boundary",
    "runtimeIdentity": "buildkitd-binary-sha256",
    "seccompMode": "proc-process-status",
    "lsm": "host-lsm-detection",
}


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


def _strict_json_document(raw: bytes, label: str) -> dict:
    """Decode an OCI JSON document without duplicate keys or non-finite values."""

    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError(f"duplicate key in {label}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError(label)),
        )
    except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
        raise DomainError("VERIFY-0002", "BuildKit OCI archive is invalid", 422) from None
    if not isinstance(value, dict):
        raise DomainError("VERIFY-0002", "BuildKit OCI archive is invalid", 422)
    return value


def _oci_descriptor(value: object, *, label: str, media_types: frozenset[str]) -> tuple[str, int]:
    if not isinstance(value, dict):
        raise DomainError("VERIFY-0002", "BuildKit OCI archive is invalid", 422)
    digest = value.get("digest")
    size = value.get("size")
    if (
        value.get("mediaType") not in media_types
        or not isinstance(digest, str)
        or not _IMAGE_DIGEST.fullmatch(digest)
        or type(size) is not int
        or size < 0
        or size > _MAX_OCI_ARCHIVE_BYTES
    ):
        raise DomainError("VERIFY-0002", f"BuildKit OCI {label} descriptor is invalid", 422)
    return digest, size


def _verify_oci_archive(path: Path, *, image_digest: str, config_digest: str) -> dict:
    """Recompute every referenced OCI blob digest and bind metadata to the archive."""

    try:
        observed = path.stat()
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_nlink != 1
            or observed.st_size <= 0
            or observed.st_size > _MAX_OCI_ARCHIVE_BYTES
        ):
            raise ValueError()
        files: dict[str, bytes] = {}
        total_bytes = 0
        with tarfile.open(path, mode="r:*") as archive:
            for member in archive.getmembers():
                pure = PurePosixPath(member.name)
                if (
                    member.name.startswith("/")
                    or "\\" in member.name
                    or ".." in pure.parts
                    or member.issym()
                    or member.islnk()
                    or not (member.isdir() or member.isfile())
                ):
                    raise ValueError()
                normalized = str(pure)
                if member.isdir():
                    continue
                if normalized in files or member.size < 0 or member.size > _MAX_OCI_ARCHIVE_BYTES:
                    raise ValueError()
                total_bytes += member.size
                if total_bytes > _MAX_OCI_ARCHIVE_BYTES:
                    raise ValueError()
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError()
                raw = stream.read(member.size + 1)
                if len(raw) != member.size:
                    raise ValueError()
                files[normalized] = raw
    except (OSError, tarfile.TarError, ValueError):
        raise DomainError("VERIFY-0002", "BuildKit OCI archive is invalid", 422) from None

    layout = _strict_json_document(files.get("oci-layout", b""), "oci-layout")
    index = _strict_json_document(files.get("index.json", b""), "index")
    manifests = index.get("manifests")
    if (
        layout != {"imageLayoutVersion": "1.0.0"}
        or index.get("schemaVersion") != 2
        or not isinstance(manifests, list)
        or len(manifests) != 1
    ):
        raise DomainError("VERIFY-0002", "BuildKit OCI archive is invalid", 422)

    manifest_digest, manifest_size = _oci_descriptor(
        manifests[0], label="manifest", media_types=frozenset({_OCI_MANIFEST_MEDIA_TYPE})
    )
    if manifest_digest != image_digest:
        raise DomainError("VERIFY-0002", "BuildKit OCI manifest digest differs", 422)

    def verified_blob(digest: str, expected_size: int) -> bytes:
        path_name = f"blobs/sha256/{digest.removeprefix('sha256:')}"
        raw = files.get(path_name)
        if (
            raw is None
            or len(raw) != expected_size
            or "sha256:" + hashlib.sha256(raw).hexdigest() != digest
        ):
            raise DomainError("VERIFY-0002", "BuildKit OCI blob digest differs", 422)
        return raw

    manifest_raw = verified_blob(manifest_digest, manifest_size)
    manifest = _strict_json_document(manifest_raw, "manifest")
    if manifest.get("schemaVersion") != 2 or manifest.get("mediaType") not in {
        None,
        _OCI_MANIFEST_MEDIA_TYPE,
    }:
        raise DomainError("VERIFY-0002", "BuildKit OCI manifest is invalid", 422)

    manifest_config_digest, manifest_config_size = _oci_descriptor(
        manifest.get("config"), label="config", media_types=frozenset({_OCI_CONFIG_MEDIA_TYPE})
    )
    if manifest_config_digest != config_digest:
        raise DomainError("VERIFY-0002", "BuildKit OCI config digest differs", 422)
    config_raw = verified_blob(manifest_config_digest, manifest_config_size)
    _strict_json_document(config_raw, "config")

    layers = manifest.get("layers")
    if not isinstance(layers, list) or not layers:
        raise DomainError("VERIFY-0002", "BuildKit OCI layers are invalid", 422)
    layer_digests = []
    referenced = {manifest_digest, manifest_config_digest}
    for index_value, layer in enumerate(layers):
        layer_digest, layer_size = _oci_descriptor(
            layer, label=f"layer {index_value}", media_types=_OCI_LAYER_MEDIA_TYPES
        )
        if layer_digest in referenced:
            raise DomainError("VERIFY-0002", "BuildKit OCI layer digest is duplicated", 422)
        verified_blob(layer_digest, layer_size)
        referenced.add(layer_digest)
        layer_digests.append(layer_digest)

    archived_blobs = {
        "sha256:" + name.removeprefix("blobs/sha256/")
        for name in files
        if name.startswith("blobs/sha256/")
    }
    if referenced != archived_blobs:
        raise DomainError("VERIFY-0002", "BuildKit OCI blob set differs", 422)
    return {
        "layoutVersion": "1.0.0",
        "manifestDigest": manifest_digest,
        "configDigest": manifest_config_digest,
        "layerDigests": layer_digests,
        "verifiedBlobCount": len(referenced),
    }


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


def _normalized_platforms(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise DomainError("RES-0006", "BuildKit worker inventory is invalid", 503, retryable=True)
    normalized = []
    for item in value:
        if isinstance(item, str):
            parts = item.split("/")
            if len(parts) not in {2, 3} or any(
                not _PLATFORM_COMPONENT.fullmatch(part) for part in parts
            ):
                raise DomainError(
                    "RES-0006", "BuildKit worker inventory is invalid", 503, retryable=True
                )
            normalized.append(item)
            continue
        if not isinstance(item, dict) or not {"os", "architecture"} <= set(item) <= {
            "os",
            "architecture",
            "variant",
        }:
            raise DomainError(
                "RES-0006", "BuildKit worker inventory is invalid", 503, retryable=True
            )
        operating_system = item.get("os")
        architecture = item.get("architecture")
        variant = item.get("variant")
        if (
            not isinstance(operating_system, str)
            or not _PLATFORM_COMPONENT.fullmatch(operating_system)
            or not isinstance(architecture, str)
            or not _PLATFORM_COMPONENT.fullmatch(architecture)
            or (
                variant is not None
                and (not isinstance(variant, str) or not _PLATFORM_COMPONENT.fullmatch(variant))
            )
        ):
            raise DomainError(
                "RES-0006", "BuildKit worker inventory is invalid", 503, retryable=True
            )
        normalized.append(
            f"{operating_system}/{architecture}"
            + (f"/{variant}" if isinstance(variant, str) else "")
        )
    return tuple(sorted(set(normalized)))


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
        field_sources = receipt.get("fieldSources")
        if (
            set(receipt) != _HEALTH_KEYS
            or receipt.get("schemaVersion") != 1
            or receipt.get("builderInstanceId") != self.configuration.builder_instance_id
            or receipt.get("builderProfileId") != self.configuration.builder_profile_id
            or receipt.get("recoveryEpoch") != self.configuration.recovery_epoch
            or receipt.get("address") != self.configuration.address
            or type(receipt.get("pid")) is not int
            or receipt["pid"] <= 1
            or type(receipt.get("processUid")) is not int
            or receipt["processUid"] <= 0
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
            or isolation.get("seccompMode")
            not in {"filter", "unavailable-ci-reference", "unconfined-ci-reference"}
            or isolation.get("lsm")
            not in {"apparmor", "selinux", "unavailable-ci-reference", "unconfined-ci-reference"}
            or type(isolation.get("noNewPrivileges")) is not bool
            or isolation.get("cgroupMode") not in {"v2", "unavailable-ci-reference"}
            or field_sources not in (_CONTAINER_FIELD_SOURCES, _PROCESS_FIELD_SOURCES)
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
        platforms = _normalized_platforms(worker.get("Platforms") or worker.get("platforms"))
        if not isinstance(worker_id, str) or not worker_id:
            raise DomainError(
                "RES-0006", "BuildKit worker inventory is invalid", 503, retryable=True
            )
        measurement = {
            "health": receipt,
            "workerId": worker_id,
            "platforms": list(platforms),
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
            platforms,
            receipt["buildkitVersion"],
            receipt["rootlesskitVersion"],
            dict(receipt["isolation"]),
            {
                "pid": receipt["pid"],
                "processUid": receipt["processUid"],
                "processStartTicks": receipt["processStartTicks"],
                "address": receipt["address"],
                "observedAt": receipt["observedAt"],
                "rootless": receipt["rootless"],
                "privileged": receipt["privileged"],
                "hostAccess": receipt["hostAccess"],
                "entitlements": list(receipt["entitlements"]),
                "runtimeIdentity": receipt["runtimeIdentity"],
                "fieldSources": dict(receipt["fieldSources"]),
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
        oci_verification = _verify_oci_archive(
            archive,
            image_digest=image_digest,
            config_digest=config_digest,
        )

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
            "ociVerification": oci_verification,
            "commandArgumentsSha256": _canonical_digest(list(arguments)),
            "startedAt": started_at.isoformat(),
            "finishedAt": finished_at.isoformat(),
            "limitations": [
                "reference-only-no-product-consumer",
                "lease-release-not-bound",
                "evidence-persistence-not-bound",
                "lan-builder-acceptance-blocked-external",
                "host-apparmor-userns-policy-relaxed",
            ],
        }
        report.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return value


#: Where the node agent leaves the product-grade receipts.  Both are read with the same
#: protections as the reference health receipt: no symlink, one link, small, owner-only.
#: This module collects them and checks the low-level file properties; the authority
#: comparison (``nodeId == leasedNodeId``, epoch agreement, required observations) is
#: ``inv.build_execution.BuildExecutionService``, and the strict field schemas are fixed
#: by the card 211 contract PR rather than here.
PRODUCT_HEALTH_RECEIPT = "product-health.json"
PRODUCT_CLEANUP_RECEIPT_PREFIX = "cleanup-"


class NodeAgentReceipts:
    """Read-only collector for the two node-agent receipts on this host.

    It deliberately has no write path and no network call: the node agent writes, the
    control plane reads.  A collector that could also produce a receipt would make the
    freshness of one the opinion of the other.
    """

    def __init__(self, directory: Path):
        self._directory = Path(directory)

    def collect_product_health(self) -> dict:
        return _protected_json(self._directory / PRODUCT_HEALTH_RECEIPT)

    def collect_cleanup_receipt(self, build_session_id: str) -> dict:
        if not isinstance(build_session_id, str) or not _SESSION_ID.fullmatch(build_session_id):
            raise DomainError(
                "VERIFY-0022", "Build cleanup receipt was asked for under an invalid session", 409
            )
        name = f"{PRODUCT_CLEANUP_RECEIPT_PREFIX}{build_session_id}.json"
        return _protected_json(self._directory / name)

    def daemon_identity(self) -> dict:
        """The daemon identity as the node agent currently reports it."""

        receipt = _protected_json(self._directory / PRODUCT_HEALTH_RECEIPT)
        daemon = receipt.get("daemon")
        if not isinstance(daemon, dict):
            raise DomainError(
                "RES-0006", "Node agent health receipt records no daemon", 503, retryable=True
            )
        return daemon

    def cancel_and_quarantine_session(self, build_session_id: str, reason_code: str) -> None:
        raise DomainError(
            "VERIFY-0022",
            "Node agent session cancellation is not connected",
            409,
        )

    def quarantine_node(self, node_id: str, reason_code: str) -> None:
        raise DomainError(
            "VERIFY-0022",
            "Node agent quarantine is not connected",
            409,
        )
