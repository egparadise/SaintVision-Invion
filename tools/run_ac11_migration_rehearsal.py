"""Hosted-only AC-11 migration restore rehearsal.

The current graph has no reversible tail, so a no-op downgrade must never be
reported as a rollback pass.  This runner records that axis as NOT_APPLICABLE,
then proves the paired restore/forward axis in two owned disposable databases:

* upgrade the source database to the parent of the irreversible head;
* seed a pre-forward sentinel and take a custom-format snapshot;
* upgrade the source to head;
* restore the snapshot into a second database and upgrade it to head;
* compare the sentinel and a canonical catalog fingerprint.

It is intentionally invoked only by the opt-in hosted workflow.  Credentials
are passed through libpq environment variables and never written to evidence.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from migration_graph import Revision, chain  # noqa: E402


SCHEMA_VERSION = "1.0.0"
RUN_PURPOSE = "s11-ac11-migration-rehearsal"
MANIFEST_PATH = (
    ROOT / "docs" / "vault" / "30_Development" / "Evidence"
    / "s11-migration-fixture-manifest-v0.json"
)
ALLOWED_EXPECTATIONS = {"PRESERVED", "DECLARED_LOSS_REQUIRES_RESTORE"}
EXPECTED_LOSSY = {
    "0001_s02_baseline",
    "0002_s03_execution",
    "0003_s09_context_eval",
    "0004_s10_lineage",
    "0005_s12_pilot_operations",
    "0006_discovery_pools_placement",
    "0007_locality_replicas",
    "0009_idempotency_and_inbox_scope",
    "0010_canonical_resource_units",
    "0025_workspace_tool_choice",
}
HEX40 = re.compile(r"^[0-9a-f]{40}$")
RUN_ID = re.compile(r"^[0-9]+$")


class RehearsalError(RuntimeError):
    """Fail-closed validation error whose message contains no credential data."""


class CatalogMismatch(RehearsalError):
    """Catalog mismatch with credential-free structural diagnostics."""

    def __init__(self, differing: list[str], diagnostics: dict[str, Any]) -> None:
        super().__init__("catalog fingerprint mismatch: " + ",".join(differing))
        self.diagnostics = diagnostics


@dataclass(frozen=True, slots=True)
class CatalogFingerprint:
    sha256: str
    counts: dict[str, int]
    sections: dict[str, list[list[Any]]]


def redacted_failure_reason(exc: Exception) -> str:
    """Keep owned diagnostics, but never serialize arbitrary exception text."""
    return str(exc) if isinstance(exc, RehearsalError) else type(exc).__name__


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, encoding="utf-8"
    )
    if result.returncode:
        raise RehearsalError(f"git {args[0]} failed")
    return result.stdout.strip()


def validate_checkout(source_head_sha: str) -> tuple[str, bool]:
    if not HEX40.fullmatch(source_head_sha):
        raise RehearsalError("source head must be a full lowercase Git SHA")
    actual = _git("rev-parse", "HEAD")
    if actual != source_head_sha:
        raise RehearsalError("checkout is not the declared source head")
    tree = _git("rev-parse", "HEAD^{tree}")
    clean = _git("status", "--porcelain") == ""
    if not clean:
        raise RehearsalError("checkout is dirty before rehearsal")
    return tree, clean


def downgrade_body_kind(source: str) -> str:
    """Return ``reversible``, ``refusal`` or ``invalid-noop`` without importing code."""
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != "downgrade":
            continue
        body = list(node.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            if isinstance(body[0].value.value, str):
                body = body[1:]
        if not body or all(
            isinstance(item, ast.Pass)
            or (
                isinstance(item, ast.Expr)
                and isinstance(item.value, ast.Constant)
                and item.value.value is Ellipsis
            )
            or (
                isinstance(item, ast.Return)
                and (
                    item.value is None
                    or isinstance(item.value, ast.Constant) and item.value.value is None
                )
            )
            for item in body
        ):
            return "invalid-noop"
        if len(body) == 1 and isinstance(body[0], ast.Raise):
            return "refusal"
        return "reversible"
    return "refusal"


def load_fixture_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RehearsalError(f"fixture manifest unreadable: {type(exc).__name__}") from None
    if set(payload) != {"schemaVersion", "designRef", "revisions"}:
        raise RehearsalError("fixture manifest has an unexpected top-level shape")
    if payload["schemaVersion"] != SCHEMA_VERSION:
        raise RehearsalError("fixture manifest schema version is unsupported")
    design = payload["designRef"]
    if set(design) != {"commit", "path", "blob"}:
        raise RehearsalError("fixture manifest designRef shape is invalid")
    commit, repo_path, blob = design["commit"], design["path"], design["blob"]
    if (
        not isinstance(commit, str)
        or not HEX40.fullmatch(commit)
        or not isinstance(repo_path, str)
        or not repo_path
        or not isinstance(blob, str)
        or not HEX40.fullmatch(blob)
    ):
        raise RehearsalError("fixture manifest designRef provenance is invalid")
    if _git("rev-parse", f"{commit}:{repo_path}") != blob:
        raise RehearsalError("fixture manifest designRef blob is unreachable")
    if not isinstance(payload["revisions"], list) or not payload["revisions"]:
        raise RehearsalError("fixture manifest revision inventory is empty")
    return payload


def validate_fixture_manifest(
    payload: dict[str, Any], revisions: Iterable[Revision]
) -> dict[str, str]:
    rows = payload["revisions"]
    mapping: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"revision", "expected"}:
            raise RehearsalError("fixture manifest revision row shape is invalid")
        revision, expected = row["revision"], row["expected"]
        if not isinstance(revision, str) or expected not in ALLOWED_EXPECTATIONS:
            raise RehearsalError("fixture manifest revision classification is invalid")
        if revision in mapping:
            raise RehearsalError("fixture manifest contains a duplicate revision")
        mapping[revision] = expected

    ordered = list(revisions)
    reversible = {r.revision for r in ordered if not r.irreversible}
    if set(mapping) != reversible:
        raise RehearsalError("fixture manifest does not exactly cover reversible revisions")
    actual_lossy = {key for key, value in mapping.items() if value == "DECLARED_LOSS_REQUIRES_RESTORE"}
    if actual_lossy != EXPECTED_LOSSY:
        raise RehearsalError("lossy reversible fixture classification drifted")
    for revision in ordered:
        kind = downgrade_body_kind(revision.path.read_text(encoding="utf-8"))
        if kind == "invalid-noop":
            raise RehearsalError(f"{revision.revision}: no-op downgrade is invalid")
        if revision.irreversible and kind != "refusal":
            raise RehearsalError(f"{revision.revision}: irreversible classification drifted")
        if not revision.irreversible and kind != "reversible":
            raise RehearsalError(f"{revision.revision}: reversible classification drifted")
    return mapping


def _database_name(prefix: str) -> str:
    return f"inv_s11_{prefix}_{uuid4().hex[:20]}"


def _db_conninfo(admin_dsn: str, database: str) -> str:
    return make_conninfo(admin_dsn, dbname=database)


def _sqlalchemy_url(admin_dsn: str, database: str) -> str:
    info = conninfo_to_dict(admin_dsn)
    return URL.create(
        "postgresql+psycopg",
        username=info.get("user"),
        password=info.get("password"),
        host=info.get("host"),
        port=int(info.get("port", 5432)),
        database=database,
    ).render_as_string(hide_password=False)


def _libpq_env(admin_dsn: str, database: str) -> dict[str, str]:
    info = conninfo_to_dict(admin_dsn)
    env = dict(os.environ)
    for source, target in (
        ("host", "PGHOST"),
        ("port", "PGPORT"),
        ("user", "PGUSER"),
        ("password", "PGPASSWORD"),
    ):
        value = info.get(source)
        if value is not None:
            env[target] = str(value)
    env["PGDATABASE"] = database
    return env


def _run_checked(argv: list[str], *, env: dict[str, str], label: str) -> None:
    result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True)
    if result.returncode:
        raise RehearsalError(f"{label} failed with exit {result.returncode}")


def _create_database(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def _drop_database(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


def _residue(admin_dsn: str, names: list[str]) -> list[str]:
    with psycopg.connect(admin_dsn) as conn:
        rows = conn.execute(
            "SELECT datname FROM pg_database WHERE datname = ANY(%s) ORDER BY datname", (names,)
        ).fetchall()
    return [row[0] for row in rows]


def _alembic_upgrade(admin_dsn: str, database: str, target: str) -> None:
    env = dict(os.environ)
    env["INV_MIGRATION_DSN"] = _sqlalchemy_url(admin_dsn, database)
    _run_checked(
        [sys.executable, "-m", "alembic", "upgrade", target],
        env=env,
        label=f"alembic upgrade {target}",
    )


def _alembic_downgrade(admin_dsn: str, database: str, target: str) -> None:
    env = dict(os.environ)
    env["INV_MIGRATION_DSN"] = _sqlalchemy_url(admin_dsn, database)
    _run_checked(
        [sys.executable, "-m", "alembic", "downgrade", target],
        env=env,
        label=f"alembic downgrade {target}",
    )


def _write_fixture_alembic(root: Path, *, head_source: str) -> Path:
    """Write an isolated two-revision Alembic tree without serializing credentials."""
    script = root / "fixture_alembic"
    versions = script / "versions"
    versions.mkdir(parents=True)
    (root / "alembic.ini").write_text(
        "[alembic]\nscript_location = " + script.as_posix() + "\n",
        encoding="utf-8",
    )
    (script / "env.py").write_text(
        textwrap.dedent(
            """
            import os
            from alembic import context
            from sqlalchemy import create_engine, pool

            engine = create_engine(os.environ["INV_AC11_FIXTURE_DSN"], poolclass=pool.NullPool)
            with engine.connect() as connection:
                context.configure(connection=connection)
                with context.begin_transaction():
                    context.run_migrations()
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (script / "script.py.mako").write_text("", encoding="utf-8")
    (versions / "0001_fixture_base.py").write_text(
        textwrap.dedent(
            """
            from alembic import op

            revision = "fixture_base"
            down_revision = None
            branch_labels = None
            depends_on = None

            def upgrade():
                op.execute("CREATE TABLE public.ac11_fixture_existing (id integer PRIMARY KEY, payload text NOT NULL)")
                op.execute("INSERT INTO public.ac11_fixture_existing(id,payload) VALUES (1,'preserve')")

            def downgrade():
                op.execute("DROP TABLE public.ac11_fixture_existing")
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (versions / "0002_fixture_head.py").write_text(head_source, encoding="utf-8")
    return root / "alembic.ini"


def _run_fixture_alembic(
    admin_dsn: str,
    database: str,
    config: Path,
    command: str,
    target: str,
) -> subprocess.CompletedProcess[bytes]:
    env = dict(os.environ)
    env["INV_AC11_FIXTURE_DSN"] = _sqlalchemy_url(admin_dsn, database)
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(config), command, target],
        cwd=ROOT,
        env=env,
        capture_output=True,
    )


def _negative_fixture_probes(admin_dsn: str, created: list[str]) -> dict[str, Any]:
    """Execute the three preregistered bad downgrades in owned disposable DBs."""
    cases: list[dict[str, Any]] = []
    fixture_heads = {
        "existing-object-deletion": textwrap.dedent(
            """
            from alembic import op
            revision = "fixture_head"
            down_revision = "fixture_base"
            branch_labels = None
            depends_on = None
            def upgrade():
                op.execute("CREATE TABLE public.ac11_fixture_added (id integer PRIMARY KEY)")
            def downgrade():
                op.execute("DROP TABLE public.ac11_fixture_added")
                op.execute("DROP TABLE public.ac11_fixture_existing")
            """
        ).lstrip(),
        "ellipsis-noop": textwrap.dedent(
            """
            from alembic import op
            revision = "fixture_head"
            down_revision = "fixture_base"
            branch_labels = None
            depends_on = None
            def upgrade():
                op.execute("CREATE TABLE public.ac11_fixture_added (id integer PRIMARY KEY)")
            def downgrade():
                ...
            """
        ).lstrip(),
    }
    for label, head_source in fixture_heads.items():
        reference = _database_name("negative_ref")
        candidate = _database_name("negative_case")
        for database in (reference, candidate):
            _create_database(admin_dsn, database)
            created.append(database)
        with tempfile.TemporaryDirectory(prefix=f"s11-ac11-{label}-") as temp:
            config = _write_fixture_alembic(Path(temp), head_source=head_source)
            for database, target in ((reference, "fixture_base"), (candidate, "head")):
                result = _run_fixture_alembic(admin_dsn, database, config, "upgrade", target)
                if result.returncode:
                    raise RehearsalError(f"{label} fixture setup failed")
            result = _run_fixture_alembic(
                admin_dsn, candidate, config, "downgrade", "fixture_base"
            )
            if result.returncode:
                raise RehearsalError(f"{label} fixture downgrade did not reach comparison")
            try:
                compare_catalogs(
                    catalog_fingerprint(admin_dsn, reference),
                    catalog_fingerprint(admin_dsn, candidate),
                )
            except CatalogMismatch:
                cases.append({"case": label, "verdict": "EXPECTED_FINDING"})
            else:
                raise RehearsalError(f"{label} fixture was not detected")

    duplicate = _database_name("negative_0009")
    _create_database(admin_dsn, duplicate)
    created.append(duplicate)
    duplicate_head = textwrap.dedent(
        """
        from alembic import op
        import sqlalchemy as sa
        revision = "fixture_head"
        down_revision = "fixture_base"
        branch_labels = None
        depends_on = None
        def upgrade():
            op.add_column("ac11_fixture_existing", sa.Column("project_id", sa.Text()))
            op.drop_constraint("uq_ac11_fixture_old", "ac11_fixture_existing", type_="unique")
            op.create_unique_constraint(
                "uq_ac11_fixture_project", "ac11_fixture_existing",
                ["project_id", "payload"],
            )
        def downgrade():
            op.drop_constraint("uq_ac11_fixture_project", "ac11_fixture_existing", type_="unique")
            op.create_unique_constraint(
                "uq_ac11_fixture_old", "ac11_fixture_existing", ["payload"]
            )
            op.drop_column("ac11_fixture_existing", "project_id")
        """
    ).lstrip()
    with tempfile.TemporaryDirectory(prefix="s11-ac11-0009-") as temp:
        config = _write_fixture_alembic(Path(temp), head_source=duplicate_head)
        base_path = Path(temp) / "fixture_alembic" / "versions" / "0001_fixture_base.py"
        base_source = base_path.read_text(encoding="utf-8").replace(
            "op.execute(\"INSERT INTO public.ac11_fixture_existing(id,payload) VALUES (1,'preserve')\")",
            "op.create_unique_constraint('uq_ac11_fixture_old','ac11_fixture_existing',['payload'])",
        )
        base_path.write_text(base_source, encoding="utf-8")
        result = _run_fixture_alembic(admin_dsn, duplicate, config, "upgrade", "head")
        if result.returncode:
            raise RehearsalError("0009 duplicate fixture setup failed")
        with psycopg.connect(_db_conninfo(admin_dsn, duplicate)) as conn:
            conn.execute(
                "INSERT INTO public.ac11_fixture_existing(id,payload,project_id) VALUES"
                "(2,'duplicate','project-a'),(3,'duplicate','project-b')"
            )
        result = _run_fixture_alembic(
            admin_dsn, duplicate, config, "downgrade", "fixture_base"
        )
        if result.returncode == 0:
            raise RehearsalError("0009 duplicate fixture unexpectedly downgraded")
        cases.append({"case": "0009-duplicate-key", "verdict": "EXPECTED_FINDING"})

    return {"passedCount": len(cases), "cases": cases}


def _seed_sentinel(admin_dsn: str, database: str) -> dict[str, str]:
    tenant = str(uuid4())
    slug = "s11-" + tenant.replace("-", "")[:20]
    display = "S11 migration restore sentinel"
    with psycopg.connect(_db_conninfo(admin_dsn, database)) as conn:
        conn.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,%s)",
            (tenant, slug, display),
        )
    return {"tenantId": tenant, "slug": slug, "displayName": display}


def _read_sentinel(admin_dsn: str, database: str, tenant: str) -> dict[str, str] | None:
    with psycopg.connect(_db_conninfo(admin_dsn, database)) as conn:
        row = conn.execute(
            "SELECT tenant_id::text,slug,display_name FROM public.tenants WHERE tenant_id=%s",
            (tenant,),
        ).fetchone()
    if row is None:
        return None
    return {"tenantId": row[0], "slug": row[1], "displayName": row[2]}


CATALOG_QUERIES = {
    "tables": """
        SELECT n.nspname,c.relname,c.relkind,pg_get_userbyid(c.relowner),
               c.relrowsecurity,c.relforcerowsecurity
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('public','inv') AND c.relkind IN ('r','p','v','m','S')
        ORDER BY 1,2,3
    """,
    "columns": """
        SELECT n.nspname,c.relname,a.attname,
               pg_catalog.format_type(a.atttypid,a.atttypmod),a.attnotnull,
               coalesce(pg_get_expr(d.adbin,d.adrelid),'')
        FROM pg_attribute a
        JOIN pg_class c ON c.oid=a.attrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
        WHERE n.nspname IN ('public','inv') AND c.relkind IN ('r','p','v','m')
          AND a.attnum>0 AND NOT a.attisdropped
        ORDER BY n.nspname,c.relname,a.attnum
    """,
    "constraints": """
        SELECT n.nspname,c.relname,co.conname,co.contype,co.convalidated,
               pg_get_constraintdef(co.oid,true)
        FROM pg_constraint co
        JOIN pg_class c ON c.oid=co.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('public','inv') ORDER BY 1,2,3
    """,
    "indexes": """
        SELECT schemaname,tablename,indexname,indexdef
        FROM pg_indexes WHERE schemaname IN ('public','inv') ORDER BY 1,2,3
    """,
    "functions": """
        SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),
               pg_get_function_result(p.oid),l.lanname,pg_get_userbyid(p.proowner),
               p.prosecdef,coalesce(array_to_string(p.proconfig,E'\\n'),''),
               pg_get_functiondef(p.oid)
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        JOIN pg_language l ON l.oid=p.prolang
        WHERE n.nspname IN ('public','inv') ORDER BY 1,2,3
    """,
    "tableGrants": """
        SELECT table_schema,table_name,grantee,privilege_type,is_grantable
        FROM information_schema.role_table_grants
        WHERE table_schema IN ('public','inv') ORDER BY 1,2,3,4
    """,
    "routineGrants": """
        SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),
               coalesce(grantee.rolname,'PUBLIC'),acl.privilege_type,
               CASE WHEN acl.is_grantable THEN 'YES' ELSE 'NO' END
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid=p.pronamespace
        CROSS JOIN LATERAL aclexplode(
            coalesce(p.proacl,acldefault('f',p.proowner))
        ) AS acl
        LEFT JOIN pg_roles grantee ON grantee.oid=acl.grantee
        WHERE n.nspname IN ('public','inv') ORDER BY 1,2,3,4,5,6
    """,
    "policies": """
        SELECT schemaname,tablename,policyname,permissive,roles,cmd,qual,with_check
        FROM pg_policies WHERE schemaname IN ('public','inv') ORDER BY 1,2,3
    """,
    "roleMemberships": """
        SELECT granted.rolname,member.rolname,admin_option
        FROM pg_auth_members m
        JOIN pg_roles granted ON granted.oid=m.roleid
        JOIN pg_roles member ON member.oid=m.member
        WHERE granted.rolname LIKE 'inv_%' OR member.rolname LIKE 'inv_%'
        ORDER BY 1,2
    """,
}


def normalize_constraint_definition(definition: str) -> str:
    if not definition.startswith("CHECK ("):
        return definition
    array = re.compile(
        r"ANY \(ARRAY\[(?P<items>"
        r"'(?:''|[^'])*'::character varying(?:::text)?"
        r"(?:,\s*'(?:''|[^'])*'::character varying(?:::text)?)*"
        r")\](?:::text\[\])?\)"
    )

    def normalize_array(match: re.Match[str]) -> str:
        items = match.group("items").replace(
            "::character varying::text", "::character varying"
        )
        return f"ANY (ARRAY[{items}])"

    return array.sub(normalize_array, definition)


def catalog_fingerprint(admin_dsn: str, database: str) -> CatalogFingerprint:
    sections: dict[str, list[list[Any]]] = {}
    with psycopg.connect(_db_conninfo(admin_dsn, database)) as conn:
        for name, query in CATALOG_QUERIES.items():
            sections[name] = [list(row) for row in conn.execute(query).fetchall()]
    # pg_dump/pg_restore can move the same text coercion from an ARRAY result
    # onto each varchar element. PostgreSQL deparses both forms differently,
    # although their stored CHECK semantics are equivalent.
    for row in sections["constraints"]:
        row[5] = normalize_constraint_definition(row[5])
    return CatalogFingerprint(
        sha256=canonical_sha256(sections),
        counts={name: len(rows) for name, rows in sections.items()},
        sections=sections,
    )


def compare_catalogs(expected: CatalogFingerprint, actual: CatalogFingerprint) -> None:
    if expected.sha256 == actual.sha256:
        return
    differing = sorted(
        name for name in set(expected.sections) | set(actual.sections)
        if expected.sections.get(name) != actual.sections.get(name)
    )
    raise CatalogMismatch(differing, catalog_diff_diagnostics(expected, actual, differing))


def _catalog_row_diagnostic(section: str, row: list[Any]) -> dict[str, Any]:
    """Return structural keys and hashes without serializing executable definitions."""
    if section == "columns":
        return {
            "key": row[:3],
            "type": row[3],
            "notNull": row[4],
            "defaultSha256": canonical_sha256(row[5]),
        }
    if section == "constraints":
        return {
            "key": row[:4],
            "validated": row[4],
            "definition": row[5][:512],
            "definitionSha256": canonical_sha256(row[5]),
        }
    if section == "functions":
        return {
            "key": row[:3],
            "result": row[3],
            "language": row[4],
            "owner": row[5],
            "securityDefiner": row[6],
            "configSha256": canonical_sha256(row[7]),
            "definitionSha256": canonical_sha256(row[8]),
        }
    if section == "routineGrants":
        return {"key": row}
    return {"rowSha256": canonical_sha256(row)}


def catalog_diff_diagnostics(
    expected: CatalogFingerprint,
    actual: CatalogFingerprint,
    differing: list[str],
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    for section in differing:
        expected_rows = expected.sections.get(section, [])
        actual_rows = actual.sections.get(section, [])
        expected_serialized = {
            json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False): row
            for row in expected_rows
        }
        actual_serialized = {
            json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False): row
            for row in actual_rows
        }
        expected_only = sorted(set(expected_serialized) - set(actual_serialized))
        actual_only = sorted(set(actual_serialized) - set(expected_serialized))
        diagnostics[section] = {
            "expectedCount": len(expected_rows),
            "actualCount": len(actual_rows),
            "expectedOnlyCount": len(expected_only),
            "actualOnlyCount": len(actual_only),
            "expectedOnlySample": [
                _catalog_row_diagnostic(section, expected_serialized[key])
                for key in expected_only[:5]
            ],
            "actualOnlySample": [
                _catalog_row_diagnostic(section, actual_serialized[key])
                for key in actual_only[:5]
            ],
        }
    return diagnostics


def _postgres_version(admin_dsn: str) -> dict[str, str]:
    with psycopg.connect(admin_dsn) as conn:
        row = conn.execute(
            "SELECT current_setting('server_version'),current_setting('server_version_num'),"
            "current_setting('lock_timeout'),current_setting('statement_timeout')"
        ).fetchone()
    return {
        "serverVersion": row[0],
        "serverVersionNum": row[1],
        "lockTimeout": row[2],
        "statementTimeout": row[3],
    }


def _junit_bytes(*, success: bool, reversible_tail: int, failure: str | None = None) -> bytes:
    suite = ET.Element(
        "testsuite",
        name="s11-ac11-migration-rehearsal",
        tests="6",
        failures="0" if success else "1",
        errors="0",
        skipped="1" if reversible_tail == 0 else "0",
    )
    ET.SubElement(suite, "testcase", classname="ac11.migration", name="fixture-manifest")
    reversible = ET.SubElement(
        suite, "testcase", classname="ac11.migration", name="reversible-segment"
    )
    if reversible_tail == 0:
        ET.SubElement(reversible, "skipped", message="no reversible tail; paired restore required")
    restore = ET.SubElement(
        suite, "testcase", classname="ac11.migration", name="irreversible-restore-forward"
    )
    if not success:
        ET.SubElement(restore, "failure", message=failure or "rehearsal failed")
    for name in (
        "negative-existing-object-deletion",
        "negative-0009-duplicate-key",
        "negative-ellipsis-noop",
    ):
        ET.SubElement(suite, "testcase", classname="ac11.migration", name=name)
    return ET.tostring(suite, encoding="utf-8", xml_declaration=True)


def run_rehearsal(
    *,
    admin_dsn: str,
    source_run_id: str,
    source_head_sha: str,
    runner_image: str,
    report_path: Path,
    junit_path: Path,
) -> int:
    if not RUN_ID.fullmatch(source_run_id):
        raise RehearsalError("source run ID must contain digits only")
    checkout_tree, clean = validate_checkout(source_head_sha)
    ordered = chain()
    manifest = load_fixture_manifest()
    classifications = validate_fixture_manifest(manifest, ordered)
    head = ordered[-1]
    last_irreversible = max(
        index for index, revision in enumerate(ordered)
        if revision.irreversible or isinstance(revision.down_revision, tuple)
    )
    restore_barrier = ordered[last_irreversible]
    parents = (
        () if restore_barrier.down_revision is None
        else (restore_barrier.down_revision,)
        if isinstance(restore_barrier.down_revision, str)
        else restore_barrier.down_revision
    )
    if len(parents) != 1:
        raise RehearsalError("restore barrier is not a single-parent irreversible revision")
    reversible_tail = len(ordered) - last_irreversible - 1

    started_at = utc_now()
    names = [_database_name("source"), _database_name("restore")]
    if reversible_tail:
        names.extend([_database_name("down_reference"), _database_name("down_candidate")])
    created: list[str] = []
    cleanup_errors: list[str] = []
    success = False
    failure: str | None = None
    failure_reason: str | None = None
    catalog_difference: dict[str, Any] | None = None
    details: dict[str, Any] = {}
    try:
        for name in names:
            _create_database(admin_dsn, name)
            created.append(name)
        _alembic_upgrade(admin_dsn, names[0], parents[0])
        sentinel = _seed_sentinel(admin_dsn, names[0])
        with tempfile.TemporaryDirectory(prefix="s11-ac11-") as temp_dir:
            archive = Path(temp_dir) / "pre-forward.dump"
            _run_checked(
                ["pg_dump", "--format=custom", "--file", str(archive)],
                env=_libpq_env(admin_dsn, names[0]),
                label="pg_dump snapshot",
            )
            archive_sha = sha256_bytes(archive.read_bytes())
            _alembic_upgrade(admin_dsn, names[0], "head")
            post_forward_sentinel = _seed_sentinel(admin_dsn, names[0])
            source_catalog = catalog_fingerprint(admin_dsn, names[0])
            source_sentinel = _read_sentinel(admin_dsn, names[0], sentinel["tenantId"])
            if source_sentinel != sentinel:
                raise RehearsalError("source sentinel changed during forward migration")
            if _read_sentinel(
                admin_dsn, names[0], post_forward_sentinel["tenantId"]
            ) != post_forward_sentinel:
                raise RehearsalError("post-forward sentinel was not committed")

            _run_checked(
                [
                    "pg_restore", "--single-transaction", "--exit-on-error",
                    "--dbname", names[1], str(archive),
                ],
                env=_libpq_env(admin_dsn, names[1]),
                label="pg_restore snapshot",
            )
            _alembic_upgrade(admin_dsn, names[1], "head")
            restored_catalog = catalog_fingerprint(admin_dsn, names[1])
            compare_catalogs(source_catalog, restored_catalog)
            restored_sentinel = _read_sentinel(admin_dsn, names[1], sentinel["tenantId"])
            if restored_sentinel != sentinel:
                raise RehearsalError("restored sentinel differs from pre-forward value")
            if _read_sentinel(admin_dsn, names[1], post_forward_sentinel["tenantId"]) is not None:
                raise RehearsalError("pre-forward snapshot unexpectedly contains post-forward data")
            details = {
                "startingRevision": parents[0],
                "headRevision": head.revision,
                "restoreBarrierRevision": restore_barrier.revision,
                "snapshotSha256": archive_sha,
                "sentinelSha256": canonical_sha256(sentinel),
                "postForwardSentinelSha256": canonical_sha256(post_forward_sentinel),
                "postForwardSentinelDisposition": "DECLARED_LOSS_REQUIRES_RESTORE",
                "catalogSha256": source_catalog.sha256,
                "catalogCounts": source_catalog.counts,
            }
        reversible_details: dict[str, Any]
        if reversible_tail:
            reference, candidate = names[2], names[3]
            _alembic_upgrade(admin_dsn, reference, restore_barrier.revision)
            _alembic_upgrade(admin_dsn, candidate, restore_barrier.revision)
            downgrade_sentinel = _seed_sentinel(admin_dsn, candidate)
            _alembic_upgrade(admin_dsn, candidate, "head")
            _alembic_downgrade(admin_dsn, candidate, restore_barrier.revision)
            compare_catalogs(
                catalog_fingerprint(admin_dsn, reference),
                catalog_fingerprint(admin_dsn, candidate),
            )
            if _read_sentinel(
                admin_dsn, candidate, downgrade_sentinel["tenantId"]
            ) != downgrade_sentinel:
                raise RehearsalError("reversible downgrade changed the preservation sentinel")
            reversible_details = {
                "startingRevision": head.revision,
                "endingRevision": restore_barrier.revision,
                "catalogEquivalent": True,
                "sentinelPreserved": True,
            }
        else:
            reversible_details = {
                "reason": "no-reversible-tail",
                "reversibleTailCount": 0,
            }
        negative_fixtures = _negative_fixture_probes(admin_dsn, created)
        details["reversibleSegment"] = reversible_details
        details["negativeFixtures"] = negative_fixtures
        success = True
    except Exception as exc:  # noqa: BLE001 - serialized as a type-only failure
        failure = type(exc).__name__
        failure_reason = redacted_failure_reason(exc)
        if isinstance(exc, CatalogMismatch):
            catalog_difference = exc.diagnostics
    finally:
        for name in reversed(created):
            try:
                _drop_database(admin_dsn, name)
            except Exception as exc:  # noqa: BLE001
                cleanup_errors.append(type(exc).__name__)
        residue = _residue(admin_dsn, created)
        if residue or cleanup_errors:
            success = False
            failure = "cleanup_failed"
            failure_reason = "owned database cleanup left residue or returned an error"

    junit = _junit_bytes(
        success=success,
        reversible_tail=reversible_tail,
        failure=failure_reason or failure,
    )
    junit_path.parent.mkdir(parents=True, exist_ok=True)
    junit_path.write_bytes(junit)
    junit_sha = sha256_bytes(junit)
    finished_at = utc_now()
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "runPurpose": RUN_PURPOSE,
        "sourceRunId": source_run_id,
        "sourceHeadSha": source_head_sha,
        "checkoutTreeSha": checkout_tree,
        "cleanCheckout": clean,
        "junitSha256": junit_sha,
        "fixtureManifestSha256": canonical_sha256(manifest),
        "environment": {
            "runnerImage": runner_image,
            "topology": "hosted-single-postgres-service",
            "synthetic": True,
            "physicalFiveNodeComparable": False,
            "postgres": _postgres_version(admin_dsn),
        },
        "startedAt": started_at,
        "finishedAt": finished_at,
        "verdict": "MEASURED_PASS" if success else "MEASURED_FAIL",
        "axes": [
            {
                "axis": "migration-reversible-segment",
                "verdict": "NOT_APPLICABLE" if reversible_tail == 0 else "MEASURED_PASS",
                **(
                    {
                        "structuralException": {
                            "reason": "no-reversible-tail",
                            "reversibleTailCount": reversible_tail,
                        }
                    }
                    if reversible_tail == 0
                    else {
                        "observationCount": 1,
                        "details": details.get("reversibleSegment", {}),
                    }
                ),
            },
            {
                "axis": "irreversible-restore-forward",
                "verdict": "MEASURED_PASS" if success else "MEASURED_FAIL",
                "observationCount": 1 if success else 0,
                "details": details,
            },
        ],
        "fixtureClassifications": {
            "PRESERVED": sorted(k for k, v in classifications.items() if v == "PRESERVED"),
            "DECLARED_LOSS_REQUIRES_RESTORE": sorted(EXPECTED_LOSSY),
        },
        "executionScope": {
            "restoreStartingRevisionsExecuted": [parents[0]],
            "reversibleDowngradeTargetsExecuted": (
                [restore_barrier.revision] if reversible_tail else []
            ),
            "lossyReversibleRevisionsExecuted": [],
            "lossyReversibleRevisionsClassifiedForFutureRestore": sorted(EXPECTED_LOSSY),
        },
        "cleanup": {
            "resourceKind": "postgres-database",
            "ownedNamePrefix": "inv_s11_",
            "attemptedCount": len(created),
            "residueCount": len(residue),
            "cleanupErrorTypes": cleanup_errors,
        },
        "failureType": failure,
        "failureReason": failure_reason,
        "catalogDifference": catalog_difference,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if success else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-head-sha", required=True)
    parser.add_argument("--runner-image", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args(argv)
    admin_dsn = os.environ.get("INV_TEST_ADMIN_DSN")
    if not admin_dsn:
        print("INV_TEST_ADMIN_DSN is required; no database was touched", file=sys.stderr)
        return 2
    try:
        return run_rehearsal(
            admin_dsn=admin_dsn,
            source_run_id=args.source_run_id,
            source_head_sha=args.source_head_sha,
            runner_image=args.runner_image,
            report_path=args.report,
            junit_path=args.junit,
        )
    except RehearsalError as exc:
        print(f"AC-11 migration rehearsal refused: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(
            f"AC-11 migration rehearsal errored: {type(exc).__name__}; no credentials emitted",
            file=sys.stderr,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
