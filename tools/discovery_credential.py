"""Issue and revoke one-time-visible discovery-only Node credentials.

The designated operator DB login must be explicitly granted membership in
``inv_discovery_issuer`` by the database administrator. Plaintext credentials
are never accepted as arguments, written to files, or sent to SQL; issue prints
one new secret to stdout only after the transaction commits.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import os
import re
import sys
import uuid

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "services/control-plane/src")]

from saintvision.identity.discovery_credentials import DISCOVERY_SCOPE, TOKEN_TTL, token_sha256
from saintvision.services.discovery_credentials import new_secret
from saintvision.ids import new_id

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_DATABASE = 3
EXIT_INTERNAL = 4
INSTALLATION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ISSUER_DSN_ENV = "INV_DISCOVERY_ISSUER_DSN"


class Refused(Exception):
    pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Issue or revoke short-lived, installation-bound discovery credentials."
    )
    sub = parser.add_subparsers(dest="action", required=True)
    issue = sub.add_parser("issue", help="rotate and issue a 15-minute grant")
    issue.add_argument("--tenant", required=True, help="tenant UUID")
    issue.add_argument("--installation", required=True, help="stable Node installation ID")
    issue.add_argument("--apply", action="store_true", help="commit and display the secret once")
    revoke = sub.add_parser("revoke", help="revoke an issued grant")
    revoke.add_argument("--tenant", required=True, help="tenant UUID")
    revoke.add_argument("--credential-id", required=True, help="dcr_ credential ID")
    revoke.add_argument("--apply", action="store_true", help="commit the revocation")
    return parser


def _validated(args):
    try:
        tenant_id = uuid.UUID(args.tenant)
    except (ValueError, TypeError, AttributeError):
        raise Refused("tenant must be a UUID") from None
    if args.action == "issue":
        if not INSTALLATION_RE.fullmatch(args.installation):
            raise Refused("installation ID must be 1..128 safe ASCII characters")
    elif not re.fullmatch(r"dcr_[0-9A-HJKMNP-TV-Z]{26}", args.credential_id):
        raise Refused("credential ID is not valid")
    return tenant_id


def _operator_role(conn) -> str:
    row = conn.execute(
        "SELECT session_user AS actor, "
        "pg_has_role(session_user, 'inv_discovery_issuer', 'MEMBER') AS allowed"
    ).fetchone()
    if not row or not row["allowed"]:
        raise Refused("database login is not an authorized discovery issuer")
    conn.execute("SET LOCAL ROLE inv_discovery_issuer")
    return row["actor"]


def _event(conn, *, tenant, credential, installation, actor, kind, outcome, reason, now):
    conn.execute(
        "INSERT INTO discovery_credential_events "
        "(event_id, tenant_id, credential_id, installation_id, actor, event_type, outcome, reason_code, occurred_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (uuid.uuid4(), tenant, credential, installation, actor, kind, outcome, reason, now),
    )


def _issue(conn, *, tenant, installation, actor, secret, now):
    if not conn.execute("SELECT 1 FROM public.tenants WHERE tenant_id=%s", (tenant,)).fetchone():
        raise Refused("tenant was not found")
    previous = conn.execute(
        "SELECT credential_id, announcement_id, last_announcement_at "
        "FROM discovery_machine_credentials "
        "WHERE tenant_id=%s AND installation_id=%s AND revoked_at IS NULL FOR UPDATE",
        (tenant, installation),
    ).fetchall()
    links = {
        (row["announcement_id"], row["last_announcement_at"])
        for row in previous
        if row["announcement_id"] is not None
    }
    if len(links) > 1:
        raise Refused("existing discovery grant links are inconsistent; no rotation performed")
    announcement_id, last_announcement_at = next(iter(links), (None, None))
    for row in previous:
        conn.execute(
            "UPDATE discovery_machine_credentials SET revoked_at=%s WHERE credential_id=%s",
            (now, row["credential_id"]),
        )
        _event(
            conn,
            tenant=tenant,
            credential=row["credential_id"],
            installation=installation,
            actor=actor,
            kind="revoked",
            outcome="allow",
            reason="rotated",
            now=now,
        )
    credential_id = new_id("discovery_credential")
    expires = now + TOKEN_TTL
    conn.execute(
        "INSERT INTO discovery_machine_credentials "
        "(credential_id,tenant_id,installation_id,scope,token_sha256,issued_by,issued_at,expires_at,"
        "announcement_id,last_announcement_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            credential_id,
            tenant,
            installation,
            DISCOVERY_SCOPE,
            token_sha256(secret),
            actor,
            now,
            expires,
            announcement_id,
            last_announcement_at,
        ),
    )
    _event(
        conn,
        tenant=tenant,
        credential=credential_id,
        installation=installation,
        actor=actor,
        kind="issued",
        outcome="allow",
        reason="operator_cli",
        now=now,
    )
    return credential_id, expires


def _revoke(conn, *, tenant, credential_id, actor, now):
    row = conn.execute(
        "SELECT credential_id, installation_id, revoked_at "
        "FROM discovery_machine_credentials WHERE tenant_id=%s AND credential_id=%s FOR UPDATE",
        (tenant, credential_id),
    ).fetchone()
    if not row:
        raise Refused("credential was not found for the specified tenant")
    if row["revoked_at"] is not None:
        return False, row["installation_id"]
    conn.execute(
        "UPDATE discovery_machine_credentials SET revoked_at=%s WHERE credential_id=%s",
        (now, credential_id),
    )
    _event(
        conn,
        tenant=tenant,
        credential=credential_id,
        installation=row["installation_id"],
        actor=actor,
        kind="revoked",
        outcome="allow",
        reason="operator_cli",
        now=now,
    )
    return True, row["installation_id"]


def run(argv=None, *, environ=None, connect=None, output=None, error=None) -> int:
    environ = os.environ if environ is None else environ
    output = sys.stdout if output is None else output
    error = sys.stderr if error is None else error
    try:
        args = _parser().parse_args(argv)
        tenant = _validated(args)
        dsn = environ.get(ISSUER_DSN_ENV)
        if not dsn:
            raise Refused(f"{ISSUER_DSN_ENV} is not set")
        if connect is None:
            import psycopg
            from psycopg.rows import dict_row

            connect = lambda value: psycopg.connect(value, row_factory=dict_row, connect_timeout=5)
        secret = new_secret() if args.action == "issue" and args.apply else None
        if args.action == "issue" and args.apply:
            is_tty = getattr(output, "isatty", None)
            if not callable(is_tty) or not is_tty():
                raise Refused("secret reveal requires an interactive terminal; no credential was written")
        now = datetime.now(timezone.utc)
        with connect(dsn) as conn:
            with conn.transaction():
                actor = _operator_role(conn)
                if args.action == "issue":
                    if not args.apply:
                        if not conn.execute(
                            "SELECT 1 FROM public.tenants WHERE tenant_id=%s", (tenant,)
                        ).fetchone():
                            raise Refused("tenant was not found")
                        output.write(
                            f"CHECK OK tenant={tenant} installation={args.installation} "
                            f"scope={DISCOVERY_SCOPE} ttl_seconds={int(TOKEN_TTL.total_seconds())}; "
                            "no credential written\n"
                        )
                        return EXIT_OK
                    credential_id, expires = _issue(
                        conn,
                        tenant=tenant,
                        installation=args.installation,
                        actor=actor,
                        secret=secret,
                        now=now,
                    )
                else:
                    if not args.apply:
                        row = conn.execute(
                            "SELECT revoked_at FROM discovery_machine_credentials "
                            "WHERE tenant_id=%s AND credential_id=%s",
                            (tenant, args.credential_id),
                        ).fetchone()
                        if not row:
                            raise Refused("credential was not found for the specified tenant")
                        output.write("CHECK OK credential exists; no revocation written\n")
                        return EXIT_OK
                    changed, _installation = _revoke(
                        conn,
                        tenant=tenant,
                        credential_id=args.credential_id,
                        actor=actor,
                        now=now,
                    )
        if args.action == "issue":
            # This is the sole output of the bearer secret. It is emitted only
            # after commit and is never included in diagnostics or audit data.
            output.write(
                "ISSUED one-time secret (copy only through the approved protected channel):\n"
                f"{secret}\n"
                f"credentialId={credential_id}\nexpiresAt={expires.isoformat()}\n"
            )
        else:
            output.write("REVOKED\n" if changed else "ALREADY REVOKED\n")
        return EXIT_OK
    except Refused as exc:
        error.write(f"REFUSED {exc}\n")
        return EXIT_REFUSED
    except Exception as exc:
        try:
            import psycopg

            if isinstance(exc, psycopg.Error):
                state = getattr(exc, "sqlstate", None)
                state = state if isinstance(state, str) and re.fullmatch(r"[0-9A-Z]{5}", state) else "unknown"
                error.write(f"DATABASE ERROR sqlstate={state}\n")
                return EXIT_DATABASE
        except ImportError:
            pass
        error.write(f"INTERNAL ERROR type={type(exc).__name__}\n")
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(run())
