"""Bind hosted AC-11 accessibility evidence to an optional user-device session.

The access token is accepted only on stdin, verified by the product's offline
resource-server verifier, and never written or printed. Without a valid manual
session the imported axis remains MEASURED_FAIL with the completeness metric at 1.
Only ``main`` and its stdin-token CLI are a trust boundary. Underscore-prefixed
Python helpers are internal seams for already-trusted same-process tests.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

import collect_ac11_accessibility_e2e as collector


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "egparadise/SaintVision-Invion"
WORKFLOW_PATH = ".github/workflows/ac11-accessibility-e2e.yml"
REPORT_MEMBER = "s11-ac11-accessibility-e2e.json"
JUNIT_MEMBER = "s11-ac11-accessibility-e2e.xml"
MEMBERS = {REPORT_MEMBER, JUNIT_MEMBER}
REGISTRY_COMMIT = "0ee9542a4f9b8c640a68545ff83a28370c94152c"
REGISTRY_PATH = "docs/vault/30_Development/Evidence/s11-ac11-target-registry-v0.json"
REGISTRY_BLOB = "eeb43dc262f5de1816237ef85fc902cdca4ab6fd"
TARGET_ID = "s11-accessibility-user-device-v1"
EMITTED_AXES: tuple[str, ...] = ("accessibility-e2e",)
MINIMUM_PYTHON = (3, 11)
MANUAL_PURPOSE = "s11-ac11-accessibility-user-device-manual"
EXPECTED_SCENARIOS = {
    "ACC-MANUAL-KEYBOARD-JOURNEY",
    "ACC-MANUAL-SCREEN-READER-NAVIGATION",
    "ACC-MANUAL-SCREEN-READER-ERRORS",
    "ACC-MANUAL-FOCUS-ORDER",
    "ACC-MANUAL-ZOOM-REFLOW",
    "ACC-MANUAL-COGNITIVE-ERROR-RECOVERY",
}
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RUN_ID_RE = re.compile(r"^[0-9]+$")
UTC_RFC3339_RE = re.compile(
    r"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T"
    r"(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\.[0-9]{1,6})?Z$"
)
PLACEHOLDER_TOKENS = ("replace_with_", "todo", "tbd", "placeholder")
MANUAL_NOT_BEFORE = datetime(2026, 10, 2, tzinfo=timezone.utc)
_RECEIPT_SEAL = object()


class AccessibilityImportError(RuntimeError):
    """Fail-closed, redacted accessibility import error."""


@dataclass(frozen=True)
class _VerifiedPerformerReceipt:
    """Opaque proof that the product verifier produced this redacted receipt."""

    value: Mapping[str, Any]
    seal: object


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _strict_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise AccessibilityImportError(f"{label} contains a duplicate key")
            result[key] = value
        return result

    def invalid(_: str) -> None:
        raise AccessibilityImportError(f"{label} contains a non-finite number")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AccessibilityImportError(f"{label} is unreadable: {type(exc).__name__}") from None
    if not isinstance(value, dict):
        raise AccessibilityImportError(f"{label} must be a JSON object")
    return value


def _json_file(path: Path, label: str) -> dict[str, Any]:
    try:
        return _strict_json_bytes(path.read_bytes(), label)
    except OSError as exc:
        raise AccessibilityImportError(f"{label} is unreadable: {type(exc).__name__}") from None


def _utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not UTC_RFC3339_RE.fullmatch(value):
        raise AccessibilityImportError(f"{label} must be strict UTC RFC3339")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise AccessibilityImportError(f"{label} must be strict UTC RFC3339") from None
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise AccessibilityImportError(f"{label} must be UTC")
    return parsed


def _bounded_public_label(value: Any, label: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= maximum
        or any(token in value.strip().lower() for token in PLACEHOLDER_TOKENS)
        or "<" in value
        or ">" in value
        or any(ord(character) < 0x20 for character in value)
        or re.search(r"(?i)bearer\s|eyJ[A-Za-z0-9_-]{8,}|[^\s@]+@[^\s@]+", value)
    ):
        raise AccessibilityImportError(f"{label} is invalid or contains a secret-like value")
    return value


def _numeric(value: Any, label: str) -> str:
    text = str(value)
    if isinstance(value, bool) or not RUN_ID_RE.fullmatch(text):
        raise AccessibilityImportError(f"{label} must contain digits only")
    return text


def _artifact_digest(value: Any) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise AccessibilityImportError("artifact digest must use sha256")
    digest = value.removeprefix("sha256:")
    if not SHA256_RE.fullmatch(digest):
        raise AccessibilityImportError("artifact digest is malformed")
    return digest


def _archive_members(archive: bytes) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(BytesIO(archive)) as bundle:
            names = bundle.namelist()
            if set(names) != MEMBERS or len(names) != len(MEMBERS):
                raise AccessibilityImportError("artifact member set is not exact")
            result: dict[str, bytes] = {}
            for name in names:
                path = PurePosixPath(name)
                info = bundle.getinfo(name)
                if path.is_absolute() or ".." in path.parts or info.is_dir():
                    raise AccessibilityImportError("artifact member path is unsafe")
                result[name] = bundle.read(name)
            return result
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise AccessibilityImportError(
            f"artifact archive is unreadable: {type(exc).__name__}"
        ) from None


def _exact_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise AccessibilityImportError(f"{label} has an unsupported shape")
    return value


def validate_manual_session(session: dict[str, Any], source_sha: str) -> None:
    required = {
        "schemaVersion", "runPurpose", "sourceHeadSha", "startedAt", "finishedAt",
        "device", "browser", "assistiveTechnologies", "scenarios", "overallResult",
        "performedBy",
    }
    _exact_object(session, required, "manual session")
    if session["schemaVersion"] != "1.0.0" or session["runPurpose"] != MANUAL_PURPOSE:
        raise AccessibilityImportError("manual session version or purpose is unknown")
    if session["sourceHeadSha"] != source_sha or not SHA1_RE.fullmatch(str(source_sha)):
        raise AccessibilityImportError("manual session source SHA differs from hosted evidence")
    started = _utc(session["startedAt"], "manual startedAt")
    finished = _utc(session["finishedAt"], "manual finishedAt")
    if started < MANUAL_NOT_BEFORE:
        raise AccessibilityImportError("manual startedAt predates the registered target")
    if finished < started:
        raise AccessibilityImportError("manual finishedAt precedes startedAt")
    device = _exact_object(
        session["device"], {"class", "operatingSystem", "displayMode", "keyboard"}, "device"
    )
    if device["class"] not in {"desktop", "laptop", "tablet", "mobile"}:
        raise AccessibilityImportError("device class is unsupported")
    if device["displayMode"] not in {"standard", "high-contrast", "zoomed"}:
        raise AccessibilityImportError("display mode is unsupported")
    if device["keyboard"] not in {"physical", "on-screen", "switch-control"}:
        raise AccessibilityImportError("keyboard type is unsupported")
    _bounded_public_label(device["operatingSystem"], "device operatingSystem", 100)
    browser = _exact_object(session["browser"], {"name", "version", "engine"}, "browser")
    for key in browser:
        _bounded_public_label(browser[key], f"browser {key}", 80)
    technologies = session["assistiveTechnologies"]
    if not isinstance(technologies, list) or not 1 <= len(technologies) <= 4:
        raise AccessibilityImportError("assistive technology list is incomplete")
    for row in technologies:
        _exact_object(row, {"kind", "product", "version"}, "assistive technology")
        if row["kind"] not in {"screen-reader", "magnifier", "voice-control", "switch-control"}:
            raise AccessibilityImportError("assistive technology kind is unsupported")
        for key in ("product", "version"):
            _bounded_public_label(row[key], f"assistive technology {key}", 80)
    identities_for_technologies = [
        (row["kind"], row["product"], row["version"]) for row in technologies
    ]
    if len(identities_for_technologies) != len(set(identities_for_technologies)):
        raise AccessibilityImportError("assistive technology rows must be unique")
    if not any(row["kind"] == "screen-reader" for row in technologies):
        raise AccessibilityImportError("a measured screen reader is required")
    scenarios = session["scenarios"]
    if not isinstance(scenarios, list) or len(scenarios) != len(EXPECTED_SCENARIOS):
        raise AccessibilityImportError("manual scenario count is incomplete")
    identities: list[str] = []
    results: list[str] = []
    for row in scenarios:
        _exact_object(row, {"scenarioId", "result"}, "manual scenario")
        if not isinstance(row["scenarioId"], str):
            raise AccessibilityImportError("manual scenarioId must be a string")
        identities.append(row["scenarioId"])
        results.append(row["result"])
    if set(identities) != EXPECTED_SCENARIOS or len(identities) != len(set(identities)):
        raise AccessibilityImportError("manual scenario identity set drifted")
    if any(result not in {"PASS", "FAIL"} for result in results):
        raise AccessibilityImportError("manual scenario result is outside the closed enum")
    recomputed = "PASS" if all(result == "PASS" for result in results) else "FAIL"
    if session["overallResult"] != recomputed:
        raise AccessibilityImportError("manual overall result differs from scenarios")
    if session["performedBy"] != {
        "kind": "human", "binding": "self-attested-session"
    }:
        raise AccessibilityImportError("manual performer declaration is unsupported")


def _seal_performer_receipt(
    receipt: dict[str, Any], now: datetime
) -> _VerifiedPerformerReceipt:
    keys = {
        "kind", "binding", "subjectSha256", "tenantSha256", "issuerSha256",
        "clientIdSha256", "authTime", "amr", "tokenExpiresAt", "jwksSha256",
        "verifiedAt",
    }
    _exact_object(receipt, keys, "performer receipt")
    if receipt["kind"] != "human" or receipt["binding"] != "oidc-fresh-auth-v1":
        raise AccessibilityImportError("performer receipt binding is unsupported")
    for field in (
        "subjectSha256", "tenantSha256", "issuerSha256", "clientIdSha256", "jwksSha256"
    ):
        if not isinstance(receipt[field], str) or not SHA256_RE.fullmatch(receipt[field]):
            raise AccessibilityImportError(f"performer receipt {field} is malformed")
    if type(receipt["authTime"]) is not int or type(receipt["tokenExpiresAt"]) is not int:
        raise AccessibilityImportError("performer receipt token times are malformed")
    if receipt["tokenExpiresAt"] <= int(now.timestamp()):
        raise AccessibilityImportError("performer receipt token is expired")
    amr = receipt["amr"]
    if not isinstance(amr, list) or amr != sorted(set(amr)) or not amr:
        raise AccessibilityImportError("performer receipt AMR is malformed")
    verified_at = _utc(receipt["verifiedAt"], "performer verifiedAt")
    if verified_at > now or (now - verified_at).total_seconds() > 300:
        raise AccessibilityImportError("performer receipt is stale or future-dated")
    return _VerifiedPerformerReceipt(dict(receipt), _RECEIPT_SEAL)


def _verified_receipt_value(receipt: object, now: datetime) -> dict[str, Any]:
    if not isinstance(receipt, _VerifiedPerformerReceipt) or receipt.seal is not _RECEIPT_SEAL:
        raise AccessibilityImportError(
            "manual import requires a receipt produced by fresh token verification"
        )
    # Revalidate at use time so a long-lived in-process object cannot outlive freshness.
    return dict(_seal_performer_receipt(dict(receipt.value), now).value)


def verify_human_token(
    token: str,
    *,
    tenant_id: str,
    issuer: str,
    audience: str,
    client_id: str,
    jwks_file: Path,
    now: datetime,
    token_verifier: Any | None = None,
) -> _VerifiedPerformerReceipt:
    if now.tzinfo is None:
        raise AccessibilityImportError("verification clock must be timezone-aware")
    services = ROOT / "services" / "control-plane" / "src"
    source = ROOT / "src"
    for path in (services, source):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from saintvision.identity.principal import Principal, has_fresh_interactive_auth

    if token_verifier is None:
        from inv.identity import AccessTokens, trusted_file

        jwks_before = trusted_file(jwks_file)
        token_verifier = AccessTokens(
            tenant_id=tenant_id,
            issuer=issuer,
            audience=audience,
            client_ids=[client_id],
            jwks_file=jwks_file,
        )
        trusted_jwks = trusted_file
    else:
        jwks_before = jwks_file.read_bytes()
        trusted_jwks = lambda path: Path(path).read_bytes()
    try:
        identity = token_verifier.verify(token)
        principal = Principal(
            user_id="manual-accessibility-import",
            tenant_id=__import__("uuid").UUID(identity.principal.tenant_id),
            external_subject=identity.principal.subject_id,
            verified_fresh_auth_claims=True,
            auth_time=identity.auth_time,
            amr=frozenset(identity.amr),
            verified_token_issuer=identity.issuer,
            verified_token_client_id=identity.client_id,
            verified_token_expires_at=identity.expires_at,
        )
        if identity.expires_at <= int(now.timestamp()) or not has_fresh_interactive_auth(
            principal, now=now
        ):
            raise AccessibilityImportError("fresh interactive human authentication is required")
        if identity.issuer != issuer or identity.client_id != client_id:
            raise AccessibilityImportError("verified token provenance differs from import policy")
        jwks_after = trusted_jwks(jwks_file)
        if jwks_after != jwks_before:
            raise AccessibilityImportError("JWKS bundle changed during verification")
    except AccessibilityImportError:
        raise
    except Exception as exc:  # noqa: BLE001 - type-only redacted boundary
        raise AccessibilityImportError(
            f"fresh-auth verification refused: {type(exc).__name__}"
        ) from None
    return _seal_performer_receipt({
        "kind": "human",
        "binding": "oidc-fresh-auth-v1",
        "subjectSha256": hashlib.sha256(identity.principal.subject_id.encode()).hexdigest(),
        "tenantSha256": hashlib.sha256(identity.principal.tenant_id.encode()).hexdigest(),
        "issuerSha256": hashlib.sha256(identity.issuer.encode()).hexdigest(),
        "clientIdSha256": hashlib.sha256(identity.client_id.encode()).hexdigest(),
        "authTime": identity.auth_time,
        "amr": sorted(identity.amr),
        "tokenExpiresAt": identity.expires_at,
        "jwksSha256": hashlib.sha256(jwks_before).hexdigest(),
        "verifiedAt": now.isoformat().replace("+00:00", "Z"),
    }, now)


def _validate_producer(report: dict[str, Any]) -> None:
    if report.get("schemaVersion") != collector.SCHEMA_VERSION:
        raise AccessibilityImportError("producer schemaVersion is unsupported")
    if report.get("runPurpose") != collector.RUN_PURPOSE or report.get("axis") != collector.AXIS:
        raise AccessibilityImportError("producer purpose or axis is unsupported")
    if report.get("acceptanceClaim") is not False:
        raise AccessibilityImportError("producer fabricated an acceptance claim")
    target = report.get("targetRef")
    expected_target = {
        "commit": collector.TARGET_COMMIT,
        "path": collector.TARGET_PATH,
        "blob": collector.TARGET_BLOB,
        "criteria": collector.CRITERIA,
    }
    if target != expected_target:
        raise AccessibilityImportError("producer target differs from the reviewed target")
    payload = report.get("payload")
    if not isinstance(payload, dict) or report.get("payloadSha256") != canonical_sha256(payload):
        raise AccessibilityImportError("producer payload digest differs from payload")
    observations = payload.get("observations")
    if not isinstance(observations, list) or {
        row.get("metric") for row in observations if isinstance(row, dict)
    } != set(collector.CRITERIA):
        raise AccessibilityImportError("producer observation identity set drifted")
    manual = [row for row in observations if row.get("metric") == "manualAcceptanceMissingCount"]
    if len(manual) != 1 or manual[0] != collector._observation(
        "manualAcceptanceMissingCount", 1, 1, "manual-acceptance-not-supplied"
    ):
        raise AccessibilityImportError("producer did not preserve fail-closed manual completeness")


def import_evidence(
    archive: bytes,
    run_metadata: dict[str, Any],
    artifact_metadata: dict[str, Any],
    *,
    manual_session: dict[str, Any] | None = None,
    performer_receipt: _VerifiedPerformerReceipt | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    members = _archive_members(archive)
    report = _strict_json_bytes(members[REPORT_MEMBER], "producer report")
    _validate_producer(report)
    source = report.get("sourceHeadSha")
    source_run_id = report.get("sourceRunId")
    if not isinstance(source, str) or not SHA1_RE.fullmatch(source):
        raise AccessibilityImportError("producer sourceHeadSha is malformed")
    if not isinstance(source_run_id, str) or not RUN_ID_RE.fullmatch(source_run_id):
        raise AccessibilityImportError("producer sourceRunId is malformed")
    run_id = _numeric(run_metadata.get("id"), "run metadata id")
    workflow_run = artifact_metadata.get("workflow_run")
    if not isinstance(workflow_run, dict):
        raise AccessibilityImportError("artifact workflow_run metadata is missing")
    artifact_run_id = _numeric(workflow_run.get("id"), "artifact workflow run id")
    artifact_id = _numeric(artifact_metadata.get("id"), "artifact id")
    if source_run_id != run_id or source_run_id != artifact_run_id:
        raise AccessibilityImportError("sourceRunId differs from GitHub metadata")
    if run_metadata.get("status") != "completed" or run_metadata.get("conclusion") != "success":
        raise AccessibilityImportError("GitHub run did not complete successfully")
    if run_metadata.get("head_sha") != source or workflow_run.get("head_sha") != source:
        raise AccessibilityImportError("GitHub run or artifact head differs from sourceHeadSha")
    repository = run_metadata.get("repository")
    if not isinstance(repository, dict) or repository.get("full_name") != REPOSITORY:
        raise AccessibilityImportError("run repository is not canonical")
    if str(run_metadata.get("path", "")).split("@", 1)[0] != WORKFLOW_PATH:
        raise AccessibilityImportError("run workflow path is not canonical")
    if run_metadata.get("event") not in {"pull_request", "workflow_dispatch"}:
        raise AccessibilityImportError("run event is not an approved opt-in trigger")
    expected_name = f"s11-ac11-accessibility-{source}"
    if artifact_metadata.get("name") != expected_name:
        raise AccessibilityImportError("artifact name is not bound to sourceHeadSha")
    if artifact_metadata.get("expired") is not False:
        raise AccessibilityImportError("artifact is expired or expiration state is unknown")
    expires_at = _utc(artifact_metadata.get("expires_at"), "artifact expiresAt")
    if expires_at <= observed_now:
        raise AccessibilityImportError("artifact is expired")
    expected_digest = _artifact_digest(artifact_metadata.get("digest"))
    observed_digest = hashlib.sha256(archive).hexdigest()
    if expected_digest != observed_digest:
        raise AccessibilityImportError("downloaded artifact digest differs from GitHub metadata")

    if (manual_session is None) != (performer_receipt is None):
        raise AccessibilityImportError("manual session and verified performer receipt are inseparable")
    bound = report
    if manual_session is not None and performer_receipt is not None:
        validate_manual_session(manual_session, source)
        receipt_value = _verified_receipt_value(performer_receipt, observed_now)
        manual_started = _utc(manual_session["startedAt"], "manual startedAt")
        manual_finished = _utc(manual_session["finishedAt"], "manual finishedAt")
        if manual_finished > observed_now:
            raise AccessibilityImportError("manual finishedAt is in the future")
        hosted_finished = _utc(report.get("finishedAt"), "producer finishedAt")
        if manual_started < hosted_finished:
            raise AccessibilityImportError("manual session predates the hosted exact-SHA run")
        auth_time = datetime.fromtimestamp(receipt_value["authTime"], timezone.utc)
        verified_at = _utc(receipt_value["verifiedAt"], "performer verifiedAt")
        if auth_time < manual_finished or verified_at < manual_finished:
            raise AccessibilityImportError(
                "fresh import authorization must be obtained after the manual session"
            )
        manual_acceptance = {
            **manual_session,
            "sessionSha256": canonical_sha256(manual_session),
            "importAuthorizationReceipt": receipt_value,
        }
        bound = collector.bind_verified_manual_acceptance(report, manual_acceptance)

    return {
        "schemaVersion": "1.0.0",
        "runPurpose": "ac11-axis-evidence",
        "axis": EMITTED_AXES[0],
        "verdict": bound["verdict"],
        "sourceRunId": source_run_id,
        "sourceHeadSha": source,
        "checkoutTreeSha": bound["checkoutTreeSha"],
        "artifactSha256": expected_digest,
        "artifactObservedSha256": observed_digest,
        "artifactAvailable": True,
        "artifactExpiresAt": expires_at.isoformat().replace("+00:00", "Z"),
        "cleanCheckout": bound["cleanCheckout"],
        "runConclusion": "success",
        "startedAt": bound["startedAt"],
        "finishedAt": (
            manual_session["finishedAt"] if manual_session is not None else bound["finishedAt"]
        ),
        "environment": {
            "comparableGroup": "ac11-accessibility-user-device-v1",
            "topology": "hosted-plus-user-device",
            "evidenceClass": "accessibility-manual-v1",
            "humanBindingPolicy": "fresh-human-import-authorization-v1",
            "automaticRunner": bound["environment"],
            "manualDeviceMeasured": manual_session is not None,
        },
        "targetRef": {
            "commit": REGISTRY_COMMIT,
            "path": REGISTRY_PATH,
            "blob": REGISTRY_BLOB,
            "targetId": TARGET_ID,
            "criteria": collector.CRITERIA,
        },
        "observations": bound["payload"]["observations"],
        "cleanup": {"residueCount": 0},
        "producerReportSha256": hashlib.sha256(members[REPORT_MEMBER]).hexdigest(),
        "junitSha256": hashlib.sha256(members[JUNIT_MEMBER]).hexdigest(),
        "manualAcceptance": bound["payload"].get("manualAcceptance"),
    }


def _token_from_stdin() -> str:
    raw = sys.stdin.read(16386)
    if len(raw) > 16385:
        raise AccessibilityImportError("access token input exceeds the bounded size")
    token = raw.strip()
    if not token:
        raise AccessibilityImportError("access token stdin is empty")
    return token


def main(argv: list[str] | None = None) -> int:
    # Check before argparse, file reads, and especially stdin.  On an unsupported
    # interpreter a fresh bearer token must remain completely unread.
    if sys.version_info[:2] < MINIMUM_PYTHON:
        print(
            "AC-11 accessibility import requires Python 3.11 or newer; "
            "access-token stdin was not read",
            file=sys.stderr,
        )
        return 2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--run-metadata", type=Path, required=True)
    parser.add_argument("--artifact-metadata", type=Path, required=True)
    parser.add_argument("--manual-session", type=Path)
    parser.add_argument("--access-token-stdin", action="store_true")
    parser.add_argument("--tenant-id")
    parser.add_argument("--issuer")
    parser.add_argument("--audience")
    parser.add_argument("--client-id")
    parser.add_argument("--jwks-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manual = _json_file(args.manual_session, "manual session") if args.manual_session else None
        receipt = None
        auth_values = [args.tenant_id, args.issuer, args.audience, args.client_id, args.jwks_file]
        if manual is not None:
            if not args.access_token_stdin or any(value is None for value in auth_values):
                raise AccessibilityImportError("manual import requires stdin token and complete verifier policy")
            now = datetime.now(timezone.utc)
            receipt = verify_human_token(
                _token_from_stdin(),
                tenant_id=args.tenant_id,
                issuer=args.issuer,
                audience=args.audience,
                client_id=args.client_id,
                jwks_file=args.jwks_file,
                now=now,
            )
        elif args.access_token_stdin or any(value is not None for value in auth_values):
            raise AccessibilityImportError("verifier inputs are invalid without a manual session")
        result = import_evidence(
            args.archive.read_bytes(),
            _json_file(args.run_metadata, "run metadata"),
            _json_file(args.artifact_metadata, "artifact metadata"),
            manual_session=manual,
            performer_receipt=receipt,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (AccessibilityImportError, OSError) as exc:
        print(f"AC-11 accessibility import refused: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - type-only redacted boundary
        print(f"AC-11 accessibility import errored: {type(exc).__name__}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
