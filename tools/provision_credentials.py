"""Operator-only credential metadata and Run grants; never writes secret files.

Set INV_CREDENTIAL_ADMIN_DSN through protected process configuration. Supply a
private JSON manifest and --root pointing to the service-owned Linux directory.
Default --check validates without writing. --apply explicitly commits one action.
register does not grant access; rotate replaces only the manifest's Run grant.
A revoked/expired grant is never reactivated by replay. This is not a public API.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "services/control-plane/src")]

from saintvision.credentials.contract import CredentialDenied
from saintvision.credentials.linux_file import CredentialBinding, LinuxFileCredentials
from saintvision.adapters.reference import recognised_secrets
from inv.runs import event

PURPOSES = {
    "llm.invoke",
    "git.read",
    "git.publish",
    "storage.read",
    "storage.write",
    "storage.gc",
    "backup.write",
    "backup.restore",
}

# CLI exit contract shared with plan_lan_migration.py:
# 0 success, 1 normal business result, 2 intentional refusal,
# 3 database/driver failure, 4 unexpected internal defect.
EXIT_REFUSED = 2
EXIT_DATABASE = 3
EXIT_INTERNAL = 4


class ProvisioningDenied(Exception):
    def __init__(self):
        super().__init__("Credential provisioning refused")


class ProvisioningDatabaseError(Exception):
    """A database/driver failure, reported without DSNs or SQL text."""

    def __init__(self, sqlstate=None):
        self.sqlstate = sqlstate if isinstance(sqlstate, str) and re.fullmatch(r"[0-9A-Z]{5}", sqlstate) else "unknown"
        super().__init__("Credential provisioning database operation failed")


class ProvisioningInternalError(Exception):
    """An unexpected provisioning defect, without carrying secret-bearing text."""

    def __init__(self, error_type):
        self.error_type = error_type if isinstance(error_type, str) else "Exception"
        super().__init__("Credential provisioning internal error")


def validate_manifest(value, action):
    try:
        required = {"tenant", "project", "subject", "run", "epoch", "credential", "version"}
        if action in {"register", "rotate"}:
            required |= {"file", "purpose", "destination"}
        if action in {"grant", "rotate"}:
            required.add("expires")
        if action == "rotate":
            required.add("oldVersion")
        if (
            action not in {"register", "grant", "revoke", "rotate"}
            or not isinstance(value, dict)
            or set(value) != required
        ):
            raise ProvisioningDenied()
        m = dict(value)
        for key in ("tenant", "epoch", "credential", "version") + (
            ("oldVersion",) if action == "rotate" else ()
        ):
            if not isinstance(m[key], str) or str(UUID(m[key])) != m[key]:
                raise ProvisioningDenied()
        for key, prefix in (("project", "prj"), ("run", "run")):
            if not isinstance(m[key], str) or not re.fullmatch(
                prefix + r"_[0-9A-HJKMNP-TV-Z]{26}", m[key]
            ):
                raise ProvisioningDenied()
        if (
            not isinstance(m["subject"], str)
            or not re.fullmatch(r"[A-Za-z0-9:_-]{1,200}", m["subject"])
            or recognised_secrets(m["subject"])
        ):
            raise ProvisioningDenied()
        if "file" in m:
            if not isinstance(m["file"], str) or not re.fullmatch(
                r"[0-9a-f]{32}[.]secret", m["file"]
            ):
                raise ProvisioningDenied()
            if (
                m["purpose"] not in PURPOSES
                or not isinstance(m["destination"], str)
                or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", m["destination"])
            ):
                raise ProvisioningDenied()
        if "expires" in m:
            m["expires"] = datetime.fromisoformat(m["expires"])
            if m["expires"].tzinfo is None:
                raise ProvisioningDenied()
            m["expires"] = m["expires"].astimezone(timezone.utc)
        if action == "rotate" and m["oldVersion"] == m["version"]:
            raise ProvisioningDenied()
        return m
    except ProvisioningDenied:
        raise
    except Exception:
        raise ProvisioningDenied() from None


def inspect_existing(provider, file_name):
    """Compute private metadata, then verify using the existing runtime reader."""
    root_fd = provider._open_root()
    fd = None
    try:
        fd = os.open(
            file_name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=root_fd
        )
        info = os.fstat(fd)
        binding = CredentialBinding(file_name, info.st_dev, info.st_ino, "0" * 64)
        provider._check_file(info, binding)
        digest, count = hashlib.sha256(), 0
        while True:
            part = os.read(fd, min(8192, 65537 - count))
            if not part:
                break
            count += len(part)
            if count > 65536:
                raise ProvisioningDenied()
            digest.update(part)
        binding = CredentialBinding(file_name, info.st_dev, info.st_ino, digest.hexdigest())
        provider._read(binding)
        return binding
    except OSError:
        # ``file_name`` is an untrusted manifest field.  Linux reports policy
        # boundary failures such as O_NOFOLLOW rejecting a symlink as OSError
        # (ELOOP), while the runtime reader deliberately maps the same family
        # to CredentialDenied.  Keep registration/rotation fail-closed and
        # consistent with that public contract instead of calling it an
        # internal provisioning defect.
        raise ProvisioningDenied() from None
    finally:
        if fd is not None:
            os.close(fd)
        os.close(root_fd)


def provision(dsn, root, manifest, action, *, apply=False):
    """One explicit transaction. Operator identity comes from PostgreSQL."""
    import psycopg
    from psycopg.rows import dict_row

    try:
        m = validate_manifest(manifest, action)
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            conn.execute("SET LOCAL lock_timeout='2s'")
            conn.execute("SET LOCAL statement_timeout='5s'")
            role = conn.execute("""SELECT current_user AS actor, r.rolsuper,
                r.oid=c.relowner AS owns_table FROM pg_roles r
                JOIN pg_class c ON c.oid='inv.credential_versions'::regclass
                WHERE r.rolname=current_user""").fetchone()
            if not role or not (role["rolsuper"] or role["owns_table"]):
                raise ProvisioningDenied()
            conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (m["tenant"],))
            epoch = conn.execute(
                "SELECT epoch FROM inv.control_epoch WHERE singleton FOR SHARE"
            ).fetchone()
            if not epoch or str(epoch["epoch"]) != m["epoch"]:
                raise ProvisioningDenied()
            gate = conn.execute(
                "SELECT tenant_id FROM inv.tenant_controls WHERE tenant_id=%s FOR SHARE",
                (m["tenant"],),
            ).fetchone()
            run = conn.execute(
                "SELECT state FROM inv.runs WHERE tenant_id=%s AND project_id=%s AND run_id=%s FOR UPDATE",
                (m["tenant"], m["project"], m["run"]),
            ).fetchone()
            if not gate or not run:
                raise ProvisioningDenied()
            # Revocation remains possible after cancellation or project disable.
            if action != "revoke":
                grant = conn.execute(
                    "SELECT enabled,can_request FROM inv.project_grants WHERE tenant_id=%s AND project_id=%s AND subject_id=%s FOR SHARE",
                    (m["tenant"], m["project"], m["subject"]),
                ).fetchone()
                if (
                    run["state"] in ("succeeded", "failed", "cancelled")
                    or not grant
                    or not grant["enabled"]
                    or not grant["can_request"]
                ):
                    raise ProvisioningDenied()
                if (
                    "expires" in m
                    and not conn.execute(
                        "SELECT %s > clock_timestamp() AS valid", (m["expires"],)
                    ).fetchone()["valid"]
                ):
                    raise ProvisioningDenied()
            key = (m["tenant"], m["project"], m["credential"])

            def version(v):
                return conn.execute(
                    "SELECT * FROM inv.credential_versions WHERE tenant_id=%s AND project_id=%s AND credential_id=%s AND version_id=%s",
                    key + (v,),
                ).fetchone()

            def grant_row(v):
                return conn.execute(
                    "SELECT *, expires_at>clock_timestamp() AS unexpired FROM inv.credential_grants WHERE tenant_id=%s AND project_id=%s AND credential_id=%s AND version_id=%s AND subject_id=%s AND run_id=%s FOR UPDATE",
                    key + (v, m["subject"], m["run"]),
                ).fetchone()

            def revoke(v):
                row = grant_row(v)
                if not row:
                    raise ProvisioningDenied()
                changed = row["enabled"] or row["revoked_at"] is None
                if apply and changed:
                    conn.execute(
                        "UPDATE inv.credential_grants SET enabled=false,revoked_at=coalesce(revoked_at,clock_timestamp()) WHERE tenant_id=%s AND project_id=%s AND credential_id=%s AND version_id=%s AND subject_id=%s AND run_id=%s",
                        key + (v, m["subject"], m["run"]),
                    )
                return changed

            changed = False
            current = version(m["version"])
            if action == "revoke":
                if not current:
                    raise ProvisioningDenied()
                changed = revoke(m["version"])
            else:
                provider = LinuxFileCredentials(root, None)
                if action in {"register", "rotate"}:
                    binding = inspect_existing(provider, m["file"])
                    values = dict(
                        purpose=m["purpose"],
                        destination=m["destination"],
                        file_name=binding.file_name,
                        device=binding.device,
                        inode=binding.inode,
                        content_sha256=binding.content_sha256,
                    )
                    if current and any(current[k] != v for k, v in values.items()):
                        raise ProvisioningDenied()
                    if not current:
                        changed = True
                        if apply:
                            conn.execute(
                                "INSERT INTO inv.credential_versions(tenant_id,project_id,credential_id,version_id,purpose,destination,file_name,device,inode,content_sha256) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                key + (m["version"], *values.values()),
                            )
                        current = values
                elif not current:
                    raise ProvisioningDenied()
                binding = CredentialBinding(
                    **{k: current[k] for k in ("file_name", "device", "inode", "content_sha256")}
                )
                provider._read(binding)
                if action == "rotate":
                    old = version(m["oldVersion"])
                    if not old or any(old[k] != current[k] for k in ("purpose", "destination")):
                        raise ProvisioningDenied()
                    old_grant = grant_row(m["oldVersion"])
                    new_grant = grant_row(m["version"])
                    if not old_grant:
                        raise ProvisioningDenied()
                    old_active = (
                        old_grant["enabled"]
                        and old_grant["revoked_at"] is None
                        and old_grant["unexpired"]
                        and str(old_grant["recovery_epoch"]) == m["epoch"]
                    )
                    # A competing rotation or explicit revocation cannot be
                    # turned into a new grant. Only an already completed exact
                    # replay may proceed with an inactive predecessor.
                    if not old_active and not new_grant:
                        raise ProvisioningDenied()
                    changed = revoke(m["oldVersion"]) or changed
                if action in {"grant", "rotate"}:
                    prior = grant_row(m["version"])
                    if prior:
                        if (
                            not prior["enabled"]
                            or prior["revoked_at"] is not None
                            or not prior["unexpired"]
                            or str(prior["recovery_epoch"]) != m["epoch"]
                            or prior["expires_at"] != m["expires"]
                        ):
                            raise ProvisioningDenied()
                    else:
                        changed = True
                        if apply:
                            conn.execute(
                                "INSERT INTO inv.credential_grants(tenant_id,project_id,credential_id,version_id,subject_id,run_id,enabled,expires_at,recovery_epoch) VALUES(%s,%s,%s,%s,%s,%s,true,%s,%s)",
                                key
                                + (m["version"], m["subject"], m["run"], m["expires"], m["epoch"]),
                            )
            if apply and changed:
                event(
                    conn,
                    m["tenant"],
                    m["run"],
                    "inv.credential." + action,
                    {
                        "credentialId": m["credential"],
                        "versionId": m["version"],
                        "subjectId": m["subject"],
                        "operatorRole": role["actor"],
                        **({"oldVersionId": m["oldVersion"]} if action == "rotate" else {}),
                    },
                )
            return {
                "action": action,
                "status": ("applied" if changed else "unchanged") if apply else "checked",
                "reference": f"svcred:1:{m['credential']}:{m['version']}",
                "executionAuthorized": False,
            }
    except ProvisioningDenied:
        raise
    except CredentialDenied:
        raise ProvisioningDenied() from None
    except psycopg.Error as error:
        raise ProvisioningDatabaseError(getattr(error, "sqlstate", None)) from None
    except Exception as error:
        # Keep rollback in the connection context manager, but never expose
        # exception text (it may contain a DSN or a credential).  The type is
        # sufficient for the caller to distinguish an internal defect from a
        # policy refusal or a database/driver failure.
        raise ProvisioningInternalError(type(error).__name__) from None


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "Invalid credential provisioning arguments; see --help.\n")


def main():
    parser = SafeParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("action", choices=["register", "grant", "revoke", "rotate"])
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--dsn-env", default="INV_CREDENTIAL_ADMIN_DSN")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.dsn_env):
            raise ProvisioningDenied()
        dsn = os.environ.get(args.dsn_env)
        if not dsn:
            raise ProvisioningDenied()
        with open(args.manifest, "rb") as f:
            raw = f.read(32769)
        if len(raw) > 32768:
            raise ProvisioningDenied()
        manifest = json.loads(raw)
        result = provision(dsn, args.root, manifest, args.action, apply=args.apply)
        print(json.dumps(result))
        return 0
    except (ProvisioningDenied, json.JSONDecodeError, UnicodeDecodeError):
        print(json.dumps({"error": "credential_provisioning_refused"}))
        return EXIT_REFUSED
    except ProvisioningDatabaseError as error:
        print(json.dumps({"error": "credential_provisioning_database_error", "sqlstate": error.sqlstate}))
        return EXIT_DATABASE
    except ProvisioningInternalError as error:
        print(json.dumps({"error": "credential_provisioning_internal_error", "errorType": error.error_type}))
        return EXIT_INTERNAL
    except (TypeError, KeyError, AttributeError) as error:
        print(json.dumps({"error": "credential_provisioning_internal_error", "errorType": type(error).__name__}))
        return EXIT_INTERNAL
    except Exception as error:
        print(json.dumps({"error": "credential_provisioning_internal_error", "errorType": type(error).__name__}))
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
